# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-MCP is a multi-model AI orchestration server that provides advanced code analysis capabilities through the Model Context Protocol (MCP). It orchestrates multiple LLM providers via LiteLLM to deliver systematic code review and analysis tools.

The server is built with FastMCP and uses a streamlined workflow architecture optimized for fast, cost-effective analysis with models like gpt-5-mini.

## Current Status

**Production Ready** ✅
- **Unit Tests**: ✅ 511 tests passing (~2s) - All tests passing (includes 24 mocked CLI tests for parsing/error handling)
- **Integration Tests**: ✅ 93 tests passing (~8-10min) - All tests passing (includes 6 CLI smoke tests, 8 CLI workflow tests)
- **Total Coverage**: ✅ 604 tests passing (~85% code coverage)
- **Model Config**: YAML-based model configuration with aliases and use-case defaults
- **Logging**: MCP tool request/response logging enabled
- **Implementation**: Checklist-based workflow with expert validation enabled
- **File Limit Enforcement**: ✅ `settings.max_files_per_review` is enforced

## Development Commands

```bash
# Type checking (required before commits)
uv run pyright

# Linting and formatting (required before commits)
uv run ruff check .
uv run ruff format .

# Run all unit tests (511 tests, ~2s, all passing ✅)
uv run pytest tests/unit/ -v

# Run integration tests (93 tests, ~5-7min with parallel, all passing ✅)
# Note: Requires real API keys (OPENAI_API_KEY, etc.)
# CLI tests will skip gracefully if CLIs not installed
RUN_E2E=1 uv run pytest tests/integration/ -n auto -v

# Or run sequentially (slower, ~15min)
RUN_E2E=1 uv run pytest tests/integration/ -v

# Run all tests (604 total)
RUN_E2E=1 uv run pytest tests/ -v

# Run the MCP server
./scripts/run_server.sh
# or: uv run python multi_mcp/server.py

# View MCP logs (request/response)
ls -lh logs/*.mcp.json
cat logs/*.mcp.json | jq .
```

## Installation & Setup

See README.md for installation instructions and environment setup.

## CLI Usage

See README.md for CLI usage examples. Note: CLI is experimental.

## Architecture

### Core Components

**`multi_mcp/server.py`**: FastMCP server implementation with factory-generated tool wrappers
- Uses `create_mcp_wrapper()` factory to auto-generate tools from schemas
- Tool wrappers decorated with `@mcp.tool()` and `@mcp_monitor` for logging
- Calls `*_impl()` functions from `multi_mcp/tools/` for actual implementation

**`multi_mcp/tools/`**: Tool implementation functions
- `codereview.py` - Code review workflow with checklist guidance and expert validation
- `chat.py` - Interactive chat for development questions
- `compare.py` - Multi-model parallel analysis
- `debate.py` - Two-step debate workflow (independent + critique)
- `models.py` - Model listing implementation

**`multi_mcp/models/`**: Model configuration and LLM integration
- `config.py` - YAML-based model config with Pydantic validation (`ModelConfig`, `ModelsConfiguration`, `PROVIDERS`)
- `resolver.py` - Model alias resolution with LiteLLM fallback (`ModelResolver`)
- `litellm_client.py` - API model execution via LiteLLM responses API (~260 lines)
- `cli_executor.py` - CLI model execution via subprocess (~270 lines)

**`multi_mcp/config/config.yaml`**: Model definitions
- Canonical model names with LiteLLM model strings
- Aliases (e.g., `mini` → `gpt-5-mini`, `sonnet` → `claude-sonnet-4.5`)
- Temperature constraints per model
- User overrides: `~/.multi_mcp/config.yaml` (optional)

**`multi_mcp/settings.py`**: Environment-based configuration using Pydantic Settings
- API keys loaded from `.env` files (cascading: project .env > ~/.multi_mcp/.env)
- Runtime defaults (`default_model`, `default_model_list`, `default_temperature`)
- Server settings (`max_retries`, `model_timeout_seconds`, etc.)
- `default_model_list`: Default models for multi-model compare (comma-separated or JSON array in .env)

