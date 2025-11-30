"""End-to-end integration tests for chat tool."""

import os

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_basic_conversation(integration_test_model):
    """Test basic chat interaction with real API."""
    import uuid

    from src.tools.chat import chat_impl

    thread_id = str(uuid.uuid4())

    response = await chat_impl(
        name="Basic chat test",
        content="What is 2 + 2? Answer in one sentence.",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "in_progress"]
    assert response["thread_id"] == thread_id
    assert "content" in response
    assert len(response["content"]) > 0

    # Should mention 4 or "four"
    content = response["content"].lower()
    assert "4" in content or "four" in content, f"Expected answer to contain '4', got: {content}"

    print(f"\n✓ Basic chat test completed: {thread_id}")
    print(f"✓ Response: {response['content'][:100]}...")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_chat_with_conversation_history(integration_test_model):
    """Test chat maintains context across multiple turns."""
    import uuid

    from src.tools.chat import chat_impl

    thread_id = str(uuid.uuid4())

    # Step 1: Establish context
    response1 = await chat_impl(
        name="First message",
        content="My favorite color is blue. Remember this.",
        step_number=1,
        next_action="continue",
        base_path="/tmp",
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response1["status"] in ["success", "in_progress"]
    assert response1["thread_id"] == thread_id

    # Step 2: Ask follow-up that requires Step 1 context
    response2 = await chat_impl(
        name="Second message",
        content="What is my favorite color? Answer in one word.",
        step_number=2,
        next_action="stop",
        base_path="/tmp",
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response2["status"] in ["success", "in_progress"]
    assert response2["thread_id"] == thread_id
    assert "content" in response2

    # Should remember blue from first message
    content = response2["content"].lower()
    assert "blue" in content, f"Expected chat to remember 'blue', got: {content}"

    print(f"\n✓ Conversation history test completed: {thread_id}")
    print(f"✓ Step 1: {response1['content'][:50]}...")
    print(f"✓ Step 2: {response2['content'][:50]}...")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_with_files(integration_test_model, tmp_path):
    """Test chat can analyze provided files."""
    import uuid

    from src.tools.chat import chat_impl

    # Create test file
    test_file = tmp_path / "example.py"
    test_file.write_text("""def calculate_area(radius):
    '''Calculate circle area.'''
    return 3.14159 * radius * radius
""")

    thread_id = str(uuid.uuid4())

    response = await chat_impl(
        name="Analyze file",
        content="What does the function in the file do? Answer in one sentence.",
        step_number=1,
        next_action="stop",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(test_file)],
    )

    assert response["status"] in ["success", "in_progress"]
    assert response["thread_id"] == thread_id
    assert "content" in response

    # Should mention circle/area/radius
    content = response["content"].lower()
    assert any(word in content for word in ["circle", "area", "radius"]), f"Expected function description, got: {content}"

    print(f"\n✓ File analysis test completed: {thread_id}")
    print(f"✓ Response: {response['content'][:100]}...")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_repository_context(integration_test_model, tmp_path):
    """Test chat loads CLAUDE.md context."""
    import uuid

    from src.tools.chat import chat_impl

    # Create repo with CLAUDE.md
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("""# Project Guidelines

## Code Style
- Always use type hints
- Maximum line length: 140 characters
- Use async/await for I/O operations
""")

    thread_id = str(uuid.uuid4())

    response = await chat_impl(
        name="Ask about guidelines",
        content="What is the maximum line length for this project? Answer with just the number.",
        step_number=1,
        next_action="stop",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
    )

    assert response["status"] in ["success", "in_progress"]
    assert response["thread_id"] == thread_id
    assert "content" in response

    # Should mention 140 from CLAUDE.md
    content = response["content"].lower()
    assert "140" in content, f"Expected '140' from CLAUDE.md context, got: {content}"

    print(f"\n✓ Repository context test completed: {thread_id}")
    print(f"✓ Response: {response['content'][:100]}...")
