"""Compare tool schema models."""

from pydantic import Field

from src.config import settings
from src.schemas.base import MultiToolRequest, MultiToolResponse


class CompareRequest(MultiToolRequest):
    """Chat request for side-by-side model compare."""

    models: list[str] = Field(
        default_factory=lambda: settings.default_model_list,
        min_length=2,
        description=f"List of LLM models to run in parallel (minimum 2) (will use default models ({settings.default_model_list}) if not specified)",
    )


class CompareResponse(MultiToolResponse):
    """Response with side-by-side compare results."""

    pass  # Inherits results: list[ModelResponse] from MultiToolResponse
