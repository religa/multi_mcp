"""Integration tests for debate tool with real API calls."""

import os

import pytest

from src.tools.debate import debate_impl

# Only run if RUN_E2E=1
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E") != "1",
    reason="Integration tests only run with RUN_E2E=1",
)


@pytest.mark.asyncio
async def test_debate_real_api_minimal(debate_models):
    """Test debate with real API call using minimal cost (2 cheap models)."""

    import uuid

    result = await debate_impl(
        name="Integration Test",
        content="What is 2+2? Keep your answer very brief (one sentence).",
        step_number=1,
        next_action="stop",
        models=debate_models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    # Check response structure
    assert result["status"] in ["success", "partial", "error"]  # Changed from "complete" to "success"
    assert "thread_id" in result
    assert "results" in result
    assert "step2_results" in result

    # Check Step 1 results
    assert len(result["results"]) == 2
    assert result["results"][0]["status"] in ["success", "error"]

    # Check Step 2 results (only if Step 1 succeeded)
    if result["status"] != "error":
        assert len(result["step2_results"]) >= 1

        # If Step 1 succeeded, check content
        if result["results"][0]["status"] == "success":
            content = result["results"][0]["content"].lower()
            assert "4" in content or "four" in content, f"Expected '4' in response, got: {content}"

            # Step 2 should reference Step 1 responses
            debate_content = result["step2_results"][0]["content"].lower()
            assert len(debate_content) > 0, "Debate response should not be empty"
