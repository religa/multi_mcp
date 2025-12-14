"""Tests for JSON parser."""

from multi_mcp.utils.json_parser import parse_llm_json


def test_parse_simple_json():
    """Test parsing simple JSON."""
    result = parse_llm_json('{"status": "no_issues_found", "message": "Great"}')
    assert result == {"status": "no_issues_found", "message": "Great"}


def test_parse_with_markdown_fence():
    """Test parsing JSON in markdown fence."""
    content = """```json
{"status": "no_issues_found", "message": "Excellent code"}
```"""
    result = parse_llm_json(content)
    assert result["status"] == "no_issues_found"
    assert result["message"] == "Excellent code"


def test_parse_with_markdown_fence_no_language():
    """Test parsing JSON in markdown fence without language tag."""
    content = """```
{"status": "no_issues_found", "message": "Good"}
```"""
    result = parse_llm_json(content)
    assert result["status"] == "no_issues_found"


def test_parse_trailing_comma():
    """Test repairing trailing commas."""
    result = parse_llm_json('{"a": 1, "b": 2,}')
    assert result == {"a": 1, "b": 2}


def test_parse_trailing_comma_in_array():
    """Test repairing trailing commas in arrays."""
    result = parse_llm_json('{"arr": [1, 2, 3,]}')
    assert result == {"arr": [1, 2, 3]}


def test_parse_unquoted_keys():
    """Test repairing unquoted keys."""
    result = parse_llm_json('{foo: "bar", baz: 123}')
    assert result == {"foo": "bar", "baz": 123}


def test_parse_python_true():
    """Test converting Python True literal."""
    result = parse_llm_json('{"a": True}')
    assert result == {"a": True}


def test_parse_python_false():
    """Test converting Python False literal."""
    result = parse_llm_json('{"a": False}')
    assert result == {"a": False}


def test_parse_python_none():
    """Test converting Python None literal."""
    result = parse_llm_json('{"a": None}')
    assert result == {"a": None}


def test_parse_python_literals_combined():
    """Test converting multiple Python literals."""
    result = parse_llm_json('{"a": True, "b": False, "c": None}')
    assert result == {"a": True, "b": False, "c": None}


def test_parse_with_line_comments():
    """Test stripping line comments."""
    result = parse_llm_json("""
    {
        "status": "no_issues_found", // This is a comment
        "message": "Good"
    }
    """)
    assert result["status"] == "no_issues_found"


def test_parse_with_block_comments():
    """Test stripping block comments."""
    result = parse_llm_json("""
    {
        "status": "no_issues_found",
        /* Block comment here */
        "message": "Good"
    }
    """)
    assert result["status"] == "no_issues_found"


def test_parse_json_in_text():
    """Test extracting JSON from surrounding text."""
    result = parse_llm_json('Here is the response: {"status": "ok", "value": 123} and more text')
    assert result == {"status": "ok", "value": 123}


def test_parse_json_with_prefix_text():
    """Test extracting JSON when preceded by text."""
    content = """The analysis is complete.

{
  "status": "no_issues_found",
  "message": "Code is excellent"
}"""
    result = parse_llm_json(content)
    assert result["status"] == "no_issues_found"


def test_parse_files_required_response():
    """Test parsing files_required special case."""
    content = """{
  "status": "files_required_to_continue",
  "message": "Need auth module",
  "files_needed": ["auth.py", "models/"]
}"""
    result = parse_llm_json(content)
    assert result["status"] == "files_required_to_continue"
    assert len(result["files_needed"]) == 2
    assert "auth.py" in result["files_needed"]


def test_parse_non_json():
    """Test that non-JSON returns None."""
    result = parse_llm_json("This is just plain text with no JSON")
    assert result is None


def test_parse_empty():
    """Test that empty string returns None."""
    result = parse_llm_json("")
    assert result is None


def test_parse_whitespace_only():
    """Test that whitespace-only string returns None."""
    result = parse_llm_json("   \n\t  ")
    assert result is None


def test_parse_invalid_json():
    """Test that completely broken JSON returns None."""
    result = parse_llm_json("{this is broken json")
    assert result is None


