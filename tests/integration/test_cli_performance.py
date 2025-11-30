"""Performance and concurrency tests for CLI models.

Tests execution time, timeouts, and concurrent CLI calls.
"""

import asyncio
import time

import pytest

from src.models.litellm_client import LiteLLMClient


class TestCLIPerformance:
    """Test CLI execution performance."""

    @pytest.mark.integration
    @pytest.mark.timeout(45)
    async def test_cli_execution_completes_within_reasonable_time(self, skip_if_no_any_cli, has_gemini_cli):
        """CLI execution completes within reasonable time."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say hello in one word."}]

        start = time.time()
        result = await client.call_async(messages=messages, model="gemini-cli")
        duration = time.time() - start

        assert result.status == "success"
        # Should complete in under 30 seconds for simple prompt
        assert duration < 30.0, f"CLI took {duration:.2f}s, expected <30s"
        # Metadata latency should match actual duration (within 1 second tolerance)
        assert abs(result.metadata.latency_ms / 1000 - duration) < 1.0

    @pytest.mark.integration
    @pytest.mark.timeout(60)
    async def test_cli_latency_metadata_accuracy(self, skip_if_no_any_cli, has_gemini_cli):
        """CLI latency metadata is accurate."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Count to 3"}]

        start = time.perf_counter()
        result = await client.call_async(messages=messages, model="gemini-cli")
        actual_duration_ms = int((time.perf_counter() - start) * 1000)

        assert result.status == "success"
        assert result.metadata.latency_ms > 0
        # Latency should be within 20% of actual duration
        difference = abs(result.metadata.latency_ms - actual_duration_ms)
        tolerance = actual_duration_ms * 0.2
        assert difference < tolerance, f"Latency {result.metadata.latency_ms}ms vs actual {actual_duration_ms}ms"


class TestCLIConcurrency:
    """Test concurrent CLI execution."""

    @pytest.mark.integration
    @pytest.mark.timeout(90)
    async def test_concurrent_cli_calls_same_model(self, skip_if_no_any_cli, has_gemini_cli):
        """Multiple CLI calls can run concurrently on same model."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say hello"}]

        # Launch 3 concurrent CLI calls
        start = time.time()
        tasks = [client.call_async(messages=messages, model="gemini-cli") for _ in range(3)]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start

        # All should succeed
        assert len(results) == 3
        assert all(r.status == "success" for r in results)

        # Concurrent execution should be faster than sequential
        # (If sequential, would take ~30s each = 90s total)
        # Concurrent should complete in <60s
        assert duration < 60.0, f"Concurrent calls took {duration:.2f}s, expected <60s"

    @pytest.mark.integration
    @pytest.mark.timeout(90)
    async def test_concurrent_different_cli_models(self, temp_project_dir, has_gemini_cli, has_codex_cli, has_claude_cli):
        """Different CLI models can run concurrently."""
        # Build list of available CLIs
        available_clis = []
        if has_gemini_cli:
            available_clis.append("gemini-cli")
        if has_codex_cli:
            available_clis.append("codex-cli")
        if has_claude_cli:
            available_clis.append("claude-cli")

        if len(available_clis) < 2:
            pytest.skip("Need at least 2 CLI models for this test")

        client = LiteLLMClient()
        messages = [{"role": "user", "content": "What is 2+2?"}]

        # Launch concurrent calls to different CLIs
        tasks = [client.call_async(messages=messages, model=cli) for cli in available_clis[:2]]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_concurrent_cli_with_different_prompts(self, skip_if_no_any_cli, has_gemini_cli):
        """Same CLI handles concurrent calls with different prompts."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        client = LiteLLMClient()

        # Different prompts
        prompts = [
            "What is 1+1?",
            "What is 2+2?",
            "What is 3+3?",
        ]
        messages_list = [[{"role": "user", "content": p}] for p in prompts]

        # Launch concurrent calls
        tasks = [client.call_async(messages=msgs, model="gemini-cli") for msgs in messages_list]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 3
        assert all(r.status == "success" for r in results)

        # Verify different answers
        contents = [r.content for r in results]
        # Should have "2", "4", "6" in responses
        assert "2" in contents[0] or "two" in contents[0].lower()
        assert "4" in contents[1] or "four" in contents[1].lower()
        assert "6" in contents[2] or "six" in contents[2].lower()


class TestCLIStressTests:
    """Stress tests for CLI execution."""

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.timeout(180)
    async def test_many_sequential_cli_calls(self, skip_if_no_any_cli, has_gemini_cli):
        """CLI handles many sequential calls without degradation."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say ok"}]

        # Run 5 sequential calls
        results = []
        for _ in range(5):
            result = await client.call_async(messages=messages, model="gemini-cli")
            results.append(result)

        # All should succeed
        assert len(results) == 5
        assert all(r.status == "success" for r in results)

        # Latency should be relatively consistent (no degradation)
        latencies = [r.metadata.latency_ms for r in results]
        avg_latency = sum(latencies) / len(latencies)
        # No call should take 2x the average
        assert all(lat < avg_latency * 2 for lat in latencies), f"Latencies: {latencies}"

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.timeout(120)
    async def test_burst_concurrent_cli_calls(self, skip_if_no_any_cli, has_gemini_cli):
        """CLI handles burst of concurrent calls."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        client = LiteLLMClient()
        messages = [{"role": "user", "content": "Say hello"}]

        # Launch 5 concurrent calls
        tasks = [client.call_async(messages=messages, model="gemini-cli") for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed (allow for rate limiting)
        from src.schemas.base import ModelResponse

        successful = [r for r in results if isinstance(r, ModelResponse) and r.status == "success"]
        assert len(successful) >= 3, f"Only {len(successful)}/5 calls succeeded"
