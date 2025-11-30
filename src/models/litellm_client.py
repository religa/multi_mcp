"""LiteLLM client wrapper with config-based model resolution."""

import asyncio
import json
import logging
import os
import shutil
import time
from typing import Any

import litellm

from src.config import settings
from src.models.config import ModelConfig
from src.models.resolver import ModelResolver
from src.schemas.base import ModelResponse, ModelResponseMetadata
from src.utils.json_parser import parse_llm_json
from src.utils.request_logger import log_llm_interaction

logger = logging.getLogger(__name__)

litellm.drop_params = True


class LiteLLMClient:
    """Wrapper for LiteLLM model calls with config-based resolution."""

    def __init__(self, resolver: ModelResolver | None = None):
        """Initialize LiteLLM client.

        Args:
            resolver: Optional ModelResolver instance. Creates one if not provided.
        """
        self._resolver: ModelResolver | None = resolver

    @property
    def resolver(self) -> ModelResolver:
        """Lazy-load resolver to avoid import-time config loading."""
        if self._resolver is None:
            self._resolver = ModelResolver()
        return self._resolver

    async def call_async(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> ModelResponse:
        """Call LiteLLM with config-based model resolution and return ModelResponse.

        Args:
            messages: List of message dicts with role and content
            model: Model name or alias (uses default if not specified)

        Returns:
            ModelResponse with status, content, metadata, error
        """
        # Resolve model: explicit > primary default
        model = model or self.resolver.get_default()

        try:
            canonical_name, model_config = self.resolver.resolve(model)

            # Route to CLI execution if this is a CLI model
            if model_config.is_cli_model():
                return await self._execute_cli_model(canonical_name, model_config, messages)

            # API model execution (existing logic)
            timeout = settings.model_timeout_seconds
            litellm_model = model_config.litellm_model

            # Apply temperature (config constraint > default)
            temp = settings.default_temperature
            if model_config.constraints and model_config.constraints.temperature is not None:
                temp = model_config.constraints.temperature

            logger.info(f"[MODEL_CALL] input={model} canonical={canonical_name} litellm={litellm_model} temp={temp}")

            # Build kwargs starting with generic params from config
            kwargs: dict[str, Any] = {
                **model_config.params,
                "model": litellm_model,
                "messages": messages,
                "temperature": temp,
                "num_retries": settings.max_retries,
                "timeout": timeout,
            }

            logger.debug(f"[MODEL_REQUEST] litellm_model={litellm_model} num_messages={len(messages)}")

            # Call LiteLLM with timeout protection
            start_time = time.perf_counter()
            response = await asyncio.wait_for(
                litellm.acompletion(**kwargs),
                timeout=timeout,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            content = response.choices[0].message.content or ""  # type: ignore[attr-defined]

            metadata = ModelResponseMetadata(
                model=canonical_name,
                prompt_tokens=response.usage.prompt_tokens,  # type: ignore[attr-defined]
                completion_tokens=response.usage.completion_tokens,  # type: ignore[attr-defined]
                total_tokens=response.usage.total_tokens,  # type: ignore[attr-defined]
                latency_ms=latency_ms,
            )
            response = ModelResponse(
                content=content,
                status="success",
                metadata=metadata,
            )

            log_llm_interaction(
                request_data={**kwargs},
                response_data=response.model_dump(),
            )
            return response

        except TimeoutError:
            logger.error(f"[MODEL_CALL] Model {model} timed out after {timeout}s")
            return ModelResponse.error_response(
                error=f"Request timed out after {timeout}s",
                model=model,
            )
        except Exception as e:
            logger.error(f"[MODEL_CALL] Model {model} failed: {e}")
            return ModelResponse.error_response(
                error=str(e),
                model=model,
            )

    def _get_cli_install_hint(self, cli_command: str) -> str:
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

    async def _execute_cli_model(
        self,
        canonical_name: str,
        config: ModelConfig,
        messages: list[dict],
    ) -> ModelResponse:
        """Execute CLI model via subprocess.

        Args:
            canonical_name: Canonical model name
            config: Model configuration
            messages: List of message dicts

        Returns:
            ModelResponse with CLI output
        """
        # Check if CLI command exists
        if not shutil.which(config.cli_command):
            install_hint = self._get_cli_install_hint(config.cli_command)
            error_msg = f"CLI command '{config.cli_command}' not found in PATH. {install_hint}"
            logger.error(f"[CLI_CALL] {error_msg}")
            return ModelResponse.error_response(
                error=error_msg,
                model=canonical_name,
            )

        # Extract prompt from messages (use last user message)
        prompt = messages[-1]["content"] if messages else ""

        # Build command
        command = [config.cli_command] + config.cli_args

        # Prepare environment
        env = os.environ.copy()
        for key, value in config.cli_env.items():
            env[key] = os.path.expandvars(value)  # Expand ${VAR}

        # Use config timeout or fall back to settings
        timeout = settings.model_timeout_seconds

        logger.info(f"[CLI_CALL] model={canonical_name} command={config.cli_command} parser={config.cli_parser}")
        logger.debug(f"[CLI_CALL] full_command={' '.join(command)}")

        start_time = time.perf_counter()

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
                error_preview = stderr[:500] if stderr else "(no stderr)"
                install_hint = self._get_cli_install_hint(config.cli_command)
                logger.error(f"[CLI_CALL] {canonical_name} failed with exit code {process.returncode}")
                logger.debug(f"[CLI_CALL] stderr: {stderr[:1000]}")
                return ModelResponse.error_response(
                    error=f"CLI '{config.cli_command}' failed with exit code {process.returncode}. "
                    f"Error: {error_preview}\n\n"
                    f"Troubleshooting: {install_hint}",
                    model=canonical_name,
                )

            # Parse output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            content = self._parse_cli_output(stdout, config.cli_parser)

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

        except asyncio.TimeoutError:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"[CLI_CALL] {canonical_name} timed out after {timeout}s")
            return ModelResponse.error_response(
                error=f"CLI '{config.cli_command}' timed out after {timeout}s. "
                f"The command took longer than expected. "
                f"Consider using a faster model or increasing MODEL_TIMEOUT_SECONDS in config.",
                model=canonical_name,
            )

        except FileNotFoundError as e:
            # This shouldn't happen due to shutil.which() check, but handle it anyway
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            install_hint = self._get_cli_install_hint(config.cli_command)
            logger.error(f"[CLI_CALL] {canonical_name} command not found: {e}")
            return ModelResponse.error_response(
                error=f"CLI command '{config.cli_command}' not found. {install_hint}",
                model=canonical_name,
            )

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"[CLI_CALL] {canonical_name} failed with exception: {type(e).__name__}: {e}")
            logger.debug(f"[CLI_CALL] Full error details", exc_info=True)
            return ModelResponse.error_response(
                error=f"CLI execution failed: {type(e).__name__}: {str(e)}",
                model=canonical_name,
            )

    def _parse_cli_output(self, stdout: str, parser_type: str) -> str:
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
                # Extract 'response' field if present (Gemini CLI format)
                if isinstance(parsed, dict) and "response" in parsed:
                    return parsed["response"]
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


litellm_client = LiteLLMClient()
