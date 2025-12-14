"""
Configuration management using Pydantic Settings.
Loads from environment variables and .env file.
"""

import json
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

load_dotenv()


class CustomEnvSettingsSource(EnvSettingsSource):
    """Custom environment settings source that handles comma-separated lists."""

    def prepare_field_value(self, field_name: str, field: Any, value: Any, value_is_complex: bool) -> Any:
        """Override to handle DEFAULT_MODEL_LIST as comma-separated."""
        if field_name == "default_model_list" and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys for providers (LiteLLM handles routing)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")

    # Azure OpenAI (optional - LiteLLM picks these up from os.environ)
    # Note: These are the exact variable names LiteLLM expects
    azure_api_key: str | None = Field(default=None, alias="AZURE_API_KEY")
    azure_api_base: str | None = Field(default=None, alias="AZURE_API_BASE")
    azure_api_version: str = Field(default="2025-04-01-preview", alias="AZURE_API_VERSION")

    # AWS Bedrock (optional - LiteLLM picks these up from os.environ)
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region_name: str | None = Field(default=None, alias="AWS_REGION_NAME")

    # Model defaults
    default_model: str = Field(default="gpt-5-mini", alias="DEFAULT_MODEL")
    default_model_list: list[str] = Field(
        default=["gpt-5-mini", "gemini-2.5-flash"],
        alias="DEFAULT_MODEL_LIST",
        description="Default models for multi-model compare (minimum 2)",
    )
    default_temperature: float = Field(default=0.2, alias="DEFAULT_TEMPERATURE")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to use our custom sources."""
        return (
            init_settings,
            CustomEnvSettingsSource(settings_cls),  # Reads from os.environ (populated by load_dotenv)
            file_secret_settings,
        )

    @model_validator(mode="before")
    @classmethod
    def parse_model_list_from_env(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Parse DEFAULT_MODEL_LIST from JSON array or comma-separated string."""
        # Check both the field name and alias
        for key in ["default_model_list", "DEFAULT_MODEL_LIST"]:
            if key in data and isinstance(data[key], str):
                value = data[key].strip()

                # Try JSON parsing first (for array format like '["mini","flash"]')
                if value.startswith("[") and value.endswith("]"):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            data[key] = parsed
                            continue
                    except json.JSONDecodeError:
                        pass  # Fall through to comma-separated parsing

                # Parse as comma-separated string
                models = [model.strip() for model in value.split(",") if model.strip()]
                # Update the data dict with parsed list (or default if empty)
                data[key] = models if models else ["gpt-5-mini", "gemini-2.5-flash"]
        return data

    # Server settings
    server_name: str = Field(default="Multi")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Retry and timeout configuration
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    model_timeout_seconds: float = Field(
        default=300.0, alias="MODEL_TIMEOUT_SECONDS", description="Timeout in seconds for individual model calls"
    )

    # File processing limits
    max_files_per_review: int = Field(
        default=100, alias="MAX_FILES_PER_REVIEW", description="Maximum number of files to include in a single code review"
    )
    max_file_size_kb: int = Field(default=50, alias="MAX_FILE_SIZE_KB", description="Maximum file size in KB for reading and processing")

    # Code review response size limits
    max_codereview_response_size: int = Field(
        default=60000,
        alias="MAX_CODEREVIEW_RESPONSE_SIZE",
        description="Maximum response size in bytes before consolidation (make another LLM call to consolidate results). Set high (e.g., 999999) to disable consolidation.",
    )

    # Artifact logging
    artifacts_dir: str = Field(
        default="",
        alias="ARTIFACTS_DIR",
        description="Directory for artifact logging (relative to base_path or absolute). Empty = disabled.",
    )

    @model_validator(mode="after")
    def set_provider_env_vars(self) -> "Settings":
        """Set provider environment variables so LiteLLM can pick them up.

        LiteLLM reads provider config directly from os.environ, so we need to
        ensure our settings (including defaults) are available there.
        """
        import os

        from multi_mcp.models.config import PROVIDERS

        # Set all provider credentials from PROVIDERS configuration
        for provider_config in PROVIDERS.values():
            for settings_attr, env_var in provider_config.credentials:
                value = getattr(self, settings_attr, None)
                if value and not os.getenv(env_var):
                    os.environ[env_var] = value

        # Set Azure API version (config parameter, not a credential)
        if self.azure_api_version and not os.getenv("AZURE_API_VERSION"):
            os.environ["AZURE_API_VERSION"] = self.azure_api_version

        return self


# Global settings instance
settings = Settings()
