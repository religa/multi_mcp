"""Prompt building utilities."""

import logging

logger = logging.getLogger(__name__)


def build_issues_section(issues_found: list[dict]) -> str:
    """Build issues section with severity.

    Args:
        issues_found: List of issue dictionaries

    Returns:
        XML-formatted issues section
    """
    if not issues_found or len(issues_found) == 0:
        return "<ISSUES_IDENTIFIED>\nNo issues identified yet.\n</ISSUES_IDENTIFIED>"

    parts = ["<ISSUES_IDENTIFIED>"]

    for issue in issues_found:
        severity = issue.get("severity", "unknown")
        file_path = issue.get("file", issue.get("location", "unknown"))
        line = issue.get("line", "")
        description = issue.get("description", "No description")
        parts.append(f'<issue severity="{severity}" file="{file_path}" line="{line}">')
        parts.append(description)
        parts.append("</issue>")

    parts.append("</ISSUES_IDENTIFIED>")
    return "\n".join(parts)


def build_expert_context(
    content: str,
    issues_found: list[dict] | None,
) -> str:
    """Build expert context for code review (stateless).

    Note: Repository context and files are handled by MessageBuilder.
    This only builds review-specific XML sections.

    Args:
        content: Code review request content/message
        issues_found: Issues list (optional)

    Returns:
        XML-formatted expert context
    """
    parts = []

    # 1. Current request
    parts.append(f"<CODE_REVIEW_REQUEST>\n{content}\n</CODE_REVIEW_REQUEST>")

    # 2. Issues
    parts.append(build_issues_section(issues_found or []))

    # 3. Task instructions
    parts.append("""<TASK>
As the Principal Engineer acting as a Quality Gate, perform the following strictly ordered workflow:

1. **CONTEXTUALIZATION**:
    - Read <REPOSITORY_CONTEXT> to understand the codebase if available
    - Review <CODE_REVIEW_REQUEST> to understand objectives and scope

2. **VERIFICATION**: Iterate through <ISSUES_IDENTIFIED>
   - For each issue: validate with precise code references
   - Confirm real issues, adjust severity if needed
   - Discard false positives with evidence

3. **DISCOVERY**: Deep static analysis of <EDITABLE_FILES> for missed issues:
   - Concurrency: race conditions, deadlocks, atomicity violations
   - Security: injection, hardcoded secrets, weak hashing, improper auth
   - Error Handling: swallowed exceptions, leaking stack traces
   - Type Safety: missing imports, type mismatches
   - Resource Management: unclosed files/sessions/connections
   - Cross-File Integrity: verify signatures match, handle failure modes
   - Architecture: over-engineering, bottlenecks, missing abstractions
   - Stress Simulations: null/empty, wrong type, extreme size, attacker input

4. **REMEDIATION**: For every confirmed issue, provide minimal safe fix

5. **OUTPUT**: Provide analysis block, then JSON result
</TASK>""")

    return "\n\n".join(parts)
