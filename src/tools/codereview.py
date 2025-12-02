"""Code review tool implementation with multi-model support."""

import logging
from typing import Literal

from src.prompts import CODEREVIEW_PROMPT
from src.schemas.base import NextAction
from src.schemas.codereview import CodeReviewModelResult, CodeReviewResponse
from src.utils.json_parser import parse_llm_json
from src.utils.message_builder import MessageBuilder
from src.utils.prompts import build_expert_context

logger = logging.getLogger(__name__)


async def codereview_impl(
    name: str,
    content: str,
    step_number: int,
    next_action: Literal["continue", "stop"],
    base_path: str,
    models: list[str],
    thread_id: str,
    relevant_files: list[str] | None = None,
    issues_found: list[dict] | None = None,
) -> dict:
    """Code review implementation with multi-model parallelism and conversation history support."""
    logger.info(f"[CODEREVIEW] {name} - step {step_number}, models={len(models)}, files={len(relevant_files or [])}")

    # Step 1: Return checklist
    if step_number == 1:
        logger.info(f"[CODEREVIEW] Starting new review {thread_id} - providing checklist")
        checklist_content = """# Code Review Checklist - Step 1

Complete this checklist, then call step 2 with your findings and relevant_files.

## Checklist:
- Read and understand the code base
- Read and understand the relevant files specified
- Map out main modules, classes and functions
- Verify intended behavior and business logic
- Check architecture, structure and design patterns
- Look for bugs, security risks and performance issues
- Identify code smells and maintainability problems
- Add files to `relevant_files` list

**Next**: Set `next_action='continue'` and `step_number=2` with findings in `content` and files in `relevant_files`."""

        result = CodeReviewResponse(
            status="in_progress",
            thread_id=thread_id,
            summary=checklist_content,
            next_action=NextAction(action="continue", reason="Complete checklist, then proceed to step 2"),
        )
        return result.model_dump(exclude_none=True)

    # Validate files
    if not relevant_files:
        logger.info(f"[CODEREVIEW] No relevant files provided at step {step_number}")
        result = CodeReviewResponse(
            status="in_progress",
            thread_id=thread_id,
            summary=(
                "⚠️ **No relevant files provided**\n\n"
                "To continue the code review, you must:\n"
                "1. Identify the files you want reviewed\n"
                "2. Add their absolute paths to the `relevant_files` parameter\n"
                "3. Include project documentation (README.md, CLAUDE.md) for context\n\n"
                "Example:\n"
                "```\nrelevant_files=[\n"
                "  '/path/to/project/README.md',\n"
                "  '/path/to/project/src/main.py',\n"
                "  '/path/to/project/tests/test_main.py'\n"
                "]\n```"
            ),
            next_action=NextAction(
                action="continue",
                reason="Add file paths to `relevant_files` parameter and retry with the same step_number",
            ),
        )
        return result.model_dump(exclude_none=True)

    logger.info(f"[CODEREVIEW] Executing parallel review with {len(models)} models")

    expert_context = build_expert_context(content=content, issues_found=issues_found)

    # Build messages with conversation history (same for all models)
    messages = await (
        MessageBuilder(
            system_prompt=CODEREVIEW_PROMPT,
            base_path=base_path,
            thread_id=thread_id,
            include_history=True,
        )
        .add_conversation_history()  # Check for existing history
        .add_repository_context()  # Skip if continuation
        .add_files(relevant_files)  # Skip if continuation
        .add_user_message(expert_context, escape_html=False)  # Already formatted XML
        .build()
    )

    # Execute in parallel
    from src.utils.llm_runner import execute_parallel

    raw_results = await execute_parallel(
        models=models,
        messages=messages,
    )

    # Store conversation (use first successful response)
    from src.memory.store import store_conversation_turn

    for result in raw_results:
        if result.status == "success":
            await store_conversation_turn(thread_id, messages, result.content)
            break

    # Parse and aggregate results
    parsed_results: list[CodeReviewModelResult] = []
    all_issues: list[dict] = []
    success_count = 0
    needs_files_count = 0

    for result in raw_results:
        if result.status == "error":
            # Keep error responses
            parsed_results.append(
                CodeReviewModelResult(
                    content=result.error or "Unknown error",
                    status="error",
                    error=result.error,
                    metadata=result.metadata,
                )
            )
            continue

        # Parse JSON response
        parsed_json = parse_llm_json(result.content)

        # Handle parse errors explicitly
        if not parsed_json or not isinstance(parsed_json, dict):
            parsed_results.append(
                CodeReviewModelResult(
                    content=result.content,
                    status="error",
                    error="Failed to parse LLM response as JSON",
                    metadata=result.metadata,
                )
            )
            continue

        status = parsed_json.get("status")

        # Extract issues and tag with model name
        model_issues: list[dict] = []
        if status == "review_complete" and "issues_found" in parsed_json:
            model_issues = parsed_json.get("issues_found", [])
        elif status == "no_issues_found":
            model_issues = []

        # Tag issues with model name for traceability
        for issue in model_issues:
            issue["model"] = result.metadata.model

        all_issues.extend(model_issues)

        # Track statuses for consensus
        if status in ["files_required_to_continue", "focused_review_required"]:
            needs_files_count += 1
        elif status in ["no_issues_found", "review_complete"]:
            success_count += 1

        # Create model result
        parsed_results.append(
            CodeReviewModelResult(
                content=result.content,
                status="success",
                metadata=result.metadata,
                issues_found=model_issues if model_issues is not None else None,
            )
        )

    # Determine aggregate status
    total_models = len(models)
    successful_models = sum(1 for r in parsed_results if r.status == "success")

    if successful_models == total_models:
        aggregate_status = "success"
    elif successful_models > 0:
        aggregate_status = "partial"
    else:
        aggregate_status = "error"

    # Consensus next_action: if ANY model needs files, action = continue
    if needs_files_count > 0:
        # Override status to indicate work is not done
        aggregate_status = "in_progress"
        next_action_obj = NextAction(
            action="continue",
            reason=f"{needs_files_count}/{total_models} models requested additional files for review",
        )
    else:
        next_action_obj = NextAction(
            action="stop",
            reason="All models completed their review",
        )

    # Build aggregate summary with stats
    issue_count = len(all_issues)
    if issue_count == 0:
        # Check if review actually succeeded before claiming "no issues"
        if needs_files_count > 0:
            aggregate_summary = f"{successful_models}/{total_models} models succeeded. Review paused - additional files required."
        elif aggregate_status == "success":
            aggregate_summary = f"{successful_models}/{total_models} models succeeded. No issues found."
        else:
            # Review failed or partially failed - don't claim success
            aggregate_summary = f"{successful_models}/{total_models} models succeeded. Review incomplete - no issues reported."
    else:
        # Group by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for issue in all_issues:
            sev = issue.get("severity", "low")
            if sev in by_severity:
                by_severity[sev].append(issue)

        severity_parts = []
        for sev in ["critical", "high", "medium", "low"]:
            count = len(by_severity[sev])
            if count > 0:
                severity_parts.append(f"{count} {sev}")

        aggregate_summary = (
            f"{successful_models}/{total_models} models succeeded. "
            f"Found {issue_count} issue(s): {', '.join(severity_parts)}. "
            f"See `results` for details."
        )

    logger.info(f"[CODEREVIEW] Complete: {successful_models}/{total_models} models succeeded, {issue_count} total issues found")

    result = CodeReviewResponse(
        thread_id=thread_id,
        status=aggregate_status,
        summary=aggregate_summary,
        results=parsed_results,
        next_action=next_action_obj,
    )

    return result.model_dump(exclude_none=True)
