"""Unified artifact saving utility.

This module provides artifact saving functionality for LLM responses,
handling both context retrieval and file operations.
"""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from multi_mcp.constants import ARTIFACT_NAME_MAX_LENGTH, ARTIFACT_NAME_MAX_WORDS
from multi_mcp.schemas.base import ModelResponse
from multi_mcp.settings import settings

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def generate_filename(
    name: str,
    workflow: str,
    model: str,
    step_number: int | None = None,
    extension: str = "md",
) -> str:
    """Generate artifact filename following convention."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_slug = slugify(name)
    model_slug = slugify(model)

    name_parts = name_slug.split("-")
    if name_parts and name_parts[0] == workflow:
        name_parts = name_parts[1:]
        name_slug = "-".join(name_parts) if name_parts else "request"

    # Shorten name to first N words (max M chars)
    name_words = name_slug.split("-")[:ARTIFACT_NAME_MAX_WORDS]
    name_slug = "-".join(name_words)[:ARTIFACT_NAME_MAX_LENGTH].rstrip("-")

    parts = [name_slug, workflow, model_slug, timestamp]

    filename = "-".join(parts) + f".{extension}"
    return filename


async def save_artifact_files(
    base_path: str,
    name: str,
    workflow: str,
    model: str,
    content: str | None,
    issues_found: list[dict] | None,
    metadata: dict[str, Any],
    step_number: int | None = None,
) -> list[Path]:
    """
    Save LLM response artifacts to disk.

    Args:
        base_path: Project base path
        name: Request name
        workflow: Workflow type (codereview, debate, etc.)
        model: Model name
        content: LLM response content (for .md file)
        issues_found: List of issues (for .json file)
        metadata: Pre-built metadata dict
        step_number: Optional step number

    Returns:
        List of created file paths (empty if artifacts disabled)
    """
    if not settings.artifacts_dir:
        return []

    base = Path(base_path).resolve()
    artifacts_sub = Path(settings.artifacts_dir)

    if artifacts_sub.is_absolute():
        # Use absolute path directly
        artifacts_path = artifacts_sub.resolve()
    else:
        # Resolve relative to base_path and validate it doesn't escape
        artifacts_path = (base / artifacts_sub).resolve()
        try:
            artifacts_path.relative_to(base)
        except ValueError as exc:
            raise ValueError("ARTIFACTS_DIR escapes base_path") from exc

    artifacts_path.mkdir(parents=True, exist_ok=True)

    created_files: list[Path] = []

    if content:
        md_filename = generate_filename(name, workflow, model, step_number, "md")
        md_path = artifacts_path / md_filename

        md_content = f"{content}\n\n---\n```yaml\n"
        md_content += yaml.dump({"metadata": metadata}, default_flow_style=False, sort_keys=False)
        md_content += "```"

        md_path.write_text(md_content, encoding="utf-8")
        created_files.append(md_path)

    if issues_found:
        json_filename = generate_filename(name, workflow, model, step_number, "json")
        json_path = artifacts_path / json_filename

        json_data = {
            "issues_found": issues_found,
            "metadata": metadata,
        }

        json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
        created_files.append(json_path)

    return created_files


async def save_tool_artifacts(
    response: ModelResponse,
) -> list[str] | None:
    """Save artifacts for a tool execution and return artifact paths.

    This is the single source of truth for artifact saving across all tools.
    All metadata (workflow, name, step_number, thread_id, base_path) is
    automatically retrieved from request context.

    Args:
        response: ModelResponse with content and metadata

    Returns:
        List of artifact file paths (as strings) if saving succeeded, None otherwise
    """
    from multi_mcp.utils.context import get_base_path, get_name, get_step_number, get_thread_id, get_workflow

    # Get all required context values
    base_path = get_base_path()
    workflow = get_workflow()
    name = get_name()
    step_number = get_step_number()
    thread_id = get_thread_id()

    # Validate required context
    if not base_path:
        logger.warning("[ARTIFACTS] No base_path in context, skipping artifact save")
        return None
    if not workflow or not name or step_number is None:
        logger.warning(
            f"[ARTIFACTS] Missing required context (workflow={workflow}, name={name}, step_number={step_number}), skipping artifact save"
        )
        return None
    if response.status != "success" or not response.content:
        return None

    artifact_metadata = {
        "thread_id": thread_id,
        "workflow": workflow,
        "step_number": step_number,
        "model": response.metadata.model,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "usage": {
            "prompt_tokens": response.metadata.prompt_tokens or 0,
            "completion_tokens": response.metadata.completion_tokens or 0,
            "total_tokens": response.metadata.total_tokens or 0,
        },
        "duration_ms": response.metadata.latency_ms or 0,
    }

    try:
        artifact_paths = await save_artifact_files(
            base_path=base_path,
            name=name,
            workflow=workflow,
            model=response.metadata.model,
            content=response.content,
            issues_found=None,  # Issues are embedded in response content
            metadata=artifact_metadata,
            step_number=step_number,
        )
    except Exception as e:
        logger.error(f"[ARTIFACTS] Failed to save artifacts: {e}")
        return None

    if artifact_paths:
        # Return relative paths from base_path
        base = Path(base_path).resolve()
        return [str(p.relative_to(base)) for p in artifact_paths]

    return None
