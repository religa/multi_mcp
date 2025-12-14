"""Minimal thread-safe conversation storage."""

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TypedDict


class Message(TypedDict):
    """Single message in conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ThreadStore:
    """Storage for a single conversation thread."""

    thread_id: str
    messages: list[Message] = field(default_factory=list)


# Module-level state
_threads: dict[str, ThreadStore] = {}
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Get or create lock (lazy init in async context)."""
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def get_thread_store(thread_id: str) -> ThreadStore:
    """Get existing thread or create new empty one."""
    lock = _get_lock()
    async with lock:
        if thread_id not in _threads:
            _threads[thread_id] = ThreadStore(thread_id=thread_id)
        return _threads[thread_id]


async def add_messages(thread_id: str, messages: list[Message]) -> None:
    """Append messages to thread."""
    if not messages:
        return
    lock = _get_lock()
    async with lock:
        if thread_id not in _threads:
            _threads[thread_id] = ThreadStore(thread_id=thread_id)
        _threads[thread_id].messages.extend(messages)


async def get_messages(thread_id: str) -> list[Message]:
    """Get all messages for thread (returns deep copy)."""
    lock = _get_lock()
    async with lock:
        if thread_id not in _threads:
            return []
        return deepcopy(_threads[thread_id].messages)


async def store_conversation_turn(
    thread_id: str,
    messages: list[dict],
    assistant_response: str,
) -> None:
    """Store a conversation turn (messages + assistant response) in history.

    Args:
        thread_id: Thread identifier
        messages: Message list sent to LLM (can be [system, user] or [...history, user])
        assistant_response: Content of assistant's response

    Handles both first call (with system prompt) and continuations.
    """
    if len(messages) == 2 and messages[0]["role"] == "system":
        # First call - store system + user + assistant
        system_msg: Message = {"role": messages[0]["role"], "content": messages[0]["content"]}  # type: ignore[typeddict-item]
        user_msg: Message = {"role": messages[1]["role"], "content": messages[1]["content"]}  # type: ignore[typeddict-item]
        assistant_msg: Message = {"role": "assistant", "content": assistant_response}
        await add_messages(thread_id, [system_msg, user_msg, assistant_msg])
    else:
        # Continuation - just store new user + assistant
        user_msg: Message = {"role": messages[-1]["role"], "content": messages[-1]["content"]}  # type: ignore[typeddict-item]
        assistant_msg: Message = {"role": "assistant", "content": assistant_response}
        await add_messages(thread_id, [user_msg, assistant_msg])
