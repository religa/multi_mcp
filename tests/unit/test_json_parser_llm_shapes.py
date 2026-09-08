"""Real-world LLM output shapes that defeated parse_llm_json.

Three of these fail on main and pass with the fix; the rest are regression guards
for shapes that already worked and must keep working. The shapes were observed
while running Claude CLI and Codex CLI as `provider: cli` models against the
`codereview` tool; in every failing case the model produced a perfectly good
answer that the parser threw away, so the model was reported as
"Failed to parse LLM response as JSON" and contributed nothing to the review.
"""

import json

from multi_mcp.utils.json_parser import parse_llm_json

REVIEW = {"status": "success", "issues_found": [{"id": "A1", "severity": "high"}]}


def test_valid_json_envelope_containing_a_fenced_block_is_returned_untouched():
    """Claude CLI's --output-format json envelope.

    The envelope is valid JSON; its "result" string holds an escaped ```json
    block. The greedy fence stripper used to match into that escaped block and
    shred the envelope, so the parser returned None.
    """
    envelope = {
        "type": "result",
        "result": "Here is the review:\n```json\n" + json.dumps(REVIEW) + "\n```",
        "duration_ms": 1234,
    }
    parsed = parse_llm_json(json.dumps(envelope))
    assert isinstance(parsed, dict)
    assert parsed["result"] == envelope["result"]


def test_prose_then_fenced_json():
    text = "## ANALYSIS\n\nSome prose.\n\n```json\n" + json.dumps(REVIEW) + "\n```"
    assert parse_llm_json(text) == REVIEW


def test_fenced_json_followed_by_more_prose():
    """Trailing prose after the closing fence.

    This one already works on main (the non-greedy fallback finds the block when
    there is only one fence pair). Kept as a regression guard, since the fix
    changes the order in which fenced blocks are tried.
    """
    text = ("## ANALYSIS\n```json\n" + json.dumps(REVIEW) + "\n```\n\n"
            "**One last thought:** finding A1 is the important one.")
    assert parse_llm_json(text) == REVIEW


def test_code_block_before_the_json_block():
    """A ```python block first: a JSON-looking fragment could be scavenged out of
    it, so the parser "succeeded" with the wrong value and never read the real
    ```json block."""
    text = ("## ANALYSIS\n```python\n"
            "BAD = [1, 2, 3]\n"
            "def f(x):\n    return {'a': x}\n```\n"
            "Result:\n```json\n" + json.dumps(REVIEW) + "\n```\n")
    parsed = parse_llm_json(text)
    assert isinstance(parsed, dict), f"expected dict, got {type(parsed).__name__}"
    assert parsed == REVIEW


def test_plain_json_and_plain_text_are_unchanged():
    assert parse_llm_json(json.dumps(REVIEW)) == REVIEW
    assert parse_llm_json("no json here at all") is None
    assert parse_llm_json("") is None


def test_extract_issue_list_accepts_schema_aliases():
    """Models diverge on the issue-list key; all shapes carry the same dicts."""
    from multi_mcp.tools.codereview import _extract_issue_list

    issues = [{"id": "A1", "severity": "high", "location": "app.py:6"}]
    assert _extract_issue_list({"issues_found": issues}) == issues
    assert _extract_issue_list({"verified_findings": issues}) == issues
    assert _extract_issue_list({"verdict": "block", "findings": issues}) == issues
    assert _extract_issue_list({"issues_found": []}) == []
    assert _extract_issue_list({"something_else": issues}) == []
