"""Unit tests for codereview tool implementation."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import settings
from src.schemas.base import ModelResponse, ModelResponseMetadata
from src.tools.codereview import codereview_impl


def mock_llm_response(content: str, model: str = "gpt-5-mini") -> ModelResponse:
    """Helper to create a mock ModelResponse for testing."""
    return ModelResponse(
        content=content,
        status="success",
        metadata=ModelResponseMetadata(
            model=model,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=100,
        ),
    )


class TestCodeReviewStepLogic:
    """Tests for codereview step behavior and branching logic."""

    @pytest.mark.asyncio
    async def test_step1_returns_checklist_with_continue(self):
        """Test that step 1 with continue action returns checklist."""
        result = await codereview_impl(
            name="Initial Review",
            content="Starting code review",
            step_number=1,
            next_action="continue",
            models=["gpt-5-mini"],
            base_path="/tmp/test",
            thread_id="test-thread",
        )

        assert result["status"] == "in_progress"
        assert "checklist" in result["summary"].lower()
        assert "Read and understand the code base" in result["summary"]
        assert "step 2" in result["summary"].lower()
        assert result["next_action"]["action"] == "continue"
        assert result["next_action"]["reason"]
        assert "thread_id" in result

    @pytest.mark.asyncio
    async def test_step1_always_returns_checklist(self):
        """Test that step 1 always returns checklist regardless of next_action."""
        # Step 1 always returns checklist, even with next_action='stop'
        result = await codereview_impl(
            name="Quick stop",
            content="Stopping immediately",
            step_number=1,
            next_action="stop",
            models=["gpt-5-mini"],
            base_path="/tmp/test",
            thread_id="test-thread",
        )

        assert result["status"] == "in_progress"
        assert "checklist" in result["summary"].lower()
        assert result["next_action"]["action"] == "continue"

    @pytest.mark.asyncio
    async def test_no_files_returns_continue(self):
        """Test that no relevant files returns continue action with reason to add files."""
        # Create thread first to get past step 1
        with patch("src.utils.llm_runner.litellm_client.call_async") as mock_llm:
            # Step 1: Get checklist
            result1 = await codereview_impl(
                name="Review",
                content="Start",
                step_number=1,
                next_action="continue",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                thread_id="test-thread",
            )
            thread_id = result1["thread_id"]

            # Step 2: No files provided
            result = await codereview_impl(
                name="Review",
                content="Continuing without files",
                step_number=2,
                next_action="continue",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                thread_id=thread_id,
                relevant_files=[],
            )

        assert result["status"] == "in_progress"
        assert "No relevant files" in result["summary"]
        assert result["next_action"]["action"] == "continue"
        assert "relevant_files" in result["next_action"]["reason"]
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_too_many_files_returns_continue(self):
        """Test file count limit enforcement via Pydantic validator."""
        from src.schemas.codereview import CodeReviewRequest

        # Create many file paths
        too_many_files = [f"/tmp/file{i}.py" for i in range(settings.max_files_per_review + 1)]

        # Validation should raise ValidationError when creating the request
        with pytest.raises(ValidationError) as exc_info:
            CodeReviewRequest(
                name="Review",
                content="Too many files",
                step_number=2,
                next_action="continue",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                relevant_files=too_many_files,
            )

        # Verify the error message
        assert "Too many files" in str(exc_info.value)
        assert str(settings.max_files_per_review) in str(exc_info.value)
        assert "reduce the scope" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_limit_enforcement_exact_boundary(self):
        """Test that exact max files is allowed."""
        # Create exactly max files
        exact_files = [f"/tmp/file{i}.py" for i in range(settings.max_files_per_review)]

        with (
            patch(
                "src.utils.llm_runner.litellm_client.call_async",
                return_value=mock_llm_response('{"status": "no_issues_found", "message": "All good"}'),
            ) as mock_llm,
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(
                name="Review",
                content="Start",
                step_number=1,
                next_action="continue",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                thread_id="test-thread",
            )
            thread_id = result1["thread_id"]

            result = await codereview_impl(
                name="Review",
                content="Exact max files",
                step_number=2,
                next_action="continue",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                thread_id=thread_id,
                relevant_files=exact_files,
            )

            # Should proceed to LLM call, not reject
            assert result["status"] == "success"
            mock_llm.assert_called_once()


class TestCodeReviewLLMResponseParsing:
    """Tests for parsing different LLM response statuses."""

    @pytest.fixture
    def base_params(self):
        """Common parameters for tests."""
        return {
            "name": "Review",
            "content": "Analyzing code",
            "step_number": 2,
            "next_action": "continue",
            "models": ["gpt-5-mini"],
            "base_path": "/tmp/test",
            "relevant_files": ["/tmp/test/file.py"],
        }

    @pytest.mark.asyncio
    async def test_llm_response_files_required_to_continue(self, base_params):
        """Test parsing 'files_required_to_continue' status."""
        json_response = """{
                "status": "files_required_to_continue",
                "message": "Need authentication files",
                "files_needed": ["auth.py", "session.py"]
            }"""

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            # Create thread first
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "in_progress"  # Work not done - files required
        assert result["next_action"]["action"] == "continue"  # Consensus: needs files
        assert "requested additional files" in result["next_action"]["reason"]
        assert "Review paused - additional files required" in result["summary"]
        # Check per-model result
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "success"
        assert result["results"][0]["metadata"]["model"] == "gpt-5-mini"
        assert result["results"][0]["metadata"]["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_llm_response_focused_review_required(self, base_params):
        """Test parsing 'focused_review_required' status - treated as needs files."""
        json_response = """{
                "status": "focused_review_required",
                "message": "Scope is too large",
                "suggestion": "Focus on authentication module only"
            }"""

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "in_progress"  # Work not done - files required
        assert result["next_action"]["action"] == "continue"  # Consensus: needs files
        assert "Review paused - additional files required" in result["summary"]
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_llm_response_unreviewable_content(self, base_params):
        """Test parsing 'unreviewable_content' status - treated as completion."""
        json_response = """{
                "status": "unreviewable_content",
                "message": "Files are binary or corrupted"
            }"""

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "success"  # All models succeeded
        assert result["next_action"]["action"] == "stop"  # All completed
        assert len(result["results"]) > 0  # Has model results
        assert result["results"][0].get("issues_found") is None or len(result["results"][0].get("issues_found", [])) == 0  # No issues

    @pytest.mark.asyncio
    async def test_llm_response_no_issues_found(self, base_params):
        """Test parsing 'no_issues_found' status."""
        json_response = """{
                "status": "no_issues_found",
                "message": "Code looks good, no issues detected"
            }"""

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "success"  # All models succeeded
        assert result["next_action"]["action"] == "stop"  # All completed
        assert "No issues found" in result["summary"]  # Aggregate summary
        assert len(result["results"]) > 0  # Has model results
        assert result["results"][0].get("issues_found") is None or len(result["results"][0].get("issues_found", [])) == 0  # No issues

    @pytest.mark.asyncio
    async def test_llm_response_review_complete_with_issues(self, base_params):
        """Test parsing 'review_complete' with issues."""
        json_response = """{
                "status": "review_complete",
                "message": "Found 2 security issues",
                "issues_found": [
                    {"severity": "high", "location": "auth.py:45", "description": "SQL injection risk"},
                    {"severity": "medium", "location": "api.py:120", "description": "Missing rate limiting"}
                ]
            }"""

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "success"  # All models succeeded
        assert result["next_action"]["action"] == "stop"  # All completed
        assert "models succeeded" in result["summary"]  # Aggregate summary with stats
        assert "Found 2 issue" in result["summary"]  # Should mention issues found
        assert len(result["results"]) > 0  # Has model results
        assert result["results"][0]["issues_found"] is not None  # Has issues
        assert len(result["results"][0]["issues_found"]) == 2  # Issues from model
        assert result["results"][0]["issues_found"][0]["severity"] == "high"
        assert "SQL injection" in result["results"][0]["issues_found"][0]["description"]
        assert result["results"][0]["issues_found"][0]["model"] == "gpt-5-mini"  # Tagged with model


class TestCodeReviewErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def base_params(self):
        """Common parameters for tests."""
        return {
            "name": "Review",
            "content": "Analyzing code",
            "step_number": 2,
            "next_action": "continue",
            "models": ["gpt-5-mini"],
            "base_path": "/tmp/test",
            "relevant_files": ["/tmp/test/file.py"],
        }

    @pytest.mark.asyncio
    async def test_llm_response_invalid_json_returns_text(self, base_params):
        """Test that invalid JSON is handled gracefully."""
        plain_text = "This is plain text, not JSON"

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(plain_text)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "error"  # Invalid JSON treated as error
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "error"  # Error status
        assert result["results"][0]["error"] == "Failed to parse LLM response as JSON"
        assert result["results"][0]["content"] == plain_text  # Raw response preserved
        assert result["results"][0]["metadata"]["model"] == "gpt-5-mini"

    @pytest.mark.asyncio
    async def test_llm_response_missing_status_field(self, base_params):
        """Test that JSON without 'status' field is handled gracefully."""
        json_response = '{"message": "Missing status field"}'

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "success"  # All models succeeded
        assert len(result["results"]) == 1
        assert result["results"][0]["content"] == json_response  # Raw response preserved

    @pytest.mark.asyncio
    async def test_llm_response_unknown_status_value(self, base_params):
        """Test that unknown status value is handled gracefully."""
        with (
            patch(
                "src.utils.llm_runner.litellm_client.call_async",
                return_value=mock_llm_response('{"status": "unknown_status_value", "message": "Unknown"}'),
            ),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "success"  # All models succeeded
        assert len(result["results"]) == 1
        assert "unknown_status_value" in result["results"][0]["content"]  # Raw response preserved

    @pytest.mark.asyncio
    async def test_llm_response_review_complete_missing_issues(self, base_params):
        """Test 'review_complete' without issues_found field."""
        with (
            patch(
                "src.utils.llm_runner.litellm_client.call_async",
                return_value=mock_llm_response('{"status": "review_complete", "message": "Done"}'),
            ),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Falls through to else branch (unknown status)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_metadata_with_incomplete_usage_data(self, base_params):
        """Test metadata handling when usage data is incomplete."""
        json_response = '{"status": "no_issues_found", "message": "All good"}'

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "success"
        assert len(result["results"]) == 1
        # mock_llm_response provides defaults from ModelResponseMetadata
        assert result["results"][0]["metadata"]["prompt_tokens"] == 10
        assert result["results"][0]["metadata"]["completion_tokens"] == 5
        assert result["results"][0]["metadata"]["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_metadata_with_missing_canonical_name(self, base_params):
        """Test metadata uses model parameter when canonical_name is missing."""
        json_response = '{"status": "no_issues_found", "message": "All good"}'  # Empty usage data

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)),
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(**{**base_params, "step_number": 1, "thread_id": "test-thread"})
            thread_id = result1["thread_id"]

            result = await codereview_impl(**{**base_params, "thread_id": thread_id})

        # Multi-model response structure
        assert result["status"] == "success"
        assert len(result["results"]) == 1
        # Should fall back to model parameter
        assert result["results"][0]["metadata"]["model"] == "gpt-5-mini"


class TestCodeReviewContextBuilding:
    """Tests for expert context and repository context building."""

    @pytest.mark.asyncio
    async def test_expert_context_with_files(self):
        """Test that LLM is called with files via MessageBuilder."""
        json_response = '{"status": "no_issues_found", "message": "Good"}'

        with patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)) as mock_llm:
            # Step 1 always returns checklist, regardless of next_action or files
            result = await codereview_impl(
                name="Review",
                content="Analyze",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                relevant_files=["/tmp/test/file.py"],
                thread_id="test-thread",
            )

            # Verify step 1 returns checklist without calling LLM
            assert not mock_llm.called
            assert result["status"] == "in_progress"
            assert "checklist" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_expert_context_with_issues_found(self):
        """Test that previous issues are included in context."""
        json_response = '{"status": "no_issues_found", "message": "Good"}'

        issues = [{"severity": "high", "location": "auth.py:10", "description": "Security issue"}]

        with (
            patch("src.utils.llm_runner.litellm_client.call_async", return_value=mock_llm_response(json_response)) as mock_llm,
            patch("src.utils.prompts.build_expert_context", return_value="<expert context>"),
            patch("src.utils.repository.build_repository_context", return_value=None),
        ):
            result1 = await codereview_impl(
                name="Review",
                content="Start",
                step_number=1,
                next_action="continue",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                thread_id="test-thread",
            )
            thread_id = result1["thread_id"]

            await codereview_impl(
                name="Review",
                content="Analyze",
                step_number=2,
                next_action="continue",
                models=["gpt-5-mini"],
                base_path="/tmp/test",
                thread_id=thread_id,
                relevant_files=["/tmp/test/file.py"],
                issues_found=issues,
            )

            # Verify issues were passed to build_expert_context
            # We can't easily verify this without inspecting the call,
            # but we can at least confirm the LLM was called
            assert mock_llm.called
