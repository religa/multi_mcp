# Contributing to Multi-MCP

Thanks for your interest in contributing! This guide will help you get started.

## Quick Start

1. **Fork and clone** the repository
2. **Install dependencies:** `uv sync --extra dev`
3. **Create a branch:** `git checkout -b feature-name`
4. **Make your changes**
5. **Run tests and checks:** `make check && make test`
6. **Submit a PR**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/multi_mcp.git
cd multi_mcp

# Install dependencies with dev extras (required for testing and linting)
uv sync --extra dev

# Create .env file
cp .env.example .env
# Add at least one API key to .env (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY)
```

## Before Submitting a PR

**IMPORTANT:** Run full integration testing before submitting your PR to ensure everything works with real API calls.

```bash
# 1. Run all code quality checks + unit tests (fast)
make check && make test

# 2. Run full integration tests (REQUIRED before PR submission)
make test-integration
# This runs 25 integration tests (~10min) with real API calls
# Requires at least one API key in .env

# Or run everything at once:
make check && make test-all

# Individual commands:

# Format code (auto-fixes issues)
make format
# or: uv run ruff format . && uv run ruff check . --fix

# Type checking
make typecheck
# or: uv run pyright

# Linting
make lint
# or: uv run ruff check .

# Unit tests (364 tests, ~2s)
make test
# or: uv run pytest tests/unit/ -v

# Integration tests (25 tests, ~2-3min with parallel execution, REQUIRED before PR)
make test-integration
# or: RUN_E2E=1 uv run pytest tests/integration/ -n auto -v
```

## Code Standards

- **Python 3.13+** required (as specified in `pyproject.toml`)
- **Type hints** on all functions
- **Async-first** - use `async def` for I/O operations
- **Test coverage** - minimum 80% overall (add tests for new features)
- **Line length** - 120 characters max (configured in `pyproject.toml`)
- **Error handling** - return structured error dicts with context
- **Logging** - use `logger.info()` for model calls with thread_id, model name, token usage

## Design Principles

- **DRY (Don't Repeat Yourself)**: Field descriptions, validation rules, and documentation defined once in Pydantic models
- **Single Source of Truth**: Schema models are the authoritative source for parameter definitions
- **Type Safety**: Full type checking with Pydantic and Pyright
- **YAGNI**: Don't add complexity until actually needed
- **KISS**: Keep it simple, stupid!
- **Clean Code**: No dead code, all imports used, all tests passing
- **Greenfield project**: No worries about backward compatibility - breaking changes are allowed

## Project Structure

```
src/
├── server.py          # FastMCP server with factory-generated tools
├── cli.py             # CLI tool (experimental)
├── config.py          # Environment-based configuration
├── schemas/           # Pydantic models for request validation
│   ├── base.py        # Base classes, ModelResponseMetadata
│   ├── codereview.py  # CodeReview request/response
│   ├── chat.py        # Chat request/response
│   ├── compare.py  # Compare request/response
│   └── debate.py      # Debate request/response
├── tools/             # Tool implementation functions (*_impl)
│   ├── codereview.py  # Code review workflow
│   ├── chat.py        # Interactive chat
│   ├── compare.py  # Multi-model parallel analysis
│   ├── debate.py      # Two-step debate workflow
│   └── models.py      # Model listing
├── models/            # Model configuration and LLM integration
│   ├── config.py      # YAML-based model config
│   ├── resolver.py    # Model alias resolution
│   └── litellm_client.py  # Async LLM API calls
├── memory/            # Conversation state management
│   └── store.py       # ThreadStore with 6-hour TTL
├── prompts/           # System prompts (markdown files)
│   ├── codereview.md
│   ├── chat.md
│   ├── compare.md
│   ├── debate-step1.md
│   └── debate-step2.md
└── utils/             # Utility functions
    ├── mcp_factory.py     # Auto-generate MCP tools from schemas
    ├── mcp_decorator.py   # Request context management
    ├── artifacts.py       # Artifact saving
    ├── llm_runner.py      # LLM execution helpers
    └── ...                # See CLAUDE.md for full list
