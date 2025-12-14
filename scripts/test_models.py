#!/usr/bin/env python3
"""Test configured LLM providers and report which are working.

Usage:
    uv run python scripts/test_models.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_mcp.config import settings
from multi_mcp.models.config import PROVIDERS
from multi_mcp.models.litellm_client import LiteLLMClient

# Models to test per provider (cheapest/fastest)
# Note: Model must exist in config/models.yaml
TEST_MODELS: dict[str, str] = {
    "openai": "gpt-5-mini",
    "anthropic": "haiku",
    "gemini": "flash",
    "azure": "azure-mini",
    "bedrock": "bedrock-sonnet",
    # "openrouter": "deepseek",  # Uncomment when models are enabled in config
}

# Short timeout for testing
TEST_TIMEOUT = 15


async def test_model(client: LiteLLMClient, model: str) -> tuple[str, bool, str]:
    """Test a single model with a minimal prompt.

    Returns:
        Tuple of (model, success, message)
    """
    messages = [{"role": "user", "content": "Say hi"}]

    try:
        # Use asyncio.wait_for() instead of mutating global settings (race condition safe)
        response = await asyncio.wait_for(
            client.call_async(messages, model=model),
            timeout=TEST_TIMEOUT,
        )

        if response.status == "success":
            latency = response.metadata.latency_ms if response.metadata else 0
            return (model, True, f"{latency}ms")
        else:
            error = response.error or "Unknown error"
            # Truncate long errors
            if len(error) > 60:
                error = error[:60] + "..."
            return (model, False, error)

    except TimeoutError:
        return (model, False, f"Timeout after {TEST_TIMEOUT}s")
    except Exception as e:
        return (model, False, str(e)[:60])


def check_provider_credentials(provider: str) -> bool:
    """Check if provider has required credentials set."""
    provider_config = PROVIDERS.get(provider)
    if not provider_config:
        return False

    for attr, _ in provider_config.credentials:
        if not getattr(settings, attr, None):
            return False
    return True


async def test_all_models() -> list[tuple[str, str, bool, str]]:
    """Test all configured models in parallel.

    Returns:
        List of (provider, model, success, message)
    """
    client = LiteLLMClient()
    tasks = []
    provider_model_map = []

    for provider, model in TEST_MODELS.items():
        if check_provider_credentials(provider):
            tasks.append(test_model(client, model))
            provider_model_map.append((provider, model))

    if not tasks:
        return []

    # Use return_exceptions=True to capture all results even if some fail
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: list[tuple[str, str, bool, str]] = []
    for (provider, model), result in zip(provider_model_map, results, strict=True):
        if isinstance(result, BaseException):
            # Task raised an exception - convert to error tuple
            output.append((provider, model, False, str(result)[:60]))
        else:
            # Task completed successfully - result is tuple[str, bool, str]
            _, success, msg = result
            output.append((provider, model, success, msg))

    return output


def print_results(results: list[tuple[str, str, bool, str]]) -> int:
    """Print test results in a nice format.

    Returns:
        Number of working providers
    """
    print("\n" + "=" * 60)
    print("Model Provider Test Results")
    print("=" * 60 + "\n")

    # Print test results first
    working = 0
    if results:
        print("Tested:")
        for provider, model, success, msg in results:
            if success:
                print(f"  ✓ {provider} ({model}): OK - {msg}")
                working += 1
            else:
                print(f"  ✗ {provider} ({model}): FAILED - {msg}")
        print()

    # Check which providers have no credentials
    unconfigured = []
    for provider in TEST_MODELS:
        if not check_provider_credentials(provider):
            unconfigured.append(provider)

    # Print unconfigured providers
    if unconfigured:
        print("Unconfigured (no API key):")
        for provider in unconfigured:
            provider_config = PROVIDERS.get(provider)
            env_vars = [env for _, env in provider_config.credentials] if provider_config else []
            print(f"  - {provider}: needs {', '.join(env_vars)}")
        print()

    # Check which providers exist but have no test model defined
    not_tested = []
    for provider in PROVIDERS:
        if provider not in TEST_MODELS:
            not_tested.append(provider)

    if not_tested:
        print("Not tested (no test model defined):")
        for provider in not_tested:
            print(f"  - {provider}")
        print()

    # Summary
    total_providers = len(PROVIDERS)
    testable = len(TEST_MODELS)
    configured = len(results)
    print("-" * 60)
    print(f"Summary: {working}/{configured} configured providers working")
    print(f"         {configured}/{testable} testable providers have API keys")
    print(f"         {testable}/{total_providers} providers have test models defined")
    print("-" * 60 + "\n")

    return working


def main() -> int:
    """Run model tests and print results."""
    print("Testing configured LLM providers...")

    results = asyncio.run(test_all_models())
    working = print_results(results)

    # Return 0 if at least one provider works, 1 otherwise
    return 0 if working > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
