"""End-to-end integration tests for CLI model execution."""

import os
import shutil

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


# ============================================================================
# CLI Availability Checks
# ============================================================================


def is_cli_available(command: str) -> bool:
    """Check if a CLI command is available in PATH."""
    return shutil.which(command) is not None


# Conditional skip decorators
skip_if_no_gemini_cli = pytest.mark.skipif(
    not is_cli_available("gemini"),
    reason="gemini CLI not found in PATH (install: pip install google-generativeai-cli)",
)

skip_if_no_codex_cli = pytest.mark.skipif(
    not is_cli_available("codex"),
    reason="codex CLI not found in PATH (install: npm install -g @anthropics/codex-cli)",
)

skip_if_no_claude_cli = pytest.mark.skipif(
    not is_cli_available("claude"),
    reason="claude CLI not found in PATH (install via anthropic)",
)


# ============================================================================
# Basic CLI Execution Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@skip_if_no_gemini_cli
async def test_gemini_cli_basic_execution():
    """Test basic Gemini CLI execution through litellm_client."""
    from src.models.litellm_client import litellm_client

    messages = [{"role": "user", "content": "What is 2+2? Answer in one short sentence only."}]

    response = await litellm_client.call_async(messages=messages, model="gemini-cli")

    assert response.status == "success", f"Expected success, got {response.status}: {response.error}"
    assert response.metadata.model == "gemini-cli"
    assert response.metadata.latency_ms > 0
    assert len(response.content) > 0

    # Should mention 4
    content = response.content.lower()
    assert "4" in content or "four" in content, f"Expected answer to contain '4', got: {content}"

    print("\n✓ Gemini CLI test passed")
    print(f"✓ Latency: {response.metadata.latency_ms}ms")
    print(f"✓ Response: {response.content[:100]}...")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@skip_if_no_codex_cli
async def test_codex_cli_basic_execution():
    """Test basic Codex CLI execution through litellm_client."""
    from src.models.litellm_client import litellm_client

    messages = [{"role": "user", "content": "What is 3+3? Answer in one short sentence only."}]

    response = await litellm_client.call_async(messages=messages, model="codex-cli")

    assert response.status == "success", f"Expected success, got {response.status}: {response.error}"
    assert response.metadata.model == "codex-cli"
    assert response.metadata.latency_ms > 0
    assert len(response.content) > 0

    # Should mention 6
    content = response.content.lower()
    assert "6" in content or "six" in content, f"Expected answer to contain '6', got: {content}"

    print("\n✓ Codex CLI test passed")
    print(f"✓ Latency: {response.metadata.latency_ms}ms")
    print(f"✓ Response: {response.content[:100]}...")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@skip_if_no_claude_cli
async def test_claude_cli_basic_execution():
    """Test basic Claude CLI execution through litellm_client."""
    from src.models.litellm_client import litellm_client

    messages = [{"role": "user", "content": "What is 4+4? Answer in one short sentence only."}]

    response = await litellm_client.call_async(messages=messages, model="claude-cli")

    assert response.status == "success", f"Expected success, got {response.status}: {response.error}"
    assert response.metadata.model == "claude-cli"
    assert response.metadata.latency_ms > 0
    assert len(response.content) > 0

    # Should mention 8
    content = response.content.lower()
    assert "8" in content or "eight" in content, f"Expected answer to contain '8', got: {content}"

    print("\n✓ Claude CLI test passed")
    print(f"✓ Latency: {response.metadata.latency_ms}ms")
    print(f"✓ Response: {response.content[:100]}...")


# ============================================================================
# CLI Models in Tool Workflows
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.timeout(60)
@skip_if_no_gemini_cli
async def test_cli_model_in_chat():
    """Test CLI model works in chat tool."""
    import uuid

    from src.tools.chat import chat_impl

    thread_id = str(uuid.uuid4())

    response = await chat_impl(
        name="CLI chat test",
        content="What is the capital of France? Answer in one sentence.",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model="gemini-cli",
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "in_progress"]
    assert response["thread_id"] == thread_id
    assert "content" in response
    assert len(response["content"]) > 0

    # Should mention Paris
    content = response["content"].lower()
    assert "paris" in content, f"Expected answer to contain 'paris', got: {content}"

    print("\n✓ CLI model in chat test passed")
    print(f"✓ Response: {response['content'][:100]}...")


