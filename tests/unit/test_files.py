"""Unit tests for file handling (utils/files.py)."""

import os
import tempfile
from pathlib import Path

import pytest

from multi_mcp.utils.paths import resolve_path


class TestPathNormalization:
    """Tests for path resolution and security."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()

            # Create some test files
            (project / "src").mkdir()
            (project / "src" / "main.py").write_text("print('hello')")
            (project / "README.md").write_text("# Project")

            yield str(project)

    def test_resolve_absolute_path_within_base(self, temp_project):
        """Test resolving absolute path within base_path."""
        file_path = os.path.join(temp_project, "src", "main.py")
        resolved = resolve_path(file_path, temp_project)

        # Both paths should resolve to same canonical path
        assert Path(resolved).resolve() == Path(file_path).resolve()
        assert Path(resolved).is_absolute()

    def test_resolve_relative_path(self, temp_project):
        """Test resolving relative path."""
        relative_path = "src/main.py"
        resolved = resolve_path(relative_path, temp_project)

        expected = os.path.join(temp_project, "src", "main.py")
        assert Path(resolved).resolve() == Path(expected).resolve()
        assert Path(resolved).exists()

    def test_resolve_path_with_dots(self, temp_project):
        """Test resolving path with .. (parent directory)."""
        # This should be allowed if it stays within base_path
        relative_path = "src/../README.md"
        resolved = resolve_path(relative_path, temp_project)

        expected = os.path.join(temp_project, "README.md")
        assert Path(resolved).resolve() == Path(expected).resolve()

    def test_reject_path_escape_with_dots(self, temp_project):
        """Test that paths escaping base_path with .. are rejected."""
        # Try to escape with ../../../
        escape_path = "../../../etc/passwd"

        with pytest.raises(ValueError) as exc_info:
            resolve_path(escape_path, temp_project)

        assert "escapes base_path" in str(exc_info.value)

    def test_reject_absolute_path_outside_base(self, temp_project):
        """Test that absolute paths outside base_path are rejected."""
        outside_path = "/etc/passwd"

        with pytest.raises(ValueError) as exc_info:
            resolve_path(outside_path, temp_project)

        assert "escapes base_path" in str(exc_info.value)

    def test_symlink_within_base(self, temp_project):
        """Test that symlinks within base_path are allowed."""
        # Create symlink pointing to file within project
        target = Path(temp_project) / "src" / "main.py"
        link = Path(temp_project) / "link.py"
        link.symlink_to(target)

        try:
            resolved = resolve_path("link.py", temp_project)
            # Symlink should be accepted (resolves to target within base)
            assert Path(resolved).exists()
            # Resolved path should be within base_path
            assert Path(resolved).resolve().is_relative_to(Path(temp_project).resolve())
        finally:
            if link.exists():
                link.unlink()

    def test_reject_symlink_outside_base(self, temp_project):
        """Test that symlinks pointing outside base_path are rejected."""
        # Create symlink pointing outside project
        link = Path(temp_project) / "evil_link.py"
        link.symlink_to("/etc/passwd")

        try:
            with pytest.raises(ValueError) as exc_info:
                resolve_path("evil_link.py", temp_project)

            # Should reject with an error message
            error_msg = str(exc_info.value).lower()
            assert "outside" in error_msg or "escapes" in error_msg
        finally:
            if link.exists():
                link.unlink()

    def test_nonexistent_path_resolves(self, temp_project):
        """Test that nonexistent paths can be resolved (validation happens elsewhere)."""
        # resolve_path should work even if file doesn't exist
        resolved = resolve_path("src/nonexistent.py", temp_project)

        expected = os.path.join(temp_project, "src", "nonexistent.py")
        assert Path(resolved).resolve() == Path(expected).resolve()


class TestBinaryFileDetection:
    """Tests for binary file detection (null byte check)."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Text file
            text = Path(tmpdir) / "text.py"
            text.write_text("print('hello world')")

            # File with null bytes
            binary = Path(tmpdir) / "binary.bin"
            binary.write_bytes(b"hello\x00world")

            yield {"text": str(text), "binary": str(binary)}

    def test_text_file_not_binary(self, temp_files):
        """Test that text files are not detected as binary."""
        from multi_mcp.utils.files import is_binary_file

        assert is_binary_file(temp_files["text"]) is False

    def test_null_bytes_detected_as_binary(self, temp_files):
        """Test that files with null bytes are detected as binary."""
        from multi_mcp.utils.files import is_binary_file

        assert is_binary_file(temp_files["binary"]) is True

    def test_nonexistent_file_not_binary(self):
        """Test that nonexistent files return False."""
        from multi_mcp.utils.files import is_binary_file

        assert is_binary_file("/nonexistent/file.xyz") is False


