"""Model configuration loader with YAML support and LiteLLM fallback."""

import logging
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, Final

import litellm
import yaml
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


# =============================================================================
# Provider Configuration
# =============================================================================


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


# =============================================================================
# Path Helpers
# =============================================================================


def get_package_config_path() -> Any:
    """Get path to bundled package config (safe for wheels/zips).

    Returns a Traversable that can be used with as_file() context manager.
    """
    return files("multi_mcp.config").joinpath("config.yaml")


def get_user_config_path() -> Path:
    """Get path to user config (~/.multi_mcp/config.yaml)."""
    return Path.home() / ".multi_mcp" / "config.yaml"


def get_user_config_dir() -> Path:
    """Get path to user config directory (~/.multi_mcp/)."""
    return Path.home() / ".multi_mcp"


# =============================================================================
# Model Configuration Schema
# =============================================================================


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
    """Model definitions loaded from config.yaml.

    Runtime defaults are in Settings class (multi_mcp/settings.py).
    """

    version: str
    models: dict[str, ModelConfig] = Field(default_factory=dict)

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


# =============================================================================
# Merge Strategy (Semantic)
# =============================================================================


def semantic_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Semantic merge: override values take precedence.

    - models: merge by model name (key-level merge)
    - aliases: user aliases override package aliases (user can "steal" an alias)
    - other keys: replaced entirely
    """
    result = base.copy()

    # Merge models by name (key-level merge)
    if "models" in override:
        result.setdefault("models", {})

        # Collect all aliases from user config (these take precedence)
        user_aliases: set[str] = set()
        for model_val in override["models"].values():
            if "aliases" in model_val:
                user_aliases.update(a.lower() for a in model_val["aliases"])

        # Remove conflicting aliases from base models (that aren't being overridden)
        # This allows user to "steal" an alias from a package model
        for model_name in result["models"]:
            if model_name not in override["models"]:
                model_config = result["models"][model_name]
                if "aliases" in model_config:
                    model_config["aliases"] = [a for a in model_config["aliases"] if a.lower() not in user_aliases]

        # Merge models
        for model_name, model_val in override["models"].items():
            if model_name in result["models"]:
                # Merge model config fields
                merged_model = result["models"][model_name].copy()
                merged_model.update(model_val)
                result["models"][model_name] = merged_model
            else:
                # Add new model
                result["models"][model_name] = model_val

    # Other keys: replace entirely
    for key, value in override.items():
        if key != "models":
            result[key] = value

    return result


# =============================================================================
# Configuration Loading
# =============================================================================


def load_package_config() -> dict[str, Any]:
    """Load package config using importlib.resources (safe for wheels)."""
    pkg_file = get_package_config_path()
    with as_file(pkg_file) as path:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)


def load_user_config() -> dict[str, Any] | None:
    """Load user config if it exists. Returns None if not found."""
    user_config = get_user_config_path()
    if not user_config.exists():
        return None

    try:
        with open(user_config, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        error_msg = f"""
Configuration Error: Invalid YAML in user config

File: {user_config}
Error: {e}

To fix:
1. Validate YAML syntax: python -c "import yaml; yaml.safe_load(open('{user_config}'))"
2. Or delete the file to use package defaults: rm {user_config}
3. Restart the server

For help, see: https://github.com/religa/multi_mcp
"""
        logger.error(error_msg)
        raise ValueError(error_msg) from e


def load_models_config(config_path: Path | None = None) -> ModelsConfiguration:
    """Load models configuration from YAML files.

    Loads package defaults and merges with user overrides if present.

    Args:
        config_path: Optional explicit path to config file (for testing).
                     If provided, loads only from this path (no merge).

    Returns:
        Validated ModelsConfiguration

    Raises:
        FileNotFoundError: If package config is missing
        ValueError: If config validation fails
    """
    # If explicit path provided, load only from that path (for testing)
    if config_path is not None:
        if not config_path.exists():
            raise FileNotFoundError(f"Model config not found: {config_path}")
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return ModelsConfiguration(**data)

    # Load package config (required)
    config_data = load_package_config()

    # Merge user config if exists (optional)
    user_data = load_user_config()
    if user_data:
        config_data = semantic_merge(config_data, user_data)

    # Validate and return
    try:
        return ModelsConfiguration(**config_data)
    except Exception as e:
        user_config = get_user_config_path()
        error_msg = f"""
Configuration Error: Validation failed

{e}

To fix:
1. Check {user_config} for invalid settings (if it exists)
2. Ensure model aliases are unique
3. Or delete user config: rm {user_config}

For help, see: https://github.com/religa/multi_mcp
"""
        logger.error(error_msg)
        raise ValueError(error_msg) from e


_config: ModelsConfiguration | None = None


def get_models_config() -> ModelsConfiguration:
    """Get cached models configuration (loaded once at startup)."""
    global _config
    if _config is None:
        _config = load_models_config()
    return _config


def reload_models_config() -> ModelsConfiguration:
    """Force reload of models configuration (clears cache)."""
    global _config
    _config = load_models_config()
    return _config