def test_parse_none_input():
    """Test that None input returns None."""
    result = parse_llm_json(None)  # type: ignore
    assert result is None


def test_parse_smart_quotes():
    """Test handling of smart quotes around keys."""
    # Smart quotes around the key
    result = parse_llm_json('{"message": "Code is excellent"}')
    assert result is not None
    assert "message" in result


def test_parse_array():
    """Test parsing JSON array."""
    result = parse_llm_json("[1, 2, 3]")
    assert result == [1, 2, 3]


def test_parse_nested_objects():
    """Test parsing nested JSON objects."""
    result = parse_llm_json('{"outer": {"inner": "value"}}')
    assert result == {"outer": {"inner": "value"}}


def test_parse_combined_issues():
    """Test handling multiple malformations at once."""
    content = """```json
{
  status: "no_issues_found",  // Comment here
  message: "Great code",
}
```"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "no_issues_found"


def test_parse_with_analysis_block():
    """Test stripping <analysis> block before parsing JSON."""
    content = """<analysis>
1. VERIFICATION:
   - Issue "SQL injection": Confirmed. Fix required.
   - Issue "Missing import": False positive. The code handles this in line 45. Discarding.
2. DISCOVERY:
   - Found potential race condition in file.py:12.
</analysis>

```json
{
  "status": "issues_found",
  "issues_found": [
    {"severity": "high", "location": "db.py:23", "description": "SQL injection"}
  ]
}
```"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "issues_found"
    assert len(result["issues_found"]) == 1
    assert result["issues_found"][0]["severity"] == "high"


def test_parse_with_analysis_block_no_fence():
    """Test stripping <analysis> block when JSON is not in a fence."""
    content = """<analysis>
1. VERIFICATION:
   - Issue "X": Confirmed.
</analysis>

{"status": "no_issues_found", "message": "All clear"}"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "no_issues_found"


def test_parse_with_analysis_block_inline():
    """Test stripping <analysis> block that appears inline with JSON."""
    content = """<analysis>Quick check: all good</analysis>{"status": "ok"}"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "ok"


def test_parse_invalid_escape_sequences():
    """Test repairing invalid escape sequences (common in LLM code samples)."""
    # Test \' (Python-style escaped single quote - invalid in JSON)
    content = r'{"code": "print(\'hello\')", "status": "ok"}'
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "ok"
    assert result["code"] == "print('hello')"

    # Test other invalid escapes
    content2 = r'{"pattern": "\\d+", "escape": "\\x41", "status": "ok"}'
    result2 = parse_llm_json(content2)
    assert result2 is not None
    assert result2["status"] == "ok"


def test_parse_complex_code_with_escapes():
    """Test parsing JSON with code samples that have invalid escapes (like real LLM output)."""
    # Simulate what an LLM might return with Python code containing \'
    content = r'{"fix": "f\'Hello {name}\'", "status": "success"}'
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "success"
    assert "Hello" in result["fix"]

    # Another common case: regex patterns with \d, \w, etc
    content2 = '{"pattern": "Match \\digit with \\d", "status": "ok"}'
    result2 = parse_llm_json(content2)
    assert result2 is not None
    assert result2["status"] == "ok"


def test_parse_protected_strings():
    """Test that string masking protects URLs, literals, and patterns inside strings."""
    # Test URL with // (should not be treated as comment)
    content1 = '{"url": "http://example.com", "status": "ok"}'
    result1 = parse_llm_json(content1)
    assert result1 is not None
    assert result1["url"] == "http://example.com"
    assert result1["status"] == "ok"

    # Test literal "None" inside string (should not be replaced with null)
    content2 = '{"message": "Found None in code", "status": "ok"}'
    result2 = parse_llm_json(content2)
    assert result2 is not None
    assert result2["message"] == "Found None in code"

    # Test UNC path with //
    content3 = '{"path": "//server/share/file.txt", "status": "ok"}'
    result3 = parse_llm_json(content3)
    assert result3 is not None
    assert result3["path"] == "//server/share/file.txt"

    # Test unquoted key pattern inside string (should not add quotes)
    content4 = '{"code": "obj = {key: value}", "status": "ok"}'
    result4 = parse_llm_json(content4)
    assert result4 is not None
    assert result4["code"] == "obj = {key: value}"

    # Test multiple issues with unquoted keys outside strings
    content5 = '{url: "http://example.com", status: "ok"}'  # unquoted keys outside
    result5 = parse_llm_json(content5)
    assert result5 is not None
    assert result5["url"] == "http://example.com"  # URL preserved
    assert result5["status"] == "ok"


