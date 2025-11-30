"""Integration tests for real CLI execution.

Tests actual CLI tools when available, with graceful skipping when not installed.
"""

import pytest

from src.models.litellm_client import LiteLLMClient


class TestGeminiCLIRealExecution:
    """Test real Gemini CLI execution."""

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_gemini_cli_basic_execution(self, skip_if_no_gemini_cli):
        """Gemini CLI executes successfully with real API call."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "What is 2+2? Answer with just the number."}]

        result = await client.call_async(messages=messages, model="gemini-cli")

        assert result.status == "success"
        assert result.content
        assert result.metadata is not None
        assert result.metadata.model == "gemini-cli"
        assert result.metadata.latency_ms > 0
        # Verify correct answer is in response
        assert "4" in result.content


class TestCodexCLIRealExecution:
    """Test real Codex CLI execution."""

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_codex_cli_basic_execution(self, skip_if_no_codex_cli):
        """Codex CLI executes successfully with real API call."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "What is 2+2? Answer with just the number."}]

        result = await client.call_async(messages=messages, model="codex-cli")

        assert result.status == "success"
        assert result.content
        assert result.metadata is not None
        assert result.metadata.model == "codex-cli"
        assert result.metadata.latency_ms > 0
        assert "4" in result.content


class TestClaudeCLIRealExecution:
    """Test real Claude CLI execution."""

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_claude_cli_basic_execution(self, skip_if_no_claude_cli):
        """Claude CLI executes successfully with real API call."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "What is 2+2? Answer with just the number."}]

        result = await client.call_async(messages=messages, model="claude-cli")

        assert result.status == "success"
        assert result.content
        assert result.metadata is not None
        assert result.metadata.model == "claude-cli"
        assert result.metadata.latency_ms > 0
        assert "4" in result.content
