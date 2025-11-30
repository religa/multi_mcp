"""Integration tests for MCP server functionality.

These tests verify that:
1. The MCP server initializes correctly
2. Tools are registered with correct signatures
3. Tool descriptions are preserved
4. Tools can be invoked successfully
"""

import inspect
import os

import pytest

# Only run if integration tests are enabled
pytestmark = pytest.mark.skipif(os.getenv("RUN_E2E") != "1", reason="Integration tests require RUN_E2E=1")


class TestMCPServerInitialization:
    """Test MCP server initialization and tool registration."""

    def test_server_module_imports(self):
        """Server module should import without errors."""
        try:
            import src.server as server_module

            assert server_module is not None
        except Exception as e:
            pytest.fail(f"Failed to import server module: {e}")

    def test_mcp_instance_exists(self):
        """MCP server instance should exist."""
        from src.server import mcp

        assert mcp is not None
        assert hasattr(mcp, "name")

    def test_all_tools_registered(self):
        """All expected tools should be registered."""
        from src.server import chat, codereview, compare, debate, models, version

        # All tools should be accessible
        assert chat is not None
        assert codereview is not None
        assert compare is not None
        assert debate is not None
        assert models is not None
        assert version is not None


class TestToolSignatures:
    """Test that tool signatures are valid and correct."""

    def test_codereview_signature_valid(self):
        """Codereview tool should have valid parameter signature."""
        from src.server import codereview

        # Extract the actual function from FastMCP wrapper
        if hasattr(codereview, "fn"):
            func = codereview.fn
        elif callable(codereview):
            func = codereview
        else:
            pytest.fail("Cannot find callable function in codereview tool")

        sig = inspect.signature(func)
        params = list(sig.parameters.items())

        # Verify no required params after optional
        found_optional = False
        for param_name, param in params:
            if param.default is not inspect.Parameter.empty:
                found_optional = True
            elif found_optional:
                pytest.fail(f"Invalid signature: required parameter '{param_name}' comes after optional parameter")

    def test_chat_signature_valid(self):
        """Chat tool should have valid parameter signature."""
        from src.server import chat

        if hasattr(chat, "fn"):
            func = chat.fn
        elif callable(chat):
            func = chat
        else:
            pytest.fail("Cannot find callable function in chat tool")

        sig = inspect.signature(func)
        params = list(sig.parameters.items())

        # Verify parameter ordering
        found_optional = False
        for param_name, param in params:
            if param.default is not inspect.Parameter.empty:
                found_optional = True
            elif found_optional:
                pytest.fail(f"Invalid signature: required parameter '{param_name}' after optional")

    def test_compare_signature_valid(self):
        """Compare tool should have valid parameter signature."""
        from src.server import compare

        if hasattr(compare, "fn"):
            func = compare.fn
        elif callable(compare):
            func = compare
        else:
            pytest.fail("Cannot find callable function in compare tool")

        sig = inspect.signature(func)
        params = list(sig.parameters.items())

        # Verify parameter ordering
        found_optional = False
        for param_name, param in params:
            if param.default is not inspect.Parameter.empty:
                found_optional = True
            elif found_optional:
                pytest.fail(f"Invalid signature: required parameter '{param_name}' after optional")

    def test_debate_signature_valid(self):
        """Debate tool should have valid parameter signature."""
        from src.server import debate

        if hasattr(debate, "fn"):
            func = debate.fn
        elif callable(debate):
            func = debate
        else:
            pytest.fail("Cannot find callable function in debate tool")

        sig = inspect.signature(func)
        params = list(sig.parameters.items())

        # Verify parameter ordering
        found_optional = False
        for param_name, param in params:
            if param.default is not inspect.Parameter.empty:
                found_optional = True
            elif found_optional:
                pytest.fail(f"Invalid signature: required parameter '{param_name}' after optional")