def test_parse_combined_with_masking():
    """Test string masking combined with other repairs."""
    # URL + comment + unquoted keys
    content = """{
        url: "http://example.com", // This is a URL
        path: "//server/share",
        message: "Value is None here",
        status: "ok"
    }"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["url"] == "http://example.com"
    assert result["path"] == "//server/share"
    assert result["message"] == "Value is None here"
    assert result["status"] == "ok"


def test_parse_single_quoted_strings():
    """Test converting single-quoted strings to double quotes."""
    content = "{'msg': 'hello', 'count': 10}"
    result = parse_llm_json(content)
    assert result is not None
    assert result["msg"] == "hello"
    assert result["count"] == 10


def test_parse_single_quotes_with_trailing_comma():
    """Test single quotes combined with trailing comma."""
    content = "{'msg': 'hello', 'count': 10,}"
    result = parse_llm_json(content)
    assert result is not None
    assert result["msg"] == "hello"
    assert result["count"] == 10


def test_parse_single_quotes_with_escaped_quotes():
    """Test single-quoted strings containing escaped single quotes."""
    content = r"{'msg': 'it\'s working', 'status': 'ok'}"
    result = parse_llm_json(content)
    assert result is not None
    assert result["msg"] == "it's working"
    assert result["status"] == "ok"


def test_parse_single_quotes_with_double_quotes_inside():
    """Test single-quoted strings containing double quotes."""
    content = """{'msg': 'he said "hello"', 'status': 'ok'}"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["msg"] == 'he said "hello"'
    assert result["status"] == "ok"


def test_parse_unclosed_code_fence():
    """Test handling unclosed code fence (LLM cut off mid-response)."""
    content = """```json
{
  "a": 1,
  "b": 2
}"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["a"] == 1
    assert result["b"] == 2


def test_parse_unclosed_fence_with_label():
    """Test unclosed fence with explicit json label."""
    content = """```json
{"status": "ok", "value": 42}"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "ok"
    assert result["value"] == 42


def test_parse_nested_code_fences():
    """Test parsing JSON with nested code fences in string values.

    This reproduces the bug where LLM responses contained code snippets
    with their own ``` fences inside JSON string fields, causing the parser
    to match the first closing ``` instead of the outermost one.
    """
    content = """```json
{
  "status": "success",
  "issues": [
    {
      "description": "Bug found",
      "fix": "```python\\nprint('hello')\\n```"
    }
  ]
}
```"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "success"
    assert isinstance(result["issues"], list)
    assert len(result["issues"]) == 1
    assert "fix" in result["issues"][0]
    assert "```python" in result["issues"][0]["fix"]


def test_parse_multiple_nested_code_fences():
    """Test parsing JSON with multiple nested code fences.

    This simulates a real code review response with multiple issues,
    each containing code fixes with markdown fences.
    """
    content = """```json
{
  "status": "success",
  "message": "Found 2 issues",
  "issues_found": [
    {
      "severity": "high",
      "location": "file.py:10",
      "description": "Issue 1",
      "fix": "```python\\ndef foo():\\n    pass\\n```"
    },
    {
      "severity": "medium",
      "location": "file.py:20",
      "description": "Issue 2",
      "fix": "```python\\ndef bar():\\n    pass\\n```"
    }
  ]
}
```"""
    result = parse_llm_json(content)
    assert result is not None
    assert result["status"] == "success"
    assert result["message"] == "Found 2 issues"
    assert len(result["issues_found"]) == 2
    assert result["issues_found"][0]["severity"] == "high"
    assert result["issues_found"][1]["severity"] == "medium"
    assert "```python" in result["issues_found"][0]["fix"]
    assert "```python" in result["issues_found"][1]["fix"]
