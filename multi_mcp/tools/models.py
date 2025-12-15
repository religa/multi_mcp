"""Models tool implementation using config."""

import logging

from multi_mcp.models.resolver import ModelResolver
from multi_mcp.settings import settings
from multi_mcp.utils.llm_runner import validate_model_credentials

logger = logging.getLogger(__name__)


async def models_impl() -> dict:
    """Return models from configuration with credential validation.

    Returns:
        Dict with models list (including credential status), default_model, and count.
        Each model dict includes credential_status ("valid"/"invalid"/"unknown") for API models.
    """
    resolver = ModelResolver()
    models = resolver.list_models(include_disabled=False)

    # Always validate credentials (instant, free) using global singleton
    for model in models:
        # Skip CLI models entirely (use .get to avoid KeyError if 'provider' missing)
        if model.get("provider") != "cli":
            litellm_model = model.get("litellm_model")
            if litellm_model:
                # Use public method for credential validation (no API call)
                try:
                    error = validate_model_credentials(litellm_model)
                    model["credential_status"] = "valid" if not error else "invalid"
                    if error:
                        model["credential_error"] = error
                except Exception as e:
                    # Handle unexpected validation errors gracefully
                    model_name = model.get("name", "unknown_model")
                    logger.warning(f"[MODELS] Failed to validate credentials for {model_name}: {type(e).__name__}")
                    model["credential_status"] = "unknown"
                    model["credential_error"] = f"Validation error: {type(e).__name__}"
            else:
                # API model without litellm_model is misconfigured
                model["credential_status"] = "unknown"
                model["credential_error"] = "Model configuration missing litellm_model"

    logger.info(f"[MODELS] Returning {len(models)} available models")

    return {
        "models": models,
        "default_model": settings.default_model,
        "count": len(models),
    }
