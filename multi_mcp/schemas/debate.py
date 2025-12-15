"""Debate tool schema models."""

from pydantic import Field

from multi_mcp.schemas.base import ModelResponse, MultiToolRequest, MultiToolResponse
from multi_mcp.settings import settings


class DebateRequest(MultiToolRequest):
    """Debate request - runs models in two steps: independent answers + debate."""

    models: list[str] = Field(
        default_factory=lambda: settings.default_model_list,
        min_length=2,
        description=f"List of LLM models to run in parallel (minimum 2) (will use default models ({settings.default_model_list}) if not specified)",
    )


class DebateResponse(MultiToolResponse):
    """Debate response with Step 1 (results) and Step 2 (step2_results)."""

    step2_results: list[ModelResponse] = Field(..., description="Step 2 debate responses where each model critiques Step 1 answers")
