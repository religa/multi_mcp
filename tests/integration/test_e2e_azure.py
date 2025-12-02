"""Test Azure OpenAI integration."""

import os

import pytest

from src.models.litellm_client import litellm_client
from src.models.resolver import ModelResolver


@pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration test")
async def test_azure_model_call():
    """Test Azure OpenAI model call."""
    messages = [{"role": "user", "content": "Say 'Azure test successful' and nothing else."}]

    response = await litellm_client.call_async(messages=messages, model="azure-mini")

    assert response.status == "success"
    assert response.content
    assert response.metadata.model == "azure-gpt-5-mini"


async def test_azure_alias_resolution():
    """Test Azure model alias resolution."""
    resolver = ModelResolver()
    canonical, config = resolver.resolve("az-mini")

    assert canonical == "azure-gpt-5-mini"
    assert config.litellm_model == "azure/gpt-5-mini"
    assert "api_version" in config.params


@pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration test")
async def test_azure_env_variables_accessible():
    """Test that Azure env variables are accessible to LiteLLM."""
    # LiteLLM should be able to see these
    assert os.getenv("AZURE_API_KEY") is not None
    assert os.getenv("AZURE_API_BASE") is not None
