"""Minimal smoke tests for CLI models (requires real CLIs installed).

These tests verify that CLIs are actually working end-to-end.
Only 2 tests per CLI - basic execution and alias resolution.

Requirements:
- Real CLI tools installed (claude, gemini, codex)
- API keys configured in environment
- Set RUN_E2E=1 to run these tests

Run with:
    RUN_E2E=1 pytest tests/integration/test_cli_smoke.py -v
"""

import pytest


@pytest.mark.integration
@pytest.mark.xdist_group(name="claude_cli")  # Sequential execution for Claude CLI
async def test_claude_cli_basic_smoke(require_cli):
    """Smoke test: Claude CLI basic execution."""
    require_cli("claude")

    from multi_mcp.utils.llm_runner import execute_single

    result = await execute_single(
        model="claude-cli",
        messages=[{"role": "user", "content": "Say 'CLI working'"}],
    )

    assert result.status == "success", f"Expected success, got: {result.error}"
    assert result.content, "Response content should not be empty"
    assert result.metadata.model == "claude-cli"


@pytest.mark.integration
@pytest.mark.xdist_group(name="claude_cli")  # Sequential execution for Claude CLI
async def test_claude_cli_alias_smoke(require_cli):
    """Smoke test: Claude CLI with alias."""
    require_cli("claude")

    from multi_mcp.utils.llm_runner import execute_single

    result = await execute_single(
        model="cl-cli",  # Using alias
        messages=[{"role": "user", "content": "Say 'Alias working'"}],
    )

    assert result.status == "success", f"Expected success, got: {result.error}"
    assert result.content, "Response content should not be empty"
    assert result.metadata.model == "claude-cli"  # Should resolve to canonical name


@pytest.mark.integration
async def test_gemini_cli_basic_smoke(require_cli):
    """Smoke test: Gemini CLI basic execution."""
    require_cli("gemini")

    from multi_mcp.utils.llm_runner import execute_single

    result = await execute_single(
        model="gemini-cli",
        messages=[{"role": "user", "content": "Say 'CLI working'"}],
    )

    assert result.status == "success", f"Expected success, got: {result.error}"
    assert result.content, "Response content should not be empty"
    assert result.metadata.model == "gemini-cli"


@pytest.mark.integration
async def test_gemini_cli_alias_smoke(require_cli):
    """Smoke test: Gemini CLI with alias."""
    require_cli("gemini")

    from multi_mcp.utils.llm_runner import execute_single

    result = await execute_single(
        model="gem-cli",  # Using alias
        messages=[{"role": "user", "content": "Say 'Alias working'"}],
    )

    assert result.status == "success", f"Expected success, got: {result.error}"
    assert result.content, "Response content should not be empty"
    assert result.metadata.model == "gemini-cli"


@pytest.mark.integration
async def test_codex_cli_basic_smoke(require_cli):
    """Smoke test: Codex CLI basic execution."""
    require_cli("codex")

    from multi_mcp.utils.llm_runner import execute_single

    result = await execute_single(
        model="codex-cli",
        messages=[{"role": "user", "content": "Say 'CLI working'"}],
    )

    assert result.status == "success", f"Expected success, got: {result.error}"
    assert result.content, "Response content should not be empty"
    assert result.metadata.model == "codex-cli"


@pytest.mark.integration
async def test_codex_cli_alias_smoke(require_cli):
    """Smoke test: Codex CLI with alias."""
    require_cli("codex")

    from multi_mcp.utils.llm_runner import execute_single

    result = await execute_single(
        model="cx-cli",  # Using alias
        messages=[{"role": "user", "content": "Say 'Alias working'"}],
    )

    assert result.status == "success", f"Expected success, got: {result.error}"
    assert result.content, "Response content should not be empty"
    assert result.metadata.model == "codex-cli"