class TestToolDescriptions:
    """Test that tool descriptions are preserved."""

    def test_codereview_has_description(self):
        """Codereview tool should have description."""
        from src.server import codereview

        # Check if tool has description
        if hasattr(codereview, "description"):
            assert codereview.description is not None
            assert len(codereview.description) > 0
            assert "code review" in codereview.description.lower()
        elif hasattr(codereview, "__doc__"):
            assert codereview.__doc__ is not None
            assert len(codereview.__doc__) > 0

    def test_chat_has_description(self):
        """Chat tool should have description."""
        from src.server import chat

        if hasattr(chat, "description"):
            assert chat.description is not None
            assert len(chat.description) > 0
        elif hasattr(chat, "__doc__"):
            assert chat.__doc__ is not None
            assert len(chat.__doc__) > 0

    def test_compare_has_description(self):
        """Compare tool should have description."""
        from src.server import compare

        if hasattr(compare, "description"):
            assert compare.description is not None
            assert len(compare.description) > 0
            assert "multiple" in compare.description.lower() or "compare" in compare.description.lower()
        elif hasattr(compare, "__doc__"):
            assert compare.__doc__ is not None

    def test_debate_has_description(self):
        """Debate tool should have description."""
        from src.server import debate

        if hasattr(debate, "description"):
            assert debate.description is not None
            assert len(debate.description) > 0
            assert "debate" in debate.description.lower()
        elif hasattr(debate, "__doc__"):
            assert debate.__doc__ is not None


class TestToolInvocation:
    """Test that tools can be invoked successfully."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_models_tool_invocation(self):
        """Models tool should be invocable and return results."""
        from src.tools.models import models_impl

        # Call the implementation directly
        result = await models_impl()

        assert isinstance(result, dict)
        assert "models" in result or "status" in result

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_version_tool_invocation(self):
        """Version tool should be invocable and return results."""
        from src.server import version

        # Get the underlying function
        if hasattr(version, "fn"):
            func = version.fn
        else:
            func = version

        result = await func()

        assert isinstance(result, dict)
        assert "version" in result or "name" in result

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_chat_tool_basic_invocation(self, integration_test_model):
        """Chat tool should accept valid parameters."""
        import uuid

        from src.tools.chat import chat_impl

        # Test with minimal required parameters
        try:
            result = await chat_impl(
                name="Test",
                content="Hello",
                step_number=1,
                next_action="stop",
                base_path="/tmp/test",
                model=integration_test_model,
                thread_id=str(uuid.uuid4()),
                relevant_files=[],
            )

            assert isinstance(result, dict)
            # Should have some response
            assert "status" in result or "response" in result or "summary" in result

        except Exception as e:
            # Expected to fail if model not configured, but signature should work
            if "API" not in str(e) and "key" not in str(e).lower():
                pytest.fail(f"Unexpected error (not API-related): {e}")


class TestServerStartup:
    """Test that server can start without errors."""

    def test_server_script_syntax(self):
        """Server script should have valid Python syntax."""
        import ast

        with open("src/server.py") as f:
            code = f.read()

        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Server script has syntax error: {e}")

    def test_mcp_factory_syntax(self):
        """MCP factory should have valid Python syntax."""
        import ast

        with open("src/utils/mcp_factory.py") as f:
            code = f.read()

        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"MCP factory has syntax error: {e}")


class TestParameterOrdering:
    """Regression tests for parameter ordering bug."""

    def test_no_syntax_error_in_generated_code(self):
        """Generated wrapper functions should not have syntax errors."""
        from src.schemas.chat import ChatRequest
        from src.schemas.codereview import CodeReviewRequest
        from src.schemas.compare import CompareRequest
        from src.schemas.debate import DebateRequest
        from src.tools.chat import chat_impl
        from src.tools.codereview import codereview_impl
        from src.tools.compare import compare_impl
        from src.tools.debate import debate_impl
        from src.utils.mcp_factory import create_mcp_wrapper

        # Test all tool schemas
        test_cases = [
            (ChatRequest, chat_impl, "Chat"),
            (CodeReviewRequest, codereview_impl, "Code Review"),
            (CompareRequest, compare_impl, "Compare"),
            (DebateRequest, debate_impl, "Debate"),
        ]

        for schema_class, impl_func, name in test_cases:
            try:
                wrapper = create_mcp_wrapper(schema_class, impl_func, f"Test {name}")
                sig = inspect.signature(wrapper)

                # Verify signature is valid
                params = list(sig.parameters.items())
                assert len(params) > 0, f"{name} should have parameters"

                # Check parameter ordering
                found_optional = False
                for param_name, param in params:
                    if param.default is not inspect.Parameter.empty:
                        found_optional = True
                    elif found_optional:
                        pytest.fail(
                            f"{name}: Required parameter '{param_name}' comes after optional parameter. This would cause SyntaxError!"
                        )

            except SyntaxError as e:
                pytest.fail(f"Generated wrapper for {name} has syntax error: {e}")
            except Exception as e:
                pytest.fail(f"Failed to create wrapper for {name}: {e}")
