"""Chat tool implementation."""

import logging
from typing import Literal

from multi_mcp.prompts import CHAT_PROMPT
from multi_mcp.schemas.chat import ChatResponse
from multi_mcp.utils.json_parser import parse_llm_json
from multi_mcp.utils.message_builder import MessageBuilder

logger = logging.getLogger(__name__)


async def chat_impl(
    name: str,
    content: str,
    step_number: int,
    next_action: Literal["continue", "stop"],
    base_path: str,
    model: str,
    thread_id: str,
    relevant_files: list[str] | None = None,
) -> dict:
    """Chat implementation with conversation history support."""
    logger.info(f"[CHAT] {name} - step {step_number}")

    # Build messages with conversation history
    messages = await (
        MessageBuilder(
            system_prompt=CHAT_PROMPT,
            base_path=base_path,
            thread_id=thread_id,
            include_history=True,
        )
        .add_conversation_history()  # Check for existing history
        .add_repository_context()  # Skip if continuation
        .add_files(relevant_files)  # Skip if continuation
        .add_user_message(content)
        .build()
    )

    from multi_mcp.utils.llm_runner import execute_single

    model_response = await execute_single(
        model=model,
        messages=messages,
        enable_web_search=True,
    )

    # Handle response
    if model_response.status == "error":
        logger.error(f"[CHAT] model_response.error: {model_response.error}")
        return ChatResponse.error_response(
            thread_id=thread_id,
            error=model_response.error,
            metadata=model_response.metadata,
        ).model_dump(exclude_none=True)

    logger.info(f"[CHAT] Response - tokens={model_response.metadata.total_tokens} latency={model_response.metadata.latency_ms}ms")
    from multi_mcp.memory.store import store_conversation_turn

    await store_conversation_turn(thread_id, messages, model_response.content)

    # Parse response
    raw_content = model_response.content
    response_status = "success"
    response_content = raw_content

    json_data = parse_llm_json(raw_content)
    if isinstance(json_data, dict):
        status = json_data.get("status")
        if status in ["files_required_to_continue", "clarification_required"]:
            response_status = "in_progress"
            response_content = json_data.get("message", raw_content)
            logger.info(f"[CHAT] Special case: {status}")

    result = ChatResponse(
        thread_id=thread_id,
        content=response_content,
        status=response_status,
        metadata=model_response.metadata,
    )

    return result.model_dump(exclude_none=True)
