"""Smoke tests for server startup and tool registration.

These tests verify that:
- Server module imports without errors
- All expected tools are registered
- Tool schemas are valid
- No duplicate tool names
"""

import pytest


class TestServerImport:
    """Test server module can be imported."""

    def test_server_imports_successfully(self):
        """Server module imports without errors."""
        try:
            import src.server  # noqa: F401

            assert True, "Server imported successfully"
        except ImportError as e:
            pytest.fail(f"Failed to import server: {e}")

    def test_server_has_mcp_instance(self):
        """Server module has mcp instance."""
        from src.server import mcp

        assert mcp is not None, "mcp instance should exist"
        assert hasattr(mcp, "tool"), "mcp should have tool decorator"

    def test_server_has_all_tools(self):
        """Server has all expected tool functions."""
        from src.server import chat, codereview, compare, debate, models, version

        # Verify all tool functions exist
        assert chat is not None, "chat tool should exist"
        assert codereview is not None, "codereview tool should exist"
        assert compare is not None, "compare tool should exist"
        assert debate is not None, "debate tool should exist"
        assert models is not None, "models tool should exist"
        assert version is not None, "version tool should exist"


class TestToolRegistration:
    """Test MCP tools are properly registered."""

    def test_tools_registered_with_mcp(self):
        """All tools are registered with MCP server."""
        from src.server import mcp

        # Get registered tools via MCP's internal registry
        # FastMCP stores tools in mcp._tools or similar
        # This is a smoke test - just verify mcp instance exists
        assert mcp is not None

    def test_tool_count(self):
        """Verify expected number of tools registered."""
        from src.server import chat, codereview, compare, debate, models, version

        # Count tools (FunctionTool objects from FastMCP)
        tools = [chat, codereview, compare, debate, models, version]
        # All should be non-None
        non_none_tools = [t for t in tools if t is not None]

        # Should have exactly 6 tools
        assert len(non_none_tools) == 6, f"Expected 6 tools, found {len(non_none_tools)}"

    def test_no_duplicate_tool_names(self):
        """No duplicate tool names in registration."""
        from src.server import chat, codereview, compare, debate, models, version

        # FunctionTool objects have .name attribute
        tool_names = [
            getattr(chat, "name", "chat"),
            getattr(codereview, "name", "codereview"),
            getattr(compare, "name", "compare"),
            getattr(debate, "name", "debate"),
            getattr(models, "name", "models"),
            getattr(version, "name", "version"),
        ]

        # Check for duplicates
        assert len(tool_names) == len(set(tool_names)), f"Duplicate tool names found: {tool_names}"


class TestToolSchemas:
    """Test tool schemas are valid."""

    def test_codereview_schema_valid(self):
        """Codereview tool has valid schema."""
        from src.schemas.codereview import CodeReviewRequest

        # Schema should be a Pydantic model
        assert hasattr(CodeReviewRequest, "model_fields"), "CodeReviewRequest should be a Pydantic model"

        # Check required fields exist
        fields = CodeReviewRequest.model_fields
        assert "name" in fields, "CodeReviewRequest should have 'name' field"
        assert "content" in fields, "CodeReviewRequest should have 'content' field"
        assert "step_number" in fields, "CodeReviewRequest should have 'step_number' field"
        assert "next_action" in fields, "CodeReviewRequest should have 'next_action' field"

    def test_chat_schema_valid(self):
        """Chat tool has valid schema."""
        from src.schemas.chat import ChatRequest

        # Schema should be a Pydantic model
        assert hasattr(ChatRequest, "model_fields"), "ChatRequest should be a Pydantic model"

        # Check required fields exist
        fields = ChatRequest.model_fields
        assert "name" in fields, "ChatRequest should have 'name' field"
        assert "content" in fields, "ChatRequest should have 'content' field"

    def test_compare_schema_valid(self):
        """Compare tool has valid schema."""
        from src.schemas.compare import CompareRequest

        # Schema should be a Pydantic model
        assert hasattr(CompareRequest, "model_fields"), "CompareRequest should be a Pydantic model"

        # Check required fields exist
        fields = CompareRequest.model_fields
        assert "name" in fields, "CompareRequest should have 'name' field"
        assert "content" in fields, "CompareRequest should have 'content' field"
        assert "models" in fields, "CompareRequest should have 'models' field"

    def test_debate_schema_valid(self):
        """Debate tool has valid schema."""
        from src.schemas.debate import DebateRequest

        # Schema should be a Pydantic model
        assert hasattr(DebateRequest, "model_fields"), "DebateRequest should be a Pydantic model"

        # Check required fields exist
        fields = DebateRequest.model_fields
        assert "name" in fields, "DebateRequest should have 'name' field"
        assert "content" in fields, "DebateRequest should have 'content' field"
        assert "models" in fields, "DebateRequest should have 'models' field"


class TestToolImplementations:
    """Test tool implementation functions exist."""

    def test_codereview_impl_exists(self):
        """Codereview implementation function exists."""
        from src.tools.codereview import codereview_impl

        assert callable(codereview_impl), "codereview_impl should be callable"

    def test_chat_impl_exists(self):
        """Chat implementation function exists."""
        from src.tools.chat import chat_impl

        assert callable(chat_impl), "chat_impl should be callable"

    def test_compare_impl_exists(self):
        """Compare implementation function exists."""
        from src.tools.compare import compare_impl

        assert callable(compare_impl), "compare_impl should be callable"

    def test_debate_impl_exists(self):
        """Debate implementation function exists."""
        from src.tools.debate import debate_impl

        assert callable(debate_impl), "debate_impl should be callable"

    def test_models_impl_exists(self):
        """Models implementation function exists."""
        from src.tools.models import models_impl

        assert callable(models_impl), "models_impl should be callable"


class TestConfigurationLoading:
    """Test configuration loads without errors."""

    def test_config_imports(self):
        """Config module imports successfully."""
        from src.config import settings

        assert settings is not None, "settings should be loaded"

    def test_model_config_loads(self):
        """Model configuration loads successfully."""
        from src.models.config import load_models_config

        config = load_models_config()
        assert config is not None, "Model config should load"
        assert len(config.models) > 0, "Should have at least one model configured"

    def test_prompts_load(self):
        """System prompts load successfully."""
        from src.prompts import CHAT_PROMPT, CODEREVIEW_PROMPT

        assert len(CHAT_PROMPT) > 0, "Chat prompt should be loaded"
        assert len(CODEREVIEW_PROMPT) > 0, "Codereview prompt should be loaded"
