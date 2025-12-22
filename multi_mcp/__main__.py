"""Enable running multi_mcp as a module: python -m multi_mcp.

Runs the MCP server (matching official MCP server patterns).
For CLI usage, use the 'multi' command instead.
"""

from multi_mcp.server import main

if __name__ == "__main__":
    main()
