"""Unit tests for repository context utilities."""

import tempfile
from pathlib import Path

import pytest

from multi_mcp.utils.context import clear_context, set_request_context
from multi_mcp.utils.repository import build_repository_context


class TestBuildRepositoryContext:
    """Tests for build_repository_context function."""

    def test_build_repository_context_from_claude_md(self):
        """Test loading context from CLAUDE.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            claude_md = base_path / "CLAUDE.md"
            claude_md.write_text("# Project Instructions\nThis is a test project.")

            result = build_repository_context(str(base_path))

            assert result is not None
            assert "<REPOSITORY_CONTEXT>" in result
            assert '<PROJECT_INSTRUCTIONS source="CLAUDE.md">' in result
            assert "This is a test project" in result
            assert "</PROJECT_INSTRUCTIONS>" in result
            assert "</REPOSITORY_CONTEXT>" in result

    def test_build_repository_context_from_agents_md_fallback(self):
        """Test loading context from AGENTS.md when CLAUDE.md doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            agents_md = base_path / "AGENTS.md"
            agents_md.write_text("# Agent Instructions\nUse these guidelines.")

            result = build_repository_context(str(base_path))

            assert result is not None
            assert "<REPOSITORY_CONTEXT>" in result
            assert '<PROJECT_INSTRUCTIONS source="AGENTS.md">' in result
            assert "Use these guidelines" in result

    def test_build_repository_context_prefers_claude_over_agents(self):
        """Test that CLAUDE.md is preferred over AGENTS.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            claude_md = base_path / "CLAUDE.md"
            agents_md = base_path / "AGENTS.md"

            claude_md.write_text("# Claude Instructions")
            agents_md.write_text("# Agent Instructions")

            result = build_repository_context(str(base_path))

            assert result is not None
            assert "CLAUDE.md" in result
            assert "Claude Instructions" in result
            assert "Agent Instructions" not in result

    def test_build_repository_context_no_base_path(self):
        """Test that None base_path returns None."""
        result = build_repository_context(None)

        assert result is None

    def test_build_repository_context_nonexistent_path(self):
        """Test that nonexistent path returns None."""
        result = build_repository_context("/nonexistent/path/12345")

        assert result is None

    def test_build_repository_context_no_context_files_returns_none(self):
        """Test that directory without context files returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # Create some other files, but not CLAUDE.md or AGENTS.md
            (base_path / "README.md").write_text("# Readme")

            result = build_repository_context(str(base_path))

            assert result is None

    def test_build_repository_context_xml_wrapping(self):
        """Test that context is properly wrapped in XML tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            claude_md = base_path / "CLAUDE.md"
            content = "Test content with <special> characters & symbols"
            claude_md.write_text(content)

            result = build_repository_context(str(base_path))

            assert result is not None
            # Check structure
            lines = result.split("\n")
            assert lines[0] == "<REPOSITORY_CONTEXT>"
            assert lines[1] == '<PROJECT_INSTRUCTIONS source="CLAUDE.md">'
            assert lines[2] == content
            assert lines[3] == "</PROJECT_INSTRUCTIONS>"
            assert lines[4] == "</REPOSITORY_CONTEXT>"

    def test_build_repository_context_strips_whitespace(self):
        """Test that file content is stripped of surrounding whitespace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            claude_md = base_path / "CLAUDE.md"
            # Add leading/trailing whitespace
            claude_md.write_text("\n\n  Test content  \n\n")

            result = build_repository_context(str(base_path))

            assert result is not None
            assert "Test content" in result
            # Check that content is stripped in the XML
            assert "\n\nTest content" in result or "Test content\n\n" not in result

    def test_build_repository_context_multiline_content(self):
        """Test that multiline content is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            claude_md = base_path / "CLAUDE.md"
            content = """# Project

Line 1
Line 2
Line 3"""
            claude_md.write_text(content)

            result = build_repository_context(str(base_path))

            assert result is not None
            assert "Line 1" in result
            assert "Line 2" in result
            assert "Line 3" in result

    def test_build_repository_context_empty_file(self):
        """Test that empty context file is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            claude_md = base_path / "CLAUDE.md"
            claude_md.write_text("")

            result = build_repository_context(str(base_path))

            # Should still return wrapped content (even if empty)
            assert result is not None
            assert "<REPOSITORY_CONTEXT>" in result
            assert "</REPOSITORY_CONTEXT>" in result

    def test_build_repository_context_file_read_error_returns_none(self):
        """Test that file read errors return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            claude_md = base_path / "CLAUDE.md"
            claude_md.write_text("test")

            # Make file unreadable (Unix only)
            import sys

            if sys.platform != "win32":
                claude_md.chmod(0o000)

                try:
                    result = build_repository_context(str(base_path))
                    # Should return None on read error
                    assert result is None
                finally:
                    # Restore permissions for cleanup
                    claude_md.chmod(0o644)
            else:
                # Skip this test on Windows
                pytest.skip("File permission test not applicable on Windows")

    def test_build_repository_context_uses_explicit_base_path_over_context(self):
        """Test that explicit base_path parameter takes precedence over context."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            # Create CLAUDE.md in both directories
            base_path1 = Path(tmpdir1)
            base_path2 = Path(tmpdir2)

            (base_path1 / "CLAUDE.md").write_text("Content from path 1")
            (base_path2 / "CLAUDE.md").write_text("Content from path 2")

            # Set context to path1
            set_request_context(base_path=str(base_path1))

            try:
                # Explicitly pass path2 - should use path2, not context
                result = build_repository_context(str(base_path2))

                assert result is not None
                assert "Content from path 2" in result
                assert "Content from path 1" not in result
            finally:
                clear_context()

    def test_build_repository_context_falls_back_to_context_when_param_is_none(self):
        """Test that context base_path is used when parameter is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "CLAUDE.md").write_text("Content from context")

            # Set context
            set_request_context(base_path=str(base_path))

            try:
                # Don't pass base_path parameter - should use context
                result = build_repository_context(None)

                assert result is not None
                assert "Content from context" in result
            finally:
                clear_context()

    def test_build_repository_context_returns_none_when_no_param_and_no_context(self):
        """Test that None is returned when neither param nor context provides base_path."""
        clear_context()

        # No parameter, no context
        result = build_repository_context(None)

        assert result is None
