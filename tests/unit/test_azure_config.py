"""Test Azure configuration."""

import os

import pytest

# Import config to trigger load_dotenv()
from src.config import settings  # noqa: F401


@pytest.mark.skipif(
    not os.getenv("AZURE_API_KEY"),
    reason="Azure API key not configured (optional)",
)
def test_azure_env_loaded():
    """Test that Azure env vars are loaded into os.environ."""
    # After load_dotenv() in config.py, Azure vars should be in environment
    assert os.getenv("AZURE_API_KEY") is not None
    assert os.getenv("AZURE_API_BASE") is not None
    assert os.getenv("AZURE_API_VERSION") is not None
