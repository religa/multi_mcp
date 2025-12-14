"""Model configuration loader with YAML support and LiteLLM fallback."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import litellm
import yaml
from pydantic import BaseModel, Field, model_validator

from multi_mcp.utils.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a single provider's credential requirements."""

    name: str  # Human-readable provider name (e.g., "Azure OpenAI")
    credentials: tuple[tuple[str, str], ...]  # Tuple of (settings_attr, env_var_name) tuples

    def __post_init__(self) -> None:
        """Validate credentials configuration.

        Raises:
            ValueError: If credentials are invalid
        """
        if not self.credentials:
            raise ValueError(f"ProviderConfig '{self.name}' must have at least one credential")

        for i, cred in enumerate(self.credentials):
            if not isinstance(cred, tuple) or len(cred) != 2:
                raise ValueError(f"ProviderConfig '{self.name}' credential {i} must be a 2-tuple, got {type(cred).__name__}")

            settings_attr, env_var = cred
            if not isinstance(settings_attr, str) or not settings_attr:
                raise ValueError(f"ProviderConfig '{self.name}' credential {i} settings_attr must be non-empty string")
            if not isinstance(env_var, str) or not env_var:
                raise ValueError(f"ProviderConfig '{self.name}' credential {i} env_var must be non-empty string")


# Provider configurations
# Maps provider ID to ProviderConfig
#
# To add a new provider:
# 1. Add entry here with name and required credentials
# 2. Add corresponding fields to Settings in multi_mcp/config.py
PROVIDERS: Final[dict[str, ProviderConfig]] = {
    "azure": ProviderConfig(
        name="Azure OpenAI",
        credentials=(("azure_api_key", "AZURE_API_KEY"), ("azure_api_base", "AZURE_API_BASE")),
    ),
    "bedrock": ProviderConfig(
        name="AWS Bedrock",
        credentials=(
            ("aws_access_key_id", "AWS_ACCESS_KEY_ID"),
            ("aws_secret_access_key", "AWS_SECRET_ACCESS_KEY"),
            ("aws_region_name", "AWS_REGION_NAME"),
        ),
    ),
    "gemini": ProviderConfig(
        name="Google Gemini",
        credentials=(("gemini_api_key", "GEMINI_API_KEY"),),
    ),
    "anthropic": ProviderConfig(
        name="Anthropic Claude",
        credentials=(("anthropic_api_key", "ANTHROPIC_API_KEY"),),
    ),
    "openrouter": ProviderConfig(
        name="OpenRouter",
        credentials=(("openrouter_api_key", "OPENROUTER_API_KEY"),),
    ),
    "openai": ProviderConfig(
        name="OpenAI",
        credentials=(("openai_api_key", "OPENAI_API_KEY"),),
    ),
}


class ModelConstraints(BaseModel):
    """Temperature and other model constraints."""

    temperature: float | None = None


class ModelConfig(BaseModel):
    """Configuration for a single model (API or CLI)."""

    provider: str | None = None  # Optional - derived from litellm_model if not set
    litellm_model: str | None = None  # Required for API models, None for CLI models
    aliases: list[str] = Field(default_factory=list)
    context_window: int | None = None
    max_tokens: int | None = None
    constraints: ModelConstraints | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    disabled: bool = False
    notes: str = ""

    # CLI-specific fields (only used when provider="cli")
    cli_command: str | None = None
    cli_args: list[str] = Field(default_factory=list)
    cli_env: dict[str, str] = Field(default_factory=dict)
    cli_parser: str = "json"  # "json", "jsonl", or "text"

    # Web search support
    provider_web_search: bool = Field(default=False, description="Whether this model supports provider-native web search via LiteLLM")

    def is_cli_model(self) -> bool:
        """Check if this is a CLI model."""
        return self.provider == "cli"

    def has_provider_web_search(self) -> bool:
        """Check if model supports provider-native web search."""
        return self.provider_web_search is True

    def get_provider(self) -> str:
        """Get provider (explicit > prefix > litellm lookup > unknown)."""
        if self.provider:
            return self.provider
        # Derive from prefix: "gemini/gemini-2.5-pro" → "gemini"
        if self.litellm_model and "/" in self.litellm_model:
            return self.litellm_model.split("/")[0]
        # Check litellm.model_cost for litellm_provider
        if self.litellm_model and self.litellm_model in litellm.model_cost:
            return litellm.model_cost[self.litellm_model].get("litellm_provider", "unknown")
        return "unknown"


class ModelsConfiguration(BaseModel):
    """Root configuration schema."""

    version: str
    default_model: str
    models: dict[str, ModelConfig]

    @model_validator(mode="after")
    def validate_aliases_unique(self) -> "ModelsConfiguration":
        """Ensure no alias collisions (case-insensitive)."""
        seen: dict[str, str] = {}

        for name, config in self.models.items():
            name_lower = name.lower()
            if name_lower in seen:
                raise ValueError(f"Model name '{name}' collides with '{seen[name_lower]}'")
            seen[name_lower] = name

            for alias in config.aliases:
                alias_lower = alias.lower()
                if alias_lower in seen:
                    raise ValueError(f"Alias '{alias}' (model '{name}') collides with '{seen[alias_lower]}'")
                seen[alias_lower] = name

        return self

    @model_validator(mode="after")
    def validate_default_resolves(self) -> "ModelsConfiguration":
        """Ensure default_model resolves to a valid model or alias."""
        if not self._resolves(self.default_model):
            raise ValueError(f"default_model '{self.default_model}' does not resolve to any model")
        return self

    def _resolves(self, name_or_alias: str) -> bool:
        """Check if a name/alias resolves to a model."""
        name_lower = name_or_alias.lower()

        for name in self.models:
            if name.lower() == name_lower:
                return True

        for config in self.models.values():
            if name_lower in [a.lower() for a in config.aliases]:
                return True

        return False


def load_models_config(config_path: Path | None = None) -> ModelsConfiguration:
    """Load models configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to config/models.yaml

    Returns:
        Validated ModelsConfiguration

    Raises:
        FileNotFoundError: If config file is missing (fail fast)
        ValueError: If config validation fails
    """
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "models.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Model config not found: {config_path}\nCreate config/models.yaml or set MODELS_CONFIG_PATH")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return ModelsConfiguration(**data)


_config: ModelsConfiguration | None = None


def get_models_config() -> ModelsConfiguration:
    """Get cached models configuration (loaded once at startup)."""
    global _config
    if _config is None:
        _config = load_models_config()
    return _config
