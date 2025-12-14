"""Tests for request context management (ContextVars)."""

import asyncio

import pytest

from multi_mcp.utils.context import (
    clear_context,
    get_base_path,
    get_name,
    get_step_number,
    get_thread_id,
    get_workflow,
    set_request_context,
)


def test_context_defaults():
    """Test that context defaults to None when not set."""
    clear_context()
    assert get_thread_id() is None
    assert get_workflow() is None
    assert get_step_number() is None
    assert get_base_path() is None
    assert get_name() is None


def test_set_and_get_thread_id():
    """Test setting and getting thread_id."""
    clear_context()
    set_request_context(thread_id="test-thread-123")
    assert get_thread_id() == "test-thread-123"
    clear_context()
    assert get_thread_id() is None


def test_set_and_get_workflow():
    """Test setting and getting workflow."""
    clear_context()
    set_request_context(workflow="codereview")
    assert get_workflow() == "codereview"
    clear_context()
    assert get_workflow() is None


def test_set_and_get_step_number():
    """Test setting and getting step_number."""
    clear_context()
    set_request_context(step_number=5)
    assert get_step_number() == 5
    clear_context()
    assert get_step_number() is None


def test_set_and_get_base_path():
    """Test setting and getting base_path."""
    clear_context()
    set_request_context(base_path="/path/to/project")
    assert get_base_path() == "/path/to/project"
    clear_context()
    assert get_base_path() is None


def test_set_and_get_name():
    """Test setting and getting name."""
    clear_context()
    set_request_context(name="Test Request")
    assert get_name() == "Test Request"
    clear_context()
    assert get_name() is None


def test_set_all_context_values():
    """Test setting all context values at once."""
    clear_context()
    set_request_context(
        thread_id="thread-456",
        workflow="chat",
        step_number=3,
        base_path="/home/user/repo",
        name="Test Step",
    )
    assert get_thread_id() == "thread-456"
    assert get_workflow() == "chat"
    assert get_step_number() == 3
    assert get_base_path() == "/home/user/repo"
    assert get_name() == "Test Step"
    clear_context()


def test_partial_context_update():
    """Test updating context values partially."""
    clear_context()
    # Set initial values
    set_request_context(thread_id="thread-1", workflow="compare")
    assert get_thread_id() == "thread-1"
    assert get_workflow() == "compare"
    assert get_base_path() is None

    # Update only base_path (others should remain)
    set_request_context(base_path="/new/path")
    assert get_thread_id() == "thread-1"  # Still set
    assert get_workflow() == "compare"  # Still set
    assert get_base_path() == "/new/path"  # Now set

    clear_context()


def test_context_overwrite():
    """Test that setting context again overwrites previous values."""
    clear_context()
    set_request_context(base_path="/old/path")
    assert get_base_path() == "/old/path"

    set_request_context(base_path="/new/path")
    assert get_base_path() == "/new/path"

    clear_context()


def test_clear_context():
    """Test that clear_context resets all values to None."""
    set_request_context(
        thread_id="test",
        workflow="debate",
        step_number=10,
        base_path="/some/path",
        name="Clear Test",
    )
    # Verify all set
    assert get_thread_id() == "test"
    assert get_workflow() == "debate"
    assert get_step_number() == 10
    assert get_base_path() == "/some/path"
    assert get_name() == "Clear Test"

    # Clear and verify all None
    clear_context()
    assert get_thread_id() is None
    assert get_workflow() is None
    assert get_step_number() is None
    assert get_base_path() is None
    assert get_name() is None


@pytest.mark.asyncio
async def test_context_isolation_between_async_tasks():
    """Test that ContextVars are isolated between async tasks."""
    results = []

    async def task1():
        set_request_context(thread_id="task1", base_path="/task1/path")
        await asyncio.sleep(0.01)  # Yield control
        results.append({"task": "task1", "thread_id": get_thread_id(), "base_path": get_base_path()})
        clear_context()

    async def task2():
        set_request_context(thread_id="task2", base_path="/task2/path")
        await asyncio.sleep(0.01)  # Yield control
        results.append({"task": "task2", "thread_id": get_thread_id(), "base_path": get_base_path()})
        clear_context()

    # Run tasks concurrently
    await asyncio.gather(task1(), task2())

    # Verify each task saw its own context
    assert len(results) == 2
    task1_result = next(r for r in results if r["task"] == "task1")
    task2_result = next(r for r in results if r["task"] == "task2")

    assert task1_result["thread_id"] == "task1"
    assert task1_result["base_path"] == "/task1/path"
    assert task2_result["thread_id"] == "task2"
    assert task2_result["base_path"] == "/task2/path"


@pytest.mark.asyncio
async def test_context_propagates_to_nested_async_calls():
    """Test that context propagates correctly to nested async function calls."""
    clear_context()

    async def inner_function():
        # Should see context from outer
        return {
            "thread_id": get_thread_id(),
            "base_path": get_base_path(),
        }

    async def outer_function():
        set_request_context(thread_id="outer-123", base_path="/outer/path")
        result = await inner_function()
        clear_context()
        return result

    result = await outer_function()
    assert result["thread_id"] == "outer-123"
    assert result["base_path"] == "/outer/path"


def test_set_none_values_does_not_change_context():
    """Test that setting None values doesn't change existing context."""
    clear_context()
    set_request_context(thread_id="test", base_path="/path")

    # Try to set None values
    set_request_context(thread_id=None, base_path=None)

    # Context should remain unchanged
    assert get_thread_id() == "test"
    assert get_base_path() == "/path"

    clear_context()
