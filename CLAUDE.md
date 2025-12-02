# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-MCP is a multi-model AI orchestration server that provides advanced code analysis capabilities through the Model Context Protocol (MCP). It orchestrates multiple LLM providers via LiteLLM to deliver systematic code review and analysis tools.

The server is built with FastMCP and uses a streamlined workflow architecture optimized for fast, cost-effective analysis with models like gpt-5-mini.

## Current Status

**Production Ready** ✅
- **Unit Tests**: ✅ 436 tests passing (~2s) - All tests passing (includes 35 smoke/contract tests, 17 CLI subprocess mocking tests)
- **Integration Tests**: ✅ 74 tests passing (~10-15min) - All tests passing (26 with VCR record/replay for 90% speedup)
- **Total Coverage**: ✅ 510 tests passing (~85% code coverage)
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

# Run all unit tests (401 tests, ~2s, all passing ✅)
uv run pytest tests/unit/ -v

# Run integration tests (74 tests, ~5-7min with parallel, all passing ✅)
# Note: Requires real API keys (OPENAI_API_KEY, etc.)
# CLI tests will skip gracefully if CLIs not installed
RUN_E2E=1 uv run pytest tests/integration/ -n auto -v

# Or run sequentially (slower, ~15min)
RUN_E2E=1 uv run pytest tests/integration/ -v

# Run all tests (475 total)
RUN_E2E=1 uv run pytest tests/ -v

# Run the MCP server
./scripts/run_server.sh
# or: uv run python src/server.py

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

**`src/server.py`**: FastMCP server implementation with factory-generated tool wrappers
- Uses `create_mcp_wrapper()` factory to auto-generate tools from schemas
- Tool wrappers decorated with `@mcp.tool()` and `@mcp_monitor` for logging
- Calls `*_impl()` functions from `src/tools/` for actual implementation

**`src/tools/`**: Tool implementation functions
- `codereview.py` - Code review workflow with checklist guidance and expert validation
- `chat.py` - Interactive chat for development questions
- `compare.py` - Multi-model parallel analysis
- `debate.py` - Two-step debate workflow (independent + critique)
- `models.py` - Model listing implementation

**`src/models/`**: Model configuration and LLM integration
- `config.py` - YAML-based model config with Pydantic validation (`ModelConfig`, `ModelsConfiguration`)
- `resolver.py` - Model alias resolution with LiteLLM fallback (`ModelResolver`)
- `litellm_client.py` - Async LLM API calls with config-based resolution

**`config/models.yaml`**: Model definitions
- Canonical model names with LiteLLM model strings
- Aliases (e.g., `mini` → `gpt-5-mini`, `sonnet` → `claude-sonnet-4.5`)
- Use-case defaults (`fast`, `smart`, `cheap`)
- Temperature constraints per model

**`src/config.py`**: Environment-based configuration using Pydantic Settings
- API keys, model defaults (`default_model`, `default_model_list`), server settings
- `default_model_list`: Default models for multi-model compare (comma-separated or JSON array in .env)
- Loads from `.env` file

**`src/schemas/`**: Pydantic models for request validation
- `base.py` - Base `BaseToolRequest`, `SingleToolRequest`, `ModelResponseMetadata`
- `codereview.py` - `CodeReviewRequest`, `CodeReviewResponse`
- `chat.py` - `ChatRequest`, `ChatResponse`
- `compare.py` - `CompareRequest`, `CompareResponse`
- `debate.py` - `DebateRequest`, `DebateResponse`
- **Single source of truth**: Field descriptions defined once in Pydantic models
- **DRY principle**: Factory auto-generates tools from schemas

**`src/memory/`**: Conversation state management
- `store.py` - `ThreadStore` class for request/response storage with 6-hour TTL

**`src/prompts/`**: System prompts loaded from markdown files
- `codereview.md` - Code review instructions with OWASP Top 10, performance patterns
- `chat.md` - Chat system prompt for development assistance
- `compare.md` - Multi-model compare instructions
- `debate-step1.md` - Independent answer phase instructions
- `debate-step2.md` - Debate and voting phase instructions
- `__init__.py` - Loads prompts into constants

