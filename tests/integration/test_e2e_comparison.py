"""Integration tests for comparison tool with real API calls."""

import os
import tempfile
from pathlib import Path

import pytest

from src.tools.comparison import comparison_impl


@pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="E2E tests require RUN_E2E=1")
@pytest.mark.asyncio
async def test_comparison_with_real_files(comparison_models):
    """Test comparison with actual files and API calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "example.py"
        test_file.write_text("def add(a, b):\n    return a + b")

        import uuid

        result = await comparison_impl(
            name="Code Review Test",
            content="Review this function for best practices",
            step_number=1,
            next_action="stop",
            models=comparison_models,
            base_path=tmpdir,
            thread_id=str(uuid.uuid4()),
            relevant_files=[str(test_file)],
        )

        # Verify overall success
        assert result["status"] in ["success", "partial"]  # Changed from "complete" to "success"
        assert len(result["results"]) == 2

        # Verify at least one model succeeded
        successes = [r for r in result["results"] if r["status"] == "success"]
        assert len(successes) >= 1

        # Verify successful models provided content
        for model_result in successes:
            assert len(model_result["content"]) > 0
            assert model_result["metadata"]["total_tokens"] > 0
