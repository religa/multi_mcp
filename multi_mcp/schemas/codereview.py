"""CodeReview schema models."""

from pydantic import Field

from multi_mcp.schemas.base import ModelResponse, MultiToolRequest, MultiToolResponse


class CodeReviewRequest(MultiToolRequest):
    """Multi-model code review request (single-model supported via models=[default])."""

    content: str = Field(
        ...,
        description=(
            "Your code review request for the expert reviewer. "
            "Step 1: Describe the project and define review objectives and focus areas. "
            "Step 2+: Report findings organized by quality, security, performance, architecture. "
            "Include: what to review, focus areas (security/concurrency/logic), specific concerns, confidence level. "
            "Exclude: code snippets (use `relevant_files`), issue lists (use `issues_found`)."
        ),
    )
    issues_found: list[dict] | None = Field(
        default=None,
        description=(
            "REQUIRED: List of issues identified with severity levels, locations, and detailed descriptions. "
            "IMPORTANT: This list is CUMULATIVE across steps. Include ALL issues found in previous steps PLUS new ones. "
            "Each dict must contain these keys: "
            "'severity' (required, one of: 'critical', 'high', 'medium', 'low'), "
            "'location' (required, format: 'filename:line_number' or 'filename' if line unknown), "
            "'description' (required, detailed explanation of the issue). "
            "Example: [{'severity': 'high', 'location': 'auth.py:45', "
            "'description': 'SQL injection vulnerability in login query - user input not sanitized'}]. "
            "Empty list is acceptable if no issues found yet."
        ),
    )


class CodeReviewModelResult(ModelResponse):
    """Individual model's code review result."""

    issues_found: list[dict] | None = Field(
        default=None,
        description=("Issues found by this specific model. Each issue is tagged with 'model' field for identification."),
    )


class CodeReviewResponse(MultiToolResponse):
    """Aggregated multi-model code review response."""

    results: list[CodeReviewModelResult] = Field(
        default_factory=list,
        description="Individual model responses with per-model issues (tagged with 'model' field)",
    )
