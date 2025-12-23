"""Test using ONLY conftest fixtures with TOP-LEVEL imports."""

import uuid

import pytest

from multi_mcp.tools.chat import chat_impl


class TestWithConftestFixtures:
    @pytest.mark.integration
    @pytest.mark.timeout(60)
    async def test_chat_continuation_with_cli(self, skip_if_no_any_cli, temp_project_dir, has_gemini_cli):
        """Exact same test as in test_cli_workflows.py."""
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
