"""Unit tests for CLI output parsers."""

import pytest

from src.models.litellm_client import LiteLLMClient


class TestJSONParser:
    """Test JSON parser for Gemini CLI format."""

    def test_parse_json_with_response_field(self):
        """Gemini CLI format: {"response": "..."}"""
        client = LiteLLMClient()
        stdout = '{"response": "Hello world"}'
        result = client._parse_cli_output(stdout, "json")
        assert result == "Hello world"

    def test_parse_json_without_response_field(self):
        """JSON without response field returns stringified JSON"""
        client = LiteLLMClient()
        stdout = '{"message": "Hello", "status": "ok"}'
        result = client._parse_cli_output(stdout, "json")
        assert "message" in result
        assert "Hello" in result

    def test_parse_json_array(self):
        """JSON array is stringified"""
        client = LiteLLMClient()
        stdout = '["item1", "item2", "item3"]'
        result = client._parse_cli_output(stdout, "json")
        assert "item1" in result
        assert "item2" in result

    def test_parse_json_fallback_to_text(self):
        """Malformed JSON falls back to text"""
        client = LiteLLMClient()
        stdout = '{malformed json'
        result = client._parse_cli_output(stdout, "json")
        assert result == stdout.strip()

    def test_parse_json_empty_string(self):
        """Empty string returns empty"""
        client = LiteLLMClient()
        stdout = ""
        result = client._parse_cli_output(stdout, "json")
        assert result == ""

    def test_parse_json_whitespace_only(self):
        """Whitespace-only returns empty"""
        client = LiteLLMClient()
        stdout = "   \n  \n  "
        result = client._parse_cli_output(stdout, "json")
        assert result == ""

    def test_parse_json_nested_response(self):
        """Nested JSON with response field"""
        client = LiteLLMClient()
        stdout = '{"response": "The answer is 42", "metadata": {"model": "test"}}'
        result = client._parse_cli_output(stdout, "json")
        assert result == "The answer is 42"

    def test_parse_json_with_unicode(self):
        """JSON with unicode characters"""
        client = LiteLLMClient()
        stdout = '{"response": "Hello 世界 🌍"}'
        result = client._parse_cli_output(stdout, "json")
        assert result == "Hello 世界 🌍"


class TestJSONLParser:
    """Test JSONL parser for Codex CLI format."""

    def test_parse_jsonl_text_events(self):
        """Extract text from type=text events"""
        client = LiteLLMClient()
        stdout = '{"type":"text","text":"Step 1"}\n{"type":"text","text":"Step 2"}'
        result = client._parse_cli_output(stdout, "jsonl")
        assert "Step 1" in result
        assert "Step 2" in result

    def test_parse_jsonl_item_completed_events(self):
        """Extract text from item.completed events (Codex format)"""
        client = LiteLLMClient()
        stdout = '{"type":"item.completed","item":{"type":"agent_message","text":"Final answer"}}'
        result = client._parse_cli_output(stdout, "jsonl")
        assert "Final answer" in result

    def test_parse_jsonl_mixed_events(self):
        """Mix of text and item.completed events"""
        client = LiteLLMClient()
        stdout = '''{"type":"text","text":"Step 1"}
{"type":"item.completed","item":{"type":"agent_message","text":"Final"}}
{"type":"text","text":"Step 2"}'''
        result = client._parse_cli_output(stdout, "jsonl")
        assert "Step 1" in result
        assert "Final" in result
        assert "Step 2" in result

    def test_parse_jsonl_ignore_non_agent_messages(self):
        """Ignore item.completed events that aren't agent_message"""
        client = LiteLLMClient()
        stdout = '''{"type":"item.completed","item":{"type":"tool_call","text":"Should ignore"}}
{"type":"item.completed","item":{"type":"agent_message","text":"Should include"}}'''
        result = client._parse_cli_output(stdout, "jsonl")
        assert "Should include" in result
        assert "Should ignore" not in result

    def test_parse_jsonl_empty_text_fields(self):
        """Skip events with empty text"""
        client = LiteLLMClient()
        stdout = '''{"type":"text","text":""}
{"type":"text","text":"Valid text"}
{"type":"item.completed","item":{"type":"agent_message","text":""}}'''
        result = client._parse_cli_output(stdout, "jsonl")
        assert result == "Valid text"

    def test_parse_jsonl_malformed_lines_skipped(self):
        """Malformed JSONL lines are skipped"""
        client = LiteLLMClient()
        stdout = '''{"type":"text","text":"Line 1"}
{malformed json
{"type":"text","text":"Line 2"}'''
        result = client._parse_cli_output(stdout, "jsonl")
        assert "Line 1" in result
        assert "Line 2" in result

    def test_parse_jsonl_fallback_to_text(self):
        """If no messages extracted, return raw text"""
        client = LiteLLMClient()
        stdout = '{"type":"other","data":"something"}'
        result = client._parse_cli_output(stdout, "jsonl")
        assert result == stdout.strip()

    def test_parse_jsonl_preserves_order(self):
        """Messages are joined in order"""
        client = LiteLLMClient()
        stdout = '''{"type":"text","text":"First"}
{"type":"text","text":"Second"}
{"type":"text","text":"Third"}'''
        result = client._parse_cli_output(stdout, "jsonl")
        lines = result.split("\n")
        assert lines[0] == "First"
        assert lines[1] == "Second"
        assert lines[2] == "Third"


