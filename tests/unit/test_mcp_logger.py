"""Unit tests for MCP logging."""

import json
from unittest.mock import patch

from multi_mcp.utils.context import clear_context, set_request_context
from multi_mcp.utils.mcp_logger import log_mcp_interaction


class TestMCPLogger:
    """Tests for MCP interaction logging."""

    def test_log_mcp_request(self, tmp_path):
        """Test logging MCP request."""
        set_request_context(thread_id="test-123")
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", tmp_path):
            log_mcp_interaction(direction="request", tool_name="codereview", data={"step": "Review code", "step_number": 1})

        # Find the log file
        log_files = list(tmp_path.glob("*.mcp.json"))
        assert len(log_files) == 1

        # Verify contents
        with open(log_files[0]) as f:
            log_data = json.load(f)

        assert log_data["direction"] == "request"
        assert log_data["tool_name"] == "codereview"
        assert log_data["thread_id"] == "test-123"
        assert log_data["data"]["step"] == "Review code"
        assert log_data["data"]["step_number"] == 1
        assert "timestamp" in log_data

    def test_log_mcp_response(self, tmp_path):
        """Test logging MCP response."""
        set_request_context(thread_id="test-123")
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", tmp_path):
            log_mcp_interaction(direction="response", tool_name="codereview", data={"status": "success", "issues_found": []})

        log_files = list(tmp_path.glob("*.mcp.json"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            log_data = json.load(f)

        assert log_data["direction"] == "response"
        assert log_data["data"]["status"] == "success"
        assert log_data["data"]["issues_found"] == []

    def test_log_mcp_no_thread_id(self, tmp_path):
        """Test logging without thread_id (e.g., models)."""
        clear_context()  # Clear any previous context
        set_request_context(thread_id=None)  # No thread_id in context
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", tmp_path):
            log_mcp_interaction(direction="request", tool_name="models", data={})

        log_files = list(tmp_path.glob("*.mcp.json"))
        assert len(log_files) == 1

        # Filename should not have thread_id part
        assert ".mcp.json" in log_files[0].name
        # Should not have double dots
        assert ".." not in log_files[0].name

        with open(log_files[0]) as f:
            log_data = json.load(f)

        assert log_data["thread_id"] is None

    def test_log_mcp_filename_format(self, tmp_path):
        """Test that filename has correct format."""
        set_request_context(thread_id="thread-456")
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", tmp_path):
            log_mcp_interaction(direction="request", tool_name="codereview", data={"test": "data"})

        log_files = list(tmp_path.glob("*.mcp.json"))
        assert len(log_files) == 1

        filename = log_files[0].name
        # Should have format: TIMESTAMP.thread-456.mcp.json
        assert ".thread-456.mcp.json" in filename
        # Should start with timestamp (8 digits for date)
        assert filename[:8].isdigit()

    def test_log_mcp_error_handling(self, tmp_path):
        """Test that logging errors don't fail the main flow."""
        # Mock write_log_file to simulate failure
        with patch("multi_mcp.utils.mcp_logger.write_log_file", return_value=None):
            # Should not raise exception
            log_mcp_interaction(direction="request", tool_name="codereview", data={"test": "data"})

    def test_log_mcp_json_serialization(self, tmp_path):
        """Test that complex data structures are properly serialized."""
        set_request_context(thread_id="test-123")
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", tmp_path):
            log_mcp_interaction(
                direction="request",
                tool_name="codereview",
                data={
                    "step": "Review",
                    "files": ["file1.py", "file2.py"],
                    "issues": [
                        {"severity": "high", "line": 42},
                        {"severity": "low", "line": 100},
                    ],
                    "metadata": {"key": "value"},
                },
            )

        log_files = list(tmp_path.glob("*.mcp.json"))
        with open(log_files[0]) as f:
            log_data = json.load(f)

        # Verify complex structures are preserved
        assert len(log_data["data"]["files"]) == 2
        assert len(log_data["data"]["issues"]) == 2
        assert log_data["data"]["issues"][0]["severity"] == "high"
        assert log_data["data"]["metadata"]["key"] == "value"

    def test_log_mcp_different_tools(self, tmp_path):
        """Test logging for different tools."""
        import time

        set_request_context(thread_id="test-123")
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", tmp_path):
            # Log codereview
            log_mcp_interaction(direction="request", tool_name="codereview", data={"step": 1})

            # Small delay to ensure different timestamps
            time.sleep(0.01)

            # Log models
            log_mcp_interaction(direction="request", tool_name="models", data={})

        log_files = list(tmp_path.glob("*.mcp.json"))
        assert len(log_files) == 2

        # Verify both were logged
        tool_names = set()
        for log_file in log_files:
            with open(log_file) as f:
                log_data = json.load(f)
                tool_names.add(log_data["tool_name"])

        assert "codereview" in tool_names
        assert "models" in tool_names