@pytest.mark.asyncio
@pytest.mark.timeout(90)
@skip_if_no_gemini_cli
async def test_cli_model_in_compare(integration_test_model):
    """Test CLI model works in compare tool alongside API model."""
    import uuid

    from src.tools.compare import compare_impl

    thread_id = str(uuid.uuid4())

    response = await compare_impl(
        name="Mixed compare test",
        content="What is 5+5? Answer in one short sentence only.",
        models=[integration_test_model, "gemini-cli"],  # API + CLI
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "partial"]
    assert response["thread_id"] == thread_id
    assert "results" in response
    assert len(response["results"]) == 2

    # Check both models succeeded
    successes = [r for r in response["results"] if r["status"] == "success"]
    assert len(successes) == 2, f"Expected 2 successes, got {len(successes)}"

    # Verify CLI model is in results
    models = [r["metadata"]["model"] for r in response["results"]]
    assert "gemini-cli" in models

    # Both should mention 10
    for result in response["results"]:
        content = result["content"].lower()
        assert "10" in content or "ten" in content, f"Expected answer to contain '10' from {result['metadata']['model']}, got: {content}"

    print("\n✓ CLI model in compare test passed")
    print(f"✓ Status: {response['status']}")
    print(f"✓ Summary: {response['summary']}")


@pytest.mark.asyncio
@pytest.mark.timeout(90)
@skip_if_no_gemini_cli
async def test_cli_model_in_codereview():
    """Test CLI model works in codereview tool (P1)."""
    import tempfile
    import uuid
    from pathlib import Path

    from src.tools.codereview import codereview_impl

    thread_id = str(uuid.uuid4())

    # Create a simple test file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("""
def add(a, b):
    return a + b

def multiply(x, y):
    return x * y
