"""Unit tests for debate tool."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from multi_mcp.schemas.base import ModelResponse, ModelResponseMetadata
from multi_mcp.schemas.debate import DebateRequest, DebateResponse
from multi_mcp.tools.debate import _format_debate_prompt, debate_impl


class TestFormatDebatePrompt:
    """Test _format_debate_prompt function for XML formatting."""

    def test_format_debate_prompt_with_xml_tags(self):
        """Test that debate prompt includes proper XML tags."""
        original_content = "How do I implement feature X?"
        step1_results = [
            ModelResponse(
                status="success",
                content="Use approach A with async/await",
                metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=100),
            ),
            ModelResponse(
                status="success",
                content="Use approach B with threading",
                metadata=ModelResponseMetadata(model="gemini-2.5-flash", total_tokens=120),
            ),
        ]

        formatted = _format_debate_prompt(original_content, step1_results)

        # Verify XML structure
        assert "<USER_MESSAGE>" in formatted
        assert "</USER_MESSAGE>" in formatted
        assert "<PREVIOUS_RESPONSES>" in formatted
        assert "</PREVIOUS_RESPONSES>" in formatted

        # NEW: Verify individual response tags
        assert '<response number="1" model="gpt-5-mini">' in formatted
        assert "</response>" in formatted
        assert '<response number="2" model="gemini-2.5-flash">' in formatted

        # Verify content is properly wrapped
        assert "How do I implement feature X?" in formatted
        assert "Use approach A with async/await" in formatted
        assert "Use approach B with threading" in formatted

        # Verify NO markdown headers (removed)
        assert "## Response 1" not in formatted
        assert "## Response 2" not in formatted

    def test_format_debate_prompt_skips_failed_responses(self):
        """Test that only successful responses are included."""
        original_content = "Question?"
        step1_results = [
            ModelResponse(status="success", content="Success 1", metadata=ModelResponseMetadata(model="gpt-5-mini")),
            ModelResponse(status="error", content="", error="Timeout", metadata=ModelResponseMetadata(model="haiku")),
            ModelResponse(status="success", content="Success 2", metadata=ModelResponseMetadata(model="gemini-2.5-flash")),
        ]

        formatted = _format_debate_prompt(original_content, step1_results)

        # Should include successful responses (note: numbering is based on position in original list)
        assert '<response number="1" model="gpt-5-mini">' in formatted
        assert "Success 1" in formatted
        assert '<response number="3" model="gemini-2.5-flash">' in formatted  # Position 3 in original list
        assert "Success 2" in formatted

        # Should not include failed response
        assert "haiku" not in formatted
        assert "Timeout" not in formatted

        # Verify NO markdown headers
        assert "## Response" not in formatted

    def test_format_debate_prompt_handles_unknown_model(self):
        """Test handling of responses with missing model name in metadata."""
        original_content = "Question?"
        step1_results = [
            ModelResponse(status="success", content="Answer", metadata=ModelResponseMetadata(model=""))  # Empty model name
        ]

        formatted = _format_debate_prompt(original_content, step1_results)

        # Should use empty string when model name is empty
        assert '<response number="1" model="">' in formatted
        assert "Answer" in formatted

        # Verify NO markdown headers
        assert "## Response" not in formatted


class TestDebateSchemas:
    """Test debate schema validation."""

    def test_debate_request_inherits_from_multi(self):
        """DebateRequest should inherit from MultiToolRequest."""
        request = DebateRequest(
            name="Test",
            content="Question?",
            step_number=1,
            next_action="stop",
            models=["gpt-5-mini", "haiku"],
            base_path="/tmp",
        )

        assert request.name == "Test"
        assert request.content == "Question?"
        assert request.models == ["gpt-5-mini", "haiku"]
        assert len(request.models) >= 2

    def test_debate_response_has_step2_results(self):
        """DebateResponse should have step2_results field."""
        response = DebateResponse(
            thread_id="test-thread",
            status="success",
            summary="Test summary",
            results=[
                ModelResponse(
                    content="Answer 1",
                    status="success",
                    metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=100),
                )
            ],
            step2_results=[
                ModelResponse(
                    content="Debate 1",
                    status="success",
                    metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=200),
                )
            ],
        )

        assert response.thread_id == "test-thread"
        assert len(response.results) == 1
        assert len(response.step2_results) == 1
        assert response.results[0].content == "Answer 1"
        assert response.step2_results[0].content == "Debate 1"


class TestDebateImpl:
    """Test debate_impl function."""

    @pytest.mark.asyncio
    async def test_both_steps_succeed(self):
        """Test full debate flow with all models succeeding."""
        step_counter = [0]

        async def mock_execute_parallel(**kwargs):
            step_counter[0] += 1
            if step_counter[0] == 1:
                # Step 1: Independent answers
                return [
                    ModelResponse(
                        content="Model 1 answer",
                        status="success",
                        metadata=ModelResponseMetadata(
                            model="gpt-5-mini",
                            prompt_tokens=100,
                            completion_tokens=200,
                            total_tokens=300,
                            latency_ms=1000,
                        ),
                    ),
                    ModelResponse(
                        content="Model 2 answer",
                        status="success",
                        metadata=ModelResponseMetadata(
                            model="haiku",
                            prompt_tokens=100,
                            completion_tokens=180,
                            total_tokens=280,
                            latency_ms=900,
                        ),
                    ),
                ]
            else:
                # Step 2: Debate responses
                return [
                    ModelResponse(
                        content="Model 1 debate",
                        status="success",
                        metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=150),
                    ),
                    ModelResponse(
                        content="Model 2 debate",
                        status="success",
                        metadata=ModelResponseMetadata(model="haiku", total_tokens=140),
                    ),
                ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test Debate",
                content="What is the best approach?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                thread_id="test-thread",
            )

        assert result["status"] == "success"
        assert len(result["results"]) == 2
        assert len(result["step2_results"]) == 2
        assert "both steps" in result["summary"]
        assert result["results"][0]["content"] == "Model 1 answer"
        assert result["step2_results"][0]["content"] == "Model 1 debate"

    @pytest.mark.asyncio
    async def test_step1_partial_failure(self):
        """Test that Step 2 only runs with Step 1 successes."""
        step_counter = [0]

        async def mock_execute_parallel(**kwargs):
            step_counter[0] += 1
            if step_counter[0] == 1:
                # Step 1: One success, one failure
                return [
                    ModelResponse(
                        content="Success",
                        status="success",
                        metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=100),
                    ),
                    ModelResponse(
                        content="",
                        status="error",
                        error="Timeout",
                        metadata=ModelResponseMetadata(model="haiku"),
                    ),
                ]
            else:
                # Step 2: Only successful model
                return [
                    ModelResponse(
                        content="Debate response",
                        status="success",
                        metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=150),
                    )
                ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                thread_id="test-thread",
            )

        assert len(result["results"]) == 2  # Both models tried Step 1
        assert len(result["step2_results"]) == 1  # Only success went to Step 2
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_all_step1_failures(self):
        """Test that debate fails when all Step 1 models fail."""

        async def mock_execute_parallel(**kwargs):
            # All models fail in Step 1
            return [
                ModelResponse(content="", status="error", error="Error 1", metadata=ModelResponseMetadata(model="gpt-5-mini")),
                ModelResponse(content="", status="error", error="Error 2", metadata=ModelResponseMetadata(model="haiku")),
            ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                thread_id="test-thread",
            )

        assert result["status"] == "error"
        assert "all 2 models failed in Step 1" in result["summary"]
        assert len(result["results"]) == 2
        # Step 2 should not be in response when all Step 1 fails
        assert "step2_results" not in result

    @pytest.mark.asyncio
    async def test_thread_id_generated(self):
        """Test that thread_id is passed through correctly."""

        async def mock_execute_parallel(**kwargs):
            return [
                ModelResponse(content="Answer", status="success", metadata=ModelResponseMetadata(model="gpt-5-mini")),
                ModelResponse(content="Answer 2", status="success", metadata=ModelResponseMetadata(model="haiku")),
            ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                thread_id="test-thread",
            )

        assert "thread_id" in result
        assert result["thread_id"] == "test-thread"

    @pytest.mark.asyncio
    async def test_thread_id_preserved(self):
        """Test that provided thread_id is preserved."""

        async def mock_execute_parallel(**kwargs):
            return [
                ModelResponse(content="Answer", status="success", metadata=ModelResponseMetadata(model="gpt-5-mini")),
                ModelResponse(content="Answer 2", status="success", metadata=ModelResponseMetadata(model="haiku")),
            ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                thread_id="my-thread-123",
            )

        assert result["thread_id"] == "my-thread-123"

    @pytest.mark.asyncio
    async def test_validation_error_with_one_model(self):
        """Test that validation fails with only one model."""
        with pytest.raises(ValidationError):
            DebateRequest(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini"],  # Only 1 model
                base_path="/tmp",
            )

    @pytest.mark.asyncio
    async def test_step2_partial_failure(self):
        """Test partial failure in Step 2."""
        step_counter = [0]

        async def mock_execute_parallel(**kwargs):
            step_counter[0] += 1
            if step_counter[0] == 1:
                # Step 1: Both succeed
                return [
                    ModelResponse(content="Answer 1", status="success", metadata=ModelResponseMetadata(model="gpt-5-mini")),
                    ModelResponse(content="Answer 2", status="success", metadata=ModelResponseMetadata(model="haiku")),
                ]
            else:
                # Step 2: One succeeds, one fails
                return [
                    ModelResponse(content="Debate 1", status="success", metadata=ModelResponseMetadata(model="gpt-5-mini")),
                    ModelResponse(content="", status="error", error="Timeout", metadata=ModelResponseMetadata(model="haiku")),
                ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                thread_id="test-thread",
            )

        assert result["status"] == "partial"
        assert "Step 1 (2/2)" in result["summary"]
        assert "Step 2 (1/2)" in result["summary"]

    @pytest.mark.asyncio
    async def test_too_many_files_error(self, tmp_path):
        """Test file count limit enforcement via Pydantic validator."""
        from multi_mcp.config import settings

        # Create too many files
        files = []
        for i in range(settings.max_files_per_review + 1):
            f = tmp_path / f"test{i}.py"
            f.write_text(f"# File {i}")
            files.append(str(f))

        # Validation happens in DebateRequest, so this should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            DebateRequest(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path=str(tmp_path),
                relevant_files=files,
            )

        # Verify the error message
        assert "Too many files" in str(exc_info.value)
        assert str(settings.max_files_per_review) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_with_relevant_files_embedding(self):
        """Test file embedding when relevant_files are provided (via MessageBuilder)."""

        async def mock_execute_parallel(**kwargs):
            # Return success for both steps
            return [
                ModelResponse(
                    content="Answer with files",
                    status="success",
                    metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=100),
                )
            ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test",
                content="Review these files",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                relevant_files=["/tmp/test.py"],
                thread_id="test-thread",
            )

            # MessageBuilder handles file embedding - just verify success
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_all_step2_models_fail(self):
        """Test when all models succeed in Step 1 but all fail in Step 2."""
        step_counter = [0]

        async def mock_execute_parallel(**kwargs):
            step_counter[0] += 1
            if step_counter[0] == 1:
                # Step 1: All succeed
                return [
                    ModelResponse(
                        content="Model 1 answer",
                        status="success",
                        metadata=ModelResponseMetadata(model="gpt-5-mini", total_tokens=100),
                    ),
                    ModelResponse(
                        content="Model 2 answer",
                        status="success",
                        metadata=ModelResponseMetadata(model="haiku", total_tokens=150),
                    ),
                ]
            else:
                # Step 2: All fail
                return [
                    ModelResponse(content="Error", status="error", metadata=ModelResponseMetadata(model="gpt-5-mini")),
                    ModelResponse(content="Error", status="error", metadata=ModelResponseMetadata(model="haiku")),
                ]

        with patch("multi_mcp.tools.debate.execute_parallel", side_effect=mock_execute_parallel):
            result = await debate_impl(
                name="Test",
                content="Question?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "haiku"],
                base_path="/tmp",
                thread_id="test-thread",
            )

            assert result["status"] == "error"
            assert "Step 2 failed for all" in result["summary"]
            assert "2 models" in result["summary"]
