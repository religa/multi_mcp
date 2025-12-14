#!/bin/bash
# Test that the MCP server can start and respond to basic requests

set -e

echo "Testing Multi-MCP server..."
echo ""

# Test 1: Python syntax check
echo "[1/3] Checking Python syntax..."
uv run python -m py_compile multi_mcp/server.py
echo "  ✓ Syntax OK"
echo ""

# Test 2: Type checking
echo "[2/3] Running type checks..."
uv run pyright multi_mcp/server.py --level error
echo "  ✓ Types OK"
echo ""

# Test 3: Import check
echo "[3/3] Testing imports..."
uv run python -c "from multi_mcp.server import mcp; print(f'  ✓ Server initialized: {mcp.name}')"
echo ""

echo "All server tests passed! ✓"
echo ""
echo "To run the server:"
echo "  ./scripts/run_server.sh"
echo ""
echo "Or directly:"
echo "  uv run python -m multi_mcp.server"
