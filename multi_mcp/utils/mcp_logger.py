"""MCP tool request/response logging."""

import logging
from typing import Any

from multi_mcp.utils.context import get_thread_id
from multi_mcp.utils.log_helpers import write_log_file

logger = logging.getLogger(__name__)


def log_mcp_interaction(
    direction: str,
    tool_name: str,
    data: dict[str, Any],
) -> None:
    """Log MCP tool request or response to file for debugging.

    Args:
        direction: "request" or "response"
        tool_name: Name of MCP tool (e.g., "codereview", "models")
        data: Request parameters or response data

    Note:
        thread_id is automatically retrieved from request context.

    Creates log file: logs/TIMESTAMP.THREAD_ID.mcp.json
    """
    thread_id = get_thread_id()

    log_data = {
        "direction": direction,
        "tool_name": tool_name,
        "thread_id": thread_id,
        "data": data,
    }

    filepath = write_log_file(log_data, "mcp", thread_id)

    if filepath:
        logger.debug(f"[MCP_LOG] {direction} {tool_name} -> {filepath.name}")
    else:
        logger.warning(f"[MCP_LOG] Failed to log {direction} for {tool_name}")
