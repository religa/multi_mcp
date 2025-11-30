"""Unit tests for CLI subprocess execution with mocking.

Tests the _execute_cli_model() method with comprehensive subprocess mocking
to verify CLI execution, error handling, and output parsing.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.config import ModelConfig
from src.models.litellm_client import LiteLLMClient


class TestGeminiCLISubprocess:
    """Test Gemini CLI (JSON parser) with subprocess mocking."""

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_gemini_successful_execution(self, mock_subprocess, mock_which):
        """Gemini CLI executes successfully and parses JSON response."""
        # Setup: CLI command exists
        mock_which.return_value = "/usr/local/bin/gemini"

        # Setup: Successful subprocess execution
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"response": "The answer is 42"}', b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json", "--yolo"],
            cli_parser="json",
            cli_env={"GEMINI_API_KEY": "${GEMINI_API_KEY}"},
        )
        messages = [{"role": "user", "content": "What is the meaning of life?"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert result.content == "The answer is 42"
        assert result.metadata.model == "gemini-cli"
        assert result.metadata.latency_ms >= 0  # Mock execution is instant

        # Verify subprocess was called correctly
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        assert call_args[0] == ("gemini", "-o", "json", "--yolo")

        # Verify communicate was called with prompt
        mock_process.communicate.assert_called_once_with(
            input=b"What is the meaning of life?"
        )

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    async def test_gemini_cli_not_found(self, mock_which):
        """Gemini CLI not found returns helpful error."""
        # Setup: CLI command not found
        mock_which.return_value = None

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify
        assert result.status == "error"
        assert result.error is not None
        assert "gemini" in result.error.lower()
        assert "not found" in result.error.lower()
        assert "npm install" in result.error.lower()  # Installation hint

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_gemini_non_zero_exit_code(self, mock_subprocess, mock_which):
        """Gemini CLI non-zero exit code returns error."""
        mock_which.return_value = "/usr/local/bin/gemini"

        # Setup: Failed subprocess execution
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: API key invalid")
        )
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify
        assert result.status == "error"
        assert result.error is not None
        assert "exit code 1" in result.error
        assert "API key invalid" in result.error

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_gemini_timeout(self, mock_subprocess, mock_which):
        """Gemini CLI timeout returns helpful error."""
        mock_which.return_value = "/usr/local/bin/gemini"

        # Setup: Timeout during communicate
        mock_process = Mock()
        mock_process.communicate = AsyncMock(side_effect=TimeoutError())
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify
        assert result.status == "error"
        assert result.error is not None
        assert "timed out" in result.error.lower()
        assert "MODEL_TIMEOUT_SECONDS" in result.error

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_gemini_json_without_response_field(self, mock_subprocess, mock_which):
        """Gemini CLI JSON without 'response' field stringifies JSON."""
        mock_which.return_value = "/usr/local/bin/gemini"

        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"message": "Hello", "status": "ok"}', b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert "message" in result.content
        assert "Hello" in result.content


class TestCodexCLISubprocess:
    """Test Codex CLI (JSONL parser) with subprocess mocking."""

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_codex_successful_execution(self, mock_subprocess, mock_which):
        """Codex CLI executes successfully and parses JSONL events."""
        mock_which.return_value = "/usr/local/bin/codex"

        # Setup: JSONL output with text events
        jsonl_output = (
            '{"type":"text","text":"Step 1"}\n'
            '{"type":"text","text":"Step 2"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"Final answer"}}\n'
        )
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(jsonl_output.encode("utf-8"), b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="codex",
            cli_args=["exec", "--json", "--dangerously-bypass-approvals-and-sandbox"],
            cli_parser="jsonl",
        )
        messages = [{"role": "user", "content": "Write a function"}]

        result = await client._execute_cli_model("codex-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert "Step 1" in result.content
        assert "Step 2" in result.content
        assert "Final answer" in result.content

        # Verify command construction
        call_args = mock_subprocess.call_args[0]
        assert "codex" in call_args
        assert "exec" in call_args
        assert "--json" in call_args

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_codex_ignores_non_agent_messages(self, mock_subprocess, mock_which):
        """Codex CLI ignores non-agent_message item.completed events."""
        mock_which.return_value = "/usr/local/bin/codex"

        # Setup: Mixed events, some should be ignored
        jsonl_output = (
            '{"type":"item.completed","item":{"type":"tool_call","text":"Should ignore"}}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"Should include"}}\n'
        )
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(jsonl_output.encode("utf-8"), b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="codex",
            cli_args=["exec", "--json"],
            cli_parser="jsonl",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("codex-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert "Should include" in result.content
        assert "Should ignore" not in result.content

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_codex_skips_empty_text(self, mock_subprocess, mock_which):
        """Codex CLI skips events with empty text fields."""
        mock_which.return_value = "/usr/local/bin/codex"

        jsonl_output = (
            '{"type":"text","text":""}\n'
            '{"type":"text","text":"Valid text"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":""}}\n'
        )
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(jsonl_output.encode("utf-8"), b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="codex",
            cli_args=["exec", "--json"],
            cli_parser="jsonl",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("codex-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert result.content == "Valid text"

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_codex_handles_malformed_jsonl(self, mock_subprocess, mock_which):
        """Codex CLI skips malformed JSONL lines."""
        mock_which.return_value = "/usr/local/bin/codex"

        jsonl_output = (
            '{"type":"text","text":"Line 1"}\n'
            '{malformed json\n'
            '{"type":"text","text":"Line 2"}\n'
        )
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(jsonl_output.encode("utf-8"), b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="codex",
            cli_args=["exec", "--json"],
            cli_parser="jsonl",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("codex-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert "Line 1" in result.content
        assert "Line 2" in result.content


class TestClaudeCLISubprocess:
    """Test Claude CLI (JSON parser) with subprocess mocking."""

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_claude_successful_execution(self, mock_subprocess, mock_which):
        """Claude CLI executes successfully and parses JSON response."""
        mock_which.return_value = "/usr/local/bin/claude"

        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"response": "Code analysis complete"}', b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="claude",
            cli_args=["--output-format", "json"],
            cli_parser="json",
            cli_env={"ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"},
        )
        messages = [{"role": "user", "content": "Review this code"}]

        result = await client._execute_cli_model("claude-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert result.content == "Code analysis complete"

        # Verify command construction
        call_args = mock_subprocess.call_args[0]
        assert "claude" in call_args
        assert "--output-format" in call_args
        assert "json" in call_args

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    async def test_claude_cli_not_found(self, mock_which):
        """Claude CLI not found returns helpful error with pip install hint."""
        mock_which.return_value = None

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="claude",
            cli_args=["--output-format", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("claude-cli", config, messages)

        # Verify
        assert result.status == "error"
        assert result.error is not None
        assert "claude" in result.error.lower()
        assert "pip install" in result.error.lower()  # Specific to Claude CLI


class TestCLISubprocessEnvironment:
    """Test environment variable handling in CLI subprocess."""

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key-12345"})
    async def test_environment_variable_expansion(self, mock_subprocess, mock_which):
        """CLI subprocess receives expanded environment variables."""
        mock_which.return_value = "/usr/local/bin/gemini"

        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"response": "ok"}', b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
            cli_env={"GEMINI_API_KEY": "${GEMINI_API_KEY}"},
        )
        messages = [{"role": "user", "content": "test"}]

        await client._execute_cli_model("gemini-cli", config, messages)

        # Verify subprocess was called with expanded env vars
        call_kwargs = mock_subprocess.call_args[1]
        assert "env" in call_kwargs
        assert call_kwargs["env"]["GEMINI_API_KEY"] == "test-key-12345"


class TestCLISubprocessMessageHandling:
    """Test message extraction and prompt building."""

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_uses_last_user_message_as_prompt(self, mock_subprocess, mock_which):
        """CLI uses last message content as prompt."""
        mock_which.return_value = "/usr/local/bin/gemini"

        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"response": "ok"}', b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test with multiple messages
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
        ]

        await client._execute_cli_model("gemini-cli", config, messages)

        # Verify only last message was sent to CLI
        mock_process.communicate.assert_called_once_with(
            input=b"Second question"
        )

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_handles_empty_messages_list(self, mock_subprocess, mock_which):
        """CLI handles empty messages list gracefully."""
        mock_which.return_value = "/usr/local/bin/gemini"

        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b'{"response": "ok"}', b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test with empty messages
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = []

        await client._execute_cli_model("gemini-cli", config, messages)

        # Verify empty string was sent
        mock_process.communicate.assert_called_once_with(input=b"")


class TestCLISubprocessEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_handles_unicode_in_output(self, mock_subprocess, mock_which):
        """CLI handles unicode characters in output."""
        mock_which.return_value = "/usr/local/bin/gemini"

        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=('{"response": "Hello 世界 🌍"}'.encode(), b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify
        assert result.status == "success"
        assert "世界" in result.content
        assert "🌍" in result.content

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_handles_generic_exception(self, mock_subprocess, mock_which):
        """CLI handles unexpected exceptions gracefully."""
        mock_which.return_value = "/usr/local/bin/gemini"

        # Setup: Raise unexpected exception
        mock_subprocess.side_effect = RuntimeError("Unexpected error")

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify
        assert result.status == "error"
        assert result.error is not None
        assert "CLI execution failed" in result.error
        assert "RuntimeError" in result.error

    @pytest.mark.asyncio
    @patch("src.models.litellm_client.shutil.which")
    @patch("src.models.litellm_client.asyncio.create_subprocess_exec")
    async def test_stderr_truncation_for_long_errors(self, mock_subprocess, mock_which):
        """CLI truncates very long stderr messages."""
        mock_which.return_value = "/usr/local/bin/gemini"

        # Setup: Long stderr message
        long_error = "Error: " + "x" * 1000
        mock_process = Mock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", long_error.encode("utf-8"))
        )
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        # Test
        client = LiteLLMClient()
        config = ModelConfig(
            provider="cli",
            cli_command="gemini",
            cli_args=["-o", "json"],
            cli_parser="json",
        )
        messages = [{"role": "user", "content": "test"}]

        result = await client._execute_cli_model("gemini-cli", config, messages)

        # Verify stderr was truncated to 500 chars
        assert result.status == "error"
        assert result.error is not None
        # The error message contains the first 500 chars of stderr
        assert "Error: x" in result.error
