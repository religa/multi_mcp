"""Unit tests for model resolver."""

from unittest.mock import patch

import pytest

from multi_mcp.models.config import ModelConfig, ModelsConfiguration
from multi_mcp.models.resolver import ModelResolver


class TestModelResolver:
    """Tests for ModelResolver class."""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for testing."""
        return ModelsConfiguration(
            version="1.0",
            default_model="gpt-5-mini",
            default_models={
                "fast": "gpt-5-mini",
                "smart": "haiku",
                "cheap": ["gpt-5-nano", "gemini-2.5-flash"],
            },
            models={
                "gpt-5-mini": ModelConfig(
                    litellm_model="openai/gpt-5-mini",
                    aliases=["mini"],
                    context_window=128000,
                    max_tokens=16000,
                ),
                "gpt-5-nano": ModelConfig(
                    litellm_model="openai/gpt-5-nano",
                    aliases=["nano"],
                ),
                "haiku": ModelConfig(
                    litellm_model="anthropic/claude-sonnet-4-5-20250929",
                    aliases=["sonnet"],
                ),
                "gemini-2.5-flash": ModelConfig(
                    litellm_model="gemini/gemini-2.5-flash",
                    aliases=["flash", "gemini"],
                ),
                "disabled-model": ModelConfig(
                    litellm_model="openai/disabled",
                    aliases=["disabled"],
                    disabled=True,
                ),
            },
        )

    @pytest.fixture
    def resolver(self, sample_config):
        """Create a resolver with sample config."""
        return ModelResolver(config=sample_config)

    def test_resolve_primary_model_exact_match(self, resolver):
        """Test resolving a primary model by exact name."""
        canonical, config = resolver.resolve("gpt-5-mini")

        assert canonical == "gpt-5-mini"
        assert config.litellm_model == "openai/gpt-5-mini"
        assert config.context_window == 128000

    def test_resolve_alias_lowercase(self, resolver):
        """Test resolving an alias (lowercase)."""
        canonical, config = resolver.resolve("mini")

        assert canonical == "gpt-5-mini"
        assert config.litellm_model == "openai/gpt-5-mini"

    def test_resolve_alias_case_insensitive(self, resolver):
        """Test that alias resolution is case-insensitive."""
        canonical, config = resolver.resolve("MINI")

        assert canonical == "gpt-5-mini"
        assert config.litellm_model == "openai/gpt-5-mini"

    def test_resolve_primary_model_case_insensitive(self, resolver):
        """Test that primary model resolution is case-insensitive."""
        canonical, config = resolver.resolve("GPT-5-MINI")

        assert canonical == "gpt-5-mini"
        assert config.litellm_model == "openai/gpt-5-mini"

    def test_resolve_multiple_aliases(self, resolver):
        """Test resolving different aliases for the same model."""
        canonical1, _ = resolver.resolve("flash")
        canonical2, _ = resolver.resolve("gemini")

        assert canonical1 == canonical2 == "gemini-2.5-flash"

    def test_resolve_disabled_model_raises_error(self, resolver):
        """Test that resolving a disabled model raises ValueError."""
        with pytest.raises(ValueError, match="disabled"):
            resolver.resolve("disabled-model")

    def test_resolve_disabled_model_via_alias_raises_error(self, resolver):
        """Test that resolving a disabled model via alias raises ValueError."""
        with pytest.raises(ValueError, match="disabled"):
            resolver.resolve("disabled")

    @patch("multi_mcp.models.resolver.litellm")
    def test_resolve_litellm_fallback_exact(self, mock_litellm, resolver):
        """Test LiteLLM fallback with exact match."""
        mock_litellm.model_cost = {"gpt-4": {"max_input_tokens": 8000, "max_output_tokens": 4000}}

        canonical, config = resolver.resolve("gpt-4")

        assert canonical == "gpt-4"
        assert config.litellm_model == "gpt-4"
        assert config.context_window == 8000
        assert config.max_tokens == 4000
        assert "Auto-generated" in config.notes

    @patch("multi_mcp.models.resolver.litellm")
    def test_resolve_litellm_fallback_with_prefix(self, mock_litellm, resolver):
        """Test LiteLLM fallback finds model with prefix."""
        mock_litellm.model_cost = {"anthropic/claude-3-opus": {"max_input_tokens": 200000, "max_output_tokens": 4000}}

        canonical, config = resolver.resolve("claude-3-opus")

        assert canonical == "claude-3-opus"
        assert config.litellm_model == "anthropic/claude-3-opus"
        assert config.context_window == 200000

    @patch("multi_mcp.models.resolver.litellm")
    def test_resolve_litellm_fallback_without_prefix(self, mock_litellm, resolver):
        """Test LiteLLM fallback removes prefix to find model."""
        mock_litellm.model_cost = {"gpt-4-turbo": {"max_input_tokens": 128000, "max_output_tokens": 4000}}

        canonical, config = resolver.resolve("openai/gpt-4-turbo")

        assert canonical == "openai/gpt-4-turbo"
        assert config.litellm_model == "gpt-4-turbo"

    @patch("multi_mcp.models.resolver.litellm")
    def test_resolve_litellm_fallback_not_found(self, mock_litellm, resolver):
        """Test LiteLLM fallback with model not in database."""
        mock_litellm.model_cost = {}

        canonical, config = resolver.resolve("unknown-model")

        assert canonical == "unknown-model"
        assert config.litellm_model == "unknown-model"
        assert config.context_window is None

    def test_alias_map_building_case_insensitive(self, resolver):
        """Test that alias map is built with case-insensitive keys."""
        assert "mini" in resolver.alias_map
        assert "gpt-5-mini" in resolver.alias_map
        assert resolver.alias_map["mini"] == "gpt-5-mini"

    def test_get_litellm_model_returns_correct_string(self, resolver):
        """Test get_litellm_model returns the LiteLLM model string."""
        result = resolver.get_litellm_model("mini")

        assert result == "openai/gpt-5-mini"

    def test_get_default(self, resolver):
        """Test get_default returns default_model."""
        result = resolver.get_default()

        assert result == "gpt-5-mini"

    def test_list_models_excludes_disabled(self, resolver):
        """Test list_models excludes disabled models by default."""
        models = resolver.list_models()

        model_names = [m["name"] for m in models]
        assert "disabled-model" not in model_names
        assert "gpt-5-mini" in model_names

    def test_list_models_includes_disabled_when_flag_set(self, resolver):
        """Test list_models includes disabled models when flag is True."""
        models = resolver.list_models(include_disabled=True)

        model_names = [m["name"] for m in models]
        assert "disabled-model" in model_names

        disabled = next(m for m in models if m["name"] == "disabled-model")
        assert disabled["disabled"] is True

    @patch("multi_mcp.models.resolver.litellm")
    def test_list_models_fills_metadata_from_litellm(self, mock_litellm, sample_config):
        """Test list_models fills missing metadata from LiteLLM."""
        mock_litellm.model_cost = {"openai/gpt-5-nano": {"max_input_tokens": 64000, "max_output_tokens": 8000}}

        resolver = ModelResolver(config=sample_config)
        models = resolver.list_models()

        nano = next(m for m in models if m["name"] == "gpt-5-nano")
        assert nano["context_window"] == 64000
        assert nano["max_tokens"] == 8000

    def test_list_models_includes_all_fields(self, resolver):
        """Test list_models includes all expected fields."""
        models = resolver.list_models()

        assert len(models) > 0
        model = models[0]

        assert "name" in model
        assert "aliases" in model
        assert "provider" in model
        assert "context_window" in model
        assert "max_tokens" in model
        assert "disabled" in model
        assert "notes" in model

    def test_model_config_get_provider_from_prefix(self, resolver):
        """Test that provider is derived from litellm_model prefix."""
        _, config = resolver.resolve("gpt-5-mini")

        provider = config.get_provider()
        assert provider == "openai"

    def test_model_config_get_provider_from_litellm_db(self):
        """Test provider lookup from LiteLLM database."""
        # Need to patch at the point where it's imported in config.py
        with patch("multi_mcp.models.config.litellm") as mock_litellm:
            mock_litellm.model_cost = {"test-model": {"litellm_provider": "test-provider"}}

            config = ModelConfig(litellm_model="test-model")
            provider = config.get_provider()

            assert provider == "test-provider"

    def test_model_config_get_provider_explicit(self):
        """Test that explicit provider is used when set."""
        config = ModelConfig(litellm_model="openai/gpt-5-mini", provider="custom-provider")

        assert config.get_provider() == "custom-provider"