**`src/utils/`**: Utility functions
- `context.py` - ContextVar-based request context management (thread_id, workflow, step_number, base_path)
- `mcp_decorator.py` - MCP tool decorator that sets context at request entry
- `mcp_factory.py` - Factory for auto-generating MCP tools from Pydantic schemas
- `mcp_logger.py` - MCP tool request/response logging
- `request_logger.py` - LLM API call logging
- `repository.py` - Repository context builder (loads CLAUDE.md/AGENTS.md from context base_path)
- `artifacts.py` - Unified artifact saving (uses base_path from context)
- `llm_runner.py` - LLM execution helpers (execute_single, execute_parallel)
- `message_builder.py` - Message construction for LLM API calls
- `paths.py` - Path resolution and validation (security)
- `prompts.py` - Expert context builder for code review
- `files.py` - File operations utilities
- `json_parser.py` - Robust JSON parsing with repair capabilities
- `helpers.py` - Version retrieval, field description extraction
- `log_helpers.py` - Log file writing, timestamp formatting

### Schema Design Pattern

**Factory-Based Tool Generation**: Tools are auto-generated from Pydantic schemas using `create_mcp_wrapper()` factory.

**Implementation** (`src/utils/mcp_factory.py`):

1. **Define Pydantic schema** with `Field()` descriptions:
```python
# src/schemas/codereview.py
class CodeReviewRequest(BaseToolRequest):
    """Code review request schema."""

    issues_found: list[dict] | None = Field(
        None,
        description="REQUIRED: List of issues with severity levels...",
    )
    # ... more fields
```

2. **Use factory to generate tool wrapper**:
```python
# src/server.py
codereview = create_mcp_wrapper(
    CodeReviewRequest,
    codereview_impl,
    "Systematic code review using external models."
)
codereview = mcp.tool()(mcp_monitor(codereview))
```

3. **Factory auto-generates function signature**:
- Extracts field descriptions from Pydantic schema
- Creates `Annotated` types for each parameter
- Builds proper function signature using `inspect.Signature`
- Handles validation and calls implementation function

**Benefits**:
- Single source of truth for parameter documentation
- Zero boilerplate - just define schema and impl function
- Automatic consistency between validation and MCP schema
- Full type safety from Pydantic
- Easy to add new tools (3 lines of code)

### Request Context Management

**ContextVars for Request-Scoped Data**: The server uses Python's `contextvars` module to manage request-scoped data that needs to be accessible deep in the call stack without explicit parameter passing.

**Managed Context Values**:
- `thread_id`: Unique request/thread identifier
- `workflow`: Workflow name (e.g., "codereview", "chat", "compare")
- `step_number`: Current step number in multi-step workflows
- `base_path`: Base directory path for the project

**Implementation** (`src/utils/context.py`):
```python
from contextvars import ContextVar

_current_thread_id: ContextVar[str | None] = ContextVar("current_thread_id", default=None)
_current_workflow: ContextVar[str | None] = ContextVar("current_workflow", default=None)
_current_step: ContextVar[int | None] = ContextVar("current_step", default=None)
_current_base_path: ContextVar[str | None] = ContextVar("current_base_path", default=None)

def set_request_context(thread_id=None, workflow=None, step_number=None, base_path=None):
    """Set context at request entry (called by mcp_decorator)."""
    if thread_id is not None:
        _current_thread_id.set(thread_id)
    # ... set other values

def get_base_path() -> str | None:
    """Get base_path from context (used by utilities)."""
    return _current_base_path.get()

def clear_context():
    """Clear all context (called in finally block)."""
    _current_thread_id.set(None)
    # ... clear other values
```

**Lifecycle**:
1. **Entry**: `mcp_decorator` extracts values from request params and calls `set_request_context()`
2. **Usage**: Utility functions call `get_thread_id()`, `get_base_path()`, etc. to access context
3. **Cleanup**: `clear_context()` is called in `finally` block to prevent leaks

**Usage Examples**:
```python
# src/utils/repository.py - Falls back to context
def build_repository_context(base_path: str | None = None) -> str | None:
    base_path = base_path or get_base_path()  # Explicit param takes precedence
    if not base_path:
        return None
    # ... load CLAUDE.md/AGENTS.md

# src/utils/artifacts.py - Gets base_path from context
async def save_tool_artifacts(response, workflow, name, step_number, thread_id=None):
    base_path = get_base_path()  # No parameter needed
    if not base_path:
        logger.warning("No base_path in context, skipping artifact save")
        return None
    # ... save artifacts
```

**Benefits**:
- **Cleaner APIs**: Utilities don't need `base_path` parameters
- **Thread-Safe**: ContextVars work correctly with async/await
- **No Leaks**: Context is cleared after each request
- **Fallback Pattern**: Functions can accept explicit parameters that override context

