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

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_gemini_cli_with_multiline_prompt(self, skip_if_no_gemini_cli):
        """Gemini CLI handles multiline prompts correctly."""
        client = LiteLLMClient()
        messages = [
            {
                "role": "user",
                "content": "Answer the following questions:\n1. What is Python?\n2. Is it a programming language?\n\nAnswer briefly.",
            }
        ]

        result = await client.call_async(messages=messages, model="gemini-cli")

        assert result.status == "success"
        assert result.content
        assert "python" in result.content.lower()

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_gemini_cli_alias_resolution(self, skip_if_no_gemini_cli):
        """Gemini CLI aliases resolve to same model."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say hello"}]

        # Test canonical name
        result1 = await client.call_async(messages=messages, model="gemini-cli")
        # Test alias
        result2 = await client.call_async(messages=messages, model="gem-cli")

        assert result1.status == "success"
        assert result2.status == "success"
        assert result1.metadata.model == result2.metadata.model


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

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_codex_cli_jsonl_parsing(self, skip_if_no_codex_cli):
        """Codex CLI JSONL output is parsed correctly."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "List 3 programming languages, one per line."}]

        result = await client.call_async(messages=messages, model="codex-cli")

        assert result.status == "success"
        assert result.content
        # JSONL parser should combine multiple text events
        assert "\n" in result.content or len(result.content) > 10

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_codex_cli_alias_resolution(self, skip_if_no_codex_cli):
        """Codex CLI aliases resolve to same model."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say hello"}]

        result1 = await client.call_async(messages=messages, model="codex-cli")
        result2 = await client.call_async(messages=messages, model="cx-cli")

        assert result1.status == "success"
        assert result2.status == "success"
        assert result1.metadata.model == result2.metadata.model


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

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_claude_cli_json_parsing(self, skip_if_no_claude_cli):
        """Claude CLI JSON output is parsed correctly."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Describe Python in one sentence."}]

        result = await client.call_async(messages=messages, model="claude-cli")

        assert result.status == "success"
        assert result.content
        assert "python" in result.content.lower()

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_claude_cli_alias_resolution(self, skip_if_no_claude_cli):
        """Claude CLI aliases resolve to same model."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say hello"}]

        result1 = await client.call_async(messages=messages, model="claude-cli")
        result2 = await client.call_async(messages=messages, model="cl-cli")

        assert result1.status == "success"
        assert result2.status == "success"
        assert result1.metadata.model == result2.metadata.model


class TestCLIOutputParsing:
    """Test CLI output parsing with real execution."""

    @pytest.mark.integration
    @pytest.mark.timeout(30)
    async def test_unicode_handling(self, skip_if_no_any_cli, has_gemini_cli, has_codex_cli, has_claude_cli):
        """CLI handles unicode characters in prompts and responses."""
        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say 'Hello 世界 🌍' back to me."}]

        # Use whichever CLI is available
        if has_gemini_cli:
            model = "gemini-cli"
        elif has_codex_cli:
            model = "codex-cli"
        elif has_claude_cli:
            model = "claude-cli"
        else:
            pytest.skip("No CLI available")

        result = await client.call_async(messages=messages, model=model)

        assert result.status == "success"
        assert result.content
        # Should handle unicode properly
        assert any(char in result.content for char in ["世界", "🌍", "Hello"])