**`multi_mcp/schemas/`**: Pydantic models for request validation
- `base.py` - Base `BaseToolRequest`, `SingleToolRequest`, `ModelResponseMetadata`
- `codereview.py` - `CodeReviewRequest`, `CodeReviewResponse`
- `chat.py` - `ChatRequest`, `ChatResponse`
- `compare.py` - `CompareRequest`, `CompareResponse`
- `debate.py` - `DebateRequest`, `DebateResponse`
- **Single source of truth**: Field descriptions defined once in Pydantic models
- **DRY principle**: Factory auto-generates tools from schemas

**`multi_mcp/memory/`**: Conversation state management
- `store.py` - `ThreadStore` class for request/response storage with 6-hour TTL

**`multi_mcp/prompts/`**: System prompts loaded from markdown files
- `codereview.md` - Code review instructions with OWASP Top 10, performance patterns
- `chat.md` - Chat system prompt for development assistance
- `compare.md` - Multi-model compare instructions
- `debate-step1.md` - Independent answer phase instructions
- `debate-step2.md` - Debate and voting phase instructions
- `__init__.py` - Loads prompts into constants

**`multi_mcp/utils/`**: Utility functions
- `context.py` - ContextVar-based request context management (thread_id, workflow, step_number, base_path)
- `mcp_decorator.py` - MCP tool decorator that sets context at request entry
- `mcp_factory.py` - Factory for auto-generating MCP tools from Pydantic schemas
- `mcp_logger.py` - MCP tool request/response logging
- `request_logger.py` - LLM API call logging
- `repository.py` - Repository context builder (loads CLAUDE.md/AGENTS.md from context base_path)
- `artifacts.py` - Unified artifact saving (uses base_path from context)
- `llm_runner.py` - LLM execution helpers with `_route_model_execution()` (routes API models → `litellm_client.execute()`, CLI models → `cli_executor.execute()`)
- `message_builder.py` - Message construction for LLM API calls
- `paths.py` - Path resolution and validation (security)
- `prompts.py` - Expert context builder for code review
- `files.py` - File operations utilities
- `json_parser.py` - Robust JSON parsing with repair capabilities
- `helpers.py` - Version retrieval, field description extraction
- `log_helpers.py` - Log file writing, timestamp formatting

### Schema Design Pattern

**Factory-Based Tool Generation**: Tools are auto-generated from Pydantic schemas using `create_mcp_wrapper()` factory (`multi_mcp/utils/mcp_factory.py`).

**Process**: Define Pydantic schema → Use factory to generate wrapper → Factory auto-generates function signature

**Benefits**: Single source of truth, zero boilerplate, full type safety, easy to add tools (3 lines)

### Request Context Management

Uses Python's `contextvars` module for request-scoped data (`thread_id`, `workflow`, `step_number`, `base_path`).
- **Implementation**: `multi_mcp/utils/context.py`
- **Entry**: `mcp_decorator` sets context from request params
- **Usage**: Utility functions call `get_thread_id()`, `get_base_path()`, etc.
- **Cleanup**: `clear_context()` prevents leaks
- **Benefits**: Cleaner APIs, thread-safe, fallback pattern for explicit params

## Code Standards

- **Line Length**: 120 characters maximum
- **Type Hints**: Required for all function signatures
- **Async-First**: All I/O operations must be async (`async def`, `await`)
- **Test Coverage**: Minimum 80% overall
- **Error Handling**: Return structured error dicts with context
- **Logging**: Use `logger.info()` for model calls with thread_id, model name, token usage

## Model Configuration

Models are defined in `multi_mcp/config/config.yaml`. See README.md for model aliases.

**Key Features:**
- Aliases resolve to full model names (e.g., `mini` → `gpt-5-mini`)
- Temperature constraints enforced per model
- LiteLLM fallback for unknown models
- User overrides via `~/.multi_mcp/config.yaml` (optional, merged with package defaults)
- Runtime defaults (model, temperature) in Settings class via `.env` files

