"""Pytest configuration for multi_mcp tests."""

import os
import shutil
from pathlib import Path

import pytest

# ============================================================================
# Integration Test Configuration
# ============================================================================

# Default model for integration tests (cheap, fast model)
# Can be overridden via INTEGRATION_TEST_MODEL environment variable
DEFAULT_INTEGRATION_TEST_MODEL = os.getenv("INTEGRATION_TEST_MODEL", "gpt-5-nano")

# Multi-model test configurations
DEFAULT_COMPARE_MODELS = [DEFAULT_INTEGRATION_TEST_MODEL, "gemini-2.5-flash"]
DEFAULT_DEBATE_MODELS = ["gpt-5-nano", "gemini-2.5-flash"]  # Different models for real debate diversity


@pytest.fixture(autouse=True)
async def clear_conversation_store():
    """Clear conversation store between tests to prevent state leakage."""
    yield  # Run the test first

    # Clear the global store after each test
    from src.memory.store import _threads

    _threads.clear()


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with standard structure."""
    project = tmp_path / "test_project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "README.md").write_text("# Test Project\n")
    return project


@pytest.fixture
def integration_test_model():
    """Get the model to use for integration tests.

    Returns the model name configured for integration tests.
    Can be overridden via INTEGRATION_TEST_MODEL environment variable.

    Example:
        INTEGRATION_TEST_MODEL=gpt-5-mini pytest tests/integration/
    """
    return DEFAULT_INTEGRATION_TEST_MODEL


@pytest.fixture
def compare_models():
    """Get models to use for compare/debate tests."""
    return DEFAULT_COMPARE_MODELS.copy()


@pytest.fixture
def debate_models():
    """Get models to use for debate tests."""
    return DEFAULT_DEBATE_MODELS.copy()


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Provide mock environment variables for testing."""
    test_vars = {
        "OPENAI_API_KEY": "sk-test-key-12345",
        "DEFAULT_MODEL": "gpt-5-mini",
        "LOG_LEVEL": "INFO",
    }
    for key, value in test_vars.items():
        monkeypatch.setenv(key, value)
    return test_vars


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (>5s)")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location."""
    for item in items:
        # Auto-mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        # Auto-mark unit tests
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)


# ============================================================================
# CLI Test Fixtures
# ============================================================================


@pytest.fixture
def has_gemini_cli():
    """Check if Gemini CLI is available."""
    return shutil.which("gemini") is not None


@pytest.fixture
def has_codex_cli():
    """Check if Codex CLI is available."""
    return shutil.which("codex") is not None


@pytest.fixture
def has_claude_cli():
    """Check if Claude CLI is available."""
    return shutil.which("claude") is not None


@pytest.fixture
def skip_if_no_gemini_cli():
    """Skip test if Gemini CLI not available."""
    if not shutil.which("gemini"):
        pytest.skip("Gemini CLI not installed - install via: npm install -g @google/generative-ai-cli")


@pytest.fixture
def skip_if_no_codex_cli():
    """Skip test if Codex CLI not available."""
    if not shutil.which("codex"):
        pytest.skip("Codex CLI not installed - install via: npm install -g @anthropic-ai/codex-cli")


@pytest.fixture
def skip_if_no_claude_cli():
    """Skip test if Claude CLI not available."""
    if not shutil.which("claude"):
        pytest.skip("Claude CLI not installed - install via: pip install anthropic-cli")


@pytest.fixture
def skip_if_no_any_cli(has_gemini_cli, has_codex_cli, has_claude_cli):
    """Skip test if no CLI is available."""
    if not (has_gemini_cli or has_codex_cli or has_claude_cli):
        pytest.skip("No CLI models available - install at least one CLI tool")
