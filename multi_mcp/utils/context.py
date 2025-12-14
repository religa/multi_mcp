"""Request context management using contextvars.

This module provides thread-safe (async-safe) context storage for request-scoped
data like thread_id, workflow, and step_number. This eliminates the need to pass
these values through every function call for logging purposes.

The context is automatically set at request entry (via mcp_decorator) and cleared
after request completion.

Example:
    # At request entry (in decorator):
    set_request_context(thread_id="abc-123", workflow="codereview", step_number=1)

    # Anywhere in the call stack:
    thread_id = get_thread_id()  # Returns "abc-123"

    # After request completes (in decorator):
    clear_context()
"""

from contextvars import ContextVar

# Thread-safe context variables
# These work correctly with async/await - each async task gets its own context
_current_thread_id: ContextVar[str | None] = ContextVar("current_thread_id", default=None)
_current_workflow: ContextVar[str | None] = ContextVar("current_workflow", default=None)
_current_step: ContextVar[int | None] = ContextVar("current_step", default=None)
_current_base_path: ContextVar[str | None] = ContextVar("current_base_path", default=None)
_current_name: ContextVar[str | None] = ContextVar("current_name", default=None)


def set_request_context(
    thread_id: str | None = None,
    workflow: str | None = None,
    step_number: int | None = None,
    base_path: str | None = None,
    name: str | None = None,
) -> None:
    """Set request context for logging (called at request entry point).

    Args:
        thread_id: Unique request/thread identifier
        workflow: Workflow name (e.g., "codereview", "chat", "compare")
        step_number: Current step number in multi-step workflows
        base_path: Base directory path for the project
        name: Request/step name (e.g., "Initial Analysis", "Security Review")
    """
    if thread_id is not None:
        _current_thread_id.set(thread_id)
    if workflow is not None:
        _current_workflow.set(workflow)
    if step_number is not None:
        _current_step.set(step_number)
    if base_path is not None:
        _current_base_path.set(base_path)
    if name is not None:
        _current_name.set(name)


def get_thread_id() -> str | None:
    """Get current thread_id from context (for logging).

    Returns:
        Thread ID string, or None if not set
    """
    return _current_thread_id.get()


def get_workflow() -> str | None:
    """Get current workflow from context.

    Returns:
        Workflow name string, or None if not set
    """
    return _current_workflow.get()


def get_step_number() -> int | None:
    """Get current step number from context.

    Returns:
        Step number integer, or None if not set
    """
    return _current_step.get()


def get_base_path() -> str | None:
    """Get current base_path from context.

    Returns:
        Base path string, or None if not set
    """
    return _current_base_path.get()


def get_name() -> str | None:
    """Get current request/step name from context.

    Returns:
        Name string, or None if not set
    """
    return _current_name.get()


def clear_context() -> None:
    """Clear all context variables (called after request completes).

    This ensures context doesn't leak between requests.
    Should be called in a finally block to guarantee cleanup.
    """
    _current_thread_id.set(None)
    _current_workflow.set(None)
    _current_step.set(None)
    _current_base_path.set(None)
    _current_name.set(None)
