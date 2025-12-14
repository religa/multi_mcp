"""Shared logging utilities for MCP and LLM interactions."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from multi_mcp.utils.paths import LOGS_DIR

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]")


def write_log_file(
    log_data: dict[str, Any],
    log_type: str,
    thread_id: str | None = None,
) -> Path | None:
    """Write log data to timestamped JSON file.

    Args:
        log_data: Data to log (will have timestamp added)
        log_type: Log type suffix (e.g., "mcp" or "llm")
        thread_id: Optional thread ID for correlation

    Returns:
        Path to created file, or None on error

    Creates log file: logs/TIMESTAMP.THREAD_ID.{log_type}.json
    """
    try:
        # Generate filename with timestamp and thread_id
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
        safe_id = _SAFE_ID_RE.sub("", thread_id) if thread_id else ""
        thread_part = f".{safe_id}" if safe_id else ""
        filename = f"{timestamp}{thread_part}.{log_type}.json"
        filepath = LOGS_DIR / filename

        # Add timestamp to log data
        log_data["timestamp"] = datetime.now(UTC).isoformat()

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        return filepath
    except Exception:
        return None
