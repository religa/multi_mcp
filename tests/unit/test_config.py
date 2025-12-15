"""Unit tests for configuration management."""

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
        assert settings.default_model_list == ["gpt-5-mini", "gemini-2.5-flash"]

    def test_no_env_var_uses_default(self, monkeypatch, tmp_path):
        """Test that default value is used when env var not set."""
        # Clear env var if it exists
        monkeypatch.delenv("DEFAULT_MODEL_LIST", raising=False)

        # Create a temporary empty .env file to prevent loading from project .env
        empty_env = tmp_path / ".env"
        empty_env.write_text("")
        monkeypatch.chdir(tmp_path)

        settings = Settings()
        assert settings.default_model_list == ["gpt-5-mini", "gemini-2.5-flash"]

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

    def test_default_model(self):
        """Test default_model default value."""
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
