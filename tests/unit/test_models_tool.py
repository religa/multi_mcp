"""Unit tests for models tool."""

from unittest.mock import patch

import pytest

from multi_mcp.models.config import ModelConfig, ModelsConfiguration
from multi_mcp.tools.models import models_impl


class TestModelsImpl:
    """Tests for models_impl function."""

    @pytest.fixture
    def sample_config(self):
        """Create sample configuration for testing."""
        return ModelsConfiguration(
            version="1.0",
            default_model="gpt-5-mini",
            models={
                "gpt-5-mini": ModelConfig(
                    litellm_model="openai/gpt-5-mini",
                    aliases=["mini"],
                    context_window=128000,
                ),
                "haiku": ModelConfig(
                    litellm_model="anthropic/claude-sonnet-4-5-20250929",
                    aliases=["sonnet"],
                ),
                "disabled-model": ModelConfig(
                    litellm_model="openai/disabled",
                    disabled=True,
                ),
            },
        )

    @pytest.mark.asyncio
    async def test_models_impl_returns_model_list(self, sample_config):
        """Test that models_impl returns list of models with credential validation."""
        with (
            patch("multi_mcp.tools.models.ModelResolver") as mock_resolver_class,
            patch("multi_mcp.tools.models.validate_model_credentials") as mock_validate,
        ):
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.config = sample_config
            mock_resolver.list_models.return_value = [
                {
                    "name": "gpt-5-mini",
                    "aliases": ["mini"],
                    "provider": "openai",
                    "context_window": 128000,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": "openai/gpt-5-mini",
                },
                {
                    "name": "haiku",
                    "aliases": ["sonnet"],
                    "provider": "anthropic",
                    "context_window": None,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": "anthropic/claude-haiku-4-5-20251001",
                },
            ]

            # Mock credential validation to return None (valid)
            mock_validate.return_value = None

            result = await models_impl()

            assert "models" in result
            assert "default_model" in result
            assert "count" in result

            assert len(result["models"]) == 2
            assert result["count"] == 2
            assert result["default_model"] == "gpt-5-mini"

            # Verify credential status is added
            for model in result["models"]:
                assert "credential_status" in model
                assert model["credential_status"] == "valid"

            # Verify list_models was called with include_disabled=False
            mock_resolver.list_models.assert_called_once_with(include_disabled=False)

    @pytest.mark.asyncio
    async def test_models_impl_includes_aliases_and_metadata(self, sample_config):
        """Test that returned models include all metadata fields."""
        with (
            patch("multi_mcp.tools.models.ModelResolver") as mock_resolver_class,
            patch("multi_mcp.tools.models.validate_model_credentials") as mock_validate,
        ):
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.config = sample_config
            mock_resolver.list_models.return_value = [
                {
                    "name": "gpt-5-mini",
                    "aliases": ["mini", "gpt5-mini"],
                    "provider": "openai",
                    "context_window": 128000,
                    "max_tokens": 16000,
                    "disabled": False,
                    "notes": "Fast and cost-effective",
                    "litellm_model": "openai/gpt-5-mini",
                },
            ]

            # Mock credential validation
            mock_validate.return_value = None

            result = await models_impl()

            model = result["models"][0]
            assert model["name"] == "gpt-5-mini"
            assert "mini" in model["aliases"]
            assert "gpt5-mini" in model["aliases"]
            assert model["provider"] == "openai"
            assert model["context_window"] == 128000
            assert model["max_tokens"] == 16000
            assert model["disabled"] is False
            assert model["notes"] == "Fast and cost-effective"
            assert model["credential_status"] == "valid"

    @pytest.mark.asyncio
    async def test_models_impl_excludes_disabled_models(self, sample_config):
        """Test that disabled models are excluded from the list."""
        with (
            patch("multi_mcp.tools.models.ModelResolver") as mock_resolver_class,
            patch("multi_mcp.tools.models.validate_model_credentials") as mock_validate,
        ):
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.config = sample_config
            # list_models should return only enabled models
            mock_resolver.list_models.return_value = [
                {
                    "name": "gpt-5-mini",
                    "aliases": ["mini"],
                    "provider": "openai",
                    "context_window": None,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": "openai/gpt-5-mini",
                },
                {
                    "name": "haiku",
                    "aliases": ["sonnet"],
                    "provider": "anthropic",
                    "context_window": None,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": "anthropic/claude-haiku-4-5-20251001",
                },
            ]

            # Mock credential validation
            mock_validate.return_value = None

            result = await models_impl()

            # Should have 2 models (disabled-model excluded)
            assert result["count"] == 2
            model_names = [m["name"] for m in result["models"]]
            assert "disabled-model" not in model_names
            assert "gpt-5-mini" in model_names
            assert "haiku" in model_names

    @pytest.mark.asyncio
    async def test_models_impl_credential_validation_invalid(self, sample_config):
        """Test that invalid credentials are properly marked."""
        with (
            patch("multi_mcp.tools.models.ModelResolver") as mock_resolver_class,
            patch("multi_mcp.tools.models.validate_model_credentials") as mock_validate,
        ):
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.config = sample_config
            mock_resolver.list_models.return_value = [
                {
                    "name": "gpt-5-mini",
                    "aliases": ["mini"],
                    "provider": "openai",
                    "context_window": 128000,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": "openai/gpt-5-mini",
                },
            ]

            # Mock credential validation to return an error
            mock_validate.return_value = "OpenAI models require OPENAI_API_KEY to be set"

            result = await models_impl()

            model = result["models"][0]
            assert model["credential_status"] == "invalid"
            assert "credential_error" in model
            assert "OPENAI_API_KEY" in model["credential_error"]

    @pytest.mark.asyncio
    async def test_models_impl_skips_cli_models(self, sample_config):
        """Test that CLI models are skipped for credential validation."""
        with (
            patch("multi_mcp.tools.models.ModelResolver") as mock_resolver_class,
            patch("multi_mcp.tools.models.validate_model_credentials") as mock_validate,
        ):
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.config = sample_config
            mock_resolver.list_models.return_value = [
                {
                    "name": "gpt-5-mini",
                    "aliases": ["mini"],
                    "provider": "openai",
                    "context_window": 128000,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": "openai/gpt-5-mini",
                },
                {
                    "name": "gemini-cli",
                    "aliases": ["gem-cli"],
                    "provider": "cli",
                    "context_window": None,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "CLI model",
                },
            ]

            # Mock credential validation
            mock_validate.return_value = None

            result = await models_impl()

            # Find models by provider
            openai_model = next(m for m in result["models"] if m["provider"] == "openai")
            cli_model = next(m for m in result["models"] if m["provider"] == "cli")

            # OpenAI model should have credential status
            assert "credential_status" in openai_model
            assert openai_model["credential_status"] == "valid"

            # CLI model should NOT have credential status
            assert "credential_status" not in cli_model

    @pytest.mark.asyncio
    async def test_models_impl_handles_validation_exception(self, sample_config):
        """Test that validation exceptions are handled gracefully."""
        with (
            patch("multi_mcp.tools.models.ModelResolver") as mock_resolver_class,
            patch("multi_mcp.tools.models.validate_model_credentials") as mock_validate,
        ):
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.config = sample_config
            mock_resolver.list_models.return_value = [
                {
                    "name": "gpt-5-mini",
                    "aliases": ["mini"],
                    "provider": "openai",
                    "context_window": 128000,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": "openai/gpt-5-mini",
                },
            ]

            # Mock credential validation to raise an exception
            mock_validate.side_effect = AttributeError("Test error")

            result = await models_impl()

            model = result["models"][0]
            assert model["credential_status"] == "unknown"
            assert "credential_error" in model
            assert "AttributeError" in model["credential_error"]

    @pytest.mark.asyncio
    async def test_models_impl_handles_missing_litellm_model(self, sample_config):
        """Test that models without litellm_model get 'unknown' status."""
        with (
            patch("multi_mcp.tools.models.ModelResolver") as mock_resolver_class,
            patch("multi_mcp.tools.models.validate_model_credentials") as mock_validate,
        ):
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.config = sample_config
            mock_resolver.list_models.return_value = [
                {
                    "name": "misconfigured-model",
                    "aliases": [],
                    "provider": "openai",  # API provider but no litellm_model
                    "context_window": None,
                    "max_tokens": None,
                    "disabled": False,
                    "notes": "",
                    "litellm_model": None,  # Missing!
                },
            ]

            result = await models_impl()

            model = result["models"][0]
            assert model["credential_status"] == "unknown"
            assert "credential_error" in model
            assert "missing litellm_model" in model["credential_error"]

            # Validation should not have been called
            mock_validate.assert_not_called()
