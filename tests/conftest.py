"""Pytest configuration for multi_mcp tests."""

import os
from pathlib import Path

import pytest

# ============================================================================
# Integration Test Configuration
# ============================================================================

# Default model for integration tests (cheap, fast model)
# Can be overridden via INTEGRATION_TEST_MODEL environment variable
DEFAULT_INTEGRATION_TEST_MODEL = os.getenv("INTEGRATION_TEST_MODEL", "gpt-5-nano")

# Multi-model test configurations
DEFAULT_COMPARISON_MODELS = [DEFAULT_INTEGRATION_TEST_MODEL, "gemini-2.5-flash"]
DEFAULT_DEBATE_MODELS = [DEFAULT_INTEGRATION_TEST_MODEL, DEFAULT_INTEGRATION_TEST_MODEL]  # Same model twice for minimal cost


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
def comparison_models():
    """Get models to use for comparison/debate tests."""
    return DEFAULT_COMPARISON_MODELS.copy()


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
