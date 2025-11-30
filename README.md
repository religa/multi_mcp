# Multi-MCP

[![CI](https://github.com/religa/multi_mcp/workflows/CI/badge.svg)](https://github.com/religa/multi_mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

A multi-model AI orchestration server that provides advanced code analysis capabilities through the Model Context Protocol (MCP). Multi-MCP orchestrates multiple LLM providers to deliver multi-agent chat, debate and code review tools.

Built as a **Model Context Protocol (MCP) server** for Claude Code CLI, Multi-MCP enables developers to leverage multiple AI models (OpenAI GPT, Anthropic Claude, Google Gemini) simultaneously for code analysis tasks. Whether you need automated code review with OWASP security checks, multi-model consensus for critical decisions, or AI-powered development assistance, this MCP server integrates directly into your Claude Code workflow. Perfect for Python developers, security teams, and AI engineers looking to automate code quality checks and leverage LLM-powered analysis in their development pipeline.

⚠️ **Early Development**: Currently supports `codereview`, `chat`, `compare`, `debate`, and `models` tools. More tools coming soon.

## Features

- **🔍 Code Review** - Systematic workflow for thorough code review using external models
- **💬 Chat** - Interactive AI assistance for development questions
- **🔄 Compare** - Multi-model parallel analysis
- **🎭 Debate** - Two-step multi-model workflow: independent answers followed by critique
- **🤖 Multi-Model Support** - Works with OpenAI, Anthropic, Google, and OpenRouter
- **🖥️ CLI Model Execution** - Run CLI-based models (Claude Code CLI, Gemini CLI, Codex CLI) alongside API models
- **🏷️ Model Aliases** - Use short names like `mini`, `sonnet`, `gemini`
- **🧵 Conversation Threading** - Maintain context across multi-step reviews

## Quick Start

**Prerequisites:**
- Python 3.13+
- [uv package manager](https://github.com/astral-sh/uv)
- API key for at least one provider (OpenAI, Anthropic, Google, or OpenRouter)

**Installation:**

```bash
# Clone and install
git clone https://github.com/religa/multi_mcp.git
cd multi_mcp
make install

# The installer will:
# 1. Install dependencies
# 2. Configure your .env file
# 3. Automatically add to Claude Code config (requires jq)
# 4. Test the installation
```

After installation, restart Claude Code and type `/multi` to see available commands.

## Usage Examples

Once installed in Claude Code, you can use these commands:

**💬 Chat** - Interactive development assistance:
```
Can you ask Multi chat what's the answer to life, universe and everything?
```

**🔍 Code Review** - Analyze code with specific models:
```
Can you multi codereview this module for code quality and maintainability using gemini-3 and codex?
```

**🔄 Compare** - Get multiple perspectives (uses default models):
```
Can you multi compare the best state management approach for this React app?
```

**🎭 Debate** - Deep analysis with critique:
```
Can you multi debate the best project code name for this project?
```

**Manual Setup:**

```bash
# Clone the repository
git clone https://github.com/religa/multi_mcp.git
cd multi_mcp

# Install dependencies
uv sync

# Create .env file from template
cp .env.example .env
# Edit .env and add your API keys

# Start the server
./scripts/run_server.sh
```

**Environment Configuration:**

Edit `.env` with your API keys:

```bash
# API Keys (configure at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=sk-or-...

# Model Configuration
DEFAULT_MODEL=gpt-5-mini
DEFAULT_MODEL_LIST=gpt-5-mini,gemini-2.5-flash
```

## CLI Usage (Experimental)

Multi-MCP includes a standalone CLI for code review without needing an MCP client.

⚠️ **Note:** The CLI is experimental and under active development.

```bash
# Review a directory
multi src/

# Review specific files
multi src/server.py src/config.py

# Use a different model
multi --model mini src/

# JSON output for CI/pipelines
multi --json src/ > results.json

# Verbose logging
multi -v src/

# Specify project root (for CLAUDE.md loading)
multi --base-path /path/to/project src/
```

**CLI Options:**

| Flag | Description |
|------|-------------|
| `paths` | Files or directories to review (required) |
| `--model MODEL` | Model to use (default: from settings) |
| `--json` | Output JSON for CI/pipelines |
| `-v, --verbose` | Enable DEBUG logging |
| `--base-path PATH` | Project root for context loading |

## Model Aliases

Use short aliases instead of full model names:

| Alias | Model | Provider |
|-------|-------|----------|
| `mini` | gpt-5-mini | OpenAI |
| `sonnet` | claude-sonnet-4.5 | Anthropic |
| `gpt` | gpt-5.1 | OpenAI |
| `gemini` | gemini-3-pro-preview | Google |
| `flash` | gemini-2.5-flash | Google |

## CLI Models

Multi-MCP can execute **CLI-based AI models** (like Gemini CLI or Codex CLI) alongside API models. CLI models run as subprocesses and work seamlessly with all existing tools.

**Benefits:**
- Use models with full tool access (file operations, shell commands)
- Mix API and CLI models in `compare` and `debate` workflows
- Leverage local CLIs without API overhead

**Configuration:**

CLI models are defined in `config/models.yaml` with `provider: cli`:

```yaml
gemini-cli:
  provider: cli
  cli_command: gemini
  cli_args:
    - "-o"
    - "json"
    - "--yolo"
  cli_env:
    GEMINI_API_KEY: "${GEMINI_API_KEY}"
  cli_parser: json
  aliases:
    - gem-cli
  notes: "Gemini CLI with full tool access"

codex-cli:
  provider: cli
  cli_command: codex
  cli_args:
    - "exec"
    - "--json"
    - "--dangerously-bypass-approvals-and-sandbox"
  cli_env: {}
  cli_parser: jsonl
  aliases:
    - cx-cli
  notes: "Codex CLI with full tool access"
```

**Usage Examples:**

Use CLI models just like API models:

```bash
# Code review with CLI model
Can you multi codereview this module using gemini-cli?

# Compare API vs CLI models
Can you multi compare the best approach using gpt-5-mini and gemini-cli?

# Chat with CLI model
Can you ask Multi chat using codex-cli how to optimize this function?
```

**Prerequisites:**

CLI models require the respective CLI tools to be installed:

```bash
# Install Gemini CLI
pip install google-generativeai-cli

# Install Codex CLI (Claude Code CLI)
npm install -g @anthropics/codex-cli
```

**Parser Types:**

- `json` - Parses JSON output (e.g., Gemini CLI with `-o json`)
- `jsonl` - Parses JSONL event streams (e.g., Codex CLI with `--json`)
- `text` - Raw text output (fallback)

## Architecture

```
multi_mcp/
├── src/
│   ├── server.py              # FastMCP server with MCP tools
│   ├── cli.py                 # Standalone CLI
│   ├── config.py              # Settings (env-based)
│   ├── models/                # Model config & LiteLLM integration
│   ├── schemas/               # Pydantic validation
│   ├── memory/                # Conversation threading
│   ├── tools/                 # Tool implementations
│   ├── prompts/               # System prompts
│   └── utils/                 # Helpers & logging
├── config/
│   └── models.yaml            # Model definitions
└── tests/
    ├── unit/                  # Unit tests
    └── integration/           # E2E tests
```

## Contributing

**Setup:**

```bash
git clone https://github.com/religa/multi_mcp.git
cd multi_mcp
uv sync --extra dev  # Install dependencies + dev tools (pytest, ruff, pyright)
```

**Development:**

```bash
uv run pyright        # Type checking
uv run ruff check .   # Linting
uv run ruff format .  # Formatting
uv run pytest         # Run unit tests
```

**Submit PRs** to `main` branch with:
- ✅ All tests passing (`uv run pytest`)
- ✅ Type checking clean (`uv run pyright`)
- ✅ Code formatted (`uv run ruff format .`)

## Troubleshooting

**"No API key found"**
- Add at least one API key to your `.env` file
- Verify it's loaded: `uv run python -c "from src.config import settings; print(settings.openai_api_key)"`

**Integration tests fail**
- Set `RUN_E2E=1` environment variable
- Verify API keys are valid and have sufficient credits

**Debug mode:**
```bash
export LOG_LEVEL=DEBUG # INFO is default
uv run python src/server.py
```

Check logs in `logs/server.log` for detailed information.

## License

MIT License - see LICENSE file for details