""")

        response = await codereview_impl(
            name="CLI codereview test",
            content="Review this Python module for code quality.",
            step_number=1,
            next_action="stop",
            base_path=tmpdir,
            model="gemini-cli",
            thread_id=thread_id,
            relevant_files=[str(test_file)],
            issues_found=None,
        )

        assert response["status"] in ["success", "in_progress"]
        assert response["thread_id"] == thread_id
        assert "content" in response
        assert len(response["content"]) > 0

        print("\n✓ CLI model in codereview test passed (P1)")
        print(f"✓ Status: {response['status']}")
        print(f"✓ Response length: {len(response['content'])} chars")
        print(f"✓ Response preview: {response['content'][:200]}...")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
@skip_if_no_gemini_cli
async def test_cli_model_in_debate(integration_test_model):
    """Test CLI model works in debate tool."""
    import uuid

    from src.tools.debate import debate_impl

    thread_id = str(uuid.uuid4())

    response = await debate_impl(
        name="CLI debate test",
        content="What is the best programming language for beginners? Answer in 2-3 sentences.",
        models=[integration_test_model, "gemini-cli"],  # API + CLI
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "partial"]
    assert response["thread_id"] == thread_id

    # Check step 1 results (stored in 'results')
    assert "results" in response
    assert len(response["results"]) == 2

    # Check step 2 results
    assert "step2_results" in response
    assert len(response["step2_results"]) == 2

    # Verify both steps had successes
    step1_successes = [r for r in response["results"] if r["status"] == "success"]
    step2_successes = [r for r in response["step2_results"] if r["status"] == "success"]
    assert len(step1_successes) >= 1, "Expected at least one step 1 success"
    assert len(step2_successes) >= 1, "Expected at least one step 2 success"

    print("\n✓ CLI model in debate test passed")
    print(f"✓ Status: {response['status']}")
    print(f"✓ Summary: {response['summary']}")


# ============================================================================
# Multiple CLI Models
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.timeout(90)
@skip_if_no_gemini_cli
@skip_if_no_codex_cli
async def test_multiple_cli_models_in_compare():
    """Test multiple CLI models work together in compare."""
    import uuid

    from src.tools.compare import compare_impl

    thread_id = str(uuid.uuid4())

    response = await compare_impl(
        name="Multi-CLI compare test",
        content="What is 7+8? Answer in one short sentence only.",
        models=["gemini-cli", "codex-cli"],  # Two CLI models
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "partial"]
    assert response["thread_id"] == thread_id
    assert len(response["results"]) == 2

    # Check both CLI models succeeded
    successes = [r for r in response["results"] if r["status"] == "success"]
    assert len(successes) == 2, f"Expected 2 successes, got {len(successes)}"

    # Verify both CLI models are in results
    models = [r["metadata"]["model"] for r in response["results"]]
    assert "gemini-cli" in models
    assert "codex-cli" in models

    # Both should mention 15
    for result in response["results"]:
        content = result["content"].lower()
        assert "15" in content or "fifteen" in content, (
            f"Expected answer to contain '15' from {result['metadata']['model']}, got: {content}"
        )

    print("\n✓ Multiple CLI models test passed")
    print(f"✓ Status: {response['status']}")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
@skip_if_no_gemini_cli
@skip_if_no_codex_cli
@skip_if_no_claude_cli
async def test_all_three_clis_in_compare():
    """Test all three CLI models (Gemini, Codex, Claude) work together in compare."""
    import uuid

    from src.tools.compare import compare_impl

    thread_id = str(uuid.uuid4())

    response = await compare_impl(
        name="Three CLI models compare test",
        content="What is 9+9? Answer in one short sentence only.",
        models=["gemini-cli", "codex-cli", "claude-cli"],  # All three CLIs
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "partial"]
    assert response["thread_id"] == thread_id
    assert len(response["results"]) == 3

    # Check all three CLI models succeeded
    successes = [r for r in response["results"] if r["status"] == "success"]
    assert len(successes) == 3, f"Expected 3 successes, got {len(successes)}"

    # Verify all three CLI models are in results
    models = [r["metadata"]["model"] for r in response["results"]]
    assert "gemini-cli" in models
    assert "codex-cli" in models
    assert "claude-cli" in models

    # All should mention 18
    for result in response["results"]:
        content = result["content"].lower()
        assert "18" in content or "eighteen" in content, (
            f"Expected answer to contain '18' from {result['metadata']['model']}, got: {content}"
        )

    print("\n✓ All three CLI models test passed")
    print(f"✓ Status: {response['status']}")
    print(f"✓ Models: {', '.join(models)}")


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_cli_model_invalid_command():
    """Test CLI model with non-existent command returns error."""
    from src.models.config import ModelConfig, get_models_config
    from src.models.litellm_client import litellm_client

    # Temporarily add a fake CLI model
    config = get_models_config()
    config.models["fake-cli"] = ModelConfig(
        provider="cli",
        cli_command="nonexistent-cli-command-12345",
        cli_args=[],
        cli_env={},
        cli_parser="text",
    )

    messages = [{"role": "user", "content": "Hello"}]

    response = await litellm_client.call_async(messages=messages, model="fake-cli")

    assert response.status == "error"
    assert "fake-cli" in response.metadata.model
    assert response.error is not None
    assert len(response.error) > 0

    # Clean up
    del config.models["fake-cli"]

    print("\n✓ CLI error handling test passed")
    print(f"✓ Error: {response.error[:100]}...")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@skip_if_no_gemini_cli
async def test_gemini_cli_with_alias():
    """Test Gemini CLI can be called via alias."""
    from src.models.litellm_client import litellm_client

    messages = [{"role": "user", "content": "What is 1+1? Answer in one short sentence."}]

    # Use alias 'gem-cli' instead of 'gemini-cli'
    response = await litellm_client.call_async(messages=messages, model="gem-cli")

    assert response.status == "success", f"Expected success, got {response.status}: {response.error}"
    assert response.metadata.model == "gemini-cli"  # Should resolve to canonical name
    assert len(response.content) > 0

    # Should mention 2
    content = response.content.lower()
    assert "2" in content or "two" in content, f"Expected answer to contain '2', got: {content}"

    print("\n✓ Gemini CLI alias test passed")
    print(f"✓ Alias 'gem-cli' resolved to: {response.metadata.model}")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@skip_if_no_codex_cli
async def test_codex_cli_with_alias():
    """Test Codex CLI can be called via alias."""
    from src.models.litellm_client import litellm_client

    messages = [{"role": "user", "content": "What is 5+3? Answer in one short sentence."}]

    # Use alias 'cx-cli' instead of 'codex-cli'
    response = await litellm_client.call_async(messages=messages, model="cx-cli")

    assert response.status == "success", f"Expected success, got {response.status}: {response.error}"
    assert response.metadata.model == "codex-cli"  # Should resolve to canonical name
    assert len(response.content) > 0

    # Should mention 8
    content = response.content.lower()
    assert "8" in content or "eight" in content, f"Expected answer to contain '8', got: {content}"

    print("\n✓ Codex CLI alias test passed")
    print(f"✓ Alias 'cx-cli' resolved to: {response.metadata.model}")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
@skip_if_no_claude_cli
async def test_claude_cli_with_alias():
    """Test Claude CLI can be called via alias."""
    from src.models.litellm_client import litellm_client

    messages = [{"role": "user", "content": "What is 6+2? Answer in one short sentence."}]

    # Use alias 'cl-cli' instead of 'claude-cli'
    response = await litellm_client.call_async(messages=messages, model="cl-cli")

    assert response.status == "success", f"Expected success, got {response.status}: {response.error}"
    assert response.metadata.model == "claude-cli"  # Should resolve to canonical name
    assert len(response.content) > 0

    # Should mention 8
    content = response.content.lower()
    assert "8" in content or "eight" in content, f"Expected answer to contain '8', got: {content}"

    print("\n✓ Claude CLI alias test passed")
    print(f"✓ Alias 'cl-cli' resolved to: {response.metadata.model}")
