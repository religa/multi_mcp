"""FastMCP server with MCP tool wrappers."""

import logging

from fastmcp import FastMCP

from multi_mcp.schemas.chat import ChatRequest
from multi_mcp.schemas.codereview import CodeReviewRequest
from multi_mcp.schemas.compare import CompareRequest
from multi_mcp.schemas.debate import DebateRequest
from multi_mcp.settings import settings
from multi_mcp.tools.chat import chat_impl
from multi_mcp.tools.codereview import codereview_impl
from multi_mcp.tools.compare import compare_impl
from multi_mcp.tools.debate import debate_impl
from multi_mcp.tools.models import models_impl
from multi_mcp.utils.helpers import get_version
from multi_mcp.utils.mcp_decorator import mcp_monitor
from multi_mcp.utils.mcp_factory import create_mcp_wrapper
from multi_mcp.utils.paths import LOGS_DIR

logger = logging.getLogger(__name__)

mcp = FastMCP(settings.server_name)

codereview = create_mcp_wrapper(
    CodeReviewRequest,
    codereview_impl,
    """Systematic code review using external models.
Covers quality, security, performance, and architecture.""",
)
codereview = mcp.tool()(mcp_monitor(codereview))

chat = create_mcp_wrapper(
    ChatRequest,
    chat_impl,
    """General chat with AI assistant.
Supports multi-turn conversations with project context and file inclusion.""",
)
chat = mcp.tool()(mcp_monitor(chat))

compare = create_mcp_wrapper(
    CompareRequest,
    compare_impl,
    """Compare responses from multiple AI models.
Runs the same content against all specified models in parallel.
Supports multi-turn conversations with project context and file inclusion.""",
)
compare = mcp.tool()(mcp_monitor(compare))

debate = create_mcp_wrapper(
    DebateRequest,
    debate_impl,
    """Multi-model debate: Step 1 (independent answers) + Step 2 (debate/critique).
Each model provides independent answer, then reviews all responses and votes.""",
)
debate = mcp.tool()(mcp_monitor(debate))


@mcp.tool()
@mcp_monitor
async def version() -> dict:
    """
    Get server version, configuration details, and list of available tools.
    """
    tool_names: list[str] = []
    if hasattr(mcp, "_tools"):
        tools_dict = mcp._tools  # type: ignore[attr-defined]
        tool_names = [tool.name for tool in tools_dict.values()]

    return {
        "name": settings.server_name,
        "version": get_version(),
        "tools": sorted(tool_names) if tool_names else ["chat", "codereview", "compare", "debate", "models", "version"],
    }


@mcp.tool()
@mcp_monitor
async def models() -> dict:
    """
    List available AI models.
    Returns model names, aliases, provider, and configuration.
    """
    return await models_impl()


@mcp.prompt(name="codereview")
async def codereview_prompt() -> str:
    """Perform systematic code review"""
    return "Use the codereview tool to analyze code for quality, security, performance, and architecture issues."


@mcp.prompt(name="chat")
async def chat_prompt() -> str:
    """Chat with AI assistant"""
    return "Use the chat tool for general conversation, questions, and assistance."


@mcp.prompt(name="compare")
async def compare_prompt() -> str:
    """Compare responses from multiple AI models"""
    return "Use the compare tool to run the same query against multiple models in parallel."


@mcp.prompt(name="debate")
async def debate_prompt() -> str:
    """Multi-model debate with critique and voting"""
    return "Use the debate tool to run a two-step debate: models answer independently, then critique and vote on best response."


@mcp.prompt(name="models")
async def models_prompt() -> str:
    """List available AI models"""
    return "Use the models tool to see all available AI models, their aliases, and configuration."


@mcp.prompt(name="version")
async def version_prompt() -> str:
    """Get server version and info"""
    return "Use the version tool to see server version, configuration details, and available tools."


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOGS_DIR / "server.log")],
    )
    logger.info(f"[SERVER] Starting {settings.server_name} on stdio")
    mcp.run(transport="stdio")
