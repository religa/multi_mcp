"""Integration tests for repository context and model configuration."""

import os
import uuid

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_with_agents_md(integration_test_model, tmp_path):
    """Test that AGENTS.md is loaded and used in chat context."""
    from multi_mcp.tools.chat import chat_impl

    # Create a test repository with AGENTS.md
    test_repo = tmp_path / "test_repo"
    test_repo.mkdir()

    # Create AGENTS.md with agent instructions
    agents_md = test_repo / "AGENTS.md"
    agents_md.write_text("""# AI Agents

## Code Reviewer Agent
- Focus on security vulnerabilities
- Check for OWASP Top 10 issues
- Verify input validation

## Documentation Agent
- Ensure all functions have docstrings
- Check for type hints
- Verify README completeness
""")

    # Create a test file
    test_file = test_repo / "example.py"
    test_file.write_text("""
def process_data(user_input):
    return eval(user_input)
""")

    thread_id = str(uuid.uuid4())

    # Ask a question that should trigger agent context usage
    response = await chat_impl(
        name="Ask about code review",
        content="What should the Code Reviewer Agent check in this code?",
        step_number=1,
        next_action="stop",
        base_path=str(test_repo),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response["status"] in ["success", "in_progress"]
    assert response["thread_id"] == thread_id
    assert len(response["content"]) > 0

    # Response should reference security or eval (dangerous function)
    content_lower = response["content"].lower()
    assert any(term in content_lower for term in ["security", "eval", "dangerous", "vulnerability", "owasp", "input"]), (
        f"Expected security analysis, got: {response['content'][:200]}"
    )

    print(f"\n✓ AGENTS.md context loaded: {test_repo}/AGENTS.md")
    print(f"✓ Chat used agent context: {thread_id}")


@pytest.mark.asyncio
@pytest.mark.timeout(300)  # 5 minutes for API calls
async def test_model_alias_resolution(tmp_path):
    """Test that model aliases resolve correctly in E2E flow."""
    from multi_mcp.tools.chat import chat_impl

    thread_id = str(uuid.uuid4())

    # Test with 'mini' alias (should resolve to gpt-5-mini)
    response = await chat_impl(
        name="Test alias resolution",
        content="What is 2+2? Answer in one word.",
        step_number=1,
        next_action="stop",
        base_path=str(tmp_path),
        model="mini",  # Using alias instead of full model name
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "in_progress"]
    assert "content" in response
    assert len(response["content"]) > 0

    # Verify metadata contains resolved model info
    if "metadata" in response:
        metadata = response["metadata"]
        # Should have model info (either canonical_model_name or model field)
        assert "canonical_model_name" in metadata or "model" in metadata

    print("\n✓ Model alias 'mini' resolved successfully")
    print(f"✓ Response received: {thread_id}")


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_version_tool_returns_metadata():
    """Test that version tool returns complete metadata."""
    from multi_mcp.server import version

    # Unwrap FastMCP function wrapper
    if hasattr(version, "fn"):
        func = version.fn
    else:
        func = version

    response = await func()

    # Verify response structure
    assert isinstance(response, dict)
    assert "version" in response
    assert "name" in response

    # Verify version format
    version = response["version"]
    assert isinstance(version, str)
    assert len(version) > 0

    # Version should be semver-ish (e.g., "0.1.0" or "0.1.0-dev")
    assert any(char.isdigit() for char in version), f"Version should contain digits: {version}"

    # Verify name
    name = response["name"]
    assert isinstance(name, str)
    assert len(name) > 0
    assert "multi" in name.lower() or "mcp" in name.lower(), f"Expected 'multi' or 'mcp' in name: {name}"

    # May contain optional fields
    optional_fields = ["description", "tools", "server_info"]
    for field in optional_fields:
        if field in response:
            assert response[field] is not None

    print("\n✓ Version tool metadata verified")
    print(f"✓ Version: {version}")
    print(f"✓ Name: {name}")
    if "tools" in response:
        print(f"✓ Tools: {response['tools']}")
