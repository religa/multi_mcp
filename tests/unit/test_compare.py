"""Unit tests for compare tool."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from multi_mcp.schemas.base import ModelResponse, ModelResponseMetadata, MultiToolRequest, MultiToolResponse
from multi_mcp.schemas.compare import CompareRequest
from multi_mcp.tools.compare import compare_impl
from multi_mcp.utils.context import set_request_context


def mock_model_response(content="Response", model="test-model", error=None):
    """Helper to create ModelResponse for mocking litellm_client.execute."""
    if error:
        return ModelResponse(
            content="",
            status="error",
            error=error,
            metadata=ModelResponseMetadata(model=model),
        )
    return ModelResponse(
        content=content,
        status="success",
        metadata=ModelResponseMetadata(
            model=model,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ),
    )


class TestCompareSchemas:
    """Test compare schema validation."""

    def test_multi_tool_request_requires_min_1_model(self):
        """MultiToolRequest requires at least 1 model."""
        with pytest.raises(ValueError, match="at least 1"):
            MultiToolRequest(
                name="test",
                content="test content",
                step_number=1,
                next_action="stop",
                models=[],  # Empty list not allowed
                base_path="/tmp",
            )

    def test_multi_tool_request_valid(self):
        """MultiToolRequest accepts 2+ models."""
        request = MultiToolRequest(
            name="test", content="test content", step_number=1, next_action="stop", models=["gpt-5-mini", "haiku"], base_path="/tmp"
        )
        assert len(request.models) == 2

    def test_compare_request_inherits_from_multi(self):
        """CompareRequest inherits MultiToolRequest fields."""
        request = CompareRequest(
            name="compare", content="What is 2+2?", step_number=1, next_action="stop", models=["model-a", "model-b"], base_path="/tmp"
        )
        assert request.models == ["model-a", "model-b"]
        assert request.content == "What is 2+2?"

    def test_model_response_success(self):
        """ModelResponse captures successful response."""
        result = ModelResponse(content="The answer is 4", status="success", metadata=ModelResponseMetadata(model="gpt-5-mini"))
        assert result.status == "success"
        assert result.error is None

    def test_model_response_error(self):
        """ModelResponse captures error."""
        result = ModelResponse(
            content="", status="error", error="API rate limit exceeded", metadata=ModelResponseMetadata(model="gpt-5-mini")
        )
        assert result.status == "error"
        assert result.error == "API rate limit exceeded"

    def test_multi_tool_response_complete(self):
        """MultiToolResponse with all models succeeded."""
        response = MultiToolResponse(
            thread_id="abc123",
            status="success",
            summary="All models succeeded",
            results=[
                ModelResponse(content="yes", status="success", metadata=ModelResponseMetadata(model="a")),
                ModelResponse(content="yes", status="success", metadata=ModelResponseMetadata(model="b")),
            ],
        )
        assert response.status == "success"
        assert len(response.results) == 2

    def test_multi_tool_response_partial(self):
        """MultiToolResponse with some models failed."""
        response = MultiToolResponse(
            thread_id="abc123",
            status="partial",
            summary="1/2 models succeeded",
            results=[
                ModelResponse(content="yes", status="success", metadata=ModelResponseMetadata(model="a")),
                ModelResponse(content="", status="error", error="timeout", metadata=ModelResponseMetadata(model="b")),
            ],
        )
        assert response.status == "partial"


class TestCompareImpl:
    """Test compare_impl function."""

    @pytest.mark.asyncio
    async def test_all_models_succeed(self):
        """Test compare with all models succeeding."""
        set_request_context(thread_id="test-thread")
        mock_response = ModelResponse(
            content="Response from model",
            status="success",
            metadata=ModelResponseMetadata(
                model="model-a",
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
            ),
        )

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            result = await compare_impl(
                name="test",
                content="What is 2+2?",
                step_number=1,
                next_action="stop",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id="test-thread",
            )

            assert result["status"] == "success"
            assert len(result["results"]) == 2
            assert all(r["status"] == "success" for r in result["results"])
            assert "all 2 models succeeded" in result["summary"]

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """Test compare with one model failing."""

        async def mock_call(canonical_name, model_config, messages, enable_web_search=False):
            if canonical_name == "model-a":
                return mock_model_response(content="Success", model="model-a")
            else:
                return mock_model_response(model="model-b", error="Model B failed")

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call_async:
            mock_call_async.side_effect = mock_call

            result = await compare_impl(
                name="test",
                content="test",
                step_number=1,
                next_action="stop",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id="test-thread",
            )

            assert result["status"] == "partial"
            assert "1/2" in result["summary"]
            assert "Failed: model-b" in result["summary"]

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        """Test compare with all models failing."""
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_model_response(error="All failed")

            result = await compare_impl(
                name="test",
                content="test",
                step_number=1,
                next_action="stop",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id="test-thread",
            )

            assert result["status"] == "error"
            assert "all 2 models failed" in result["summary"]

    @pytest.mark.asyncio
    async def test_thread_id_generated(self):
        """Test that thread_id is passed through correctly."""
        mock_response = mock_model_response(content="ok")

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            result = await compare_impl(
                name="test", content="test", step_number=1, next_action="stop", models=["a", "b"], base_path="/tmp", thread_id="test-thread"
            )

            assert "thread_id" in result
            assert result["thread_id"] == "test-thread"

    @pytest.mark.asyncio
    async def test_thread_id_preserved(self):
        """Test that provided thread_id is preserved."""
        set_request_context(thread_id="test-thread")
        mock_response = mock_model_response(content="ok")

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            result = await compare_impl(
                name="test",
                content="test",
                step_number=1,
                next_action="stop",
                models=["a", "b"],
                base_path="/tmp",
                thread_id="my-custom-thread",
            )

            assert result["thread_id"] == "my-custom-thread"

    @pytest.mark.asyncio
    async def test_compare_requires_min_2_models(self):
        """Test that Compare tool requires at least 2 models (even though base allows 1)."""
        with pytest.raises(ValidationError):
            CompareRequest(name="test", content="test", step_number=1, next_action="stop", models=["only-one"], base_path="/tmp")

    @pytest.mark.asyncio
    async def test_system_prompt_included(self):
        """Test that system prompt is included in model calls."""
        set_request_context(thread_id="test-thread")
        mock_response = mock_model_response(content="ok")

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            await compare_impl(
                name="test",
                content="What is 2+2?",
                step_number=1,
                next_action="stop",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id="test-thread",
            )

            # Verify system message was included in calls
            assert mock_call.call_count == 2
            for call in mock_call.call_args_list:
                messages = call.kwargs["messages"]
                assert len(messages) == 2
                assert messages[0]["role"] == "system"
                assert "Technical Expert" in messages[0]["content"]  # Compare prompt
                assert messages[1]["role"] == "user"
                # Content is now XML-wrapped by MessageBuilder
                assert "<USER_MESSAGE>" in messages[1]["content"]
                assert "What is 2+2?" in messages[1]["content"]
                assert "</USER_MESSAGE>" in messages[1]["content"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("files", [None, []])
    async def test_files_none_or_empty(self, files):
        """Test compare handles None/empty files identically."""
        mock_response = mock_model_response(content="Response", model="gpt-5-mini")

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            result = await compare_impl(
                name="Test",
                content="What is 2+2?",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "model-b"],
                base_path="/tmp",
                relevant_files=files,
                thread_id="test-thread",
            )

            assert result["status"] == "success"
            # Verify no file embedding in LLM call (but USER_MESSAGE tags are always present)
            call_args = mock_call.call_args_list[0]
            messages = call_args[1]["messages"]
            assert "<EDITABLE_FILES>" not in messages[-1]["content"]
            # USER_MESSAGE tags are now always present (from MessageBuilder)
            assert "<USER_MESSAGE>" in messages[-1]["content"]
            assert "What is 2+2?" in messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_with_files(self, tmp_path):
        """Test file embedding works correctly."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass")

        mock_response = mock_model_response(content="Looks good", model="gpt-5-mini")

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            result = await compare_impl(
                name="Test",
                content="Review this",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "model-b"],
                base_path=str(tmp_path),
                relevant_files=[str(test_file)],
                thread_id="test-thread",
            )

            assert result["status"] == "success"

            # Verify file was embedded with correct structure
            call_args = mock_call.call_args_list[0]
            messages = call_args[1]["messages"]
            user_content = messages[-1]["content"]

            assert "<EDITABLE_FILES>" in user_content
            assert "test.py" in user_content
            assert "def hello(): pass" in user_content
            assert "<USER_MESSAGE>" in user_content
            assert "Review this" in user_content

    @pytest.mark.asyncio
    async def test_too_many_files(self, tmp_path):
        """Test file count limit enforcement via Pydantic validator."""
        from multi_mcp.config import settings

        # Create too many files
        files = []
        for i in range(settings.max_files_per_review + 1):
            f = tmp_path / f"test{i}.py"
            f.write_text(f"# File {i}")
            files.append(str(f))

        # Validation happens in CompareRequest, so this should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            CompareRequest(
                name="Test",
                content="Review",
                step_number=1,
                next_action="stop",
                models=["gpt-5-mini", "model-b"],
                base_path=str(tmp_path),
                relevant_files=files,
            )

        # Verify the error message
        assert "Too many files" in str(exc_info.value)
        assert str(settings.max_files_per_review) in str(exc_info.value)
