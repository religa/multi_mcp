"""Unit tests for configuration management."""

from unittest.mock import patch

from multi_mcp.models.config import ModelConfig, ModelsConfiguration, check_cli_availability
from multi_mcp.settings import Settings


class TestDefaultModelListParsing:
    """Test DEFAULT_MODEL_LIST parsing with different formats."""

    def test_comma_separated_format(self, monkeypatch):
        """Test comma-separated string format."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "mini,flash,haiku")
        settings = Settings()
        assert settings.default_model_list == ["mini", "flash", "haiku"]

    def test_comma_separated_with_spaces(self, monkeypatch):
        """Test comma-separated format with spaces around model names."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "mini, flash, haiku")
        settings = Settings()
        assert settings.default_model_list == ["mini", "flash", "haiku"]

    def test_comma_separated_extra_spaces(self, monkeypatch):
        """Test comma-separated format with extra whitespace."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "  mini  ,  flash  ,  haiku  ")
        settings = Settings()
        assert settings.default_model_list == ["mini", "flash", "haiku"]

    def test_json_array_format(self, monkeypatch):
        """Test JSON array format (backward compatibility)."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", '["mini","flash","haiku"]')
        settings = Settings()
        assert settings.default_model_list == ["mini", "flash", "haiku"]

    def test_json_array_with_spaces(self, monkeypatch):
        """Test JSON array format with spaces."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", '["mini", "flash", "haiku"]')
        settings = Settings()
        assert settings.default_model_list == ["mini", "flash", "haiku"]

    def test_single_model_comma_separated(self, monkeypatch):
        """Test single model in comma-separated format."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "mini")
        settings = Settings()
        assert settings.default_model_list == ["mini"]

    def test_single_model_json_array(self, monkeypatch):
        """Test single model in JSON array format."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", '["mini"]')
        settings = Settings()
        assert settings.default_model_list == ["mini"]

    def test_trailing_comma(self, monkeypatch):
        """Test comma-separated format with trailing comma."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "mini,flash,")
        settings = Settings()
        assert settings.default_model_list == ["mini", "flash"]

    def test_empty_string_uses_default(self, monkeypatch):
        """Test empty string falls back to default."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "")
        settings = Settings()
        assert settings.default_model_list == ["gpt-5-mini", "gemini-3-flash"]

    def test_no_env_var_uses_default(self, monkeypatch, tmp_path):
        """Test that default value is used when env var not set."""
        # Clear env var if it exists
        monkeypatch.delenv("DEFAULT_MODEL_LIST", raising=False)

        # Create a temporary empty .env file to prevent loading from project .env
        empty_env = tmp_path / ".env"
        empty_env.write_text("")
        monkeypatch.chdir(tmp_path)

        settings = Settings()
        assert settings.default_model_list == ["gpt-5-mini", "gemini-3-flash"]

    def test_full_model_names(self, monkeypatch):
        """Test with full model names instead of aliases."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "gpt-5-mini,gemini-2.5-flash,claude-sonnet-4.5")
        settings = Settings()
        assert settings.default_model_list == ["gpt-5-mini", "gemini-2.5-flash", "claude-sonnet-4.5"]

    def test_mixed_aliases_and_full_names(self, monkeypatch):
        """Test mixing aliases and full names."""
        monkeypatch.setenv("DEFAULT_MODEL_LIST", "mini,gemini-2.5-flash,sonnet")
        settings = Settings()
        assert settings.default_model_list == ["mini", "gemini-2.5-flash", "sonnet"]


class TestOtherConfigSettings:
    """Test other configuration settings."""

    def test_default_model(self, monkeypatch):
        """Test default_model default value."""
        monkeypatch.delenv("DEFAULT_MODEL", raising=False)
        settings = Settings()
        assert settings.default_model == "gpt-5-mini"

    def test_default_model_override(self, monkeypatch):
        """Test default_model can be overridden."""
        monkeypatch.setenv("DEFAULT_MODEL", "claude-sonnet-4.5")
        settings = Settings()
        assert settings.default_model == "claude-sonnet-4.5"

    def test_default_temperature(self):
        """Test default_temperature default value."""
        settings = Settings()
        assert settings.default_temperature == 0.2

    def test_max_files_per_review(self):
        """Test max_files_per_review default value."""
        settings = Settings()
        assert settings.max_files_per_review == 100

    def test_max_file_size_kb(self):
        """Test max_file_size_kb default value."""
        settings = Settings()
        assert settings.max_file_size_kb == 50

    def test_server_name(self):
        """Test server_name default value."""
        settings = Settings()
        assert settings.server_name == "Multi"

    def test_log_level(self):
        """Test log_level default value."""
        settings = Settings()
        assert settings.log_level == "INFO"


class TestCheckCliAvailability:
    """Tests for check_cli_availability function."""

    def test_marks_available_cli(self):
        """Test that installed CLI commands are marked available."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gemini-cli": ModelConfig(provider="cli", cli_command="gemini"),
            },
        )
        with patch("multi_mcp.models.config.shutil.which", return_value="/usr/bin/gemini"):
            check_cli_availability(config)
        assert config.models["gemini-cli"].cli_available is True

    def test_marks_unavailable_cli(self):
        """Test that missing CLI commands are marked unavailable."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gemini-cli": ModelConfig(provider="cli", cli_command="gemini"),
            },
        )
        with patch("multi_mcp.models.config.shutil.which", return_value=None):
            check_cli_availability(config)
        assert config.models["gemini-cli"].cli_available is False

    def test_skips_api_models(self):
        """Test that API models are not checked."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gpt-5-mini": ModelConfig(litellm_model="openai/gpt-5-mini"),
            },
        )
        with patch("multi_mcp.models.config.shutil.which") as mock_which:
            check_cli_availability(config)
            mock_which.assert_not_called()
        assert config.models["gpt-5-mini"].cli_available is None

    def test_mixed_models(self):
        """Test with both API and CLI models."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gpt-5-mini": ModelConfig(litellm_model="openai/gpt-5-mini"),
                "gemini-cli": ModelConfig(provider="cli", cli_command="gemini"),
                "codex-cli": ModelConfig(provider="cli", cli_command="codex"),
            },
        )
        with patch("multi_mcp.models.config.shutil.which", side_effect=lambda cmd: "/usr/bin/gemini" if cmd == "gemini" else None):
            check_cli_availability(config)

        assert config.models["gpt-5-mini"].cli_available is None
        assert config.models["gemini-cli"].cli_available is True
        assert config.models["codex-cli"].cli_available is False
