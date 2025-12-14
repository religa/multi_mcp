"""Integration tests for CLI models in MCP tool workflows.

Tests that CLI models work correctly when used in actual MCP tools
like chat, compare, debate, and codereview.
"""

import uuid

import pytest

from multi_mcp.tools.chat import chat_impl
from multi_mcp.tools.compare import compare_impl
from multi_mcp.tools.debate import debate_impl


class TestChatWithCLI:
    """Test chat tool with CLI models."""

    @pytest.mark.integration
    @pytest.mark.timeout(150)  # Increased for real API calls without VCR caching
    async def test_chat_with_cli_model(self, skip_if_no_any_cli, temp_project_dir, has_gemini_cli):
        """Chat tool works with CLI model."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        response = await chat_impl(
            name="CLI chat test",
            content="What is Python? Answer in one sentence.",
            step_number=1,
            next_action="stop",
            base_path=str(temp_project_dir),
            model="gemini-cli",
            thread_id=str(uuid.uuid4()),
        )

        assert response["status"] == "success"
        assert response["content"]
        assert "python" in response["content"].lower()
        assert response.get("metadata") is not None
        assert response.get("thread_id") is not None

    @pytest.mark.integration
    @pytest.mark.timeout(60)
    async def test_chat_continuation_with_cli(self, skip_if_no_any_cli, temp_project_dir, has_gemini_cli):
        """Multi-step chat works with CLI models."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        # First message
        response1 = await chat_impl(
            name="Step 1",
            content="What is Python?",
            step_number=1,
            next_action="continue",
            base_path=str(temp_project_dir),
            model="gemini-cli",
            thread_id=str(uuid.uuid4()),
        )

        assert response1["status"] == "success"
        assert response1.get("thread_id") is not None
        thread_id = response1["thread_id"]

        # Continuation
        response2 = await chat_impl(
            name="Step 2",
            content="What are its main features? Answer briefly.",
            step_number=2,
            next_action="stop",
            base_path=str(temp_project_dir),
            model="gemini-cli",
            thread_id=thread_id,
        )

        assert response2["status"] == "success"
        assert response2["thread_id"] == thread_id
        assert response2["content"]


