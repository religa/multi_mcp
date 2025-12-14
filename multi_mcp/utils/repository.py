"""Repository context utilities for expert analysis."""

import logging
from pathlib import Path

from multi_mcp.utils.context import get_base_path

logger = logging.getLogger(__name__)


def build_repository_context(base_path: str | None = None) -> str | None:
    """Build REPOSITORY_CONTEXT from CLAUDE.md or AGENTS.md.

    Args:
        base_path: Optional base directory to search for context files.
                   If not provided, falls back to context value from request.

    Returns:
        Repository context string with XML tags, or None if no context found
    """
    # Use explicit param if provided, otherwise fall back to context
    base_path = base_path or get_base_path()

    if not base_path:
        logger.debug("[REPO_CONTEXT] No base_path provided, skipping repository context")
        return None

    path = Path(base_path)
    if not path.exists():
        logger.warning(f"[REPO_CONTEXT] base_path does not exist: {base_path}")
        return None

    # Find context file
    context_file = None
    for filename in ["CLAUDE.md", "AGENTS.md"]:
        file_path = path / filename
        if file_path.exists():
            context_file = file_path
            logger.debug(f"[REPO_CONTEXT] Found context file: {filename}")
            break

    if not context_file:
        logger.debug(f"[REPO_CONTEXT] No CLAUDE.md or AGENTS.md found in {base_path}")
        return None

    try:
        content = context_file.read_text(encoding="utf-8").strip()
        logger.info(f"[REPO_CONTEXT] Loaded {context_file.name}: {len(content)} chars")

        result = "\n".join(
            [
                "<REPOSITORY_CONTEXT>",
                f'<PROJECT_INSTRUCTIONS source="{context_file.name}">',
                content,
                "</PROJECT_INSTRUCTIONS>",
                "</REPOSITORY_CONTEXT>",
            ]
        )

        return result

    except Exception as e:
        logger.error(f"[REPO_CONTEXT] Failed to read {context_file}: {e}")
        return None
