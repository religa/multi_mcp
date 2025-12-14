"""Debate tool implementation - two-step multi-model workflow."""

import logging
from typing import Literal

from multi_mcp.prompts import DEBATE_STEP1_PROMPT, DEBATE_STEP2_PROMPT
from multi_mcp.schemas.base import ModelResponse, MultiToolResponse
from multi_mcp.schemas.debate import DebateResponse
from multi_mcp.utils.llm_runner import execute_parallel
from multi_mcp.utils.message_builder import MessageBuilder

logger = logging.getLogger(__name__)


def _format_debate_prompt(original_content: str, step1_results: list[ModelResponse]) -> str:
    """Format Step 2 user message with original question and all Step 1 responses.

    Returns XML-formatted content matching debate-step2 prompt expectations.
    Uses <USER_MESSAGE> and <PREVIOUS_RESPONSES> XML tags for structured input.
    Each response is wrapped in <response> tag with model and number attributes.

    Format:
        <response number="1" model="gpt-5-mini">
        [response content]
        </response>
    """
    responses_xml = []
    for i, result in enumerate(step1_results, 1):
        if result.status == "success":
            model_name = result.metadata.model if result.metadata else "Unknown"
            responses_xml.append(f'<response number="{i}" model="{model_name}">\n{result.content}\n</response>')

    responses_section = "\n\n".join(responses_xml)

    return f"""<USER_MESSAGE>
{original_content}
</USER_MESSAGE>

<PREVIOUS_RESPONSES>
{responses_section}
</PREVIOUS_RESPONSES>
"""


async def debate_impl(
    name: str,
    content: str,
    step_number: int,
    next_action: Literal["continue", "stop"],
    base_path: str,
    models: list[str],
    thread_id: str,
    relevant_files: list[str] | None = None,
) -> dict:
    """Two-step debate workflow - fully stateless.
    Returns:
        DebateResponse dict with both step1 and step2 results
    """
    logger.info(f"[DEBATE] Starting with {len(models)} models, {len(relevant_files or [])} files")

    # Build messages using STANDARD PATTERN
    messages = await (
        MessageBuilder(system_prompt=DEBATE_STEP1_PROMPT, base_path=base_path)
        .add_repository_context()
        .add_files(relevant_files)
        .add_user_message(content)
        .build()
    )

    logger.info(f"[DEBATE:STEP1] Running {len(models)} models in parallel")
    step1_results = await execute_parallel(
        models=models,
        messages=messages,
        enable_web_search=True,
    )

    step1_successes = sum(1 for r in step1_results if r.status == "success")

    if step1_successes == 0:
        logger.error(f"[DEBATE:STEP1] All {len(models)} models failed")
        return MultiToolResponse(
            thread_id=thread_id,
            status="error",
            summary=f"Debate failed: all {len(models)} models failed in Step 1",
            results=step1_results,
        ).model_dump(exclude_none=True)

    logger.info(f"[DEBATE:STEP1] Complete: {step1_successes}/{len(models)} succeeded")

    successful_models = [models[i] for i, r in enumerate(step1_results) if r.status == "success"]

    debate_prompt = _format_debate_prompt(content, step1_results)

    # Build Step 2 messages with FULL context
    # Models need repository context and files to critique Step 1 responses
    # escape_html=False to preserve XML tags in debate_prompt
    step2_messages = await (
        MessageBuilder(system_prompt=DEBATE_STEP2_PROMPT, base_path=base_path)
        .add_repository_context()  # Add CLAUDE.md/AGENTS.md context
        .add_files(relevant_files)  # Add file contents for code reference
        .add_user_message(debate_prompt, wrap_xml=False, escape_html=False)  # Contains XML tags
        .build()
    )

    logger.info(f"[DEBATE:STEP2] Running {len(successful_models)} models (Step 1 successes)")
    step2_results = await execute_parallel(
        models=successful_models,
        messages=step2_messages,
        enable_web_search=False,  # Disable web search for debate step 2 (uses step 1 results)
    )

    step2_successes = sum(1 for r in step2_results if r.status == "success")

    if step2_successes == len(successful_models):
        status = "success"
        summary = f"Debate complete: {step2_successes}/{len(successful_models)} models succeeded in both steps"
    elif step2_successes > 0:
        status = "partial"
        summary = f"Debate partial: Step 1 ({step1_successes}/{len(models)}), Step 2 ({step2_successes}/{len(successful_models)})"
    else:
        status = "error"
        summary = f"Debate error: Step 2 failed for all {len(successful_models)} models"

    logger.info(f"[DEBATE] {summary}")

    response = DebateResponse(
        thread_id=thread_id,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        results=step1_results,  # Step 1 independent answers
        step2_results=step2_results,  # Step 2 debate responses
    )

    return response.model_dump(exclude_none=True)
