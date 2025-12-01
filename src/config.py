"""
Configuration management using Pydantic Settings.
Loads from environment variables and .env file.
"""

import json
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


class CustomEnvSettingsSource(EnvSettingsSource):
    """Custom environment settings source that handles comma-separated lists."""

    def prepare_field_value(self, field_name: str, field: Any, value: Any, value_is_complex: bool) -> Any:
        """Override to handle DEFAULT_MODEL_LIST as comma-separated."""
        if field_name == "default_model_list" and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CustomDotEnvSettingsSource(DotEnvSettingsSource):
    """Custom .env file settings source that handles comma-separated lists."""

    def prepare_field_value(self, field_name: str, field: Any, value: Any, value_is_complex: bool) -> Any:
        """Override to handle DEFAULT_MODEL_LIST as comma-separated."""
        if field_name == "default_model_list" and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys for providers (LiteLLM handles routing)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")

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
        # Replace the default sources with our custom ones that handle comma-separated lists
        return (
            init_settings,
            CustomEnvSettingsSource(settings_cls),
            CustomDotEnvSettingsSource(settings_cls, env_file=".env", env_file_encoding="utf-8"),
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
        default=180.0, alias="MODEL_TIMEOUT_SECONDS", description="Timeout in seconds for individual model calls"
    )

    # File processing limits
    max_files_per_review: int = Field(
        default=100, alias="MAX_FILES_PER_REVIEW", description="Maximum number of files to include in a single code review"
    )
    max_file_size_kb: int = Field(default=50, alias="MAX_FILE_SIZE_KB", description="Maximum file size in KB for reading and processing")

    # Artifact logging
    artifacts_dir: str = Field(
        default="",
        alias="ARTIFACTS_DIR",
        description="Directory for artifact logging (relative to base_path). Empty = disabled.",
    )


# Global settings instance
settings = Settings()
