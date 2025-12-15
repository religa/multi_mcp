"""Base schema models for all tools."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from multi_mcp.settings import settings


class ModelResponseMetadata(BaseModel):
    """Metadata about the model execution."""

    model: str = Field(..., description="Canonical model name used for analysis")
    prompt_tokens: int = Field(default=0, description="Tokens in the prompt")
    completion_tokens: int = Field(default=0, description="Tokens in the completion")
    total_tokens: int = Field(default=0, description="Total tokens used")
    latency_ms: int = Field(default=0, description="LLM call latency in milliseconds")
    artifacts: list[str] | None = Field(
        default=None,
        description="Absolute paths to saved artifact files (markdown, JSON, etc.) if artifacts are enabled",
    )
    source_models: list[str] | None = Field(
        default=None,
        description=(
            "List of source model names that contributed to consolidated result. "
            "Only populated for consolidated responses from consolidate_model_results(). "
            "Regular single-model or multi-model responses leave this as None."
        ),
    )
    consolidation_model: str | None = Field(
        default=None,
        description=(
            "Model used to perform consolidation (e.g., 'gpt-5-mini'). "
            "Only populated for consolidated responses from consolidate_model_results(). "
            "None indicates no consolidation was performed."
        ),
    )

    @classmethod
    def error_metadata(cls, model: str = "unknown", latency_ms: int = 0) -> "ModelResponseMetadata":
        """Create metadata for error responses with zero values."""
        return cls(model=model, prompt_tokens=0, completion_tokens=0, total_tokens=0, latency_ms=latency_ms)


# =============================================================================
# Request Schemas
# =============================================================================


class BaseToolRequest(BaseModel):
    """Base request for all workflow tools (no model field)."""

    thread_id: str | None = Field(
        None,
        description=(
            "Thread ID to continue previous conversation and preserve context. "
            "WHEN TO USE:\n"
            "- None/omit: Starting a brand new review or chat session (step_number=1)\n"
            "- Provide thread_id: Continuing a multi-step workflow from a previous response (step_number>1)\n"
            "The thread_id is returned in every response - save it and reuse it for follow-up steps. "
        ),
    )

    name: str = Field(..., description="Step name (e.g., 'Initial Analysis', 'Security Review')")
    content: str = Field(
        ...,
        description=(
            "Your question to the AI Assistant. "
            "Provide detailed context: your goal, what you've tried, what worked, any specific challenges. "
            "IMPORTANT: Always include paths to relevant files in `relevant_files` - do NOT skip this step."
        ),
    )
    step_number: int = Field(..., ge=1, description="Current step")
    next_action: Literal["continue", "stop"] = Field(..., description="Recommended next action: 'continue' to proceed, 'stop' to end")
    base_path: str = Field(
        ...,
        description="Absolute path to project root to id the project and load project files",
    )
    relevant_files: list[str] | None = Field(
        default=None,
        description=(
            f"Absolute paths of ALL files relevant to this question (up to {settings.max_files_per_review} files). "
            "CRITICAL: For project-level questions (features, architecture, design), you MUST include project documentation "
            "(README.md, docs/, architecture diagrams). "
            "For code-specific questions, include the implementation files, related modules, tests, and configs. "
            "Example 1: 'What feature should we build?' → Include README.md, src/server.py, config/*.*, tests/. "
            "Example 2: 'Review this function' → Include the file with the function, related modules, tests, and documentation."
        ),
    )

    @field_validator("relevant_files")
    @classmethod
    def validate_file_count(cls, v: list[str] | None) -> list[str] | None:
        """Validate that file count doesn't exceed maximum."""
        if v is not None and len(v) > settings.max_files_per_review:
            raise ValueError(
                f"Too many files provided ({len(v)}). Maximum allowed is {settings.max_files_per_review} files per request. "
                f"Please reduce the scope and try again with fewer files."
            )
        return v

    @property
    def workflow_name(self) -> str:
        """Derive workflow name from class name."""
        class_name = self.__class__.__name__
        if class_name.endswith("Request"):
            class_name = class_name[:-7]  # len("Request") = 7
        return class_name.lower()


class SingleToolRequest(BaseToolRequest):
    """Request for single-model tools (e.g., codereview, chat)."""

    model: str = Field(default=settings.default_model, description=f"LLM Model name to use (default: {settings.default_model})")


class MultiToolRequest(BaseToolRequest):
    """Request for multi-model parallel execution (e.g., compare, codereview)."""

    models: list[str] = Field(
        default_factory=lambda: settings.default_model_list,
        min_length=1,
        description=f"List of LLM models to run in parallel (minimum 1) (will use default models ({settings.default_model_list}) if not specified)",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class NextAction(BaseModel):
    """Server suggestion for next step."""

    action: Literal["continue", "stop"] = Field(
        ...,
        description=(
            "Suggested action:\n"
            "- 'continue': Proceed with next step (step_number+1) with current scope\n"
            "- 'stop': Review is complete, no further action needed"
        ),
    )
    reason: str = Field(..., description="Why this action is suggested and what the client should do next")


class ModelResponse(BaseModel):
    """Base response from any model call. Model info is in metadata.model."""

    content: str = Field(..., description="LLM response content")
    status: Literal["success", "warning", "error"] = Field(
        ..., description="Model call status: 'success' (succeeded), 'warning' (succeeded with issues), 'error' (failed)"
    )
    error: str | None = Field(default=None, description="Error/warning message if status is 'error' or 'warning'")
    metadata: ModelResponseMetadata = Field(..., description="Execution metadata (contains model name, tokens, latency)")

    @classmethod
    def error_response(cls, error: str | None = None, content: str = "", model: str = "unknown", latency_ms: int = 0) -> "ModelResponse":
        """Create an error response with default values."""
        if error is None:
            error = "Unknown error"

        return cls(
            content=content,
            status="error",
            error=error,
            metadata=ModelResponseMetadata.error_metadata(model=model, latency_ms=latency_ms),
        )


class SingleToolResponse(ModelResponse):
    """Response from single-model tools (chat, codereview)."""

    thread_id: str = Field(..., description="Thread identifier")
    status: Literal["success", "in_progress", "error"] = Field(..., description="Response status")
    next_action: NextAction | None = Field(default=None, description="Server hint for next step")

    @classmethod
    def error_response(
        cls, thread_id: str, error: str | None = None, content: str = "", next_action=None, metadata: ModelResponseMetadata | None = None
    ) -> "ModelResponse":
        """Create an error response with default values."""
        if metadata is None:
            metadata = ModelResponseMetadata.error_metadata()
        if error is None:
            error = "Unknown error"
        return cls(
            thread_id=thread_id,
            content=content,
            status="error",
            next_action=next_action,
            error=error,
            metadata=metadata,
        )


class MultiToolResponse(BaseModel):
    """Response from multi-model parallel execution."""

    thread_id: str = Field(..., description="Thread identifier")
    summary: str = Field(..., description="Execution summary (e.g., '2/3 models succeeded')")
    results: list[ModelResponse] = Field(..., description="Individual model responses")
    status: Literal["success", "in_progress", "partial", "error"] = Field(
        ...,
        description="Overall status: 'success' (all succeeded), 'in_progress' (some still running), 'partial' (some failed), 'error' (all failed)",
    )
    next_action: NextAction | None = Field(default=None, description="Server hint for next step")
