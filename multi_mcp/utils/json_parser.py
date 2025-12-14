"""Robust JSON extraction and parsing for LLM responses.

This module provides utilities to extract and parse JSON from LLM responses
that may contain markdown formatting, comments, or other non-standard JSON.
"""

import json
import re
from typing import Any

_CODE_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

_ANALYSIS_BLOCK_RE = re.compile(r"<analysis>[\s\S]*?</analysis>", re.IGNORECASE)

_COMMENT_RE = re.compile(
    r"""
    //.*?$           |   # line comments
    /\*[\s\S]*?\*/       # block comments
    """,
    re.MULTILINE | re.VERBOSE,
)

_UNQUOTED_KEY_RE = re.compile(r"(?P<prefix>[{\[,]\s*)(?P<key>[A-Za-z_][A-Za-z0-9_\-]*)(?P<suffix>\s*:)")

_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')

_SMART_QUOTES = {
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',  # double quotes
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",  # single quotes
}


def _strip_code_fences(s: str) -> str:
    """Strip markdown code fences from string.

    Handles both complete fences (```json ... ```) and unclosed fences
    where the LLM was cut off mid-response (```json ...).

    IMPORTANT: Uses greedy matching to handle nested code fences inside JSON strings.
    For example, if the JSON contains a "fix" field with code snippets that have their
    own ```python ... ``` fences, we want to match the OUTERMOST fences, not the first
    closing ``` we encounter.
    """
    # Use greedy matching (.*?) to get content between outermost fences
    # This handles nested code fences inside JSON strings
    greedy_pattern = re.compile(r"```(?:json|JSON)?\s*([\s\S]*)\s*```\s*$", re.IGNORECASE)
    m = greedy_pattern.search(s)
    if m:
        return m.group(1)

    # Fallback: try non-greedy if greedy didn't work
    m = _CODE_FENCE_RE.search(s)
    if m:
        return m.group(1)

    # Check for unclosed fence (opening ``` but no closing ```)
    unclosed_match = re.search(r"```(?:json|JSON)?\s*([\s\S]+)", s, re.IGNORECASE)
    if unclosed_match:
        return unclosed_match.group(1)

    return s


def _strip_analysis_blocks(s: str) -> str:
    """Remove <analysis>...</analysis> blocks from string."""
    return re.sub(_ANALYSIS_BLOCK_RE, "", s)


def _strip_comments(s: str) -> str:
    """Remove line and block comments from string."""
    return re.sub(_COMMENT_RE, "", s)


def _normalize_quotes(s: str) -> str:
    """Replace smart quotes with standard quotes."""
    for k, v in _SMART_QUOTES.items():
        s = s.replace(k, v)
    return s


def _convert_single_to_double_quotes(s: str) -> str:
    """Convert single-quoted strings to double-quoted strings.

    JSON requires double quotes for strings. This handles LLM responses
    that use single quotes instead.

    Approach:
    - Find single-quoted strings (handling escaped quotes inside)
    - Replace outer single quotes with double quotes
    - Escape any unescaped double quotes inside the string
    """
    result = []
    i = 0
    length = len(s)

    while i < length:
        # Check if we're at the start of a single-quoted string
        if s[i] == "'":
            # Collect the string content
            string_start = i
            i += 1
            string_content = []
            escaped = False

            while i < length:
                if escaped:
                    # After escape, add the char literally
                    string_content.append(s[i])
                    escaped = False
                elif s[i] == "\\":
                    # Escape sequence - keep the backslash
                    string_content.append("\\")
                    escaped = True
                elif s[i] == "'":
                    # End of single-quoted string
                    # Escape any unescaped double quotes in the content
                    content_str = "".join(string_content)
                    # Replace unescaped " with \"
                    content_str = content_str.replace('"', '\\"')
                    # Build double-quoted string
                    result.append('"' + content_str + '"')
                    i += 1
                    break
                else:
                    string_content.append(s[i])
                i += 1
            else:
                # Unclosed single quote - just keep original
                result.append(s[string_start:i])
        else:
            result.append(s[i])
            i += 1

    return "".join(result)


