"""LiteLLM client wrapper with config-based model resolution."""

import asyncio
import logging
import time
from typing import Any

import litellm

from multi_mcp.constants import DEFAULT_MAX_TOKENS
from multi_mcp.models.config import PROVIDERS, ModelConfig
from multi_mcp.models.resolver import ModelResolver
from multi_mcp.schemas.base import ModelResponse, ModelResponseMetadata
from multi_mcp.settings import settings
from multi_mcp.utils.request_logger import log_llm_interaction

logger = logging.getLogger(__name__)

litellm.drop_params = True


def _extract_content_from_responses_api(response) -> str:
    """Extract text from responses API output array.

    Handles both OpenAI/Azure ([reasoning/web_search_call, message]) and Anthropic/Gemini ([message]).
    Supports both object and dict formats (LiteLLM's responses API can return either depending on provider).
    """
    # Check if response has output array
    if not hasattr(response, "output") or not response.output:
        logger.warning("[RESPONSE_PARSE] Response has no output or empty output array")
        return ""

    for item in response.output:
        # LiteLLM's responses API can return items as dicts or objects depending on provider/version
        # Handle both formats for 'type' and 'content' extraction
        item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)

        if item_type == "message":
            # Extract content (supports both dict and object formats)
            content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)

            # Handle None content
            if content is None:
                logger.debug("[RESPONSE_PARSE] Message item has None content, skipping")
                continue

            # Handle content as list of text items
            if isinstance(content, list):
                return "".join(c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "") for c in content if c)
            # Handle content as string (fallback)
            elif isinstance(content, str):
                return content
            else:
                # Unexpected content type
                logger.debug(f"[RESPONSE_PARSE] Unexpected content type '{type(content).__name__}' in message item")

    # No message item found in output
    logger.warning("[RESPONSE_PARSE] No message item found in response.output, returning empty string")
    return ""


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

    def _validate_provider_credentials(self, litellm_model: str) -> str | None:
        """Validate that required provider credentials are configured.

        Args:
            litellm_model: LiteLLM model string (e.g., "azure/gpt-5-mini", "gemini/gemini-2.5-flash")

        Returns:
            Error message if credentials missing, None if valid
        """
        # Extract provider from litellm_model (format: "provider/model-name")
        provider = litellm_model.split("/")[0].lower() if "/" in litellm_model else None
        if not provider:
            return None

        provider_config = PROVIDERS.get(provider)
        if not provider_config:
            return None

        missing = []
        present = []

        for attr, env_var in provider_config.credentials:
            if not getattr(settings, attr, None):
                missing.append(env_var)
            else:
                present.append(env_var)

        if not missing:
            return None

        msg = f"{provider_config.name} models require {' and '.join(missing)} to be set in environment or .env file"
        if present:
            msg += f" (already set: {', '.join(present)})"
        return msg

    def validate_model_credentials(self, litellm_model: str) -> str | None:
        """Public wrapper for credential validation (safe to call from other modules).

        Args:
            litellm_model: LiteLLM model string (e.g., "azure/gpt-5-mini", "gemini/gemini-2.5-flash")

        Returns:
            Error message if credentials missing, None if valid
        """
        return self._validate_provider_credentials(litellm_model)

    async def execute(
        self,
        canonical_name: str,
        model_config: ModelConfig,
        messages: list[dict],
        enable_web_search: bool = False,
    ) -> ModelResponse:
        """Execute LiteLLM API call (API models only).

        Args:
            canonical_name: Canonical model name (pre-resolved)
            model_config: Model configuration (pre-resolved)
            messages: List of message dicts with role and content
            enable_web_search: Enable provider-native web search if supported

        Returns:
            ModelResponse with status, content, metadata, error

        Note:
            Model should already be resolved by the caller.
            CLI models should be routed through CLIExecutor.
        """
        try:
            # Reject CLI models - they should be routed elsewhere
            if model_config.is_cli_model():
                error_msg = f"Model '{canonical_name}' is a CLI model. Use CLIExecutor for CLI models."
                logger.error(f"[MODEL_CALL] {error_msg}")
                return ModelResponse.error_response(
                    error=error_msg,
                    model=canonical_name,
                )

            # API model execution (existing logic)
            timeout = settings.model_timeout_seconds
            litellm_model = model_config.litellm_model

            # Validate we have a litellm_model for API calls
            if not litellm_model:
                error_msg = f"Model '{canonical_name}' has no litellm_model configured"
                logger.error(f"[MODEL_CALL] {error_msg}")
                return ModelResponse.error_response(
                    error=error_msg,
                    model=canonical_name,
                )

            # Validate provider credentials before making API call
            credential_error = self._validate_provider_credentials(litellm_model)
            if credential_error:
                logger.error(f"[MODEL_CALL] Credential validation failed for {litellm_model}: {credential_error}")
                return ModelResponse.error_response(
                    error=credential_error,
                    model=canonical_name,
                )

            # Apply temperature (config constraint > default)
            temp = settings.default_temperature
            if model_config.constraints and model_config.constraints.temperature is not None:
                temp = model_config.constraints.temperature

            logger.info(f"[MODEL_CALL] canonical={canonical_name} litellm={litellm_model} temp={temp}")

            # Build kwargs starting with generic params from config
            kwargs: dict[str, Any] = {
                **model_config.params,
                "model": litellm_model,
                "input": messages,
                "temperature": temp,
                "num_retries": settings.max_retries,
                "timeout": timeout,
            }

            # Set max_tokens: config value > sensible default
            max_tokens = model_config.max_tokens if model_config.max_tokens is not None else DEFAULT_MAX_TOKENS
            kwargs["max_tokens"] = max_tokens
            logger.debug(f"[MODEL_CALL] Using max_tokens={max_tokens} ({'config' if model_config.max_tokens else 'default'})")

            # Enable provider-native web search if requested and supported
            if enable_web_search and model_config.has_provider_web_search():
                kwargs["tools"] = [{"type": "web_search"}]
                logger.info(f"[WEB_SEARCH] Enabled for model: {canonical_name}")

            logger.debug(f"[MODEL_REQUEST] litellm_model={litellm_model} num_messages={len(messages)}")

            # Call LiteLLM with timeout protection
            start_time = time.perf_counter()
            response = await asyncio.wait_for(
                litellm.aresponses(**kwargs),
                timeout=timeout,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            content = _extract_content_from_responses_api(response)

            # Extract usage stats (responses API only provides total_tokens)
            total_tokens = 0
            if hasattr(response, "usage") and response.usage:  # type: ignore[attr-defined]
                total_tokens = getattr(response.usage, "total_tokens", 0)  # type: ignore[attr-defined]

            metadata = ModelResponseMetadata(
                model=canonical_name,
                prompt_tokens=0,  # Not available in responses API
                completion_tokens=0,  # Not available in responses API
                total_tokens=total_tokens,
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
            logger.error(f"[MODEL_CALL] Model {canonical_name} timed out after {timeout}s")
            return ModelResponse.error_response(
                error=f"Request timed out after {timeout}s",
                model=canonical_name,
            )
        except Exception as e:
            logger.error(f"[MODEL_CALL] Model {canonical_name} failed: {e}")
            return ModelResponse.error_response(
                error=str(e),
                model=canonical_name,
            )
