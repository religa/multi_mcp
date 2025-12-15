"""Tests for .env file loading."""

import os
from pathlib import Path


class TestEnvLoading:
    """Tests for cascading .env file loading."""

    def test_user_env_path(self):
        """User .env path is in ~/.multi_mcp/."""
        from multi_mcp.settings import get_user_env_path

        expected = Path.home() / ".multi_mcp" / ".env"
        assert get_user_env_path() == expected

    def test_env_precedence_first_loaded_wins(self, tmp_path, monkeypatch):
        """With override=False, first loaded value wins."""
        # Setup: Create both .env files with different values
        user_env = tmp_path / "user" / ".env"
        project_env = tmp_path / "project" / ".env"

        user_env.parent.mkdir(parents=True)
        project_env.parent.mkdir(parents=True)

        user_env.write_text("TEST_KEY_PRECEDENCE=user_value\n")
        project_env.write_text("TEST_KEY_PRECEDENCE=project_value\n")

        # Clear any existing value
        monkeypatch.delenv("TEST_KEY_PRECEDENCE", raising=False)

        # Load in correct order (user first, then project)
        from dotenv import load_dotenv

        load_dotenv(user_env, override=False)
        load_dotenv(project_env, override=False)

        # First loaded wins with override=False
        assert os.getenv("TEST_KEY_PRECEDENCE") == "user_value"

        # Cleanup
        monkeypatch.delenv("TEST_KEY_PRECEDENCE", raising=False)

    def test_env_override_behavior(self, tmp_path, monkeypatch):
        """Project .env can override user .env if loaded second with override=True."""
        user_env = tmp_path / "user" / ".env"
        project_env = tmp_path / "project" / ".env"

        user_env.parent.mkdir(parents=True)
        project_env.parent.mkdir(parents=True)

        user_env.write_text("TEST_KEY_OVERRIDE=user_value\n")
        project_env.write_text("TEST_KEY_OVERRIDE=project_value\n")

        monkeypatch.delenv("TEST_KEY_OVERRIDE", raising=False)

        from dotenv import load_dotenv

        # Load user first
        load_dotenv(user_env, override=False)
        # Load project second with override=True
        load_dotenv(project_env, override=True)

        # With override=True, later value wins
        assert os.getenv("TEST_KEY_OVERRIDE") == "project_value"

        # Cleanup
        monkeypatch.delenv("TEST_KEY_OVERRIDE", raising=False)


class TestUserConfigPath:
    """Tests for user config path helpers."""

    def test_user_config_path(self):
        """User config path is in ~/.multi_mcp/."""
        from multi_mcp.models.config import get_user_config_path

        expected = Path.home() / ".multi_mcp" / "config.yaml"
        assert get_user_config_path() == expected

    def test_user_config_dir(self):
        """User config dir is ~/.multi_mcp/."""
        from multi_mcp.models.config import get_user_config_dir

        expected = Path.home() / ".multi_mcp"
        assert get_user_config_dir() == expected
