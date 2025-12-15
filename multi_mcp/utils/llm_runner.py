"""Shared parallel model execution utility."""

import asyncio
import logging

from multi_mcp.constants import DEFAULT_MAX_CONCURRENCY
from multi_mcp.models.cli_executor import CLIExecutor
from multi_mcp.models.config import ModelConfig
from multi_mcp.models.litellm_client import LiteLLMClient
from multi_mcp.models.resolver import ModelResolver
from multi_mcp.schemas.base import ModelResponse

logger = logging.getLogger(__name__)

# Module-level private instances for routing
_resolver = ModelResolver()
_cli_executor = CLIExecutor()
_litellm_client = LiteLLMClient()


def validate_model_credentials(litellm_model: str) -> str | None:
    """Validate provider credentials for an API model.

    Args:
        litellm_model: LiteLLM model string (e.g., "openai/gpt-5-mini")

    Returns:
        Error message if credentials missing, None if valid
    """
    return _litellm_client.validate_model_credentials(litellm_model)


async def _route_model_execution(
    canonical_name: str,
    model_config: ModelConfig,
    messages: list[dict],
    enable_web_search: bool = False,
) -> ModelResponse:
    """Route model execution to appropriate executor (CLI or API).

    Args:
        canonical_name: Resolved canonical model name
        model_config: Model configuration object
        messages: List of message dicts
        enable_web_search: Enable provider-native web search if supported (API only)

    Returns:
        ModelResponse from the appropriate executor
    """
    if model_config.is_cli_model():
        logger.debug(f"[LLM_RUNNER] Routing {canonical_name} to CLI executor")
        return await _cli_executor.execute(
            canonical_name=canonical_name,
            model_config=model_config,
            messages=messages,
            enable_web_search=enable_web_search,
        )
    else:
        logger.debug(f"[LLM_RUNNER] Routing {canonical_name} to API client")
        return await _litellm_client.execute(
            canonical_name=canonical_name,
            model_config=model_config,
            messages=messages,
            enable_web_search=enable_web_search,
        )


async def execute_single(
    model: str,
    messages: list[dict],
    enable_web_search: bool = False,
) -> ModelResponse:
    """Execute single-model LLM call with automatic artifact saving.

    Routes to appropriate executor based on model type (API vs CLI).

    Args:
        model: Model name to use
        messages: Pre-built messages array
        enable_web_search: Enable provider-native web search if supported (API only)

    Returns:
        ModelResponse with artifacts in metadata if saving succeeded
    """
    from multi_mcp.utils.artifacts import save_tool_artifacts

    # Resolve model and route to appropriate executor
    canonical_name, model_config = _resolver.resolve(model)

    response = await _route_model_execution(
        canonical_name=canonical_name,
        model_config=model_config,
        messages=messages,
        enable_web_search=enable_web_search,
    )

    if response.status == "success":
        artifact_paths = await save_tool_artifacts(response=response)

        if artifact_paths:
            response.metadata.artifacts = artifact_paths

    return response


async def execute_parallel(
    models: list[str],
    messages: list[dict],
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    enable_web_search: bool = False,
) -> list[ModelResponse]:
    """
    Execute messages against multiple models in parallel.

    Args:
        models: List of model names
        messages: Pre-built messages array (same for all models)
        max_concurrency: Max concurrent calls (default: 5)
        enable_web_search: Enable provider-native web search if supported

    Note:
        All artifact metadata (workflow, name, step_number, thread_id, base_path)
        is automatically retrieved from request context.

    Returns:
        list[ModelResponse]: One response per model (includes errors/timeouts)
    """
    # Use Semaphore for concurrency control (throttles instead of rejecting)
    sem = asyncio.Semaphore(max_concurrency)

    logger.info(f"[LLM_RUNNER] Executing {len(models)} models in parallel (max_concurrency: {max_concurrency})")

    async def _bounded_call(model_name: str) -> ModelResponse:
        async with sem:
            # Resolve model and route to appropriate executor
            canonical_name, model_config = _resolver.resolve(model_name)

            response = await _route_model_execution(
                canonical_name=canonical_name,
                model_config=model_config,
                messages=messages,
                enable_web_search=enable_web_search,
            )

            if response.status == "success":
                from multi_mcp.utils.artifacts import save_tool_artifacts

                artifact_paths = await save_tool_artifacts(response=response)

                if artifact_paths:
                    response.metadata.artifacts = artifact_paths

            return response

    # Run all models in parallel (throttled by semaphore)
    tasks = [_bounded_call(model) for model in models]

    results: list[ModelResponse] = await asyncio.gather(*tasks)

    successes = sum(1 for r in results if r.status == "success")
    logger.info(f"[LLM_RUNNER] Complete: {successes}/{len(results)} models succeeded")

    return results
