"""Unit tests for CLI executor."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from multi_mcp.models.cli_executor import CLIExecutor
from multi_mcp.models.config import ModelConfig
from multi_mcp.schemas.base import ModelResponse


class TestCLIExecutor:
    """Tests for CLIExecutor class."""

    @pytest.fixture
    def cli_executor(self):
        """Create CLI executor instance."""
        return CLIExecutor()

    @pytest.fixture
    def cli_model_config(self):
        """Create sample CLI model config."""
        return ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["chat"],
            cli_parser="json",
            cli_env={},
        )

    @pytest.fixture
    def mock_subprocess_success(self):
        """Create mock successful subprocess."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'{"response": "Test response from CLI"}', b""))
        return mock_process

    @pytest.fixture
    def mock_subprocess_failure(self):
        """Create mock failed subprocess."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error: something went wrong"))
        return mock_process

    @pytest.mark.asyncio
    async def test_execute_success(self, cli_executor, cli_model_config, mock_subprocess_success):
        """Test successful CLI execution."""
        with (
            patch("shutil.which", return_value="/usr/bin/gemini"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
            patch("multi_mcp.models.cli_executor.log_llm_interaction"),
        ):
            mock_exec.return_value = mock_subprocess_success

            result = await cli_executor.execute(
                canonical_name="gemini-cli",
                model_config=cli_model_config,
                messages=[{"role": "user", "content": "Test prompt"}],
            )

            assert isinstance(result, ModelResponse)
            assert result.status == "success"
            assert result.content == "Test response from CLI"
            assert result.metadata.model == "gemini-cli"
            assert result.metadata.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self, cli_executor, cli_model_config):
        """Test CLI command not found in PATH."""
        with patch("shutil.which", return_value=None):
            result = await cli_executor.execute(
                canonical_name="gemini-cli",
                model_config=cli_model_config,
                messages=[{"role": "user", "content": "Test"}],
            )

            assert result.status == "error"
            assert "not found in PATH" in result.error
            assert "Install via" in result.error or "Ensure" in result.error

    @pytest.mark.asyncio
    async def test_execute_missing_cli_command(self, cli_executor):
        """Test error when cli_command is not configured."""
        config = ModelConfig(provider="cli")

        result = await cli_executor.execute(
            canonical_name="test-cli",
            model_config=config,
            messages=[{"role": "user", "content": "Test"}],
        )

        assert result.status == "error"
        assert "no cli_command configured" in result.error

    @pytest.mark.asyncio
    async def test_execute_timeout(self, cli_executor, cli_model_config):
        """Test CLI execution timeout handling."""
        with (
            patch("shutil.which", return_value="/usr/bin/gemini"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
            patch("multi_mcp.models.cli_executor.settings") as mock_settings,
        ):
            mock_settings.model_timeout_seconds = 1

            # Create mock process that will timeout
            mock_process = MagicMock()
            mock_process.returncode = None  # Still running
            mock_process.kill = MagicMock()
            mock_process.communicate = AsyncMock(side_effect=TimeoutError())

            mock_exec.return_value = mock_process

            # First call to communicate() will timeout
            async def slow_communicate(*args, **kwargs):
                await asyncio.sleep(10)  # Longer than timeout
                return (b"", b"")

            mock_process.communicate.side_effect = None
            mock_process.communicate = slow_communicate

            result = await cli_executor.execute(
                canonical_name="gemini-cli",
                model_config=cli_model_config,
                messages=[{"role": "user", "content": "Test"}],
            )

            assert result.status == "error"
            assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_non_zero_exit(self, cli_executor, cli_model_config, mock_subprocess_failure):
        """Test CLI execution with non-zero exit code."""
        with (
            patch("shutil.which", return_value="/usr/bin/gemini"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        ):
            mock_exec.return_value = mock_subprocess_failure

            result = await cli_executor.execute(
                canonical_name="gemini-cli",
                model_config=cli_model_config,
                messages=[{"role": "user", "content": "Test"}],
            )

            assert result.status == "error"
            assert "failed with exit code 1" in result.error
            assert "Error: something went wrong" in result.error

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self, cli_executor, cli_model_config):
        """Test CLI execution exception handling."""
        with (
            patch("shutil.which", return_value="/usr/bin/gemini"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        ):
            mock_exec.side_effect = Exception("Unexpected error")

            result = await cli_executor.execute(
                canonical_name="gemini-cli",
                model_config=cli_model_config,
                messages=[{"role": "user", "content": "Test"}],
            )

            assert result.status == "error"
            assert "CLI execution failed" in result.error
            assert "Unexpected error" in result.error

    def test_parse_output_json(self, cli_executor):
        """Test JSON output parsing."""
        stdout = '{"response": "Test response"}'
        result = cli_executor._parse_output(stdout, "json")
        assert result == "Test response"

    def test_parse_output_json_claude_format(self, cli_executor):
        """Test JSON output parsing with Claude CLI format."""
        stdout = '{"result": "Test response", "is_error": false}'
        result = cli_executor._parse_output(stdout, "json")
        assert result == "Test response"

    def test_parse_output_json_error(self, cli_executor):
        """Test JSON output parsing with Claude CLI error."""
        stdout = '{"result": "Error message", "is_error": true}'
        with pytest.raises(ValueError, match="Claude CLI error"):
            cli_executor._parse_output(stdout, "json")

    def test_parse_output_json_malformed(self, cli_executor):
        """Test JSON parsing fallback for malformed JSON."""
        stdout = "not valid json"
        result = cli_executor._parse_output(stdout, "json")
        # Should fall back to text parsing
        assert result == "not valid json"

    def test_parse_output_jsonl(self, cli_executor):
        """Test JSONL output parsing."""
        stdout = """{"type": "text", "text": "Hello"}
{"type": "text", "text": "World"}"""
        result = cli_executor._parse_output(stdout, "jsonl")
        assert result == "Hello\nWorld"

    def test_parse_output_jsonl_codex_format(self, cli_executor):
        """Test JSONL output parsing with Codex format."""
        stdout = '{"type": "item.completed", "item": {"type": "agent_message", "text": "Test response"}}'
        result = cli_executor._parse_output(stdout, "jsonl")
        assert result == "Test response"

    def test_parse_output_jsonl_empty_lines(self, cli_executor):
        """Test JSONL parsing skips empty lines."""
        stdout = """{"type": "text", "text": "Hello"}