def _mask_strings(s: str) -> tuple[str, dict[str, str]]:
    """Mask string literals with placeholders to protect during repairs.

    This prevents regex-based repairs from corrupting content inside JSON strings.
    For example, URLs with '//' won't be treated as comments, and literal words
    like 'None' won't be replaced with 'null'.

    Returns:
        tuple of (masked_string, placeholder_map)
    """
    strings = {}
    counter = 0

    def replace_string(match):
        nonlocal counter
        placeholder = f"@STR_{counter}@"
        strings[placeholder] = match.group(0)
        counter += 1
        return placeholder

    masked = _STRING_RE.sub(replace_string, s)
    return masked, strings


def _unmask_strings(s: str, strings: dict[str, str]) -> str:
    """Restore masked string literals.

    Args:
        s: String with placeholders
        strings: Map of placeholders to original strings

    Returns:
        String with original string literals restored
    """
    for placeholder, original in strings.items():
        s = s.replace(placeholder, original)
    return s


def _extract_first_json_block(s: str) -> str | None:
    """Extract first JSON object or array from string.

    Handles nested braces/brackets and string escaping.
    """
    starts = [(s.find("{"), "{"), (s.find("["), "[")]
    starts = [(i, ch) for i, ch in starts if i != -1]
    if not starts:
        return None

    start, opener = min(starts, key=lambda x: x[0])
    closer = "}" if opener == "{" else "]"

    depth = 0
    in_str = False
    esc = False
    quote_char = ""

    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                quote_char = c
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
    return None


def _repair_json(s: str) -> str:
    """Repair common JSON formatting issues.

    Handles:
    - Comments
    - Smart quotes
    - Single-quoted strings
    - Python/JavaScript literals
    - Unquoted keys
    - Trailing commas
    - Invalid escape sequences

    Uses string masking to protect string literal content from corruption
    during regex-based repairs.
    """
    # Basic cleanup
    s = s.strip()
    s = s.lstrip("\ufeff")

    # Normalize smart quotes before masking (safe to run on everything)
    s = _normalize_quotes(s)

    # Convert single-quoted strings to double-quoted strings
    s = _convert_single_to_double_quotes(s)

    # Mask string literals to protect their content during repairs
    masked, string_map = _mask_strings(s)

    # Apply repairs on masked content (won't corrupt string internals)
    masked = _strip_comments(masked)

    # Convert Python/JS literals to JSON (only outside strings)
    masked = re.sub(r"\bNone\b", "null", masked)
    masked = re.sub(r"\bTrue\b", "true", masked)
    masked = re.sub(r"\bFalse\b", "false", masked)
    masked = re.sub(r"\bundefined\b", "null", masked)
    masked = re.sub(r"\bNaN\b", "null", masked)
    masked = re.sub(r"\bInfinity\b", "1e9999", masked)
    masked = re.sub(r"\b-Infinity\b", "-1e9999", masked)

    # Fix unquoted keys and trailing commas (structural repairs)
    masked = re.sub(_UNQUOTED_KEY_RE, r'\g<prefix>"\g<key>"\g<suffix>', masked)
    masked = re.sub(_TRAILING_COMMA_RE, r"\1", masked)

    # Restore original string literals
    s = _unmask_strings(masked, string_map)

    # Fix invalid escape sequences (including inside strings)
    # JSON only allows: \" \\ \/ \b \f \n \r \t \uXXXX
    # Replace \' with ' (single quotes don't need escaping in JSON)
    s = s.replace("\\'", "'")
    # Replace other invalid escapes by removing the backslash
    # Match backslash followed by any char that's NOT a valid escape
    s = re.sub(r'\\([^"\\\/bfnrtu])', r"\1", s)

    return s


def parse_llm_json(text: str) -> Any | None:
    """Parse JSON from LLM response with robust error handling.

    Tries to extract and parse JSON from text that may contain:
    - Markdown code fences
    - Surrounding text
    - Comments
    - Non-standard JSON formatting

    Args:
        text: Raw text from LLM response

    Returns:
        Parsed JSON object/array, or None if parsing fails
    """
    if not isinstance(text, str) or not text.strip():
        return None

    raw = _strip_analysis_blocks(text)
    raw = _strip_code_fences(raw)
    candidate = raw.strip()

    if not (candidate.startswith("{") or candidate.startswith("[")):
        block = _extract_first_json_block(candidate)
        if block is None:
            return None
        candidate = block

    try:
        return json.loads(candidate)
    except Exception:
        pass

    repaired = _repair_json(candidate)
    try:
        return json.loads(repaired)
    except Exception:
        return None