class TestEmbedFilesForExpert:
    """Tests for embed_files_for_expert function."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory with various file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()

            # Create test files
            (project / "small.py").write_text("print('hello')\nprint('world')")
            (project / "README.md").write_text("# Project\nThis is a test")

            # Create large file
            large_content = "x" * (500 * 1024)  # 500KB
            (project / "large.txt").write_text(large_content)

            # Create binary file
            (project / "binary.bin").write_bytes(b"hello\x00world")

            yield str(project)

    def test_embed_files_basic(self, temp_project):
        """Test basic file embedding."""
        from multi_mcp.utils.files import embed_files_for_expert

        files = [os.path.join(temp_project, "small.py")]
        result = embed_files_for_expert(files, temp_project)

        assert "<EDITABLE_FILES>" in result
        assert "</EDITABLE_FILES>" in result
        assert "small.py" in result
        assert "print('hello')" in result
        assert "print('world')" in result
        # Check line numbers
        assert "   1│" in result
        assert "   2│" in result

    def test_embed_files_empty_list(self, temp_project):
        """Test embedding with empty file list."""
        from multi_mcp.utils.files import embed_files_for_expert

        result = embed_files_for_expert([], temp_project)

        assert "<EDITABLE_FILES>" in result
        assert "No files to embed" in result
        assert "</EDITABLE_FILES>" in result

    def test_embed_files_skips_binary(self, temp_project):
        """Test that binary files are skipped."""
        from multi_mcp.utils.files import embed_files_for_expert

        files = [
            os.path.join(temp_project, "small.py"),
            os.path.join(temp_project, "binary.bin"),
        ]
        result = embed_files_for_expert(files, temp_project)

        assert "small.py" in result
        assert "binary.bin" not in result
        assert "print('hello')" in result

    def test_embed_files_skips_large_files(self, temp_project):
        """Test that large files are skipped."""
        from multi_mcp.utils.files import embed_files_for_expert

        files = [
            os.path.join(temp_project, "small.py"),
            os.path.join(temp_project, "large.txt"),
        ]
        result = embed_files_for_expert(files, temp_project)

        assert "small.py" in result
        assert "large.txt" not in result

    def test_embed_files_skips_invalid_paths(self, temp_project):
        """Test that invalid paths are skipped gracefully."""
        from multi_mcp.utils.files import embed_files_for_expert

        files = [
            os.path.join(temp_project, "small.py"),
            "/nonexistent/file.py",
            os.path.join(temp_project, "README.md"),
        ]
        result = embed_files_for_expert(files, temp_project)

        # Valid files should be included
        assert "small.py" in result
        assert "README.md" in result
        # Invalid file should be skipped
        assert "nonexistent" not in result

    def test_embed_files_multiple_files(self, temp_project):
        """Test embedding multiple files."""
        from multi_mcp.utils.files import embed_files_for_expert

        files = [
            os.path.join(temp_project, "small.py"),
            os.path.join(temp_project, "README.md"),
        ]
        result = embed_files_for_expert(files, temp_project)

        # Both files should be present
        assert 'path="' + os.path.join(temp_project, "small.py") + '"' in result
        assert 'path="' + os.path.join(temp_project, "README.md") + '"' in result
        assert "print('hello')" in result
        assert "# Project" in result

    def test_embed_files_with_path_traversal_attempt(self, temp_project):
        """Test that path traversal attempts are blocked."""
        from multi_mcp.utils.files import embed_files_for_expert

        files = [
            "../../../etc/passwd",
            os.path.join(temp_project, "small.py"),
        ]
        result = embed_files_for_expert(files, temp_project)

        # Traversal attempt should be skipped
        assert "passwd" not in result
        # Valid file should still be included
        assert "small.py" in result

    def test_embed_files_preserves_file_path_in_output(self, temp_project):
        """Test that original file path is preserved in XML."""
        from multi_mcp.utils.files import embed_files_for_expert

        # Use relative path
        files = ["small.py"]
        result = embed_files_for_expert(files, temp_project)

        # Should preserve the original relative path in the XML
        assert 'path="small.py"' in result

    def test_embed_files_xml_structure(self, temp_project):
        """Test that output has correct XML structure."""
        from multi_mcp.utils.files import embed_files_for_expert

        files = [os.path.join(temp_project, "small.py")]
        result = embed_files_for_expert(files, temp_project)

        # Check XML tags
        assert result.startswith("<EDITABLE_FILES>")
        assert result.endswith("</EDITABLE_FILES>")
        assert "<file path=" in result
        assert "relative_path=" in result
        assert "filename=" in result
        assert "</file>" in result

        # Verify content is directly inside file tags (no <content> wrapper)
        assert "<content>" not in result
        assert "</content>" not in result

    def test_embed_files_path_attributes(self, temp_project):
        """Test that path, relative_path, and filename attributes are correct."""
        from multi_mcp.utils.files import embed_files_for_expert

        # Create a nested directory structure
        subdir = Path(temp_project) / "src" / "utils"
        subdir.mkdir(parents=True)
        test_file = subdir / "helper.py"
        test_file.write_text("# Helper module")

        # Test with absolute path
        abs_path = str(test_file)
        result = embed_files_for_expert([abs_path], temp_project)

        # Verify all three attributes
        assert f'path="{abs_path}"' in result
        assert 'relative_path="src/utils/helper.py"' in result
        assert 'filename="helper.py"' in result

        # Test with relative path
        result2 = embed_files_for_expert(["src/utils/helper.py"], temp_project)
        assert 'path="src/utils/helper.py"' in result2
        assert 'relative_path="src/utils/helper.py"' in result2
        assert 'filename="helper.py"' in result2
