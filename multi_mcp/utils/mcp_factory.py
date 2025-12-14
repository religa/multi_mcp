"""Factory for auto-generating MCP tool wrappers from Pydantic schemas."""

import inspect
import logging
import uuid
from collections.abc import Callable
from typing import Annotated

from pydantic import BaseModel, ValidationError

from multi_mcp.utils.helpers import get_field_description

logger = logging.getLogger(__name__)


def create_mcp_wrapper(
    schema_class: type[BaseModel],
    impl_func: Callable,
    docstring: str | None = None,
) -> Callable:
    """
    Auto-generate MCP tool wrapper from Pydantic schema and implementation function.

    Uses inspect.Signature to dynamically create function signature without exec().

    Args:
        schema_class: Pydantic model class defining the tool's request schema
        impl_func: Implementation function to call (e.g., chat_impl, codereview_impl)
        docstring: Optional docstring for the generated wrapper

    Returns:
        Wrapper function with proper signature and annotations for FastMCP

    Example:
        @mcp.tool()
        @mcp_monitor
        @create_mcp_wrapper(ChatRequest, chat_impl, "General chat with AI assistant.")
        async def chat():
            pass  # Body replaced by wrapper
    """
    impl_name = impl_func.__name__

    # Build parameter list from schema fields
    parameters = []

    for field_name, field_info in schema_class.model_fields.items():
        description = get_field_description(schema_class, field_name)

        annotated_type = Annotated[field_info.annotation, description]

        default = inspect.Parameter.empty if field_info.is_required() else None

        param = inspect.Parameter(
            name=field_name,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=default,
            annotation=annotated_type,
        )

        parameters.append(param)

    parameters.sort(key=lambda p: p.default != inspect.Parameter.empty)

    new_signature = inspect.Signature(parameters=parameters, return_annotation=dict)

    async def wrapper(**kwargs) -> dict:
        """Auto-generated wrapper."""
        args = {k: v for k, v in kwargs.items() if v is not None}

        if "thread_id" not in args or args.get("thread_id") is None:
            args["thread_id"] = str(uuid.uuid4())

        try:
            model = schema_class(**args)
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                field = error.get("loc", ("field",))[-1]
                msg = error.get("msg", "Validation failed")
                error_details.append(f"  - {field}: {msg}")

            error_content = (
                "**Request validation failed**\n\n"
                "The following fields have validation errors:\n" + "\n".join(error_details) + "\n\n"
                "Please correct these fields and retry your request."
            )

            return {
                "status": "error",
                "thread_id": args.get("thread_id", "unknown"),
                "content": error_content,
            }
        except Exception as e:
            # Catch any other unexpected errors
            logger.exception(f"Unexpected error in {impl_name} wrapper: {e}")

            return {
                "status": "error",
                "thread_id": args.get("thread_id", "unknown"),
                "content": (
                    f"**Unexpected error during request processing**\n\n"
                    f"An error occurred while preparing your request. "
                    f"Check the server logs for details.\n\n"
                    f"Error: {str(e)[:200]}"
                ),
            }

        # Try to call implementation function
        try:
            return await impl_func(**model.model_dump())
        except Exception as e:
            # Catch implementation errors
            logger.exception(f"Error in {impl_name} implementation: {e}")

            return {
                "status": "error",
                "thread_id": args.get("thread_id", "unknown"),
                "content": (
                    f"**Tool execution error**\n\n"
                    f"An error occurred during tool execution. "
                    f"Check the server logs for details.\n\n"
                    f"Error: {str(e)[:200]}"
                ),
            }

    wrapper.__signature__ = new_signature

    annotations = {}
    for param in parameters:
        annotations[param.name] = param.annotation
    annotations["return"] = dict

    wrapper.__annotations__ = annotations

    wrapper.__name__ = impl_func.__name__.replace("_impl", "")
    wrapper.__module__ = impl_func.__module__

    if docstring:
        wrapper.__doc__ = docstring
    else:
        wrapper.__doc__ = f"Auto-generated wrapper for {impl_name}"

    return wrapper
