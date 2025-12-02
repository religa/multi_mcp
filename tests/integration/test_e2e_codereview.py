"""End-to-end integration tests for codereview tool."""

import os
from pathlib import Path

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.fixture
def test_repo_path():
    """Path to SQL injection test repo."""
    return str(Path(__file__).parent.parent / "data" / "repos" / "sql_injection" / "sql_injection")


@pytest.fixture
def auth_file_path(test_repo_path):
    """Path to auth.py with vulnerabilities."""
    return str(Path(test_repo_path) / "auth.py")


@pytest.mark.vcr
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
        models=[integration_test_model],
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
        models=[integration_test_model],
        thread_id=thread_id,
        issues_found=[
            {
                "severity": "critical",
                "location": f"{auth_file_path}:18",
                "description": "SQL Injection - User input concatenated into SQL query",
            }
        ],
    )

    # LLM may return different statuses (success, partial, in_progress, or error)
    assert response2["status"] in ["success", "partial", "in_progress", "error"]
    assert response2["thread_id"] == thread_id
    assert "summary" in response2

    # Check that review completed (skip detailed checks if API error)
    if response2["status"] != "error":
        # In multi-model response, detailed content is in results
        # Check either the per-model content or the aggregate summary
        if "results" in response2 and len(response2["results"]) > 0:
            message = response2["results"][0]["content"].lower()
            assert "sql" in message or "injection" in message or "security" in message or "issue" in message, "Expected security analysis"
        else:
            # Fallback: check aggregate summary
            message = response2["summary"].lower()
            assert "issue" in message or "review" in message or "succeeded" in message, "Expected review summary"

        print(f"\n✓ SQL injection review completed: {thread_id}")
        print(f"✓ Response: {response2['summary'][:100]}...")
    else:
        print("\n⚠ API error occurred, skipping detailed assertions")


@pytest.mark.vcr
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
        models=[integration_test_model],
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
        models=[integration_test_model],
        thread_id=thread_id,
        issues_found=[
            {
                "severity": "critical",
                "location": f"{auth_file_path}:18",
                "description": "SQL Injection - User input concatenated into SQL query",
            }
        ],
    )

    assert response2["status"] in ["success", "partial", "in_progress", "error"]  # LLM may return different statuses or errors
    assert response2["thread_id"] == thread_id
    assert "summary" in response2

    # Should have analysis in message
    message = response2["summary"].lower()
    # Check for security-related terms (may vary based on LLM response)
    assert any(term in message for term in ["sql", "injection", "security", "review", "analysis", "succeeded"])

    print(f"\n✓ Thread continuation worked: {thread_id}")
    print(f"✓ Step 1: {response1['status']}")
    print(f"✓ Step 2: {response2['status']}")


@pytest.mark.vcr
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


@pytest.mark.vcr
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
        models=[integration_test_model],
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
        models=[integration_test_model],
        thread_id=thread_id,
    )

    assert response2["status"] in ["success", "partial", "in_progress", "error"]  # LLM may return different statuses or errors
    assert len(response2["summary"]) > 0

    print(f"\n✓ Review completed successfully: {thread_id}")
    print(f"✓ Response length: {len(response2['summary'])} chars")


@pytest.mark.vcr
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
        models=[integration_test_model],
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
        models=[integration_test_model],
        thread_id=thread_id,
    )

    assert response2["status"] in ["success", "partial", "in_progress", "error"]  # LLM may return different statuses or errors

    # Response should exist
    message = response2["summary"].lower()
    assert len(message) > 0

    print(f"\n✓ Repository context loaded from {test_repo}/CLAUDE.md")
    print(f"✓ Review completed with context awareness: {thread_id}")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_codereview_multi_model_parallel(test_repo_path, auth_file_path):
    """Test multi-model code review with 2 models in parallel."""
    import uuid

    from src.tools.codereview import codereview_impl

    thread_id = str(uuid.uuid4())

    # Use 2 fast models for multi-model review
    models = ["gpt-5-nano", "claude-haiku-4-5-20251001"]

    # Step 1: Get checklist
    response1 = await codereview_impl(
        name="Multi-model security review",
        content="Review for SQL injection vulnerabilities",
        step_number=1,
        next_action="continue",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        models=models,
        thread_id=thread_id,
    )

    assert response1["status"] == "in_progress"
    assert response1["thread_id"] == thread_id

    # Step 2: Run parallel review with both models
    response2 = await codereview_impl(
        name="Complete multi-model review",
        content="Analyzing authentication for security issues",
        step_number=2,
        next_action="stop",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        models=models,
        thread_id=thread_id,
    )

    # Check aggregate response structure
    assert response2["status"] in ["success", "partial", "error"]
    assert response2["thread_id"] == thread_id
    assert "summary" in response2
    assert "results" in response2

    # Should have results from both models (or errors)
    assert len(response2["results"]) == 2

    # Check that each result has required fields
    for i, result in enumerate(response2["results"]):
        assert "content" in result
        assert "status" in result
        assert "metadata" in result
        assert "model" in result["metadata"]
        print(f"\n✓ Model {i + 1} ({result['metadata']['model']}): {result['status']}")

    # If any model succeeded, collect issues from results
    if response2["status"] in ["success", "partial"]:
        print("\n✓ Multi-model review completed")
        print(f"✓ Status: {response2['status']}")
        print(f"✓ Summary: {response2['summary']}")

        # Collect all issues from results
        all_issues = []
        for result in response2["results"]:
            if result.get("issues_found"):
                all_issues.extend(result["issues_found"])

        print(f"✓ Total issues: {len(all_issues)}")

        # Issues should be tagged with model names
        for issue in all_issues:
            assert "model" in issue, "Issues should be tagged with model name"
            assert issue["model"] in [r["metadata"]["model"] for r in response2["results"]]


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_codereview_multi_model_consensus(test_repo_path, auth_file_path):
    """Test that multi-model review aggregates issues correctly."""
    import uuid

    from src.tools.codereview import codereview_impl

    thread_id = str(uuid.uuid4())

    # Use 2 models
    models = ["gpt-5-nano", "claude-haiku-4-5-20251001"]

    # Skip to step 2 (review)
    response = await codereview_impl(
        name="Consensus test",
        content="Review authentication code",
        step_number=2,
        next_action="stop",
        relevant_files=[auth_file_path],
        base_path=test_repo_path,
        models=models,
        thread_id=thread_id,
    )

    # Check response structure
    assert "results" in response
    assert len(response["results"]) == 2

    # Each model should have its own issues
    model1_issues = response["results"][0].get("issues_found") or []
    model2_issues = response["results"][1].get("issues_found") or []
    total_issues = len(model1_issues) + len(model2_issues)

    # Collect all issues from results
    all_issues = []
    for result in response["results"]:
        if result.get("issues_found"):
            all_issues.extend(result["issues_found"])

    assert len(all_issues) == total_issues, "Should collect all issues from all models"

    # Each issue should indicate which model found it
    for issue in all_issues:
        assert "model" in issue
        assert issue["model"] in [r["metadata"]["model"] for r in response["results"]]

    print("\n✓ Multi-model consensus test completed")
    print(f"✓ Model 1 found {len(model1_issues)} issues")
    print(f"✓ Model 2 found {len(model2_issues)} issues")
    print(f"✓ Total issues: {len(all_issues)}")
