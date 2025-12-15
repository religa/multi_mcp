.PHONY: help install install-hooks verify test test-integration test-all clean lint format format-check typecheck check pre-commit server

# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

help:
	@echo "Multi-MCP Makefile Commands"
	@echo ""
	@echo "Setup/Installation:"
	@echo "  make install             Run installation script (setup venv, deps, .env)"
	@echo "  make install-hooks       Install git pre-commit hooks (API key checks)"
	@echo "  make verify              Verify installation is working"
	@echo ""
	@echo "Development:"
	@echo "  make server              Run the MCP server"
	@echo "  make check               Run all code quality checks (format, typecheck, lint)"
	@echo "  make pre-commit          Run pre-commit checks (format-check, lint, typecheck, test)"
	@echo ""
	@echo "Testing:"
	@echo "  make test                Run unit tests only (fast)"
	@echo "  make test-integration    Run integration tests (requires API keys)"
	@echo "  make test-all            Run all tests (unit + integration)"
	@echo ""
	@echo "Code Quality (individual):"
	@echo "  make format              Format code with ruff (fixes in place)"
	@echo "  make format-check        Check formatting without modifying files"
	@echo "  make typecheck           Run pyright type checker"
	@echo "  make lint                Run ruff linter"
	@echo ""
	@echo "Other:"
	@echo "  make clean               Remove build artifacts and cache"

install:
	@echo "Running Multi-MCP installation..."
	@chmod +x scripts/install.sh
	./scripts/install.sh

install-hooks:
	@echo "Installing git pre-commit hooks..."
	@chmod +x .githooks/pre-commit
	@ln -sf ../../.githooks/pre-commit .git/hooks/pre-commit
	@echo "✓ Git hooks installed"
	@echo ""
	@echo "Pre-commit hook will now check cassettes for API keys before commits."
	@echo "Test it: git add <file> && git commit -m 'test'"

verify:
	@echo "Verifying Multi-MCP installation..."
	@if [ ! -d ".venv" ]; then \
		echo "ERROR: Virtual environment not found. Run 'make install' first."; \
		exit 1; \
	fi
	@if [ ! -f ".env" ]; then \
		echo "ERROR: .env file not found. Run 'make install' to generate it."; \
		exit 1; \
	fi
	@echo "✓ Virtual environment exists"
	@echo "✓ .env file exists"
	@.venv/bin/python -c "from multi_mcp.server import mcp; print('✓ Server module loads correctly')" || \
		(echo "ERROR: Server module failed to load"; exit 1)
	@echo ""
	@echo "Installation verified! Next steps:"
	@echo "1. Add API keys to .env file"
	@echo "2. Configure your MCP client (see docs/INSTALL_QUICKSTART.md)"
	@echo "3. Restart MCP client and type /multi"

server:
	@echo "Starting Multi-MCP server..."
	./scripts/run_server.sh

check: format typecheck lint
	@echo "✓ All code quality checks passed!"

pre-commit: format-check lint typecheck test
	@echo "✓ All pre-commit checks passed!"

format-check:
	@echo "Checking code formatting with ruff..."
	@uv run ruff format --check .

test:
	@echo "Running unit tests..."
	uv run pytest tests/unit/ -v

test-cov:
	@echo "Running unit tests with coverage report..."
	uv run pytest tests/unit/ --cov=multi_mcp --cov-report=term-missing --cov-report=html
	@echo "✓ Coverage report generated at htmlcov/index.html"

test-integration:
	@echo "Running integration tests in parallel (requires API keys)..."
	@if [ -z "$$OPENAI_API_KEY" ] && [ -z "$$GEMINI_API_KEY" ] && [ -z "$$OPENROUTER_API_KEY" ]; then \
		echo "ERROR: No API keys set (need OPENAI_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY)"; \
		echo "Set at least one: export OPENAI_API_KEY='sk-...'"; \
		exit 1; \
	fi
	RUN_E2E=1 uv run pytest tests/integration/ -n auto -v

test-all:
	@echo "Running all tests (unit + integration in parallel)..."
	@if [ -z "$$OPENAI_API_KEY" ] && [ -z "$$GEMINI_API_KEY" ] && [ -z "$$OPENROUTER_API_KEY" ]; then \
		echo "ERROR: No API keys set (need OPENAI_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY)"; \
		echo "Set at least one: export OPENAI_API_KEY='sk-...'"; \
		exit 1; \
	fi
	uv run pytest tests/unit/ -v
	RUN_E2E=1 uv run pytest tests/integration/ -n auto -v
	@echo "✓ All tests passed!"

lint:
	@echo "Running ruff linter..."
	uv run ruff check .

format:
	@echo "Formatting code with ruff..."
	uv run ruff format .
	uv run ruff check . --fix

typecheck:
	@echo "Running pyright type checker..."
	uv run pyright

clean:
	@echo "Cleaning build artifacts and cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.swp" -delete
	rm -rf .coverage htmlcov/ dist/ build/ .ruff_cache/ .mypy_cache/ .pyright/
	@echo "✓ Cleaned successfully!"
