"""Unit tests for LiteLLM client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from multi_mcp.models.config import ModelConfig, ModelConstraints, ModelsConfiguration
from multi_mcp.models.litellm_client import LiteLLMClient
from multi_mcp.models.resolver import ModelResolver
from multi_mcp.schemas.base import ModelResponse


class TestLiteLLMClient:
    """Tests for LiteLLMClient class."""

    @pytest.fixture
    def sample_config(self):
        """Create sample configuration for testing."""
        return ModelsConfiguration(
            version="1.0",
            models={
                "gpt-5-mini": ModelConfig(
                    litellm_model="openai/gpt-5-mini", aliases=["mini"], constraints=ModelConstraints(temperature=1.0)
                ),
                "gpt-5-pro": ModelConfig(litellm_model="openai/gpt-5-pro", aliases=["pro"]),
            },
        )

    @pytest.fixture
    def client(self, sample_config):
        """Create LiteLLM client with sample config."""
        resolver = ModelResolver(config=sample_config)
        return LiteLLMClient(resolver=resolver)

    @pytest.fixture
    def mock_llm_response(self):
        """Create mock LiteLLM responses API response."""
        mock_response = MagicMock()

        # Responses API format
        mock_message = MagicMock()
        mock_message.type = "message"
        mock_message.role = "assistant"

        mock_content_item = MagicMock()
        mock_content_item.text = "Test response"
        mock_message.content = [mock_content_item]

        mock_response.output = [mock_message]

        # Usage stats (only total_tokens available in responses API)
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 150

        return mock_response

    @pytest.mark.asyncio
    async def test_call_async_success(self, client, mock_llm_response):
        """Test successful LLM call."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert isinstance(result, ModelResponse)
            assert result.status == "success"
            assert result.content == "Test response"
            assert result.metadata.model == "gpt-5-mini"
            assert result.metadata.total_tokens == 150
            assert result.metadata.prompt_tokens == 0  # Not available in responses API
            assert result.metadata.completion_tokens == 0  # Not available in responses API
            assert result.metadata.latency_ms >= 0
            mock_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_async_with_model_resolution(self, client, mock_llm_response):
        """Test that model aliases are resolved correctly."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("mini")  # Alias
            result = await client.execute(
                canonical_name=canonical_name,
                model_config=model_config,
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert result.metadata.model == "gpt-5-mini"
            # Check that litellm_model was passed to acompletion
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["model"] == "openai/gpt-5-mini"

    @pytest.mark.asyncio
    async def test_call_async_uses_default_model_when_none_specified(self, client, mock_llm_response):
        """Test that default model is used when no model specified."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            default_model = client.resolver.get_default()
            canonical_name, model_config = client.resolver.resolve(default_model)
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.metadata.model == "gpt-5-mini"
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["model"] == "openai/gpt-5-mini"

    @pytest.mark.asyncio
    async def test_call_async_temperature_uses_default(self, client, mock_llm_response):
        """Test that default temperature is used when no constraint."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("gpt-5-pro")  # No temperature constraint
            await client.execute(canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}])

            call_kwargs = mock_completion.call_args[1]
            # Should use default temperature from settings (0.2)
            assert call_kwargs["temperature"] == 0.2

    @pytest.mark.asyncio
    async def test_call_async_temperature_constraint_enforced(self, client, mock_llm_response):
        """Test that model temperature constraints override default temperature."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")  # Has temperature=1.0 constraint
            await client.execute(canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}])

            call_kwargs = mock_completion.call_args[1]
            # Constraint should override default temperature
            assert call_kwargs["temperature"] == 1.0

    @pytest.mark.asyncio
    async def test_call_async_logging(self, client, mock_llm_response):
        """Test that LLM interactions are logged."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction") as mock_log,
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")
            await client.execute(canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}])

            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            # Request data now contains the kwargs passed to litellm
            assert call_args["request_data"]["model"] == "openai/gpt-5-mini"
            assert call_args["request_data"]["input"] == [{"role": "user", "content": "Hello"}]  # Changed from "messages" to "input"
            # Response data is the ModelResponse dumped to dict
            assert call_args["response_data"]["content"] == "Test response"
            assert call_args["response_data"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_call_async_api_error_handling(self, client):
        """Test that API errors return error response."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.side_effect = Exception("API error")

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert isinstance(result, ModelResponse)
            assert result.status == "error"
            assert "API error" in result.error
            assert result.metadata.model == "gpt-5-mini"

    @pytest.mark.asyncio
    async def test_call_async_timeout_handling(self, client):
        """Test that timeout errors return error response."""
        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.side_effect = TimeoutError()

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert isinstance(result, ModelResponse)
            assert result.status == "error"
            assert "timed out" in result.error
            assert result.metadata.model == "gpt-5-mini"

    @pytest.mark.asyncio
    async def test_call_async_messages_parameter(self, client, mock_llm_response):
        """Test that messages are passed correctly to LiteLLM as 'input'."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]

        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")
            await client.execute(canonical_name=canonical_name, model_config=model_config, messages=messages)

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["input"] == messages  # Changed from "messages" to "input"
            assert len(call_kwargs["input"]) == 2

    @pytest.mark.asyncio
    async def test_call_async_includes_model_params(self, sample_config, mock_llm_response):
        """Test that model-specific params are included in LLM call."""
        # Create config with custom params and explicit max_tokens
        config = ModelsConfiguration(
            version="1.0",
            models={
                "custom-model": ModelConfig(
                    litellm_model="provider/custom-model",
                    max_tokens=2000,  # Use explicit max_tokens field, not params
                    params={"top_p": 0.9},
                ),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("custom-model")
            await client.execute(canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}])

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["top_p"] == 0.9
            assert call_kwargs["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_call_async_uses_default_max_tokens(self, sample_config, mock_llm_response):
        """Test that default max_tokens (32768) is used when not configured."""
        # Use sample_config which doesn't have max_tokens set
        resolver = ModelResolver(config=sample_config)
        client = LiteLLMClient(resolver=resolver)

        with (
            patch("multi_mcp.models.litellm_client.litellm.aresponses", new_callable=AsyncMock) as mock_completion,
            patch("multi_mcp.models.litellm_client.log_llm_interaction"),
            patch.object(client, "_validate_provider_credentials", return_value=None),
        ):
            mock_completion.return_value = mock_llm_response

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")
            await client.execute(canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}])

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["max_tokens"] == 32768  # Default value

    def test_lazy_resolver_loading(self):
        """Test that resolver is lazy-loaded."""
        client = LiteLLMClient()

        # Resolver should not be created yet
        assert client._resolver is None

        # Access resolver property
        resolver = client.resolver

        # Now resolver should be created
        assert resolver is not None
        assert isinstance(resolver, ModelResolver)

        # Second access should return same instance
        resolver2 = client.resolver
        assert resolver is resolver2

    @pytest.mark.asyncio
    async def test_credential_validation_azure_missing_key(self, sample_config):
        """Test that Azure models fail with explicit error when AZURE_API_KEY is missing."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "azure-gpt-5-mini": ModelConfig(litellm_model="azure/gpt-5-mini", aliases=["azure-mini"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.azure_api_key = None
            mock_settings.azure_api_base = "https://example.azure.com"

            canonical_name, model_config = client.resolver.resolve("azure-gpt-5-mini")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "AZURE_API_KEY" in result.error
            assert "environment or .env file" in result.error
            assert "already set: AZURE_API_BASE" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_azure_missing_base(self, sample_config):
        """Test that Azure models fail with explicit error when AZURE_API_BASE is missing."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "azure-gpt-5-mini": ModelConfig(litellm_model="azure/gpt-5-mini", aliases=["azure-mini"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.azure_api_key = "test-key"
            mock_settings.azure_api_base = None

            canonical_name, model_config = client.resolver.resolve("azure-gpt-5-mini")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "AZURE_API_BASE" in result.error
            assert "environment or .env file" in result.error
            assert "already set: AZURE_API_KEY" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_azure_missing_both(self, sample_config):
        """Test that Azure models show both missing credentials."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "azure-gpt-5-mini": ModelConfig(litellm_model="azure/gpt-5-mini", aliases=["azure-mini"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.azure_api_key = None
            mock_settings.azure_api_base = None

            canonical_name, model_config = client.resolver.resolve("azure-gpt-5-mini")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "AZURE_API_KEY" in result.error
            assert "AZURE_API_BASE" in result.error
            assert "environment or .env file" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_gemini_missing(self, sample_config):
        """Test that Gemini models fail with explicit error when GEMINI_API_KEY is missing."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gemini-2.5-flash": ModelConfig(litellm_model="gemini/gemini-2.5-flash", aliases=["flash"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.gemini_api_key = None

            canonical_name, model_config = client.resolver.resolve("gemini-2.5-flash")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "GEMINI_API_KEY" in result.error
            assert "environment or .env file" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_anthropic_missing(self, sample_config):
        """Test that Anthropic models fail with explicit error when ANTHROPIC_API_KEY is missing."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "claude-sonnet-4.5": ModelConfig(litellm_model="anthropic/claude-sonnet-4-5-20250929", aliases=["sonnet"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.anthropic_api_key = None

            canonical_name, model_config = client.resolver.resolve("claude-sonnet-4.5")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "ANTHROPIC_API_KEY" in result.error
            assert "environment or .env file" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_openrouter_missing(self, sample_config):
        """Test that OpenRouter models fail with explicit error when OPENROUTER_API_KEY is missing."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "openrouter-model": ModelConfig(litellm_model="openrouter/some-model", aliases=["or"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.openrouter_api_key = None

            canonical_name, model_config = client.resolver.resolve("openrouter-model")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "OPENROUTER_API_KEY" in result.error
            assert "environment or .env file" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_openai_missing(self, sample_config):
        """Test that OpenAI models fail with explicit error when OPENAI_API_KEY is missing."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gpt-5-mini": ModelConfig(litellm_model="openai/gpt-5-mini", aliases=["mini"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.openai_api_key = None

            canonical_name, model_config = client.resolver.resolve("gpt-5-mini")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "OPENAI_API_KEY" in result.error
            assert "environment or .env file" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_bedrock_missing_all(self, sample_config):
        """Test that Bedrock models fail with explicit error when all AWS credentials are missing."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "bedrock-model": ModelConfig(litellm_model="bedrock/anthropic.claude-sonnet-4-5-v2", aliases=["bedrock"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.aws_access_key_id = None
            mock_settings.aws_secret_access_key = None
            mock_settings.aws_region_name = None

            canonical_name, model_config = client.resolver.resolve("bedrock-model")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "AWS_ACCESS_KEY_ID" in result.error
            assert "AWS_SECRET_ACCESS_KEY" in result.error
            assert "AWS_REGION_NAME" in result.error
            assert "environment or .env file" in result.error

    @pytest.mark.asyncio
    async def test_credential_validation_bedrock_partial(self, sample_config):
        """Test that Bedrock shows which AWS credentials are already set."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "bedrock-model": ModelConfig(litellm_model="bedrock/anthropic.claude-sonnet-4-5-v2", aliases=["bedrock"]),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        with patch("multi_mcp.models.litellm_client.settings") as mock_settings:
            mock_settings.aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
            mock_settings.aws_secret_access_key = None
            mock_settings.aws_region_name = "us-east-1"

            canonical_name, model_config = client.resolver.resolve("bedrock-model")
            result = await client.execute(
                canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "Hello"}]
            )

            assert result.status == "error"
            assert "AWS_SECRET_ACCESS_KEY" in result.error
            assert "already set: AWS_ACCESS_KEY_ID, AWS_REGION_NAME" in result.error

    @pytest.mark.asyncio
    async def test_call_async_rejects_cli_models(self, sample_config):
        """Test that call_async rejects CLI models."""
        config = ModelsConfiguration(
            version="1.0",
            models={
                "gemini-cli": ModelConfig(provider="cli", cli_command="gemini", cli_args=["chat"], cli_parser="json"),
            },
        )
        resolver = ModelResolver(config=config)
        client = LiteLLMClient(resolver=resolver)

        canonical_name, model_config = client.resolver.resolve("gemini-cli")
        result = await client.execute(
            canonical_name=canonical_name, model_config=model_config, messages=[{"role": "user", "content": "test"}]
        )

        assert result.status == "error"
        assert "CLI model" in result.error
        assert "Use CLIExecutor" in result.error
        assert result.metadata.model == "gemini-cli"
