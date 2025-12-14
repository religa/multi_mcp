"""System prompts loaded from markdown files."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Prompts directory
_PROMPTS_DIR = Path(__file__).parent


def _load_prompt(filename: str) -> str:
    """Load prompt from markdown file."""
    path = _PROMPTS_DIR / filename
    try:
        content = path.read_text(encoding="utf-8").strip()
        return content
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {path}")
        raise


CODEREVIEW_PROMPT = _load_prompt("codereview.md")
CODEREVIEW_CONSOLIDATION_PROMPT = _load_prompt("codereview-consolidation.md")
CHAT_PROMPT = _load_prompt("chat.md")
COMPARE_PROMPT = _load_prompt("compare.md")
DEBATE_STEP1_PROMPT = _load_prompt("debate-step1.md")
DEBATE_STEP2_PROMPT = _load_prompt("debate-step2.md")


__all__ = [
    "CODEREVIEW_PROMPT",
    "CODEREVIEW_CONSOLIDATION_PROMPT",
    "CHAT_PROMPT",
    "COMPARE_PROMPT",
    "DEBATE_STEP1_PROMPT",
    "DEBATE_STEP2_PROMPT",
]
