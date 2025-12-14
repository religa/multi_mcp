"""Unit tests for request_logger utilities."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from multi_mcp.utils.context import clear_context, set_request_context
from multi_mcp.utils.request_logger import log_llm_interaction


class TestLogLLMInteraction:
    """Tests for log_llm_interaction function."""

    def test_log_llm_interaction_creates_file(self):
        """Test that log_llm_interaction creates a log file."""
        set_request_context(thread_id="test-123")
        request_data = {"model": "gpt-5-mini", "messages": [{"role": "user", "content": "Hello"}]}
        response_data = {"content": "Hi there", "usage": {"total_tokens": 10}}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                # Check that file was created
                files = list(Path(tmpdir).glob("*.llm.json"))
                assert len(files) == 1
                assert "test-123" in files[0].name

    def test_log_llm_interaction_contains_request_data(self):
        """Test that log file contains request data."""
        set_request_context(thread_id="test-123")
        request_data = {
            "model_input": "gpt-5-mini",
            "canonical_name": "gpt-5-mini",
            "temperature": 1.0,
        }
        response_data = {"content": "Response"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                assert len(files) == 1

                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)

                assert logged["request"]["model_input"] == "gpt-5-mini"
                assert logged["request"]["temperature"] == 1.0

    def test_log_llm_interaction_contains_response_data(self):
        """Test that log file contains response data."""
        set_request_context(thread_id="test-123")
        request_data = {"model": "gpt-5-mini"}
        response_data = {
            "content": "Test response",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)

                assert logged["response"]["content"] == "Test response"
                assert logged["response"]["usage"]["total_tokens"] == 15

    def test_log_llm_interaction_includes_thread_id(self):
        """Test that thread_id is included in log data."""
        set_request_context(thread_id="test-123")
        request_data = {"model": "gpt-5-mini"}
        response_data = {"content": "Response"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)

                assert logged["thread_id"] == "test-123"

    def test_log_llm_interaction_without_thread_id(self):
        """Test logging without thread_id."""
        clear_context()  # Clear any previous context
        # Don't set context - thread_id should be None
        request_data = {"model": "gpt-5-mini"}
        response_data = {"content": "Response"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                assert len(files) == 1

                # Verify thread_id is None in log data
                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)
                assert logged["thread_id"] is None

                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)

                assert logged["thread_id"] is None

    def test_log_llm_interaction_with_complex_messages(self):
        """Test logging with complex message structures."""
        set_request_context(thread_id="test-123")
        request_data = {
            "model": "gpt-5-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "What is 2+2?"},
            ],
        }
        response_data = {"content": "4", "usage": {"total_tokens": 20}}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)

                messages = logged["request"]["messages"]
                assert len(messages) == 2
                assert messages[0]["role"] == "system"
                assert messages[1]["role"] == "user"

    def test_log_llm_interaction_handles_write_errors(self):
        """Test that write errors are handled gracefully."""
        set_request_context(thread_id="test-123")
        request_data = {"model": "gpt-5-mini"}
        response_data = {"content": "Response"}

        # Use invalid directory to trigger error
        with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path("/invalid/nonexistent/dir")):
            # Should not raise exception
            log_llm_interaction(request_data, response_data)

    def test_log_llm_interaction_file_naming(self):
        """Test that log files have correct naming convention."""
        set_request_context(thread_id="test-123")
        request_data = {"model": "gpt-5-mini"}
        response_data = {"content": "Response"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                assert len(files) == 1

                filename = files[0].name
                # Should have format: TIMESTAMP.THREADID.llm.json
                assert "test-123" in filename
                assert filename.endswith(".llm.json")

    def test_log_llm_interaction_timestamp_added(self):
        """Test that timestamp is added to logged data."""
        set_request_context(thread_id="test-123")
        request_data = {"model": "gpt-5-mini"}
        response_data = {"content": "Response"}

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)

                assert "timestamp" in logged
                # ISO format timestamp
                assert "T" in logged["timestamp"]

    def test_log_llm_interaction_preserves_all_fields(self):
        """Test that all request/response fields are preserved."""
        set_request_context(thread_id="test-123")
        request_data = {
            "model_input": "mini",
            "canonical_name": "gpt-5-mini",
            "litellm_model": "openai/gpt-5-mini",
            "temperature": 1.0,
            "num_messages": 2,
        }
        response_data = {
            "content": "Response",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "model": "openai/gpt-5-mini",
            "canonical_name": "gpt-5-mini",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("multi_mcp.utils.log_helpers.LOGS_DIR", Path(tmpdir)):
                log_llm_interaction(request_data, response_data)

                files = list(Path(tmpdir).glob("*.llm.json"))
                with open(files[0], encoding="utf-8") as f:
                    logged = json.load(f)

                # All request fields should be present
                assert logged["request"]["model_input"] == "mini"
                assert logged["request"]["canonical_name"] == "gpt-5-mini"
                assert logged["request"]["temperature"] == 1.0

                # All response fields should be present
                assert logged["response"]["content"] == "Response"
                assert logged["response"]["usage"]["total_tokens"] == 150