class TestTextParser:
    """Test plain text parser."""

    def test_parse_text_strips_whitespace(self):
        """Text parser removes leading/trailing whitespace"""
        client = LiteLLMClient()
        stdout = "  \n  Answer here  \n  "
        result = client._parse_cli_output(stdout, "text")
        assert result == "Answer here"

    def test_parse_text_preserves_internal_whitespace(self):
        """Text parser preserves internal formatting"""
        client = LiteLLMClient()
        stdout = "Line 1\n\nLine 2\n  Indented"
        result = client._parse_cli_output(stdout, "text")
        assert result == stdout.strip()

    def test_parse_text_empty_string(self):
        """Empty string returns empty"""
        client = LiteLLMClient()
        stdout = ""
        result = client._parse_cli_output(stdout, "text")
        assert result == ""

    def test_parse_text_unicode(self):
        """Text parser handles unicode"""
        client = LiteLLMClient()
        stdout = "Hello 世界 🌍"
        result = client._parse_cli_output(stdout, "text")
        assert result == "Hello 世界 🌍"


class TestParserEdgeCases:
    """Test edge cases across all parsers."""

    def test_unknown_parser_type_falls_back_to_text(self):
        """Unknown parser type falls back to text"""
        client = LiteLLMClient()
        stdout = "Some output"
        result = client._parse_cli_output(stdout, "unknown")
        assert result == stdout.strip()

    def test_none_parser_type_falls_back_to_text(self):
        """None parser type falls back to text"""
        client = LiteLLMClient()
        stdout = "Some output"
        result = client._parse_cli_output(stdout, None)
        assert result == stdout.strip()

    def test_very_long_output_handled(self):
        """Very long output doesn't cause issues"""
        client = LiteLLMClient()
        stdout = "x" * 100000  # 100KB of text
        result = client._parse_cli_output(stdout, "text")
        assert len(result) == 100000

    def test_newline_variations(self):
        """Different newline styles handled"""
        client = LiteLLMClient()
        stdout_unix = "Line 1\nLine 2\nLine 3"
        stdout_windows = "Line 1\r\nLine 2\r\nLine 3"

        result_unix = client._parse_cli_output(stdout_unix, "text")
        result_windows = client._parse_cli_output(stdout_windows, "text")

        assert "Line 1" in result_unix
        assert "Line 1" in result_windows
