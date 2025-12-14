"""Request/response logging utilities for debugging."""

import logging

from multi_mcp.utils.context import get_thread_id
from multi_mcp.utils.log_helpers import write_log_file

logger = logging.getLogger(__name__)


def log_llm_interaction(
    request_data: dict,
    response_data: dict,
) -> None:
    """Log LLM request/response to file for debugging.

    Args:
        request_data: Request information (model, messages, temperature, etc.)
        response_data: Response from LLM (content, usage, model, etc.)

    Note:
        thread_id is automatically retrieved from request context.
    """
    thread_id = get_thread_id()

    log_data = {
        "thread_id": thread_id,
        "request": request_data,
        "response": response_data,
    }

    filepath = write_log_file(log_data, "llm", thread_id)

    if filepath:
        logger.debug(f"[REQUEST_LOGGER] Saved interaction to {filepath}")
    else:
        logger.warning("[REQUEST_LOGGER] Failed to log interaction")
