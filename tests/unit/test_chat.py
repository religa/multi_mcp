"""Unit tests for chat tool."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from multi_mcp.schemas.base import ModelResponse, ModelResponseMetadata
from multi_mcp.tools.chat import chat_impl


def mock_llm_response(content: str, model: str = "gpt-5-mini") -> ModelResponse:
    """Helper to create a ModelResponse for mocking _call_single_model."""
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


class TestChatBasicFunctionality:
    """Tests for basic chat functionality (stateless)."""

    @pytest.mark.asyncio
    async def test_new_thread_created_when_none(self):
        """Test that new thread is created when thread_id is None."""
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response("Hello! How can I help?")):
            result = await chat_impl(
                name="Chat",
                content="Hello",
                step_number=1,
                next_action="continue",
                model="gpt-5-mini",
                base_path="/tmp/test",
                thread_id="test-thread",
            )

        assert result["status"] == "success"
        assert "thread_id" in result
        assert len(result["thread_id"]) > 0  # UUID generated

    @pytest.mark.asyncio
    async def test_stop_action_still_calls_llm(self):
        """Test that next_action='stop' still processes the message (chat always calls LLM)."""
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response("Goodbye! Have a great day.")):
            result = await chat_impl(
                name="Chat",
                content="Goodbye",
                step_number=2,
                next_action="stop",
                model="gpt-5-mini",
                base_path="/tmp/test",
                thread_id="test-thread",
            )

        assert result["status"] == "success"
        assert "Goodbye" in result["content"]
        assert "metadata" in result  # LLM was called


class TestChatLLMCalls:
    """Tests for chat LLM interaction."""

    @pytest.mark.asyncio
    async def test_llm_called_with_message(self):
        """Test that LLM is called with user message."""
        with patch(
            "multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response("I can help with that.")
        ) as mock_llm:
            result = await chat_impl(
                name="Chat",
                content="How do I write tests?",
                step_number=1,
                next_action="continue",
                model="gpt-5-mini",
                base_path="/tmp/test",
                thread_id="test-thread",
            )

        # LLM should be called
        mock_llm.assert_called_once()

        # Check the messages passed to LLM
        call_args = mock_llm.call_args
        messages = call_args.kwargs["messages"]

        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        # Content is now XML-wrapped
        assert "<USER_MESSAGE>" in messages[-1]["content"]
        assert "How do I write tests?" in messages[-1]["content"]
        assert "</USER_MESSAGE>" in messages[-1]["content"]

        # Check response
        assert result["status"] == "success"
        assert result["content"] == "I can help with that."
        assert result["metadata"]["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_response_includes_metadata(self):
        """Test that response includes token usage metadata."""
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response("Response text")):
            result = await chat_impl(
                name="Chat",
                content="Test message",
                step_number=1,
                next_action="continue",
                model="gpt-5-mini",
                base_path="/tmp/test",
                thread_id="test-thread",
            )

        assert "metadata" in result
        assert result["metadata"]["model"] == "gpt-5-mini"
        assert result["metadata"]["prompt_tokens"] == 10
        assert result["metadata"]["completion_tokens"] == 5
        assert result["metadata"]["total_tokens"] == 15
        assert "latency_ms" in result["metadata"]


class TestChatFileHandling:
    """Tests for file handling in chat."""

    @pytest.mark.asyncio
    async def test_chat_with_relevant_files(self):
        """Test chat with files provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    return 'world'\n")

            with patch("multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response("Response")) as mock_llm:
                result = await chat_impl(
                    name="Chat",
                    content="Review this code",
                    step_number=1,
                    next_action="continue",
                    model="gpt-5-mini",
                    base_path=tmpdir,
                    relevant_files=[str(test_file)],
                    thread_id="test-thread",
                )

        assert result["status"] == "success"
        assert "thread_id" in result

        # Verify file content was included in LLM call
        call_args = mock_llm.call_args
        messages = call_args.kwargs["messages"]
        user_message = messages[-1]["content"]

        # Should contain both the user content and embedded file
        assert "Review this code" in user_message
        assert "EDITABLE_FILES" in user_message
        assert "test.py" in user_message

    @pytest.mark.asyncio
    async def test_chat_works_without_files(self):
        """Test backward compatibility - chat works without files."""
        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response("Hello!")) as mock_llm:
            result = await chat_impl(
                name="Chat",
                content="Hi",
                step_number=1,
                next_action="continue",
                model="gpt-5-mini",
                base_path="/tmp/test",
                relevant_files=None,  # No files
                thread_id="test-thread",
            )

        assert result["status"] == "success"

        # Verify no file content in message
        call_args = mock_llm.call_args
        messages = call_args.kwargs["messages"]
        user_message = messages[-1]["content"]

        # Content is XML-wrapped but without files
        assert "<USER_MESSAGE>" in user_message
        assert "Hi" in user_message
        assert "</USER_MESSAGE>" in user_message
        assert "EDITABLE_FILES" not in user_message


class TestChatSpecialCases:
    """Tests for special case responses (JSON status handling)."""

    @pytest.mark.asyncio
    async def test_chat_files_required_response(self):
        """Test special case: files_required_to_continue."""
        json_response = '{"status": "files_required_to_continue", "message": "To answer this question, I need to see: src/auth.py"}'

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response(json_response)):
            result = await chat_impl(
                name="Chat",
                content="Review auth",
                step_number=1,
                next_action="continue",
                model="gpt-5-mini",
                base_path="/tmp/project",
                thread_id="test-thread",
            )

        assert result["status"] == "in_progress"
        assert "src/auth.py" in result["content"]

    @pytest.mark.asyncio
    async def test_chat_normal_text_response(self):
        """Test normal text response (no special case)."""
        with patch(
            "multi_mcp.utils.llm_runner._litellm_client.execute",
            return_value=mock_llm_response("Authentication is handled in src/auth.py..."),
        ):
            result = await chat_impl(
                name="Chat",
                content="How does auth work?",
                step_number=1,
                next_action="continue",
                model="gpt-5-mini",
                base_path="/tmp/project",
                thread_id="test-thread",
            )

        assert result["status"] == "success"
        assert "Authentication is handled" in result["content"]

    @pytest.mark.asyncio
    async def test_chat_clarification_required_response(self):
        """Test special case: clarification_required."""
        json_response = '{"status": "clarification_required", "message": "Which module did you mean - auth or authentication?", "options": ["auth module", "authentication service"]}'

        with patch("multi_mcp.utils.llm_runner._litellm_client.execute", return_value=mock_llm_response(json_response)):
            result = await chat_impl(
                name="Chat",
                content="Review auth",
                step_number=1,
                next_action="continue",
                model="gpt-5-mini",
                base_path="/tmp/project",
                thread_id="test-thread",
            )

        assert result["status"] == "in_progress"
        assert "Which module" in result["content"]
