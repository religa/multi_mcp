"""Tests to ensure .env.example stays in sync with code."""

from pathlib import Path

import pytest

from multi_mcp.models.config import PROVIDERS


class TestEnvExampleSync:
    """Ensure .env.example contains all required environment variables."""

    @pytest.fixture
    def env_example_path(self) -> Path:
        """Get path to .env.example in repo root."""
        return Path(__file__).parents[2] / ".env.example"

    @pytest.fixture
    def env_example_content(self, env_example_path: Path) -> str:
        """Read .env.example content."""
        assert env_example_path.exists(), f".env.example not found at {env_example_path}"
        return env_example_path.read_text()

    def test_env_example_exists(self, env_example_path: Path):
        """Verify .env.example file exists in repo root."""
        assert env_example_path.exists(), ".env.example must exist in repo root for easy developer setup"

    def test_env_example_contains_all_provider_credentials(self, env_example_content: str):
        """Ensure .env.example contains all credentials from PROVIDERS dict.

        This prevents drift between code and documentation.
        """
        missing = []

        for provider_id, provider_config in PROVIDERS.items():
            for _, env_var in provider_config.credentials:
                # Check for the env var (commented or not)
                if f"{env_var}=" not in env_example_content:
                    missing.append(f"{env_var} (provider: {provider_id})")

        assert not missing, f".env.example is missing these credentials: {missing}"

    def test_env_example_contains_runtime_settings(self, env_example_content: str):
        """Ensure .env.example documents key runtime settings."""
        required_settings = [
            "DEFAULT_MODEL",
            "DEFAULT_MODEL_LIST",
            "DEFAULT_TEMPERATURE",
            "LOG_LEVEL",
        ]

        missing = [s for s in required_settings if f"{s}=" not in env_example_content]
        assert not missing, f".env.example is missing these settings: {missing}"

    def test_env_example_has_copy_instructions(self, env_example_content: str):
        """Ensure .env.example has clear setup instructions."""
        assert "cp .env.example .env" in env_example_content or "copy" in env_example_content.lower(), (
            ".env.example should have copy instructions"
        )
