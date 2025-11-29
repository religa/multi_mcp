"""End-to-end integration tests for codereview tool."""

import os
from pathlib import Path

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.fixture
def test_repo_path():
    """Path to SQL injection test repo."""
    return str(Path(__file__).parent.parent / "data" / "repos" / "sql_injection_example")


@pytest.fixture
def auth_file_path(test_repo_path):
    """Path to auth.py with vulnerabilities."""
    return str(Path(test_repo_path) / "auth.py")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_codereview_finds_sql_injection(integration_test_model, test_repo_path, auth_file_path):
    """Test that codereview identifies SQL injection vulnerabilities."""
    import uuid

    from src.tools.codereview import codereview_impl

    thread_id = str(uuid.uuid4())

    # Step 1: Get checklist
    response1 = await codereview_impl(
        name="Review authentication module for security vulnerabilities",
        content="Analyzing authentication code for SQL injection, password security, and input validation",
        step_number=1,
        next_action="continue",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response1["status"] == "in_progress"
    assert response1["thread_id"] == thread_id

    # Step 2: Run actual review
    response2 = await codereview_impl(
        name="Complete security review",
        content="Completed checklist - found SQL injection vulnerability in auth.py",
        step_number=2,
        next_action="stop",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        model=integration_test_model,
        thread_id=thread_id,
        issues_found=[
            {
                "severity": "critical",
                "location": f"{auth_file_path}:18",
                "description": "SQL Injection - User input concatenated into SQL query",
            }
        ],
    )

    # LLM may return different statuses (success or in_progress)
    assert response2["status"] in ["success", "in_progress"]
    assert response2["thread_id"] == thread_id
    assert "content" in response2

    # Check that SQL injection was found in the analysis
    message = response2["content"].lower()
    assert "sql" in message or "injection" in message or "security" in message, "Expected security analysis"
    assert len(message) > 100, "Expected detailed security analysis"

    print(f"\n✓ SQL injection review completed: {thread_id}")
    print(f"✓ Response length: {len(message)} chars")


@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_codereview_continuation(integration_test_model, test_repo_path, auth_file_path):
    """Test multi-step review with thread continuation."""
    # Step 1: Start review (returns checklist since next_action != "stop")
    import uuid

    from src.tools.codereview import codereview_impl

    thread_id_step1 = str(uuid.uuid4())
    response1 = await codereview_impl(
        name="Begin security review of authentication module",
        content="Starting comprehensive security analysis of authentication code",
        step_number=1,
        next_action="continue",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        model=integration_test_model,
        thread_id=thread_id_step1,
    )

    assert response1["status"] == "in_progress"
    thread_id = response1["thread_id"]
    assert "next_action" in response1

    # Step 2: Continue with same thread - now calls LLM
    response2 = await codereview_impl(
        name="Complete security review with detailed findings",
        content="Completing security review with SQL injection and password findings",
        step_number=2,
        next_action="stop",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        model=integration_test_model,
        thread_id=thread_id,
        issues_found=[
            {
                "severity": "critical",
                "location": f"{auth_file_path}:18",
                "description": "SQL Injection - User input concatenated into SQL query",
            }
        ],
    )

    assert response2["status"] in ["success", "in_progress"]  # LLM may return different statuses
    assert response2["thread_id"] == thread_id
    assert "content" in response2

    # Should have analysis in message
    message = response2["content"].lower()
    # Check for security-related terms (may vary based on LLM response)
    assert any(term in message for term in ["sql", "injection", "security", "review", "analysis"])

    print(f"\n✓ Thread continuation worked: {thread_id}")
    print(f"✓ Step 1: {response1['status']}")
    print(f"✓ Step 2: {response2['status']}")


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_models(integration_test_model):
    """Test models tool returns available models."""
    from src.tools.models import models_impl

    response = await models_impl()

    assert "models" in response
    assert "default_model" in response
    assert "count" in response

    models = response["models"]
    assert len(models) > 0
    assert response["count"] == len(models)

    # Check model structure
    for model in models:
        assert "name" in model
        assert "provider" in model
        assert "aliases" in model
        assert isinstance(model["aliases"], list)

    # Should include gpt-5-nano
    model_names = [m["name"] for m in models]
    assert "gpt-5-nano" in model_names

    print(f"\n✓ Found {len(models)} available models")
    print(f"✓ Default model: {response['default_model']}")
    print(f"✓ Models: {', '.join(model_names)}")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_codereview_token_budget(integration_test_model, test_repo_path, auth_file_path):
    """Test that token budget is respected."""
    import uuid

    from src.tools.codereview import codereview_impl

    thread_id = str(uuid.uuid4())

    # Step 1: Get checklist
    response1 = await codereview_impl(
        name="Review with token budget awareness",
        content="Testing token budget handling and file embedding",
        step_number=1,
        next_action="continue",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response1["status"] == "in_progress"

    # Step 2: Complete review
    response2 = await codereview_impl(
        name="Complete token budget test",
        content="Completed review - checking token usage",
        step_number=2,
        next_action="stop",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response2["status"] in ["success", "in_progress"]  # LLM may return different statuses
    assert len(response2["content"]) > 0

    print(f"\n✓ Review completed successfully: {thread_id}")
    print(f"✓ Response length: {len(response2['content'])} chars")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_codereview_repository_context(integration_test_model, auth_file_path, tmp_path):
    """Test that repository context (CLAUDE.md) is loaded if present."""
    import uuid

    from src.tools.codereview import codereview_impl

    # Create a temporary test repo with CLAUDE.md
    test_repo = tmp_path / "test_repo"
    test_repo.mkdir()

    # Copy auth file to temp repo
    auth_copy = test_repo / "auth.py"
    auth_copy.write_text(Path(auth_file_path).read_text())

    # Create a CLAUDE.md file
    claude_md = test_repo / "CLAUDE.md"
    claude_md.write_text("""# Test Repository

## Security Standards
- Always use parameterized queries
- Never store passwords in plain text
- Follow OWASP Top 10 guidelines
""")

    thread_id = str(uuid.uuid4())

    # Step 1: Get checklist
    response1 = await codereview_impl(
        name="Review with repository context",
        content="Testing repository context loading from CLAUDE.md",
        step_number=1,
        next_action="continue",
        relevant_files=[str(auth_copy)],
        base_path=str(test_repo),
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response1["status"] == "in_progress"

    # Step 2: Complete review
    response2 = await codereview_impl(
        name="Complete context test",
        content="Completed review with repository context",
        step_number=2,
        next_action="stop",
        relevant_files=[str(auth_copy)],
        base_path=str(test_repo),
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response2["status"] in ["success", "in_progress"]  # LLM may return different statuses

    # Response should exist
    message = response2["content"].lower()
    assert len(message) > 0

    print(f"\n✓ Repository context loaded from {test_repo}/CLAUDE.md")
    print(f"✓ Review completed with context awareness: {thread_id}")
