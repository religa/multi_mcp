#!/usr/bin/env bash
# Run the Multi-MCP FastMCP server on stdio

set -euo pipefail

# Change to project root
cd "$(dirname "$0")/.."

# Ensure .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please create .env from .env.example and configure API keys"
    exit 1
fi

# Run the server
exec uv run python -m multi_mcp.server