{"type": "text", "text": "World"}"""
        result = cli_executor._parse_output(stdout, "jsonl")
        assert result == "Hello\nWorld"

    def test_parse_output_text(self, cli_executor):
        """Test text output parsing."""
        stdout = "  Simple text response  \n"
        result = cli_executor._parse_output(stdout, "text")
        assert result == "Simple text response"

    def test_get_install_hint_gemini(self, cli_executor):
        """Test install hint for gemini CLI."""
        hint = cli_executor._get_install_hint("gemini")
        assert "npm install" in hint
        assert "@google/generative-ai-cli" in hint

    def test_get_install_hint_codex(self, cli_executor):
        """Test install hint for codex CLI."""
        hint = cli_executor._get_install_hint("codex")
        assert "npm install" in hint
        assert "@anthropic-ai/codex-cli" in hint

    def test_get_install_hint_claude(self, cli_executor):
        """Test install hint for claude CLI."""
        hint = cli_executor._get_install_hint("claude")
        assert "pip install" in hint
        assert "anthropic-cli" in hint

    def test_get_install_hint_unknown(self, cli_executor):
        """Test install hint for unknown CLI."""
        hint = cli_executor._get_install_hint("unknown-cli")
        assert "Ensure 'unknown-cli' is installed" in hint

    @pytest.mark.asyncio
    async def test_execute_injects_api_keys(self, cli_executor):
        """Test that API keys from settings are injected into environment."""
        config = ModelConfig(
            provider="cli",
            cli_command="test-cli",
            cli_args=[],
            cli_parser="text",
            cli_env={"API_KEY": "${ANTHROPIC_API_KEY}"},
        )

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Success", b""))

        with (
            patch("shutil.which", return_value="/usr/bin/test-cli"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
            patch("multi_mcp.models.cli_executor.settings") as mock_settings,
            patch("multi_mcp.models.cli_executor.log_llm_interaction"),
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.openai_api_key = None
            mock_settings.gemini_api_key = None
            mock_settings.openrouter_api_key = None
            mock_settings.model_timeout_seconds = 120

            mock_exec.return_value = mock_process

            result = await cli_executor.execute(
                canonical_name="test-cli",
                model_config=config,
                messages=[{"role": "user", "content": "Test"}],
            )

            # Verify environment was passed with API keys
            call_kwargs = mock_exec.call_args[1]
            assert "env" in call_kwargs
            # The env should have ANTHROPIC_API_KEY set
            assert "ANTHROPIC_API_KEY" in call_kwargs["env"]
            assert call_kwargs["env"]["ANTHROPIC_API_KEY"] is not None
            # And API_KEY should be expanded (not the template string)
            assert "API_KEY" in call_kwargs["env"]
            assert not call_kwargs["env"]["API_KEY"].startswith("${")  # Verify it was expanded
            assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_uses_last_user_message(self, cli_executor, cli_model_config):
        """Test that last user message is used as prompt."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
        ]

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'{"response": "Answer"}', b""))

        with (
            patch("shutil.which", return_value="/usr/bin/gemini"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
            patch("multi_mcp.models.cli_executor.log_llm_interaction"),
        ):
            mock_exec.return_value = mock_process

            await cli_executor.execute(
                canonical_name="gemini-cli",
                model_config=cli_model_config,
                messages=messages,
            )

            # Verify stdin received last message content
            communicate_call = mock_process.communicate.call_args
            stdin_data = communicate_call[1]["input"]
            assert stdin_data == b"Second question"

    @pytest.mark.asyncio
    async def test_execute_logs_interaction(self, cli_executor, cli_model_config, mock_subprocess_success):
        """Test that CLI interactions are logged."""
        with (
            patch("shutil.which", return_value="/usr/bin/gemini"),
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
            patch("multi_mcp.models.cli_executor.log_llm_interaction") as mock_log,
        ):
            mock_exec.return_value = mock_subprocess_success

            await cli_executor.execute(
                canonical_name="gemini-cli",
                model_config=cli_model_config,
                messages=[{"role": "user", "content": "Test"}],
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            assert call_args["request_data"]["model"] == "gemini-cli"
            assert call_args["request_data"]["cli"] is True
            assert "command" in call_args["request_data"]
            assert call_args["response_data"]["content"] == "Test response from CLI"
            assert call_args["response_data"]["status"] == "success"
