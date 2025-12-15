"""Model alias resolution with LiteLLM fallback."""

import logging
from typing import Any

import litellm

from multi_mcp.models.config import ModelConfig, ModelsConfiguration, get_models_config
from multi_mcp.settings import settings

logger = logging.getLogger(__name__)


class ModelResolver:
    """Resolves model names/aliases to LiteLLM model strings.

    Resolution order:
    1. Primary models in config (exact match)
    2. Aliases in config
    3. LiteLLM model database (passthrough)
    """

    def __init__(self, config: ModelsConfiguration | None = None):
        self.config = config or get_models_config()
        self._build_alias_map()

    def _build_alias_map(self) -> None:
        self.alias_map: dict[str, str] = {}

        for name, model in self.config.models.items():
            self.alias_map[name.lower()] = name
            for alias in model.aliases:
                self.alias_map[alias.lower()] = name

    def resolve(self, name_or_alias: str) -> tuple[str, ModelConfig]:
        """Resolve alias to (canonical_name, config).

        Resolution order:
        1. Primary models in config (exact match)
        2. Aliases in config
        3. LiteLLM model database (passthrough with auto-generated config)

        Args:
            name_or_alias: Model name or alias (case-insensitive)

        Returns:
            Tuple of (canonical_name, ModelConfig)

        Raises:
            ValueError: If model name is empty/invalid or model is disabled
        """
        # Validate input to avoid generating misleading fallback configs
        if not isinstance(name_or_alias, str) or not name_or_alias.strip():
            raise ValueError("Model name or alias must be a non-empty string")

        name_lower = name_or_alias.strip().lower()

        # Step 1 & 2: Check config (primary names and aliases)
        canonical = self.alias_map.get(name_lower)

        if canonical is not None:
            model_config = self.config.models[canonical]
            if model_config.disabled:
                raise ValueError(f"Model '{canonical}' is disabled")
            return canonical, model_config

        # Step 3: Fallback to LiteLLM database
        logger.info(f"[RESOLVER] Model '{name_or_alias}' not in config, using LiteLLM passthrough")
        return self._create_litellm_fallback(name_or_alias)

    def _find_in_litellm_db(self, model_name: str) -> str | None:
        """Find model in LiteLLM database, trying with/without prefixes.

        Args:
            model_name: Model identifier to look up

        Returns:
            LiteLLM model string if found, None otherwise
        """
        if model_name in litellm.model_cost:
            return model_name

        # Try removing prefix (e.g., "openai/gpt-5-mini" → "gpt-5-mini")
        if "/" in model_name:
            unprefixed = model_name.split("/", 1)[1]
            if unprefixed in litellm.model_cost:
                return unprefixed

        for prefix in ["openai/", "anthropic/", "gemini/", "azure/", "openrouter/"]:
            candidate = f"{prefix}{model_name}"
            if candidate in litellm.model_cost:
                return candidate

        return None

    def _create_litellm_fallback(self, model_name: str) -> tuple[str, ModelConfig]:
        """Create ModelConfig from LiteLLM model database.

        Args:
            model_name: The model name to look up in LiteLLM

        Returns:
            Tuple of (canonical_name, auto-generated ModelConfig)
        """
        # Find the best LiteLLM model identifier (prefer prefixed when available)
        litellm_model = self._find_in_litellm_db(model_name) or model_name
        if litellm_model != model_name:
            logger.debug(f"[RESOLVER] Using prefixed model '{litellm_model}' for '{model_name}'")

        model_info = self._get_litellm_model_info(litellm_model)

        config = ModelConfig(
            litellm_model=litellm_model,
            aliases=[],
            context_window=model_info.get("context_window"),
            max_tokens=model_info.get("max_tokens"),
            notes="Auto-generated from LiteLLM database",
        )

        return model_name, config

    def _get_litellm_model_info(self, model_name: str) -> dict[str, Any]:
        """Fetch model metadata from LiteLLM's model database.

        Args:
            model_name: Model identifier

        Returns:
            Dict with context_window, max_tokens if available
        """
        try:
            found_model = self._find_in_litellm_db(model_name)
            if found_model:
                info = litellm.model_cost[found_model]
                return {
                    "context_window": info.get("max_input_tokens"),
                    "max_tokens": info.get("max_output_tokens"),
                }
        except Exception:
            logger.warning(f"[RESOLVER] Failed to get LiteLLM model info for '{model_name}'", exc_info=True)

        return {}

    def get_litellm_model(self, name_or_alias: str) -> str | None:
        """Get the LiteLLM model string for a name/alias.

        Returns None for CLI models that don't use LiteLLM.
        """
        _, config = self.resolve(name_or_alias)
        return config.litellm_model

    def get_default(self) -> str:
        """Get the default model from Settings.

        Returns:
            Default model name from settings
        """
        return settings.default_model

    def list_models(self, include_disabled: bool = False) -> list[dict]:
        """List all models with their metadata."""
        result = []
        for name, config in self.config.models.items():
            if config.disabled and not include_disabled:
                continue

            # Fill missing metadata from LiteLLM if not in config
            context_window = config.context_window
            max_tokens = config.max_tokens

            # Only try to fetch LiteLLM info for API models (not CLI models)
            if (context_window is None or max_tokens is None) and config.litellm_model:
                litellm_info = self._get_litellm_model_info(config.litellm_model)
                if context_window is None:
                    context_window = litellm_info.get("context_window")
                if max_tokens is None:
                    max_tokens = litellm_info.get("max_tokens")

            result.append(
                {
                    "name": name,
                    "aliases": config.aliases,
                    "provider": config.get_provider(),
                    "litellm_model": config.litellm_model,
                    "context_window": context_window,
                    "max_tokens": max_tokens,
                    "disabled": config.disabled,
                    "notes": config.notes,
                }
            )
        return result