**LiteLLM Responses API:**
- Uses `litellm.aresponses()` instead of `litellm.acompletion()` for unified web search across providers
- Unified `tools=[{"type": "web_search"}]` parameter works with OpenAI, Azure, Anthropic, Gemini
- **Limitation**: Only `total_tokens` available (no `prompt_tokens`/`completion_tokens` breakdown)
- Web search enabled via `enable_web_search=True` parameter in `litellm_client.execute()`

## Testing Strategy

### Unit Tests (511 tests) ✅
**Location:** `tests/unit/`
- Mock LiteLLM with fixtures, test `*_impl()` functions directly
- No real API calls, Runtime: ~2 seconds, Coverage: ~85%
- Tests: schemas, tools (codereview/chat/compare/debate), models, MCP factory, CLI, utils

### Integration Tests (93 tests) ✅
**Location:** `tests/integration/`
- End-to-end tests with real APIs (codereview, chat, compare, debate, web search)
- MCP server integration, CLI workflows, error handling, thread management
- Requires: Real API keys, `RUN_E2E=1`, Runtime: ~8-10 minutes
- VCR: Currently disabled (see `tests/cassettes/README.md`)

### Logging

- **MCP Tools**: `logs/TIMESTAMP.THREAD_ID.mcp.json` (requests/responses)
- **LLM API**: `logs/TIMESTAMP.THREAD_ID.llm.json` (model calls, usage stats)
- **Console**: `logs/server.log` with structured tags `[CODEREVIEW]`, `[CHAT]`, etc.
- View: `cat logs/*.mcp.json | jq .` or `cat logs/*.llm.json | jq .`

## Common Development Tasks

### Adding a New MCP Tool
1. Create Pydantic schema in `multi_mcp/schemas/`
2. Create `*_impl()` function in `multi_mcp/tools/`
3. Add factory wrapper in `multi_mcp/server.py`: `create_mcp_wrapper(Schema, impl, "Description")`
4. Add tests in `tests/unit/` and `tests/integration/`
5. Add system prompt (if needed) in `multi_mcp/prompts/`

**Debugging**: Check logs in `logs/` directory, use `LOG_LEVEL=DEBUG` in `.env`
**Prompts**: Edit `multi_mcp/prompts/*.md`, changes take effect on server restart

## Design Principles

- **DRY (Don't Repeat Yourself)**: Field descriptions, validation rules, and documentation defined once in Pydantic models
- **Single Source of Truth**: Schema models are the authoritative source for parameter definitions
- **Type Safety**: Full type checking with Pydantic and Pyright
- **YAGNI**: Don't add complexity until actually needed
- **KISS**: Keep it simple, stupid!
- **Clean Code**: No dead code, all imports used, all tests passing
- **Greenfield project**: No worries about backward compatibility

## Project Notes

- **Architecture**: Clean, streamlined workflow design with FastMCP and LiteLLM
- **Current State**: Production-ready with expert validation enabled
- **Breaking Changes Allowed**: Greenfield project, no backward compatibility concerns
- **Documentation**: New documentation should be saved to `docs/`
- **Temporary Files**: Use `tmp/` for experiments, spikes, complex bash scripts
- **Reference Projects**: `ref/` contains reference projects to check documentation - DO NOT modify these
- **File Operations**: Use Claude Code's Read/Write tools, NOT Bash(cat > dir/file.ex << 'EOF')
- **Running Python scripts**: Use Claude Code's Read/Write tools to generate files in `tmp/` and execute with `uv run python tmp/file_name.py`
- **Complex Scripts**: Write to `tmp/` directory first, then execute
- **Live Testing**: Always use low-cost models (gpt-5-mini, claude-haiku-4-5-20251001, gemini-2.5-flash) for rapid iteration
- **Deterministic Patterns**: Prefer checklist-based guidance over LLM-generated suggestions for intermediate steps
- **Testing**: ALWAYS test after making bigger changes - run `uv run pytest tests/unit/` (fast) or `RUN_E2E=1 uv run pytest` (full)
- **Git Commits**: Ensure all tests pass `make test-all` and code is linted `make check` before committing

