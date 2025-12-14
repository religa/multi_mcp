"""Unit tests for log_helpers utilities."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from multi_mcp.utils.log_helpers import write_log_file


class TestWriteLogFile:
    """Tests for write_log_file function."""

    def test_write_log_file_creates_file(self):
        """Test that write_log_file creates a JSON file."""
        log_data = {"test": "data", "value": 123}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test", thread_id="thread123")

                assert filepath is not None
                assert filepath.exists()
                assert filepath.suffix == ".json"
                assert "test.json" in filepath.name

    def test_write_log_file_contains_data(self):
        """Test that written file contains correct data."""
        log_data = {"test": "data", "value": 123}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test", thread_id="thread123")

                assert filepath is not None
                with open(filepath, encoding="utf-8") as f:
                    loaded = json.load(f)

                assert loaded["test"] == "data"
                assert loaded["value"] == 123
                assert "timestamp" in loaded

    def test_write_log_file_adds_timestamp(self):
        """Test that timestamp is added to log data."""
        log_data = {"test": "data"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test")

                assert filepath is not None
                with open(filepath, encoding="utf-8") as f:
                    loaded = json.load(f)

                assert "timestamp" in loaded
                # Timestamp should be ISO format
                assert "T" in loaded["timestamp"]

    def test_write_log_file_includes_thread_id_in_filename(self):
        """Test that thread_id is included in filename."""
        log_data = {"test": "data"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test", thread_id="thread123")

                assert filepath is not None
                assert "thread123" in filepath.name

    def test_write_log_file_without_thread_id(self):
        """Test that filename works without thread_id."""
        log_data = {"test": "data"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test")

                assert filepath is not None
                # Should have format: TIMESTAMP.test.json
                parts = filepath.stem.split(".")
                assert len(parts) == 2  # timestamp.test
                assert parts[-1] == "test"

    def test_write_log_file_sanitizes_thread_id(self):
        """Test that thread_id is sanitized for safe filenames."""
        log_data = {"test": "data"}
        unsafe_id = "thread@123#with$unsafe%chars!"

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test", thread_id=unsafe_id)

                assert filepath is not None
                # Only safe characters should remain
                assert "@" not in filepath.name
                assert "#" not in filepath.name
                assert "$" not in filepath.name
                assert "%" not in filepath.name
                assert "!" not in filepath.name
                assert "thread123withunsafechars" in filepath.name

    def test_write_log_file_with_different_log_types(self):
        """Test different log type suffixes."""
        log_data = {"test": "data"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                mcp_file = write_log_file(log_data, "mcp")
                llm_file = write_log_file(log_data, "llm")

                assert mcp_file is not None
                assert llm_file is not None
                assert "mcp.json" in mcp_file.name
                assert "llm.json" in llm_file.name

    def test_write_log_file_error_handling(self):
        """Test that write errors return None."""
        log_data = {"test": "data"}

        # Use invalid directory to trigger error
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path("/invalid/nonexistent/dir")):
            filepath = write_log_file(log_data, "test")

            assert filepath is None

    def test_write_log_file_timestamp_format(self):
        """Test that timestamp has correct format."""
        log_data = {"test": "data"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test")

                assert filepath is not None
                # Filename should start with YYYYMMDD_HHMMSS_mmm (19 chars)
                filename = filepath.stem
                timestamp_part = filename.split(".")[0]
                # Format: YYYYMMDD_HHMMSS_mmm (8 + 1 + 6 + 1 + 3 = 19)
                assert len(timestamp_part) == 19
                assert timestamp_part[8] == "_"
                assert timestamp_part[15] == "_"

    def test_write_log_file_unicode_content(self):
        """Test that unicode content is preserved."""
        log_data = {
            "message": "Hello 世界",
            "emoji": "🎉",
            "special": "Ñoño",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test")

                assert filepath is not None
                with open(filepath, encoding="utf-8") as f:
                    loaded = json.load(f)

                assert loaded["message"] == "Hello 世界"
                assert loaded["emoji"] == "🎉"
                assert loaded["special"] == "Ñoño"

    def test_write_log_file_pretty_formatted(self):
        """Test that JSON is pretty-printed."""
        log_data = {"test": "data", "nested": {"key": "value"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                filepath = write_log_file(log_data, "test")

                assert filepath is not None
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()

                # Should have indentation (pretty-printed)
                assert "  " in content  # JSON indent=2
                assert "\n" in content
