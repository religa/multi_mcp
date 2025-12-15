"""CLI model execution via subprocess."""

import asyncio
import json
import logging
import os
import re
import shutil
import time

from multi_mcp.constants import DEBUG_LOG_MAX_LENGTH, ERROR_PREVIEW_MAX_LENGTH
from multi_mcp.models.config import ModelConfig
from multi_mcp.schemas.base import ModelResponse, ModelResponseMetadata
from multi_mcp.settings import settings
from multi_mcp.utils.json_parser import parse_llm_json
from multi_mcp.utils.request_logger import log_llm_interaction

logger = logging.getLogger(__name__)


class CLIExecutor:
    """Executes CLI models via subprocess."""

    async def execute(
        self,
        canonical_name: str,
        model_config: ModelConfig,
        messages: list[dict],
        enable_web_search: bool = False,
    ) -> ModelResponse:
        """Execute CLI model via subprocess.

        Args:
            canonical_name: Canonical model name
            model_config: Model configuration
            messages: List of message dicts
            enable_web_search: Enable web search (ignored for CLI models)

        Returns:
            ModelResponse with CLI output
        """
        # Note: enable_web_search is ignored for CLI models (not supported)

        # Validate CLI command is set
        if not model_config.cli_command:
            error_msg = f"CLI model '{canonical_name}' has no cli_command configured"
            logger.error(f"[CLI_CALL] {error_msg}")
            return ModelResponse.error_response(
                error=error_msg,
                model=canonical_name,
            )

        # Narrow type for type checker - we know cli_command is str here
        cli_command: str = model_config.cli_command

        # Check if CLI command exists
        if not shutil.which(cli_command):
            install_hint = self._get_install_hint(cli_command)
            error_msg = f"CLI command '{cli_command}' not found in PATH. {install_hint}"
            logger.error(f"[CLI_CALL] {error_msg}")
            return ModelResponse.error_response(
                error=error_msg,
                model=canonical_name,
            )

        # Extract prompt from messages (use last user message)
        prompt = messages[-1]["content"] if messages else ""

        # Build command
        command = [cli_command] + model_config.cli_args

        # Prepare environment
        env = os.environ.copy()

        # Inject API keys from settings into environment for expansion
        # This allows ${ANTHROPIC_API_KEY} etc. to work even if not in os.environ
        if settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.openai_api_key:
            env["OPENAI_API_KEY"] = settings.openai_api_key
        if settings.gemini_api_key:
            env["GEMINI_API_KEY"] = settings.gemini_api_key
        if settings.openrouter_api_key:
            env["OPENROUTER_API_KEY"] = settings.openrouter_api_key

        # Now expand variables in cli_env (e.g., ${ANTHROPIC_API_KEY})
        # Use our env dict for expansion, not os.environ (which may not have the keys in CI)
        for key, value in model_config.cli_env.items():
            expanded = self._expand_env_vars(value, env)
            env[key] = expanded

        # Use config timeout or fall back to settings
        timeout = settings.model_timeout_seconds

        logger.info(f"[CLI_CALL] model={canonical_name} command={cli_command} parser={model_config.cli_parser}")
        logger.debug(f"[CLI_CALL] full_command={' '.join(command)}")

        start_time = time.perf_counter()
        process: asyncio.subprocess.Process | None = None

        try:
            # Execute CLI subprocess
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(input=prompt.encode("utf-8")),
                timeout=timeout,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            if process.returncode != 0:
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                stdout = stdout_bytes.decode("utf-8", errors="replace")

                # Use stderr if available, otherwise use stdout (some CLIs write errors to stdout)
                error_output = stderr if stderr else stdout
                error_preview = error_output[:ERROR_PREVIEW_MAX_LENGTH] if error_output else "(no output)"

                install_hint = self._get_install_hint(cli_command)
                logger.error(f"[CLI_CALL] {canonical_name} failed with exit code {process.returncode}")
                logger.debug(f"[CLI_CALL] stderr: {stderr[:DEBUG_LOG_MAX_LENGTH]}")
                logger.debug(f"[CLI_CALL] stdout: {stdout[:DEBUG_LOG_MAX_LENGTH]}")
                return ModelResponse.error_response(
                    error=f"CLI '{cli_command}' failed with exit code {process.returncode}. "
                    f"Error: {error_preview}\n\n"
                    f"Troubleshooting: {install_hint}",
                    model=canonical_name,
                    latency_ms=latency_ms,
                )

            # Parse output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            content = self._parse_output(stdout, model_config.cli_parser)

            metadata = ModelResponseMetadata(
                model=canonical_name,
                prompt_tokens=0,  # CLI doesn't report tokens
                completion_tokens=0,
                total_tokens=0,
                latency_ms=latency_ms,
            )

            response = ModelResponse(
                content=content,
                status="success",
                metadata=metadata,
            )

            log_llm_interaction(
                request_data={
                    "model": canonical_name,
                    "cli": True,
                    "command": command,
                    "prompt_length": len(prompt),
                },
                response_data=response.model_dump(),
            )

            return response

        except TimeoutError:
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Clean up timed-out subprocess
            if process and process.returncode is None:
                process.kill()
                try:
                    await process.communicate()  # Drain pipes to prevent resource leak
                except Exception:
                    logger.debug("[CLI_CALL] Error while cleaning up timed-out CLI process", exc_info=True)

            logger.error(f"[CLI_CALL] {canonical_name} timed out after {timeout}s")
            return ModelResponse.error_response(
                error=f"CLI '{cli_command}' timed out after {timeout}s. "
                f"The command took longer than expected. "
                f"Consider using a faster model or increasing MODEL_TIMEOUT_SECONDS in config.",
                model=canonical_name,
                latency_ms=latency_ms,
            )

        except FileNotFoundError as e:
            # This shouldn't happen due to shutil.which() check, but handle it anyway
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            install_hint = self._get_install_hint(cli_command)
            logger.error(f"[CLI_CALL] {canonical_name} command not found: {e}")
            return ModelResponse.error_response(
                error=f"CLI command '{cli_command}' not found. {install_hint}",
                model=canonical_name,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Clean up failed subprocess
            if process and process.returncode is None:
                process.kill()
                try:
                    await process.communicate()  # Drain pipes to prevent resource leak
                except Exception:
                    logger.debug("[CLI_CALL] Error while cleaning up failed CLI process", exc_info=True)

            logger.error(f"[CLI_CALL] {canonical_name} failed with exception: {type(e).__name__}: {e}")
            logger.debug("[CLI_CALL] Full error details", exc_info=True)
            return ModelResponse.error_response(
                error=f"CLI execution failed: {type(e).__name__}: {str(e)}",
                model=canonical_name,
                latency_ms=latency_ms,
            )

    def _get_install_hint(self, cli_command: str) -> str:
        """Get installation hint for common CLI tools.

        Args:
            cli_command: CLI command name

        Returns:
            Installation hint string
        """
        hints = {
            "gemini": "Install via: npm install -g @google/generative-ai-cli",
            "codex": "Install via: npm install -g @anthropic-ai/codex-cli",
            "claude": "Install via: pip install anthropic-cli",
        }
        return hints.get(cli_command, f"Ensure '{cli_command}' is installed and in PATH")

    def _parse_output(self, stdout: str, parser_type: str) -> str:
        """Parse CLI output based on parser type.

        Args:
            stdout: Raw CLI stdout
            parser_type: "json", "jsonl", or "text"

        Returns:
            Parsed content string
        """
        if parser_type == "json":
            # Use existing robust JSON parser (handles malformed JSON)
            parsed = parse_llm_json(stdout)
            if parsed is not None:
                # Extract content based on CLI format
                if isinstance(parsed, dict):
                    # Claude CLI format: check for errors first
                    # {"type":"result","is_error":true/false,"result":"content"}
                    if "is_error" in parsed and parsed["is_error"]:
                        # Claude CLI returned an error
                        error_msg = parsed.get("result", "Unknown error from Claude CLI")
                        raise ValueError(f"Claude CLI error: {error_msg}")

                    # Gemini CLI format: {"response": "content"}
                    if "response" in parsed:
                        return parsed["response"]
                    # Claude CLI format: {"result": "content"}
                    elif "result" in parsed:
                        return parsed["result"]
                return str(parsed)
            else:
                logger.warning("[CLI_PARSE] JSON parse failed, falling back to text")
                return stdout.strip()

        elif parser_type == "jsonl":
            # Parse JSONL (one JSON per line, extract text from events)
            lines = stdout.strip().split("\n")
            messages = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    # Handle different event types
                    if event.get("type") == "text":
                        text = event.get("text", "")
                        if text:  # Skip empty text fields
                            messages.append(text)
                    elif event.get("type") == "item.completed":
                        # Codex format: extract text from item
                        item = event.get("item", {})
                        if item.get("type") == "agent_message":
                            text = item.get("text", "")
                            if text:
                                messages.append(text)
                except json.JSONDecodeError:
                    continue
            return "\n".join(messages) if messages else stdout.strip()

        else:  # "text" or fallback
            return stdout.strip()

    def _expand_env_vars(self, value: str, env: dict[str, str]) -> str:
        """Expand environment variables in a string using provided env dict.

        Handles ${VAR_NAME} syntax. Uses the provided env dict instead of os.environ
        so that variables injected from settings are properly expanded.

        Args:
            value: String that may contain ${VAR_NAME} patterns
            env: Environment dict to use for variable lookup

        Returns:
            String with variables expanded
        """

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            result = env.get(var_name)
            # If variable not found in env, return original ${VAR} syntax
            return result if result is not None else match.group(0)

        return re.sub(r"\$\{([^}]+)\}", replacer, value)
