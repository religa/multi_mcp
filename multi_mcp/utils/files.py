"""File handling utilities."""

import logging
import os

from multi_mcp.constants import BYTES_PER_KB
from multi_mcp.settings import settings
from multi_mcp.utils.paths import resolve_path

logger = logging.getLogger(__name__)


def is_binary_file(file_path: str) -> bool:
    """Check if file is binary (contains null bytes)."""
    try:
        with open(file_path, "rb") as f:
            return b"\x00" in f.read(4096)
    except OSError:
        return False


def embed_files_for_expert(files: list[str], base_path: str | None = None) -> str:
    """Embed file contents for expert analysis."""
    if not files:
        return "<EDITABLE_FILES>\nNo files to embed\n</EDITABLE_FILES>"

    max_size = settings.max_file_size_kb * BYTES_PER_KB
    embedded_parts = ["<EDITABLE_FILES>"]

    for file_path in files:
        try:
            resolved = resolve_path(file_path, base_path) if base_path else file_path
        except ValueError:
            continue

        try:
            if os.path.getsize(resolved) > max_size:
                continue
            if is_binary_file(resolved):
                continue
        except OSError:
            continue

        try:
            with open(resolved, encoding="utf-8") as f:
                lines = f.readlines()
            content = "\n".join(f"{i + 1:4d}│ {line.rstrip()}" for i, line in enumerate(lines))

            filename = os.path.basename(resolved)
            # Use realpath for both to handle symlinks consistently (e.g., /var -> /private/var on macOS)
            if base_path:
                resolved_base = os.path.realpath(base_path)
                resolved_file = os.path.realpath(resolved)
                relative_path = os.path.relpath(resolved_file, resolved_base)
            else:
                relative_path = file_path

            embedded_parts.append(f'<file path="{file_path}" relative_path="{relative_path}" filename="{filename}">\n{content}\n</file>\n')
        except Exception:
            continue

    embedded_parts.append("</EDITABLE_FILES>")
    return "\n".join(embedded_parts)
