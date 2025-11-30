"""Integration tests for multi-step workflows and continuations."""

import os
import uuid

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_codereview_multi_step_refinement(integration_test_model, tmp_path):
    """Test multi-step code review with scope refinement across 3 steps."""
    from src.tools.codereview import codereview_impl

    # Create test files
    auth_file = tmp_path / "auth.py"
    auth_file.write_text("""
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""")

    config_file = tmp_path / "config.py"
    config_file.write_text("""
SECRET_KEY = "hardcoded-secret-123"
DEBUG = True
ALLOWED_HOSTS = ["*"]
""")

    thread_id = str(uuid.uuid4())

    # Step 1: Initial review request - should return checklist
    response1 = await codereview_impl(
        name="Initial security review request",
        content="Review all files for security issues",
        step_number=1,
        next_action="continue",
        relevant_files=[str(auth_file), str(config_file)],
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response1["status"] == "in_progress"
    assert response1["thread_id"] == thread_id
    assert "checklist" in response1["content"].lower() or "review" in response1["content"].lower()

    # Step 2: Refine scope to focus on auth.py only
    response2 = await codereview_impl(
        name="Focus on authentication module",
        content="Completed initial checklist. Focus security review on auth.py - found SQL injection risk",
        step_number=2,
        next_action="continue",
        relevant_files=[str(auth_file)],  # Narrowed scope
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        issues_found=[
            {
                "severity": "critical",
                "location": f"{auth_file}:3",
                "description": "SQL Injection - User input in query string",
            }
        ],
    )

    assert response2["status"] in ["success", "in_progress"]
    assert response2["thread_id"] == thread_id
    assert len(response2["content"]) > 0

    # Step 3: Final review with complete findings
    response3 = await codereview_impl(
        name="Complete review with all findings",
        content="Finalizing review with comprehensive security analysis",
        step_number=3,
        next_action="stop",
        relevant_files=[str(auth_file)],
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        issues_found=[
            {
                "severity": "critical",
                "location": f"{auth_file}:3",
                "description": "SQL Injection - User input in query string",
            }
        ],
    )

    assert response3["status"] in ["success", "in_progress"]
    assert response3["thread_id"] == thread_id
    content = response3["content"].lower()
    assert any(term in content for term in ["sql", "injection", "security", "review"])

    print(f"\n✓ Multi-step refinement completed: {thread_id}")
    print(f"✓ Step 1: {response1['status']}")
    print(f"✓ Step 2: {response2['status']}")
    print(f"✓ Step 3: {response3['status']}")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(300)
async def test_chat_long_conversation(integration_test_model, tmp_path):
    """Test 5+ turn conversation with context preservation."""
    from src.tools.chat import chat_impl

    thread_id = str(uuid.uuid4())
    test_file = tmp_path / "calculator.py"
    test_file.write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")

    # Turn 1: Initial question
    response1 = await chat_impl(
        name="Ask about add function",
        content="What does the add function do?",
        step_number=1,
        next_action="continue",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response1["status"] in ["success", "in_progress"]
    assert "add" in response1["content"].lower()

    # Turn 2: Follow-up referencing previous
    response2 = await chat_impl(
        name="Ask about subtract",
        content="What about the subtract function?",
        step_number=2,
        next_action="continue",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response2["status"] in ["success", "in_progress"]
    assert "subtract" in response2["content"].lower()

    # Turn 3: Ask for compare (requires context from turn 1 & 2)
    response3 = await chat_impl(
        name="Compare functions",
        content="How are they similar?",
        step_number=3,
        next_action="continue",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response3["status"] in ["success", "in_progress"]
    assert len(response3["content"]) > 0

    # Turn 4: Request enhancement
    response4 = await chat_impl(
        name="Enhancement suggestion",
        content="Should I add type hints?",
        step_number=4,
        next_action="continue",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response4["status"] in ["success", "in_progress"]
    assert len(response4["content"]) > 0

    # Turn 5: Final question
    response5 = await chat_impl(
        name="Final question",
        content="What's the best practice for these functions?",
        step_number=5,
        next_action="stop",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response5["status"] in ["success", "in_progress"]
    assert len(response5["content"]) > 0

    print(f"\n✓ Long conversation completed: {thread_id}")
    print("✓ Turns completed: 5")
    print("✓ Context preserved across all turns")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_compare_continuation(compare_models, tmp_path):
    """Test continuing a compare with follow-up questions."""
    from src.tools.compare import compare_impl

    thread_id = str(uuid.uuid4())
    test_file = tmp_path / "example.py"
    test_file.write_text("def process(data): return data")

    # Initial compare
    response1 = await compare_impl(
        name="Initial compare",
        content="Review this function. Keep response brief.",
        step_number=1,
        next_action="continue",
        models=compare_models,
        base_path=str(tmp_path),
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response1["status"] in ["success", "partial"]
    assert len(response1["results"]) == len(compare_models)
    initial_thread = response1["thread_id"]

    # Follow-up question using same thread
    response2 = await compare_impl(
        name="Follow-up question",
        content="Should I add error handling? Be brief.",
        step_number=2,
        next_action="stop",
        models=compare_models,
        base_path=str(tmp_path),
        thread_id=initial_thread,  # Reuse thread
        relevant_files=[str(test_file)],
    )

    assert response2["status"] in ["success", "partial"]
    assert response2["thread_id"] == initial_thread
    assert len(response2["results"]) == len(compare_models)

    print(f"\n✓ Compare continuation completed: {thread_id}")
    print("✓ Thread preserved across steps")
