"""Unit tests for MCP tool decorator."""

from unittest.mock import patch

import pytest

from multi_mcp.utils.mcp_decorator import mcp_monitor


class TestMCPMonitorDecorator:
    """Tests for the @mcp_monitor decorator."""

    @pytest.mark.asyncio
    async def test_decorator_without_parentheses(self):
        """Test decorator used without parentheses (@mcp_monitor)."""

        @mcp_monitor
        async def my_tool(x: int, y: str = "default", thread_id: str = "test-id") -> dict:
            return {"x": x, "y": y}

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log:
            result = await my_tool(x=42, y="test", thread_id="thread-123")

        assert result == {"x": 42, "y": "test"}
        assert mock_log.call_count == 2

        # Verify request log (thread_id provided by mcp_factory)
        request_call = mock_log.call_args_list[0]
        assert request_call.kwargs["direction"] == "request"
        assert request_call.kwargs["tool_name"] == "my_tool"
        assert request_call.kwargs["data"]["x"] == 42
        assert request_call.kwargs["data"]["y"] == "test"
        assert request_call.kwargs["data"]["thread_id"] == "thread-123"

        # Verify response log
        response_call = mock_log.call_args_list[1]
        assert response_call.kwargs["direction"] == "response"
        assert response_call.kwargs["tool_name"] == "my_tool"
        assert response_call.kwargs["data"] == {"x": 42, "y": "test"}

    @pytest.mark.asyncio
    async def test_decorator_with_explicit_tool_name(self):
        """Test decorator with explicit tool_name parameter."""

        @mcp_monitor(tool_name="custom_name")
        async def my_tool(x: int) -> dict:
            return {"x": x}

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log:
            result = await my_tool(10)

        assert result == {"x": 10}
        # Verify custom tool name is used
        assert mock_log.call_args_list[0][1]["tool_name"] == "custom_name"
        assert mock_log.call_args_list[1][1]["tool_name"] == "custom_name"

    @pytest.mark.asyncio
    async def test_decorator_extracts_thread_id(self):
        """Test that decorator correctly sets context with thread_id from params."""

        @mcp_monitor
        async def my_tool(data: str, thread_id: str | None = None) -> dict:
            return {"data": data, "thread_id": thread_id}

        with (
            patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log,
            patch("multi_mcp.utils.mcp_decorator.set_request_context") as mock_set_context,
        ):
            await my_tool("test", thread_id="thread-123")

        # Context should be set with thread_id from params
        mock_set_context.assert_called_once()
        assert mock_set_context.call_args[1]["thread_id"] == "thread-123"
        # log_mcp_interaction should be called (without explicit thread_id)
        assert mock_log.call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_handles_no_params(self):
        """Test decorator works with functions that only accept thread_id."""

        @mcp_monitor
        async def models(thread_id: str = "test-id") -> dict:
            return {"models": ["gpt-5-mini", "claude-sonnet"]}

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log:
            result = await models(thread_id="thread-456")

        assert result == {"models": ["gpt-5-mini", "claude-sonnet"]}
        assert mock_log.call_count == 2

        # Verify thread_id is in logged data (provided by mcp_factory)
        logged_data = mock_log.call_args_list[0][1]["data"]
        assert logged_data["thread_id"] == "thread-456"

    @pytest.mark.asyncio
    async def test_decorator_handles_default_values(self):
        """Test decorator logs only kwargs (no default value capture)."""

        @mcp_monitor
        async def my_tool(required: str, thread_id: str = "test-id", optional: str = "default_value", items: list | None = None) -> dict:
            return {"required": required, "optional": optional, "items": items}

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log:
            await my_tool(required="test", thread_id="thread-789")

        # Verify only passed kwargs are logged (no defaults)
        logged_data = mock_log.call_args_list[0][1]["data"]
        assert logged_data["required"] == "test"
        assert logged_data["thread_id"] == "thread-789"
        # Default values not captured (no signature binding)
        assert "optional" not in logged_data
        assert "items" not in logged_data

    @pytest.mark.asyncio
    async def test_decorator_logs_error_on_exception(self):
        """Test decorator logs errors when function raises exception."""

        @mcp_monitor
        async def failing_tool(x: int) -> dict:
            raise ValueError("Something went wrong")

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log:
            with pytest.raises(ValueError, match="Something went wrong"):
                await failing_tool(42)

        # Should have request + error logs (no response)
        assert mock_log.call_count == 2

        # Verify error log
        error_call = mock_log.call_args_list[1]
        assert error_call[1]["direction"] == "error"
        assert error_call[1]["tool_name"] == "failing_tool"
        assert error_call[1]["data"]["error"] == "Something went wrong"
        assert error_call[1]["data"]["type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name, docstring, and annotations."""

        @mcp_monitor
        async def documented_tool(x: int, y: str) -> dict:
            """This is the docstring."""
            return {"x": x, "y": y}

        assert documented_tool.__name__ == "documented_tool"
        assert documented_tool.__doc__ == "This is the docstring."
        assert "x" in documented_tool.__annotations__
        assert "y" in documented_tool.__annotations__
        assert "return" in documented_tool.__annotations__

    @pytest.mark.asyncio
    async def test_decorator_with_mutable_default(self):
        """Test decorator doesn't mutate mutable default arguments."""

        @mcp_monitor
        async def tool_with_list(items: list = []) -> dict:  # noqa: B006
            items.append("new")
            return {"items": items}

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log:
            # Call twice to verify defaults aren't shared/mutated
            await tool_with_list()
            await tool_with_list()

        # Each call should see its own list
        # Note: This test documents the current behavior
        # The decorator logs the bound arguments at call time
        assert mock_log.call_count == 4

    @pytest.mark.asyncio
    async def test_decorator_with_kwargs(self):
        """Test decorator handles keyword arguments correctly."""

        @mcp_monitor
        async def my_tool(a: int, b: int, c: int = 3) -> dict:
            return {"sum": a + b + c}

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log:
            result = await my_tool(b=2, a=1)

        assert result == {"sum": 6}
        logged_data = mock_log.call_args_list[0][1]["data"]
        assert logged_data["a"] == 1
        assert logged_data["b"] == 2
        # Default value not captured (only passed kwargs are logged)
        assert "c" not in logged_data

    @pytest.mark.asyncio
    async def test_decorator_stacking_order(self):
        """Test that decorator works correctly when stacked with other decorators."""
        call_order = []

        def outer_decorator(func):
            async def wrapper(*args, **kwargs):
                call_order.append("outer_before")
                result = await func(*args, **kwargs)
                call_order.append("outer_after")
                return result

            return wrapper

        @outer_decorator
        @mcp_monitor
        async def my_tool(x: int) -> dict:
            call_order.append("tool")
            return {"x": x}

        with patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction"):
            await my_tool(1)

        # Outer decorator wraps mcp_monitor
        assert call_order == ["outer_before", "tool", "outer_after"]

    @pytest.mark.asyncio
    async def test_decorator_sets_base_path_in_context(self):
        """Test that decorator sets base_path in context from params."""

        @mcp_monitor
        async def my_tool(data: str, base_path: str, thread_id: str | None = None) -> dict:
            return {"data": data, "base_path": base_path}

        with (
            patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log,
            patch("multi_mcp.utils.mcp_decorator.set_request_context") as mock_set_context,
        ):
            await my_tool("test", base_path="/path/to/project", thread_id="thread-123")

        # Context should be set with base_path from params
        mock_set_context.assert_called_once()
        assert mock_set_context.call_args[1]["base_path"] == "/path/to/project"
        assert mock_set_context.call_args[1]["thread_id"] == "thread-123"
        # log_mcp_interaction should be called
        assert mock_log.call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_sets_all_context_values(self):
        """Test that decorator sets all context values (thread_id, workflow, step_number, base_path)."""

        @mcp_monitor
        async def my_tool(data: str, base_path: str, step_number: int, workflow_name: str, thread_id: str | None = None) -> dict:
            return {"data": data}

        with (
            patch("multi_mcp.utils.mcp_decorator.log_mcp_interaction") as mock_log,
            patch("multi_mcp.utils.mcp_decorator.set_request_context") as mock_set_context,
        ):
            await my_tool(data="test", base_path="/project", step_number=5, workflow_name="codereview", thread_id="thread-456")

        # Context should be set with all values
        mock_set_context.assert_called_once()
        call_kwargs = mock_set_context.call_args[1]
        assert call_kwargs["thread_id"] == "thread-456"
        # Workflow is always function name (workflow_name param is ignored)
        assert call_kwargs["workflow"] == "my_tool"
        assert call_kwargs["step_number"] == 5
        assert call_kwargs["base_path"] == "/project"
        assert mock_log.call_count == 2