class TestCompareWithCLI:
    """Test compare tool with CLI models."""

    @pytest.mark.integration
    @pytest.mark.timeout(150)
    async def test_compare_with_single_cli_model(self, skip_if_no_any_cli, temp_project_dir, has_gemini_cli):
        """Compare works with a single CLI model."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        response = await compare_impl(
            name="CLI compare",
            content="What is 2+2? Answer with just the number.",
            step_number=1,
            next_action="stop",
            base_path=str(temp_project_dir),
            models=["gemini-cli"],
            thread_id=str(uuid.uuid4()),
        )

        assert response["status"] == "success"
        assert len(response["results"]) == 1
        assert response["results"][0]["metadata"]["model"] == "gemini-cli"
        assert response["results"][0]["status"] == "success"
        assert "4" in response["results"][0]["content"]

    @pytest.mark.integration
    @pytest.mark.timeout(90)
    async def test_compare_with_mixed_models(self, skip_if_no_any_cli, temp_project_dir, integration_test_model, has_gemini_cli):
        """Compare works with mix of API and CLI models."""
        if not has_gemini_cli:
            pytest.skip("Need Gemini CLI for this test")

        response = await compare_impl(
            name="Mixed model compare",
            content="What is 2+2? Answer with just the number.",
            step_number=1,
            next_action="stop",
            base_path=str(temp_project_dir),
            models=[integration_test_model, "gemini-cli"],  # Mix of API and CLI
            thread_id=str(uuid.uuid4()),
        )

        assert response["status"] == "success"
        assert len(response["results"]) == 2
        # Verify both models responded
        assert all(r["status"] == "success" for r in response["results"])
        # Verify both got the right answer
        for model_response in response["results"]:
            assert "4" in model_response["content"]

    @pytest.mark.integration
    @pytest.mark.timeout(90)
    async def test_compare_with_multiple_cli_models(self, temp_project_dir, has_gemini_cli, has_codex_cli, has_claude_cli):
        """Compare works with multiple CLI models."""
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

        response = await compare_impl(
            name="Multi-CLI compare",
            content="What is 2+2? Answer with just the number.",
            step_number=1,
            next_action="stop",
            base_path=str(temp_project_dir),
            models=available_clis[:2],  # Use first 2 available
            thread_id=str(uuid.uuid4()),
        )

        assert response["status"] in ["success", "partial"]  # partial is OK if one CLI has config issues
        assert len(response["results"]) == 2
        # At least one should succeed
        successes = [r for r in response["results"] if r["status"] == "success"]
        assert len(successes) >= 1, "At least one CLI model should succeed"


class TestDebateWithCLI:
    """Test debate tool with CLI models."""

    @pytest.mark.integration
    @pytest.mark.timeout(300)  # 5 minutes for CLI models
    async def test_debate_with_cli_models(self, temp_project_dir, has_gemini_cli, has_codex_cli, integration_test_model):
        """Debate workflow works with CLI models."""
        # Need at least one CLI for this test
        if not (has_gemini_cli or has_codex_cli):
            pytest.skip("Need at least one CLI for this test")

        # Use CLI + API model for diversity
        if has_gemini_cli:
            cli_model = "gemini-cli"
        else:
            cli_model = "codex-cli"

        response = await debate_impl(
            name="CLI debate",
            content="What is the best programming language? Answer briefly.",
            step_number=1,
            next_action="stop",
            base_path=str(temp_project_dir),
            models=[integration_test_model, cli_model],
            thread_id=str(uuid.uuid4()),
        )

        assert response["status"] == "success"
        # Step 1: Independent answers
        assert response.get("results") is not None
        assert len(response["results"]) == 2
        # Step 2: Debate/critique responses (only successful Step 1 models participate)
        assert response.get("step2_results") is not None
        assert len(response["step2_results"]) >= 1


class TestCLIErrorHandling:
    """Test error handling in workflows with CLI models."""

    @pytest.mark.integration
    @pytest.mark.timeout(60)
    async def test_compare_continues_when_cli_unavailable(self, temp_project_dir, integration_test_model):
        """Compare continues when CLI model is not available."""
        response = await compare_impl(
            name="Resilience test",
            content="What is 2+2?",
            step_number=1,
            next_action="stop",
            base_path=str(temp_project_dir),
            models=[integration_test_model, "nonexistent-cli"],
            thread_id=str(uuid.uuid4()),
        )

        # Should complete with partial results
        assert response["status"] == "partial"  # Changed from "success" since one model fails
        assert len(response["results"]) == 2

        # Find results by model name
        results_by_model = {r["metadata"]["model"]: r for r in response["results"]}

        # API model should succeed
        assert integration_test_model in results_by_model
        assert results_by_model[integration_test_model]["status"] == "success"

        # Nonexistent CLI should error gracefully
        assert "nonexistent-cli" in results_by_model
        assert results_by_model["nonexistent-cli"]["status"] == "error"

    @pytest.mark.integration
    @pytest.mark.timeout(150)  # Two-step debate: 60s timeout per step, 2 steps = ~120s total
    async def test_debate_with_one_cli_failure(self, temp_project_dir, integration_test_model, has_gemini_cli, has_codex_cli):
        """Debate handles CLI failure gracefully."""
        if not (has_gemini_cli or has_codex_cli):
            pytest.skip("Need at least one CLI for this test")

        cli_model = "gemini-cli" if has_gemini_cli else "codex-cli"

        response = await debate_impl(
            name="Failure handling",
            content="What is Python?",
            step_number=1,
            next_action="stop",
            base_path=str(temp_project_dir),
            models=[integration_test_model, cli_model, "nonexistent-cli"],
            thread_id=str(uuid.uuid4()),
        )

        # Debate should complete even with one or more failures (may be partial)
        assert response["status"] in ["success", "partial"]
        # At least 1 model should have answered successfully
        assert len([a for a in response["results"] if a["status"] == "success"]) >= 1
