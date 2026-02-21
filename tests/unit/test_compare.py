"""Unit tests for compare tool."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from multi_mcp.memory.store import get_messages, make_model_thread_id
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
        from multi_mcp.settings import settings

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


class TestCompareMultiTurn:
    """Test multi-turn compare with per-model conversation history."""

    @pytest.mark.asyncio
    async def test_compare_stores_per_model_history(self):
        """Test that compare stores conversation history per model."""
        thread_id = f"test-multi-turn-{uuid.uuid4()}"

        async def mock_execute(canonical_name, model_config, messages, enable_web_search=False):
            return mock_model_response(content=f"Response from {canonical_name}", model=canonical_name)

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_execute

            result = await compare_impl(
                name="Turn 1",
                content="First question",
                step_number=1,
                next_action="continue",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id=thread_id,
            )

            assert result["status"] == "success"

        # Verify per-model history was stored
        history_a = await get_messages(make_model_thread_id(thread_id, "model-a"))
        history_b = await get_messages(make_model_thread_id(thread_id, "model-b"))

        # Each model should have system + user + assistant (3 messages)
        assert len(history_a) == 3
        assert history_a[-1]["role"] == "assistant"
        assert "Response from model-a" in history_a[-1]["content"]

        assert len(history_b) == 3
        assert history_b[-1]["role"] == "assistant"
        assert "Response from model-b" in history_b[-1]["content"]

    @pytest.mark.asyncio
    async def test_compare_second_turn_uses_history(self):
        """Test that second turn includes first turn history per model."""
        thread_id = f"test-second-turn-{uuid.uuid4()}"
        captured_messages: dict[str, list] = {}

        async def mock_execute_turn1(canonical_name, model_config, messages, enable_web_search=False):
            return mock_model_response(content=f"Turn 1 response from {canonical_name}", model=canonical_name)

        async def mock_execute_turn2(canonical_name, model_config, messages, enable_web_search=False):
            captured_messages[canonical_name] = messages
            return mock_model_response(content=f"Turn 2 response from {canonical_name}", model=canonical_name)

        # Turn 1: Execute and store history
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_execute_turn1

            await compare_impl(
                name="Turn 1",
                content="First question",
                step_number=1,
                next_action="continue",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id=thread_id,
            )

        # Turn 2: Should include history from turn 1
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_execute_turn2

            await compare_impl(
                name="Turn 2",
                content="Second question",
                step_number=2,
                next_action="stop",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id=thread_id,
            )

        # Verify each model received its own history plus new question
        for model in ["model-a", "model-b"]:
            messages = captured_messages[model]
            # Should have: system + user1 + assistant1 + user2
            assert len(messages) == 4
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[2]["role"] == "assistant"
            assert f"Turn 1 response from {model}" in messages[2]["content"]
            assert messages[3]["role"] == "user"
            assert "Second question" in messages[3]["content"]

    @pytest.mark.asyncio
    async def test_compare_model_history_isolation(self):
        """Test that model A doesn't see model B's history."""
        thread_id = f"test-isolation-{uuid.uuid4()}"
        captured_messages: dict[str, list] = {}

        async def mock_execute_turn1(canonical_name, model_config, messages, enable_web_search=False):
            # Different responses per model
            if canonical_name == "model-a":
                return mock_model_response(content="A says: I prefer PostgreSQL", model=canonical_name)
            else:
                return mock_model_response(content="B says: I prefer MongoDB", model=canonical_name)

        async def mock_execute_turn2(canonical_name, model_config, messages, enable_web_search=False):
            captured_messages[canonical_name] = messages
            return mock_model_response(content="Turn 2", model=canonical_name)

        # Turn 1
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_execute_turn1

            await compare_impl(
                name="Turn 1",
                content="What database do you recommend?",
                step_number=1,
                next_action="continue",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id=thread_id,
            )

        # Turn 2
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_execute_turn2

            await compare_impl(
                name="Turn 2",
                content="Why not the other option?",
                step_number=2,
                next_action="stop",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id=thread_id,
            )

        # Model A should only see "PostgreSQL" in its history, not "MongoDB"
        msgs_a = captured_messages["model-a"]
        history_content_a = " ".join(m["content"] for m in msgs_a)
        assert "PostgreSQL" in history_content_a
        assert "MongoDB" not in history_content_a

        # Model B should only see "MongoDB" in its history, not "PostgreSQL"
        msgs_b = captured_messages["model-b"]
        history_content_b = " ".join(m["content"] for m in msgs_b)
        assert "MongoDB" in history_content_b
        assert "PostgreSQL" not in history_content_b

    @pytest.mark.asyncio
    async def test_compare_failed_model_no_history(self):
        """Test that failed models don't store history."""
        thread_id = f"test-failure-{uuid.uuid4()}"

        async def mock_execute(canonical_name, model_config, messages, enable_web_search=False):
            if canonical_name == "model-a":
                return mock_model_response(content="Success", model=canonical_name)
            else:
                return mock_model_response(model=canonical_name, error="Model B failed")

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = mock_execute

            result = await compare_impl(
                name="Turn 1",
                content="Test question",
                step_number=1,
                next_action="continue",
                models=["model-a", "model-b"],
                base_path="/tmp",
                thread_id=thread_id,
            )

            assert result["status"] == "partial"

        # Model A should have history stored
        history_a = await get_messages(make_model_thread_id(thread_id, "model-a"))
        assert len(history_a) == 3

        # Model B should NOT have history (it failed)
        history_b = await get_messages(make_model_thread_id(thread_id, "model-b"))
        assert len(history_b) == 0
