"""Code review tool implementation with multi-model support."""

import logging
from collections import Counter
from typing import Literal

from multi_mcp.prompts import CODEREVIEW_PROMPT
from multi_mcp.schemas.base import NextAction
from multi_mcp.schemas.codereview import CodeReviewModelResult, CodeReviewResponse
from multi_mcp.utils.message_builder import MessageBuilder
from multi_mcp.utils.prompts import build_expert_context

logger = logging.getLogger(__name__)


def _count_issues_by_severity(issues: list[dict]) -> list[str]:
    """Count issues by severity and return formatted severity parts.

    Args:
        issues: List of issue dicts with 'severity' field

    Returns:
        List of formatted strings like ["5 critical", "3 high"]
    """
    return [f"{count} {sev}" for sev, count in Counter(issue.get("severity", "unknown") for issue in issues).items()]


def _build_model_status_summary(raw_results: list) -> str:
    """Build summary of which models succeeded/failed and why.

    Args:
        raw_results: List of model results with status and metadata

    Returns:
        Formatted string like "gpt-5-mini (3 issues), codex (TimeoutError), gemini-3 (5 issues)"

    Note:
        For errors, extracts the exception name from error strings (e.g., "AuthenticationError" from
        "litellm.AuthenticationError: Missing API key"). This keeps error messages concise and clear.
    """
    parts = []
    for result in raw_results:
        model = result.metadata.model
        if result.status == "success":
            # Count issues if available
            issues = getattr(result, "issues_found", None) or []
            issue_count = len(issues) if isinstance(issues, list) else 0
            parts.append(f"{model} ({issue_count} issues)")
        else:
            # Extract exception name from error string (e.g., "litellm.AuthenticationError: message" -> "litellm.AuthenticationError")
            error = result.error or "error"
            exception_name = error.split(":", 1)[0].strip() if ":" in error else error[:50]
            parts.append(f"{model} ({exception_name})")
    return ", ".join(parts)


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
    from multi_mcp.utils.llm_runner import execute_parallel

    raw_results = await execute_parallel(
        models=models,
        messages=messages,
    )

    # Store conversation (use first successful response)
    from multi_mcp.memory.store import store_conversation_turn

    for result in raw_results:
        if result.status == "success":
            await store_conversation_turn(thread_id, messages, result.content)
            break

    # Check if consolidation is needed based on response size AND number of successful models
    from multi_mcp.settings import settings

    total_size = sum(len(r.content.encode("utf-8")) for r in raw_results)
    total_models = len(models)
    successful_count = sum(1 for r in raw_results if r.status == "success")

    # Only consolidate if we have 2+ successful models AND response is large
    should_consolidate = successful_count >= 2 and total_size > settings.max_codereview_response_size

    logger.info(
        f"[CODEREVIEW] Total response size: {total_size} bytes "
        f"(threshold: {settings.max_codereview_response_size}), "
        f"successful models: {successful_count}/{total_models}, "
        f"consolidate: {should_consolidate}"
    )

    if should_consolidate:
        # V3: Consolidate all model results into single result
        from multi_mcp.utils.consolidation import consolidate_model_results

        logger.info(f"[CODEREVIEW] Consolidating {len(raw_results)} model results")

        # Get typed CodeReviewModelResult directly from consolidation
        consolidated_result = await consolidate_model_results(raw_results)

        # Determine aggregate status and next_action
        issues = consolidated_result.issues_found or []
        issue_count = len(issues)

        # Parse issues from raw results for model summary (need to parse JSON first)
        from multi_mcp.utils.json_parser import parse_llm_json

        parsed_raw_results: list[CodeReviewModelResult] = []
        for r in raw_results:
            if r.status == "success":
                parsed_json = parse_llm_json(r.content)
                if parsed_json and isinstance(parsed_json, dict):
                    # Convert ModelResponse to CodeReviewModelResult with issues_found
                    parsed_raw_results.append(
                        CodeReviewModelResult(
                            content=r.content,
                            status=r.status,
                            error=r.error,
                            metadata=r.metadata,
                            issues_found=parsed_json.get("issues_found", []),
                        )
                    )
                else:
                    # No valid JSON, create result with empty issues
                    parsed_raw_results.append(
                        CodeReviewModelResult(
                            content=r.content,
                            status=r.status,
                            error=r.error,
                            metadata=r.metadata,
                            issues_found=[],
                        )
                    )
            else:
                # Error/warning status - create result with empty issues
                parsed_raw_results.append(
                    CodeReviewModelResult(
                        content=r.content,
                        status=r.status,
                        error=r.error,
                        metadata=r.metadata,
                        issues_found=[],
                    )
                )

        # Build model status summary with parsed issue counts
        model_summary = _build_model_status_summary(parsed_raw_results)

        # Count original issues before deduping
        original_issue_count = sum(len(getattr(r, "issues_found", None) or []) for r in parsed_raw_results if r.status == "success")

        # Validation: consolidation should not increase issue count
        if issue_count > original_issue_count:
            logger.warning(
                f"[CODEREVIEW] Consolidation increased issue count from {original_issue_count} to {issue_count}. "
                "This suggests the consolidation LLM may be splitting issues or creating new ones. "
                "Using original_issue_count as the deduplicated count."
            )

        if consolidated_result.status == "error":
            aggregate_status = "error"
            aggregate_summary = f"Review failed - all {total_models} models encountered errors. Models: {model_summary}"
            next_action_obj = NextAction(action="stop", reason="All models failed")
        elif issue_count == 0:
            aggregate_status = "success"
            aggregate_summary = f"Review complete. Models: {model_summary}. No issues found after consolidation."
            next_action_obj = NextAction(action="stop", reason="Review complete, no issues")
        else:
            # Count by severity
            severity_parts = _count_issues_by_severity(issues)

            aggregate_status = "success"
            # Format summary based on whether deduplication reduced the count
            if issue_count < original_issue_count:
                dedup_phrase = f"{original_issue_count} issues total, {issue_count} after deduplication"
            elif issue_count == original_issue_count:
                dedup_phrase = f"{issue_count} issues found"
            else:
                # This shouldn't happen, but handle it gracefully
                dedup_phrase = f"{issue_count} issues after consolidation (original: {original_issue_count})"

            aggregate_summary = f"Review complete. Models: {model_summary}. Found {dedup_phrase}: {', '.join(severity_parts)}."
            next_action_obj = NextAction(action="stop", reason="Review complete")

        logger.info(f"[CODEREVIEW] Consolidated result: {issue_count} issues, status={aggregate_status}")

        result = CodeReviewResponse(
            thread_id=thread_id,
            status=aggregate_status,
            summary=aggregate_summary,
            results=[consolidated_result],  # Single consolidated result
            next_action=next_action_obj,
        )

    else:
        # V2: Return multiple results without consolidation (old behavior)
        from multi_mcp.utils.json_parser import parse_llm_json

        logger.info("[CODEREVIEW] Skipping consolidation - using multi-model results")

        parsed_results: list[CodeReviewModelResult] = []
        all_issues: list[dict] = []
        success_count = 0
        needs_files_count = 0

        for result in raw_results:
            if result.status == "error":
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

            if not parsed_json or not isinstance(parsed_json, dict):
                parsed_results.append(
                    CodeReviewModelResult(
                        content=result.content,
                        status="warning",
                        error="Failed to parse LLM response as JSON - returning raw result in content field",
                        metadata=result.metadata,
                    )
                )
                continue

            status = parsed_json.get("status")
            model_issues: list[dict] = []
            if status == "success" and "issues_found" in parsed_json:
                model_issues = parsed_json.get("issues_found", [])
            elif status == "no_issues_found":
                model_issues = []

            # Tag issues with model name
            for issue in model_issues:
                issue["model"] = result.metadata.model

            all_issues.extend(model_issues)

            if status in ["files_required_to_continue", "focused_review_required"]:
                needs_files_count += 1
            elif status in ["no_issues_found", "success"]:
                success_count += 1

            parsed_results.append(
                CodeReviewModelResult(
                    content=result.content,
                    status="success",
                    metadata=result.metadata,
                    issues_found=model_issues if model_issues is not None else None,
                )
            )

        # Determine aggregate status
        successful_models = sum(1 for r in parsed_results if r.status == "success")
        warning_models = sum(1 for r in parsed_results if r.status == "warning")
        error_models = sum(1 for r in parsed_results if r.status == "error")

        if successful_models == total_models:
            aggregate_status = "success"
        elif error_models == total_models:
            aggregate_status = "error"
        else:
            aggregate_status = "partial"

        if needs_files_count > 0:
            aggregate_status = "in_progress"
            next_action_obj = NextAction(
                action="continue",
                reason=f"{needs_files_count}/{total_models} models requested additional files",
            )
        else:
            next_action_obj = NextAction(action="stop", reason="All models completed their review")

        # Build aggregate summary with model details
        issue_count = len(all_issues)
        status_parts = []
        if successful_models > 0:
            status_parts.append(f"{successful_models} succeeded")
        if warning_models > 0:
            status_parts.append(f"{warning_models} with warnings")
        if error_models > 0:
            status_parts.append(f"{error_models} failed")
        status_breakdown = f"{'/'.join(status_parts)}" if status_parts else "no models"

        # Build model status summary
        model_summary = _build_model_status_summary(parsed_results)

        if issue_count == 0:
            if needs_files_count > 0:
                aggregate_summary = (
                    f"{status_breakdown} of {total_models} models. Models: {model_summary}. Review paused - additional files required."
                )
            elif aggregate_status == "success":
                aggregate_summary = f"{status_breakdown} of {total_models} models. Models: {model_summary}. No issues found."
            else:
                aggregate_summary = f"{status_breakdown} of {total_models} models. Models: {model_summary}. Review incomplete."
        else:
            severity_parts = _count_issues_by_severity(all_issues)

            aggregate_summary = (
                f"{status_breakdown} of {total_models} models. Models: {model_summary}. "
                f"Found {issue_count} issue(s): {', '.join(severity_parts)}."
            )

        logger.info(f"[CODEREVIEW] Complete: {status_breakdown}, {issue_count} total issues")

        result = CodeReviewResponse(
            thread_id=thread_id,
            status=aggregate_status,
            summary=aggregate_summary,
            results=parsed_results,
            next_action=next_action_obj,
        )

    return result.model_dump(exclude_none=True)