```

## Testing

We have 510 total tests: 436 unit tests (~2s) and 74 integration tests (~10-15min with real API calls).

```bash
# Unit tests only (436 tests, ~2s, fast - run before every commit)
make test
# or: uv run pytest tests/unit/ -v

# Integration tests (74 tests, ~10-15min, requires real API keys)
make test-integration
# or: RUN_E2E=1 uv run pytest tests/integration/ -n auto -v

# Run integration tests sequentially (slower, ~15min)
RUN_E2E=1 uv run pytest tests/integration/ -v

# Run with specific number of workers
RUN_E2E=1 uv run pytest tests/integration/ -n 4 -v

# All tests (510 total)
make test-all
# or: RUN_E2E=1 uv run pytest -v

# Run with coverage report
uv run pytest tests/unit/ --cov=src --cov-report=html
```

**Note:** Integration tests require at least one API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY) and make real API calls which cost money. They are **disabled in CI** to save costs. We use low-cost models (gpt-5-mini, gemini-2.5-flash) for testing.

**Parallel Execution:** Integration tests can run in parallel using `pytest-xdist` (`-n auto`), but currently run sequentially by default. Tests use unique thread IDs (UUIDs) so they don't conflict.

**VCR Status:** VCR (cassette recording) is currently **disabled** due to compatibility issues with httpx/litellm. All integration tests make real API calls. See `tests/cassettes/README.md` for details.

### Test Organization

- `tests/unit/` - Fast unit tests with mocked LLM calls (no API keys needed)
- `tests/integration/` - End-to-end tests with real API calls (requires API keys)

### Writing Tests

- Focus on testing `*_impl()` functions directly (no MCP server needed)
- Mock LiteLLM using the `mock_litellm` fixture
- Use `AsyncMock` for async operations
- Minimum 80% code coverage required

## Reporting Issues

Found a bug or have a feature request? [Open an issue](https://github.com/religa/multi_mcp/issues/new) and include:
- **Bugs:** Description, steps to reproduce, expected vs actual behavior, environment details
- **Features:** Description, use case, proposed solution

## Pull Request Process

1. **Create an issue first** (for major changes)
2. **Keep PRs focused** - one feature/fix per PR
3. **Add tests** for new functionality (both unit and integration if applicable)
4. **Run full integration testing** locally before submitting:
   ```bash
   make test-integration
   # or: RUN_E2E=1 uv run pytest tests/integration/ -v
   ```
5. **Update docs** if you change APIs (README.md, CLAUDE.md, or docs/)
6. **Ensure all checks pass**:
   - ✅ Unit tests (364 tests)
   - ✅ Integration tests (25 tests) - **REQUIRED locally before PR**
   - ✅ Type checking (pyright)
   - ✅ Linting (ruff check)
   - ✅ Format check (ruff format --check)

**CI Notes:**
- Integration tests are **disabled in CI** (cost money) but **REQUIRED locally before submitting PR**
- CI runs unit tests + code quality checks on every push/PR
- All CI checks must pass before merge
- You must confirm integration tests passed locally when submitting PR

## Architecture Overview

Multi-MCP uses a clean, factory-based architecture:

**Factory Pattern for MCP Tools:**
- Tools are auto-generated from Pydantic schemas using `create_mcp_wrapper()` factory
- Schema models define field descriptions once (DRY principle)
- Implementation functions (`*_impl()`) contain business logic
- MCP decorators handle context management and logging

**Request Context Management:**
- Uses Python's `contextvars` for request-scoped data
- Context includes: `thread_id`, `workflow`, `step_number`, `base_path`
- Set at entry via `@mcp_decorator`, accessed via `get_*()` helpers
- Enables clean APIs without explicit parameter passing

**Model Configuration:**
- YAML-based model config (`config/models.yaml`)
- Aliases resolve to full model names (e.g., `mini` → `gpt-5-mini`)
- Use-case defaults: `fast`, `smart`, `cheap`
- Supports both API models (via LiteLLM) and CLI models (subprocess execution)

For detailed architecture documentation, see `CLAUDE.md`.

## Development Workflow

### Adding a New MCP Tool

Follow this pattern (see CLAUDE.md for details):

1. **Create Pydantic schema** in `multi_mcp/schemas/` (inherit from `BaseToolRequest` or `SingleToolRequest`)
2. **Create implementation function** in `multi_mcp/tools/` (e.g., `my_tool_impl()`)
3. **Add factory-generated wrapper** in `multi_mcp/server.py`:
   ```python
   my_tool = create_mcp_wrapper(MyToolRequest, my_tool_impl, "Description")
   my_tool = mcp.tool()(mcp_monitor(my_tool))
   ```
4. **Add unit tests** in `tests/unit/test_my_tool.py`
5. **Add integration test** in `tests/integration/test_e2e_my_tool.py`
6. **Add system prompt** (if needed) in `multi_mcp/prompts/my_tool.md`

### Debugging

```bash
# Check MCP logs (request/response)
cat logs/*.mcp.json | jq .

# Check LLM API logs
cat logs/*.llm.json | jq .

# Check console logs
tail -f logs/server.log

# Enable verbose logging
LOG_LEVEL=DEBUG uv run python multi_mcp/server.py
```

### Cleanup

```bash
# Remove all cache and build artifacts
make clean
```

This removes:
- `__pycache__/` directories
- `.pytest_cache/`
- `*.egg-info/` (including `multi.egg-info/`)
- `.ruff_cache/`, `.mypy_cache/`, `.pyright/`
- `*.pyc`, `*.pyo`, `*.swp` files
- Coverage reports, dist/, build/

## Logging and Debugging

Multi-MCP has comprehensive logging for development and debugging:

**MCP Tool Logging** (`multi_mcp/utils/mcp_logger.py`):
- Logs all MCP tool requests and responses
- Format: `logs/TIMESTAMP.THREAD_ID.mcp.json`
- Tracks: tool_name, direction (request/response), data, thread_id

**LLM API Logging** (`multi_mcp/utils/request_logger.py`):
- Logs all LiteLLM API calls
- Format: `logs/TIMESTAMP.THREAD_ID.llm.json`
- Tracks: model, messages, temperature, usage, response

**Console Logging:**
- All logs also go to `logs/server.log`
- Structured tags: `[CODEREVIEW]`, `[CHAT]`, `[COMPARE]`, `[MODEL_CALL]`, `[MCP_LOG]`

**Example log files:**
```
logs/
├── server.log                         # Console logs
├── 20251204_180512_345.thread123.mcp.json  # MCP request
├── 20251204_180514_678.thread123.mcp.json  # MCP response
└── 20251204_180515_234.thread123.llm.json  # LLM API call
```

## Common Development Tasks

**Updating Prompts:**
- Edit files in `multi_mcp/prompts/*.md`
- Changes take effect on server restart
- Test with: `RUN_E2E=1 uv run pytest tests/integration/`

**Adding New Models:**
- Edit `config/models.yaml`
- Add aliases, temperature constraints, provider info
- Update tests if model behavior differs
- See `CLAUDE.md` for model configuration details

**Debugging Model Calls:**
- Check MCP logs: `cat logs/*.mcp.json | jq .`
- Check LLM logs: `cat logs/*.llm.json | jq .`
- Check console logs for tagged entries with thread_id
- Use `LOG_LEVEL=DEBUG` for verbose output

## Project File Guidelines

- **Documentation**: New documentation goes in `docs/`
- **Temporary Files**: Use `tmp/` for experiments and complex bash scripts
- **Reference Projects**: `ref/` contains reference projects - DO NOT modify
- **No Bash for File Operations**: Use Claude Code's Read/Write tools, NOT Bash commands
- **Python Scripts**: Write to `tmp/` directory first, then execute with `uv run python tmp/file_name.py`

## Questions?

Open an issue with the "Question" type and we'll help you out!
