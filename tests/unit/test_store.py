"""Unit tests for conversation store."""

import pytest

from multi_mcp.memory.store import Message, add_messages, get_messages, get_thread_store, store_conversation_turn


@pytest.mark.asyncio
async def test_add_and_get_messages():
    """Test basic storage and retrieval."""
    messages: list[Message] = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]
    await add_messages("thread-1", messages)

    retrieved = await get_messages("thread-1")
    assert len(retrieved) == 2
    assert retrieved[0]["content"] == "Hello"
    assert retrieved[1]["content"] == "Hi!"


@pytest.mark.asyncio
async def test_get_nonexistent_thread():
    """Test retrieving from nonexistent thread returns empty list."""
    retrieved = await get_messages("nonexistent-thread")
    assert retrieved == []


@pytest.mark.asyncio
async def test_thread_isolation():
    """Test threads don't leak into each other."""
    await add_messages("thread-a", [{"role": "user", "content": "A"}])
    await add_messages("thread-b", [{"role": "user", "content": "B"}])

    msgs_a = await get_messages("thread-a")
    msgs_b = await get_messages("thread-b")

    assert len(msgs_a) == 1
    assert msgs_a[0]["content"] == "A"
    assert len(msgs_b) == 1
    assert msgs_b[0]["content"] == "B"


@pytest.mark.asyncio
async def test_empty_messages_list():
    """Test adding empty messages list is a no-op."""
    await add_messages("thread-empty", [])
    retrieved = await get_messages("thread-empty")
    # Should return empty since no messages were added
    assert len(retrieved) == 0


@pytest.mark.asyncio
async def test_message_mutation_protection():
    """Test that returned messages are copies (mutation protection)."""
    original: list[Message] = [{"role": "user", "content": "Original"}]
    await add_messages("thread-mut", original)

    retrieved = await get_messages("thread-mut")
    retrieved[0]["content"] = "Modified"

    # Original should be unchanged
    retrieved_again = await get_messages("thread-mut")
    assert retrieved_again[0]["content"] == "Original"


@pytest.mark.asyncio
async def test_multiple_adds_to_same_thread():
    """Test multiple add operations append correctly."""
    await add_messages("thread-multi", [{"role": "user", "content": "First"}])
    await add_messages("thread-multi", [{"role": "assistant", "content": "Second"}])
    await add_messages("thread-multi", [{"role": "user", "content": "Third"}])

    retrieved = await get_messages("thread-multi")
    assert len(retrieved) == 3
    assert retrieved[0]["content"] == "First"
    assert retrieved[1]["content"] == "Second"
    assert retrieved[2]["content"] == "Third"


@pytest.mark.asyncio
async def test_get_thread_store():
    """Test direct ThreadStore access."""
    store = await get_thread_store("thread-direct")
    assert store.thread_id == "thread-direct"
    assert len(store.messages) == 0

    # Same store should be returned on second call
    store2 = await get_thread_store("thread-direct")
    assert store is store2


@pytest.mark.asyncio
async def test_concurrent_access():
    """Test concurrent access to same thread is safe."""
    import asyncio

    async def add_msg(content: str):
        await add_messages("thread-concurrent", [{"role": "user", "content": content}])

    # Add 10 messages concurrently
    await asyncio.gather(*[add_msg(f"Message {i}") for i in range(10)])

    retrieved = await get_messages("thread-concurrent")
    assert len(retrieved) == 10
    # All messages should be present (order may vary due to concurrency)
    contents = {msg["content"] for msg in retrieved}
    assert len(contents) == 10  # All unique


@pytest.mark.asyncio
async def test_store_conversation_turn_first_call():
    """Test storing first conversation turn (with system prompt)."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
    ]
    assistant_response = "Hi there!"

    await store_conversation_turn("thread-first", messages, assistant_response)

    retrieved = await get_messages("thread-first")
    assert len(retrieved) == 3
    assert retrieved[0]["role"] == "system"
    assert retrieved[0]["content"] == "You are a helpful assistant"
    assert retrieved[1]["role"] == "user"
    assert retrieved[1]["content"] == "Hello"
    assert retrieved[2]["role"] == "assistant"
    assert retrieved[2]["content"] == "Hi there!"


@pytest.mark.asyncio
async def test_store_conversation_turn_continuation():
    """Test storing continuation turn (without system prompt)."""
    # First, add initial conversation
    await add_messages(
        "thread-cont",
        [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
        ],
    )

    # Now test continuation
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "First message"},
        {"role": "assistant", "content": "First response"},
        {"role": "user", "content": "Second message"},
    ]
    assistant_response = "Second response"

    await store_conversation_turn("thread-cont", messages, assistant_response)

    retrieved = await get_messages("thread-cont")
    assert len(retrieved) == 5  # 3 initial + 2 new
    assert retrieved[3]["role"] == "user"
    assert retrieved[3]["content"] == "Second message"
    assert retrieved[4]["role"] == "assistant"
    assert retrieved[4]["content"] == "Second response"
