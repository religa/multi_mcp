"""Test Azure OpenAI integration."""

import os

import pytest

from multi_mcp.models.resolver import ModelResolver
from multi_mcp.utils.llm_runner import execute_single


@pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration test")
@pytest.mark.skipif(not os.getenv("AZURE_API_KEY"), reason="Azure credentials not configured")
async def test_azure_model_call():
    """Test Azure OpenAI model call.

    Note: This test will skip if Azure connection fails (e.g., endpoint not accessible,
    model not deployed, etc.) to avoid blocking CI/CD when Azure is not fully configured.
    """
    messages = [{"role": "user", "content": "Say 'Azure test successful' and nothing else."}]

    response = await execute_single(
        model="azure-mini",
        messages=messages,
    )

    if response.status == "error" and "Connection error" in response.error:
        pytest.skip(f"Azure connection failed (may not be configured): {response.error}")

    assert response.status == "success"
    assert response.content
    assert response.metadata.model == "azure-gpt-5-mini"


async def test_azure_alias_resolution():
    """Test Azure model alias resolution."""
    resolver = ModelResolver()
    canonical, config = resolver.resolve("az-mini")

    assert canonical == "azure-gpt-5-mini"
    assert config.litellm_model == "azure/gpt-5-mini"
    # api_version is now read from environment (AZURE_API_VERSION) instead of params


@pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration test")
@pytest.mark.skipif(not os.getenv("AZURE_API_KEY"), reason="Azure credentials not configured")
async def test_azure_env_variables_accessible():
    """Test that Azure env variables are accessible to LiteLLM."""
    # LiteLLM should be able to see these
    assert os.getenv("AZURE_API_KEY") is not None
    assert os.getenv("AZURE_API_BASE") is not None
