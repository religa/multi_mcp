# Multi-MCP: Multi-Model Code Review and Analysis MCP Server for Claude Code

<!-- mcp-name: io.github.religa/multi-mcp -->

[![CI](https://github.com/religa/multi_mcp/workflows/CI/badge.svg)](https://github.com/religa/multi_mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A **multi-model AI orchestration MCP server** for **automated code review** and **LLM-powered analysis**. Multi-MCP integrates with **Claude Code CLI** and **OpenCode** to orchestrate multiple AI models (OpenAI GPT, Anthropic Claude, Google Gemini) for **code quality checks**, **security analysis** (OWASP Top 10), and **multi-agent consensus**. Built on the **Model Context Protocol (MCP)**, this tool enables Python developers and DevOps teams to automate code reviews with AI-powered insights directly in their development workflow.

![Demo Video](https://github.com/user-attachments/assets/39c3f100-e20d-4c3d-8130-b01c401f2d29)

## Features

- **🔍 Code Review** - Systematic workflow with OWASP Top 10 security checks and performance analysis
- **💬 Chat** - Interactive development assistance with repository context awareness
- **🔄 Compare** - Parallel multi-model analysis for architectural decisions
- **🎭 Debate** - Multi-agent consensus workflow (independent answers + critique)
- **🤖 Multi-Model Support** - OpenAI GPT, Anthropic Claude, Google Gemini, and OpenRouter
- **🖥️ CLI & API Models** - Mix CLI-based (Gemini CLI, Codex CLI) and API models
- **🏷️ Model Aliases** - Use short names like `mini`, `sonnet`, `gemini`
- **🧵 Threading** - Maintain context across multi-step reviews

## How It Works

Multi-MCP acts as an **MCP server** that Claude Code or OpenCode connects to, providing AI-powered code analysis tools:

1. **Install** the MCP server and configure your AI model API keys
2. **Integrate** with Claude Code or OpenCode automatically via `make install`
3. **Invoke** tools using natural language (e.g., "multi codereview this file")
4. **Get Results** from multiple AI models orchestrated in parallel

## Performance

**Fast Multi-Model Analysis:**
- ⚡ **Parallel Execution** - 3 models in ~10s (vs ~30s sequential)
- 🔄 **Async Architecture** - Non-blocking Python asyncio
- 💾 **Conversation Threading** - Maintains context across multi-step reviews
- 📊 **Low Latency** - Response time = slowest model, not sum of all models

## Quick Start

**Prerequisites:**
- Python 3.11+
- API key for at least one provider (OpenAI, Anthropic, Google, or OpenRouter)

### Installation

<!-- Claude Code Plugin - Coming Soon
#### Option 1: Claude Code Plugin (Recommended)

```bash
# Add the marketplace
/plugin marketplace add religa/multi_mcp

# Install the plugin
/plugin install multi-mcp@multi_mcp
```

Then configure API keys in `~/.multi_mcp/.env` (see [Configuration](#configuration)).
-->

#### Option 1: From Source

```bash
# Clone and install
git clone https://github.com/religa/multi_mcp.git
cd multi_mcp
# Execute ./scripts/install.sh
make install

# The installer will:
# 1. Install dependencies (uv sync)
# 2. Generate your .env file
# 3. Automatically add to Claude Code / OpenCode config (requires jq)
# 4. Test the installation
```

#### Option 2: Manual Configuration

If you prefer not to run `make install`:

```bash
# Install dependencies
uv sync

# Copy and configure .env
cp .env.example .env
# Edit .env with your API keys
```

Add to Claude Code (`~/.claude.json`) or OpenCode (`~/.opencode/opencode.json`), replacing `/path/to/multi_mcp` with your actual clone path:

**Claude Code:**

```json
{
  "mcpServers": {
    "multi": {
      "type": "stdio",
      "command": "/path/to/multi_mcp/.venv/bin/python",
      "args": ["-m", "multi_mcp.server"]
    }
  }
}
```

**OpenCode:**

```json
{
  "mcp": {
    "multi": {
      "type": "local",
      "command": ["/path/to/multi_mcp/.venv/bin/python", "-m", "multi_mcp.server"],
      "enabled": true
    }
  }
}
```

## Configuration

### Environment Configuration (API Keys & Settings)

Multi-MCP loads settings from `.env` files in this order (highest priority first):
1. **Environment variables** (already set in shell)
2. **Project `.env`** (current directory or project root)
3. **User `.env`** (`~/.multi_mcp/.env`) - fallback for pip installs

Edit `.env` with your API keys:

```bash
# API Keys (configure at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=sk-or-...

# Azure OpenAI (optional)
AZURE_API_KEY=...
AZURE_API_BASE=https://your-resource.openai.azure.com/

# AWS Bedrock (optional)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=us-east-1

# Model Configuration
DEFAULT_MODEL=gpt-5-mini
DEFAULT_MODEL_LIST=gpt-5-mini,gemini-3-flash
```

### Model Configuration (Adding Custom Models)

Models are defined in YAML configuration files (user config wins):
1. **Package defaults**: `multi_mcp/config/config.yaml` (bundled with package)
2. **User overrides**: `~/.multi_mcp/config.yaml` (optional, takes precedence)

To add your own models, create `~/.multi_mcp/config.yaml` (see [`config.yaml`](multi_mcp/config/config.yaml) and [`config.override.example.yaml`](multi_mcp/config/config.override.example.yaml) for examples):

```yaml
version: "1.0"

models:
  # Add a new API model
  my-custom-gpt:
    litellm_model: openai/gpt-4o
    aliases:
      - custom
    notes: "My custom GPT-4o configuration"

  # Add a custom CLI model
  my-local-llm:
    provider: cli
    cli_command: ollama
    cli_args:
      - "run"
      - "llama3.2"
    cli_parser: text
    aliases:
      - local
    notes: "Local LLaMA via Ollama"

  # Override an existing model's settings
  gpt-5-mini:
    constraints:
      temperature: 0.5  # Override default temperature
```

**Merge behavior:**
- New models are added alongside package defaults
- Existing models are merged (your settings override package defaults)
- Aliases can be "stolen" from package models to your custom models

## Usage Examples

Once installed in your MCP client (Claude Code or OpenCode), you can use these commands:

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

## Enabling Allowlist

Edit `~/.claude/settings.json` and add the following lines to `permissions.allow` to enable Claude Code to use Multi MCP without blocking for user permission:

```json
{
  "permissions": {
    "allow": [
      ...
      "mcp__multi__chat",
      "mcp__multi__codereview",
      "mcp__multi__compare",
      "mcp__multi__debate",
      "mcp__multi__models"
    ],
  },
  "env": {
    "MCP_TIMEOUT": "300000",
    "MCP_TOOL_TIMEOUT": "300000"
  },
}
```

## Model Aliases

Use short aliases instead of full model names:

| Alias | Model | Provider |
|-------|-------|----------|
| `mini` | gpt-5-mini | OpenAI |
| `nano` | gpt-5-nano | OpenAI |
| `gpt` | gpt-5.2 | OpenAI |
| `codex` | gpt-5.1-codex | OpenAI |
| `sonnet` | claude-sonnet-4.5 | Anthropic |
| `haiku` | claude-haiku-4.5 | Anthropic |
| `opus` | claude-opus-4.5 | Anthropic |
| `gemini` | gemini-3-pro-preview | Google |
| `flash` | gemini-3-flash | Google |
| `azure-mini` | azure-gpt-5-mini | Azure |
| `bedrock-sonnet` | bedrock-claude-4-5-sonnet | AWS |

Run `multi:models` to see all available models and aliases.

## CLI Models

Multi-MCP can execute **CLI-based AI models** (like Gemini CLI, Codex CLI, or Claude CLI) alongside API models. CLI models run as subprocesses and work seamlessly with all existing tools.

**Benefits:**
- Use models with full tool access (file operations, shell commands)
- Mix API and CLI models in `compare` and `debate` workflows
- Leverage local CLIs without API overhead

**Built-in CLI Models:**
- `gemini-cli` (alias: `gem-cli`) - Gemini CLI with auto-edit mode
- `codex-cli` (alias: `cx-cli`) - Codex CLI with full-auto mode
- `claude-cli` (alias: `cl-cli`) - Claude CLI with acceptEdits mode

**Adding Custom CLI Models:**

Add to `~/.multi_mcp/config.yaml` (see [Model Configuration](#model-configuration-adding-custom-models)):

```yaml
version: "1.0"

models:
  my-ollama:
    provider: cli
    cli_command: ollama
    cli_args:
      - "run"
      - "codellama"
    cli_parser: text  # "json", "jsonl", or "text"
    aliases:
      - ollama
    notes: "Local CodeLlama via Ollama"
```

**Prerequisites:**

CLI models require the respective CLI tools to be installed:

```bash
# Gemini CLI
npm install -g @anthropic-ai/gemini-cli

# Codex CLI
npm install -g @openai/codex

# Claude CLI
npm install -g @anthropic-ai/claude-code
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

## Why Multi-MCP?

| Feature | Multi-MCP | Single-Model Tools |
|---------|-----------|-------------------|
| Parallel model execution | ✅ | ❌ |
| Multi-model consensus | ✅ | Varies |
| Model debates | ✅ | ❌ |
| CLI + API model support | ✅ | ❌ |
| OWASP security analysis | ✅ | Varies |


## Troubleshooting

**"No API key found"**
- Add at least one API key to your `.env` file
- Verify it's loaded: `uv run python -c "from multi_mcp.settings import settings; print(settings.openai_api_key)"`

**Integration tests fail**
- Set `RUN_E2E=1` environment variable
- Verify API keys are valid and have sufficient credits

**Debug mode:**
```bash
export LOG_LEVEL=DEBUG # INFO is default
uv run python -m multi_mcp.server
```

Check logs in `logs/server.log` for detailed information.

## FAQ

**Q: Do I need all three AI providers?**
A: No, just one API key (OpenAI, Anthropic, or Google) is enough to get started.

**Q: Does it truly run in parallel?**
A: Yes! When you use `codereview`, `compare` or `debate` tools, all models are executed concurrently using Python's `asyncio.gather()`. This means you get responses from multiple models in the time it takes for the slowest model to respond, not the sum of all response times.

**Q: How many models can I run at the same time?**
A: There's no hard limit! You can run as many models as you want in parallel. In practice, 2-5 models work well for most use cases. All tools use your configured default models (typically 2-3), but you can specify any number of models you want.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code standards
- Testing guidelines
- Pull request process

**Quick start:**
```bash
git clone https://github.com/YOUR_USERNAME/multi_mcp.git
cd multi_mcp
uv sync --extra dev
make check && make test
```

## License

MIT License - see LICENSE file for details

## Links

- [Issue Tracker](https://github.com/religa/multi_mcp/issues)
- [Contributing Guide](CONTRIBUTING.md)