## Code Standards

- **Line Length**: 120 characters maximum
- **Type Hints**: Required for all function signatures
- **Async-First**: All I/O operations must be async (`async def`, `await`)
- **Test Coverage**: Minimum 80% overall
- **Error Handling**: Return structured error dicts with context
- **Logging**: Use `logger.info()` for model calls with thread_id, model name, token usage

## Model Configuration

Models are defined in `config/models.yaml`. See README.md for model aliases and use-case defaults.

**Key Features:**
- Aliases resolve to full model names (e.g., `mini` → `gpt-5-mini`)
- Use-case defaults: request by purpose (`fast`, `smart`, `cheap`)
- Temperature constraints enforced per model
- LiteLLM fallback for unknown models

## Testing Strategy

### Unit Tests (401 tests) ✅
**Location:** `tests/unit/`
- `test_schemas.py` (27) - Pydantic request validation, field descriptions
- `test_store.py` (10) - ThreadStore request/response storage
- `test_codereview.py` (18) - Codereview step logic, LLM response parsing, error handling
- `test_chat.py` (9) - Chat tool thread handling, stop action, file embedding
- `test_compare.py` (17) - Multi-model parallel execution, timeouts
- `test_debate.py` (12) - Two-step debate workflow with multi-model consensus
- `test_model_resolver.py` (21) - Model resolution, alias mapping, LiteLLM fallback
- `test_model_config.py` (16) - YAML loading, validation, alias uniqueness
- `test_litellm_client.py` (11) - LLM client wrapper, temperature constraints
- `test_models_tool.py` (3) - Model listing tool implementation
- `test_files.py` (21) - Path resolution, security validation, file embedding
- `test_mcp_logger.py` (7) - MCP tool logging
- `test_mcp_decorator.py` (12) - MCP tool decorator and context management
- `test_mcp_factory.py` (41) - Factory-based tool generation
- `test_prompts.py` (6) - Expert context building, issue formatting
- `test_repository.py` (14) - Repository context loading (CLAUDE.md/AGENTS.md)
- `test_log_helpers.py` (11) - Log file writing, timestamp formatting
- `test_request_logger.py` (10) - LLM request/response logging
- `test_helpers.py` (13) - Version retrieval, field description extraction
- `test_json_parser.py` (27) - JSON parsing and repair
- `test_llm_runner.py` (8) - LLM execution helper functions
- `test_message_builder.py` (14) - Message construction for LLM calls
- `test_context.py` (13) - ContextVar request context management
- `test_artifacts.py` (13) - Artifact saving and file management
- `test_save_tool_artifacts.py` (10) - Tool artifact saving integration
- `test_cli_parsers.py` (24) - CLI output parsing (JSON, JSONL, text)
- `test_cli_subprocess.py` (17) - CLI subprocess execution with comprehensive mocking

**Approach:**
- Mock LiteLLM with `mock_litellm` fixture (when needed)
- Focus on testing `*_impl()` functions directly (no MCP server needed)
- Use `AsyncMock` for async operations
- No real API calls in unit tests
- Runtime: ~2 seconds
- **Coverage**: ~85% overall code coverage

### Integration Tests (74 tests) ✅
**Location:** `tests/integration/`
- `test_e2e_codereview.py` (6) - End-to-end codereview with real APIs
- `test_e2e_chat.py` (4) - Chat functionality and repository context
- `test_e2e_compare.py` (1) - Multi-model compare with real APIs
- `test_e2e_debate.py` (2) - Two-step debate workflow with real APIs
- `test_e2e_error_handling.py` (6) - Error handling and edge cases
- `test_e2e_workflows.py` (3) - Multi-step workflows and continuations
- `test_e2e_thread_management.py` (2) - Thread isolation and concurrency
- `test_e2e_context_and_config.py` (3) - AGENTS.md, model aliases, version tool
- `test_e2e_cli_models.py` (13) - CLI model configuration and execution tests
- `test_mcp_server.py` (17) - MCP server integration testing
- `test_cli_real_execution.py` (3) - Real CLI smoke tests (removed 7 redundant tests)
- `test_cli_workflows.py` (8) - CLI models in chat, compare, debate workflows
- `test_cli_performance.py` (7) - CLI performance, concurrency, and stress testing

**Requirements:**
- Real API keys (OPENAI_API_KEY or other providers)
- `RUN_E2E=1` environment variable
- Uses gpt-5-nano for fast, cost-effective testing (configurable via fixtures)

