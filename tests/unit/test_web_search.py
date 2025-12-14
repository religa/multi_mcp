"""Unit tests for web search functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from multi_mcp.models.config import ModelConfig
from multi_mcp.models.litellm_client import LiteLLMClient
from multi_mcp.models.resolver import ModelResolver


def test_has_provider_web_search():
    """Test has_provider_web_search() method."""
    # Model with web search
    config_with = ModelConfig(litellm_model="anthropic/claude-sonnet-4.5", provider_web_search=True)
    assert config_with.has_provider_web_search() is True

    # Model without web search
    config_without = ModelConfig(litellm_model="openai/gpt-3.5-turbo", provider_web_search=False)
    assert config_without.has_provider_web_search() is False


@pytest.mark.asyncio
async def test_web_search_disabled_by_default():
    """Test that web search is NOT enabled when flag is False."""
    mock_response = MagicMock()

    # Responses API format
    mock_message = MagicMock()
    mock_message.type = "message"
    mock_content_item = MagicMock()
    mock_content_item.text = "Response"
    mock_message.content = [mock_content_item]
    mock_response.output = [mock_message]

    mock_response.usage = MagicMock()
    mock_response.usage.total_tokens = 75

    # Mock credential validation to always pass
    with (
        patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
        patch("multi_mcp.models.litellm_client.LiteLLMClient._validate_provider_credentials", return_value=None),
    ):
        mock_completion.return_value = mock_response

        client = LiteLLMClient()

        # Resolve model first
        resolver = ModelResolver()
        canonical_name, model_config = resolver.resolve("claude-sonnet-4.5")

        response = await client.execute(
            canonical_name=canonical_name,
            model_config=model_config,
            messages=[{"role": "user", "content": "Hello"}],
            enable_web_search=False,
        )

        # Verify tools were NOT passed
        call_kwargs = mock_completion.call_args[1]
        assert "tools" not in call_kwargs
        assert response.status == "success"


@pytest.mark.asyncio
async def test_web_search_unsupported_model_silent():
    """Test that unsupported models just don't get web search (no error)."""
    mock_response = MagicMock()

    # Responses API format
    mock_message = MagicMock()
    mock_message.type = "message"
    mock_content_item = MagicMock()
    mock_content_item.text = "Response"
    mock_message.content = [mock_content_item]
    mock_response.output = [mock_message]

    mock_response.usage = MagicMock()
    mock_response.usage.total_tokens = 75

    # Mock credential validation to always pass
    with (
        patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
        patch("multi_mcp.models.litellm_client.LiteLLMClient._validate_provider_credentials", return_value=None),
    ):
        mock_completion.return_value = mock_response

        client = LiteLLMClient()

        # Resolve model first
        resolver = ModelResolver()
        canonical_name, model_config = resolver.resolve("gpt-5-nano")

        response = await client.execute(
            canonical_name=canonical_name,
            model_config=model_config,
            messages=[{"role": "user", "content": "Hello"}],
            enable_web_search=True,
        )

        # Verify no tools were passed (model doesn't support it)
        call_kwargs = mock_completion.call_args[1]
        assert "tools" not in call_kwargs
        # No error - just silently doesn't use web search
        assert response.status == "success"


@pytest.mark.asyncio
async def test_web_search_openai_provider():
    """Test that OpenAI models still support web search."""
    mock_response = MagicMock()

    # Responses API format
    mock_message = MagicMock()
    mock_message.type = "message"
    mock_content_item = MagicMock()
    mock_content_item.text = "Response"
    mock_message.content = [mock_content_item]
    mock_response.output = [mock_message]

    mock_response.usage = MagicMock()
    mock_response.usage.total_tokens = 75

    # Mock credential validation to always pass
    with (
        patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
        patch("multi_mcp.models.litellm_client.LiteLLMClient._validate_provider_credentials", return_value=None),
    ):
        mock_completion.return_value = mock_response

        client = LiteLLMClient()

        # Resolve model first
        resolver = ModelResolver()
        canonical_name, model_config = resolver.resolve("gpt-5-mini")

        # Test OpenAI (gpt-5-mini) - still has web search support
        await client.execute(
            canonical_name=canonical_name,
            model_config=model_config,
            messages=[{"role": "user", "content": "Test"}],
            enable_web_search=True,
        )
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["tools"] == [{"type": "web_search"}]
