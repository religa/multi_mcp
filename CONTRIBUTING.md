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

# Integration tests (25 tests, ~10min, REQUIRED before PR)
make test-integration
# or: RUN_E2E=1 uv run pytest tests/integration/ -v
```

## Code Standards

- **Python 3.13+** required (as specified in `pyproject.toml`)
- **Type hints** on all functions
- **Async-first** - use `async def` for I/O operations
- **Test coverage** - minimum 80% overall (add tests for new features)
- **Line length** - 140 characters max (configured in `pyproject.toml`)
- **Error handling** - return structured error dicts with context
- **Logging** - use `logger.info()` for model calls with thread_id, model name, token usage

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
│   ├── comparison.py  # Comparison request/response
│   └── debate.py      # Debate request/response
├── tools/             # Tool implementation functions (*_impl)
│   ├── codereview.py  # Code review workflow
│   ├── chat.py        # Interactive chat
│   ├── comparison.py  # Multi-model parallel analysis
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
│   ├── comparison.md
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

We have 389 total tests: 364 unit tests (~2s) and 25 integration tests (~10min).

```bash
# Unit tests only (364 tests, ~2s, fast - run before every commit)
make test
# or: uv run pytest tests/unit/ -v

# Integration tests (25 tests, ~10min, requires real API keys)
make test-integration
# or: RUN_E2E=1 uv run pytest tests/integration/ -v

# All tests (389 total)
make test-all
# or: RUN_E2E=1 uv run pytest -v

# Run with coverage report
uv run pytest tests/unit/ --cov=src --cov-report=html
```

**Note:** Integration tests require at least one API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY) and make real API calls which cost money. They are **disabled in CI** to save costs.

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

## Development Workflow

### Adding a New MCP Tool

Follow this pattern (see CLAUDE.md for details):

1. **Create Pydantic schema** in `src/schemas/` (inherit from `BaseToolRequest` or `SingleToolRequest`)
2. **Create implementation function** in `src/tools/` (e.g., `my_tool_impl()`)
3. **Add factory-generated wrapper** in `src/server.py`:
   ```python
   my_tool = create_mcp_wrapper(MyToolRequest, my_tool_impl, "Description")
   my_tool = mcp.tool()(mcp_monitor(my_tool))
   ```
4. **Add unit tests** in `tests/unit/test_my_tool.py`
5. **Add integration test** in `tests/integration/test_e2e_my_tool.py`
6. **Add system prompt** (if needed) in `src/prompts/my_tool.md`

### Debugging

```bash
# Check MCP logs (request/response)
cat logs/*.mcp.json | jq .

# Check LLM API logs
cat logs/*.llm.json | jq .

# Check console logs
tail -f logs/server.log

# Enable verbose logging
LOG_LEVEL=DEBUG uv run python src/server.py
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

## Questions?

Open an issue with the "Question" type and we'll help you out!
