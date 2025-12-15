"""Unit tests for model configuration loading and validation."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from multi_mcp.models.config import (
    ModelConfig,
    ModelsConfiguration,
    get_models_config,
    load_models_config,
)


class TestModelConfig:
    """Tests for ModelConfig class."""

    def test_model_config_get_provider_from_explicit(self):
        """Test that explicit provider is used when set."""
        config = ModelConfig(litellm_model="openai/gpt-5-mini", provider="custom-provider")

        assert config.get_provider() == "custom-provider"

    def test_model_config_get_provider_from_prefix(self):
        """Test that provider is derived from litellm_model prefix."""
        config = ModelConfig(litellm_model="anthropic/claude-3-opus")

        assert config.get_provider() == "anthropic"

    def test_model_config_get_provider_from_prefix_gemini(self):
        """Test provider extraction for gemini prefix."""
        config = ModelConfig(litellm_model="gemini/gemini-2.5-pro")

        assert config.get_provider() == "gemini"

    @patch("multi_mcp.models.config.litellm")
    def test_model_config_get_provider_from_litellm_db(self, mock_litellm):
        """Test provider lookup from LiteLLM database."""
        mock_litellm.model_cost = {"test-model": {"litellm_provider": "test-provider"}}

        config = ModelConfig(litellm_model="test-model")
        provider = config.get_provider()

        assert provider == "test-provider"

    @patch("multi_mcp.models.config.litellm")
    def test_model_config_get_provider_unknown(self, mock_litellm):
        """Test that unknown models return 'unknown' provider."""
        mock_litellm.model_cost = {}

        config = ModelConfig(litellm_model="unknown-model")
        provider = config.get_provider()

        assert provider == "unknown"


class TestModelsConfiguration:
    """Tests for ModelsConfiguration validation."""

    def test_models_configuration_valid(self):
        """Test that valid configuration passes validation."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gpt-5-mini": ModelConfig(
                    litellm_model="openai/gpt-5-mini",
                    aliases=["mini"],
                ),
            },
        )

        assert config.version == "1.0"
        assert "gpt-5-mini" in config.models

    def test_models_configuration_unique_aliases_validation(self):
        """Test that duplicate aliases are rejected."""
        with pytest.raises(ValueError, match="collides"):
            ModelsConfiguration(
                version="1.0",
                models={
                    "model1": ModelConfig(
                        litellm_model="provider/model1",
                        aliases=["alias1"],
                    ),
                    "model2": ModelConfig(
                        litellm_model="provider/model2",
                        aliases=["alias1"],  # Duplicate alias
                    ),
                },
            )

    def test_models_configuration_duplicate_alias_case_insensitive(self):
        """Test that alias collision is case-insensitive."""
        with pytest.raises(ValueError, match="collides"):
            ModelsConfiguration(
                version="1.0",
                models={
                    "model1": ModelConfig(
                        litellm_model="provider/model1",
                        aliases=["Mini"],
                    ),
                    "model2": ModelConfig(
                        litellm_model="provider/model2",
                        aliases=["mini"],  # Case-insensitive collision
                    ),
                },
            )

    def test_models_configuration_duplicate_model_name_case_insensitive(self):
        """Test that model name collision is case-insensitive."""
        with pytest.raises(ValueError, match="collides"):
            ModelsConfiguration(
                version="1.0",
                models={
                    "gpt-mini": ModelConfig(litellm_model="provider/gpt-mini"),
                    "GPT-Mini": ModelConfig(litellm_model="provider/GPT-Mini"),
                },
            )


class TestLoadModelsConfig:
    """Tests for load_models_config function."""

    def test_load_models_config_success(self):
        """Test loading valid YAML configuration."""
        yaml_content = """
version: "1.0"

models:
  gpt-5-mini:
    litellm_model: openai/gpt-5-mini
    aliases:
      - mini
    context_window: 128000
    max_tokens: 16000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            config = load_models_config(config_path)

            assert config.version == "1.0"
            assert "gpt-5-mini" in config.models
            assert config.models["gpt-5-mini"].context_window == 128000
        finally:
            config_path.unlink()

    def test_load_models_config_missing_file_raises(self):
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Model config not found"):
            load_models_config(Path("/nonexistent/path/models.yaml"))

    def test_load_models_config_invalid_yaml_raises(self):
        """Test that invalid YAML raises error."""
        yaml_content = """
version: "1.0"
models:
  gpt-5-mini:
    litellm_model: openai/gpt-5-mini
    aliases: [mini
  # Invalid YAML - unclosed bracket
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            with pytest.raises(yaml.YAMLError):
                load_models_config(config_path)
        finally:
            config_path.unlink()

    def test_load_models_config_validation_error_raises(self):
        """Test that validation errors are raised (e.g., alias collision)."""
        yaml_content = """
version: "1.0"

models:
  gpt-5-mini:
    litellm_model: openai/gpt-5-mini
    aliases:
      - mini
  other-model:
    litellm_model: openai/other
    aliases:
      - mini
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="collides"):
                load_models_config(config_path)
        finally:
            config_path.unlink()


class TestGetModelsConfig:
    """Tests for get_models_config caching."""

    def test_get_models_config_caching(self):
        """Test that get_models_config caches the configuration."""
        # Reset cache
        import multi_mcp.models.config

        multi_mcp.models.config._config = None

        with patch("multi_mcp.models.config.load_models_config") as mock_load:
            mock_config = ModelsConfiguration(
                version="1.0",
                models={
                    "gpt-5-mini": ModelConfig(litellm_model="openai/gpt-5-mini"),
                },
            )
            mock_load.return_value = mock_config

            # First call should load
            config1 = get_models_config()
            assert mock_load.call_count == 1

            # Second call should use cache
            config2 = get_models_config()
            assert mock_load.call_count == 1  # Not called again

            assert config1 is config2

        # Reset cache for other tests
        multi_mcp.models.config._config = None