**Status:**
- ✅ All integration tests passing
- Runtime: ~10-15 minutes (due to real API calls)
- **VCR Enabled**: 26 tests use record/replay for 90% speedup

### VCR Record/Replay Pattern

**What is VCR?** VCR (Video Cassette Recorder) records real API interactions on first run, then replays them on subsequent runs - achieving 90% speedup (10-15 min → <1 min).

**How It Works:**

1. **First Run (Recording)**:
   ```bash
   # Record real API calls (requires API keys)
   RUN_E2E=1 pytest tests/integration/test_e2e_codereview.py -v
   ```
   - Makes real API calls to OpenAI/Anthropic/Google
   - VCR records request (URI, method, body) + response (status, headers, body)
   - Saves cassette as `tests/cassettes/test_e2e_codereview__test_basic_codereview.yaml`
   - Runtime: ~10-15 minutes (real API latency)

2. **Subsequent Runs (Replay)**:
   ```bash
   # Replay from cassettes (no API keys needed)
   pytest tests/integration/test_e2e_codereview.py -v
   ```
   - VCR matches requests and returns recorded responses instantly
   - No real API calls made
   - Runtime: ~1 minute (90% speedup!)

**Common Workflows:**

```bash
# Re-record all cassettes (when API behavior changes)
rm -rf tests/cassettes/*.yaml && RUN_E2E=1 pytest tests/integration/ -v

# Re-record specific test
rm tests/cassettes/test_e2e_codereview__test_basic_codereview.yaml
RUN_E2E=1 pytest tests/integration/test_e2e_codereview.py::test_basic_codereview -v

# Force real API calls (bypass VCR)
RUN_E2E=1 pytest tests/integration/ --disable-recording -v
```

**Configuration** (`tests/conftest.py`):
- **Security**: Auto-filters sensitive headers (`authorization`, `api-key`, etc.)
- **Record Mode**: `"once"` (record new, replay existing)
- **Storage**: `tests/cassettes/` directory
- **Matching**: URI + method + body

**Benefits:**
- 90% speedup in development (replay mode)
- Cost savings (no repeated LLM API calls)
- Offline testing (works without API keys after first record)
- Deterministic tests (same responses every time)

**See Also:** `tests/cassettes/README.md` for detailed VCR documentation

### Logging

**MCP Tool Logging** (`src/utils/mcp_logger.py`)
- Logs all MCP tool requests and responses
- Format: `logs/TIMESTAMP.THREAD_ID.mcp.json`
- Tracks: tool_name, direction (request/response), data, thread_id

**LLM API Logging** (`src/utils/request_logger.py`)
- Logs all LiteLLM API calls
- Format: `logs/TIMESTAMP.THREAD_ID.llm.json`
- Tracks: model, messages, temperature, usage, response

**Console Logging**
- All logs also go to `logs/server.log`
- Structured tags: `[CODEREVIEW]`, `[CHAT]`, `[COMPARE]`, `[MODEL_CALL]`, `[MCP_LOG]`

**Log Files:**
```
logs/
├── server.log                         # Console logs
├── 20251123_180512_345.thread123.mcp.json  # MCP request
├── 20251123_180514_678.thread123.mcp.json  # MCP response
└── 20251123_180515_234.thread123.llm.json  # LLM API call
```

## Common Development Tasks

### Adding a New MCP Tool

Follow this pattern to add new tools:

1. **Create Pydantic schema** in `src/schemas/` (inherit from `BaseToolRequest` or `SingleToolRequest`)
2. **Create implementation function** in `src/tools/` (e.g., `my_tool_impl()`)
3. **Add factory-generated wrapper** in `src/server.py`:
   ```python
   my_tool = create_mcp_wrapper(MyToolRequest, my_tool_impl, "Description")
   my_tool = mcp.tool()(mcp_monitor(my_tool))
   ```
4. **Add tests** in `tests/unit/` and `tests/integration/`
5. **Add system prompt** (if needed) in `src/prompts/`

**Debugging Model Calls**:
- Check MCP logs: `cat logs/*.mcp.json | jq .`
- Check LLM logs: `cat logs/*.llm.json | jq .`
- Check console logs for `[TOOL_NAME]` entries with thread_id
- Use `LOG_LEVEL=DEBUG` in `.env` for verbose output

**Updating Prompts**:
- Edit `src/prompts/*.md`
- Changes take effect immediately (loaded on server start)
- Test changes: `RUN_E2E=1 uv run pytest tests/integration/`

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

