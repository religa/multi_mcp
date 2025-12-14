"""Test MessageBuilder message construction."""

import pytest

from multi_mcp.utils.message_builder import MessageBuilder


@pytest.mark.asyncio
async def test_basic_message_building():
    """Test basic message construction."""
    messages = await MessageBuilder(system_prompt="Test prompt", base_path=None).add_user_message("Hello").build()

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "Test prompt"
    assert messages[1]["role"] == "user"
    assert "Hello" in messages[1]["content"]
    assert "<USER_MESSAGE>" in messages[1]["content"]


@pytest.mark.asyncio
async def test_cannot_call_add_user_message_twice():
    """Test that add_user_message can only be called once."""
    builder = MessageBuilder(system_prompt="Test", base_path=None)
    builder.add_user_message("First")

    with pytest.raises(ValueError, match="can only be called once"):
        builder.add_user_message("Second")


@pytest.mark.asyncio
async def test_cannot_build_without_user_message():
    """Test that build() requires add_user_message."""
    builder = MessageBuilder(system_prompt="Test", base_path=None)

    with pytest.raises(ValueError, match="Must call add_user_message"):
        await builder.build()


@pytest.mark.asyncio
async def test_with_repository_context(tmp_path):
    """Test repository context loading."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Project\nTest project")

    messages = await (
        MessageBuilder(system_prompt="Test", base_path=str(tmp_path)).add_repository_context().add_user_message("Question").build()
    )

    user_msg = messages[1]["content"]
    assert "<REPOSITORY_CONTEXT>" in user_msg
    assert "Test project" in user_msg
    assert "<USER_MESSAGE>" in user_msg


@pytest.mark.asyncio
async def test_repository_context_caching(tmp_path):
    """Test that repository context is cached by mtime."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Version 1")

    # First call - should load from disk
    messages1 = await (
        MessageBuilder(system_prompt="Test", base_path=str(tmp_path)).add_repository_context().add_user_message("Question 1").build()
    )

    # Second call - should use cache
    messages2 = await (
        MessageBuilder(system_prompt="Test", base_path=str(tmp_path)).add_repository_context().add_user_message("Question 2").build()
    )

    # Both should have same repo context
    assert "Version 1" in messages1[1]["content"]
    assert "Version 1" in messages2[1]["content"]

    # Update file (change mtime)
    import time

    time.sleep(0.01)  # Ensure mtime changes
    claude_md.write_text("# Version 2")

    # Third call - should reload from disk (cache invalidated)
    messages3 = await (
        MessageBuilder(system_prompt="Test", base_path=str(tmp_path)).add_repository_context().add_user_message("Question 3").build()
    )

    assert "Version 2" in messages3[1]["content"]
    assert "Version 1" not in messages3[1]["content"]


@pytest.mark.asyncio
async def test_with_files(tmp_path):
    """Test file embedding."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello(): pass")

    messages = await (
        MessageBuilder(system_prompt="Test", base_path=str(tmp_path)).add_files([str(test_file)]).add_user_message("Review this").build()
    )

    user_msg = messages[1]["content"]
    assert "<EDITABLE_FILES>" in user_msg
    assert "def hello()" in user_msg


@pytest.mark.asyncio
async def test_all_components_together(tmp_path):
    """Test combining all message components in correct order."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Project")

    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1")

    messages = await (
        MessageBuilder(system_prompt="System", base_path=str(tmp_path))
        .add_repository_context()
        .add_files([str(test_file)])
        .add_user_message("Current question")
        .build()
    )

    assert len(messages) == 2
    user_msg = messages[1]["content"]

    # All components present and in correct order
    repo_idx = user_msg.index("<REPOSITORY_CONTEXT>")
    files_idx = user_msg.index("<EDITABLE_FILES>")
    curr_idx = user_msg.index("<USER_MESSAGE>")

    assert repo_idx < files_idx < curr_idx


@pytest.mark.asyncio
async def test_escape_html_default():
    """Test that HTML is escaped by default."""
    messages = await MessageBuilder(system_prompt="Test", base_path=None).add_user_message("<script>alert('xss')</script>").build()

    user_msg = messages[1]["content"]
    assert "&lt;script&gt;" in user_msg
    # Exclude our own XML tags when checking for script tag
    content_without_tags = user_msg.replace("<USER_MESSAGE>", "").replace("</USER_MESSAGE>", "")
    assert "<script>" not in content_without_tags


@pytest.mark.asyncio
async def test_no_escape_when_disabled():
    """Test that HTML escaping can be disabled."""
    messages = await (
        MessageBuilder(system_prompt="Test", base_path=None).add_user_message("<CUSTOM_TAG>content</CUSTOM_TAG>", escape_html=False).build()
    )

    user_msg = messages[1]["content"]
    assert "<CUSTOM_TAG>" in user_msg
    assert "&lt;CUSTOM_TAG&gt;" not in user_msg


@pytest.mark.asyncio
async def test_wrap_xml_disabled():
    """Test that XML wrapping can be disabled."""
    messages = await MessageBuilder(system_prompt="Test", base_path=None).add_user_message("Plain content", wrap_xml=False).build()

    user_msg = messages[1]["content"]
    assert "<USER_MESSAGE>" not in user_msg
    assert "Plain content" in user_msg


@pytest.mark.asyncio
async def test_wrap_xml_false_with_escape_html_false():
    """Test both wrapping and escaping can be disabled."""
    messages = await (
        MessageBuilder(system_prompt="Test", base_path=None)
        .add_user_message("<CUSTOM>content</CUSTOM>", wrap_xml=False, escape_html=False)
        .build()
    )

    user_msg = messages[1]["content"]
    assert user_msg == "<CUSTOM>content</CUSTOM>"


@pytest.mark.asyncio
async def test_no_files():
    """Test with no files (None)."""
    messages = await MessageBuilder(system_prompt="Test", base_path=None).add_files(None).add_user_message("Question").build()

    user_msg = messages[1]["content"]
    assert "<EDITABLE_FILES>" not in user_msg
    assert "Question" in user_msg


@pytest.mark.asyncio
async def test_empty_files_list():
    """Test with empty files list."""
    messages = await MessageBuilder(system_prompt="Test", base_path=None).add_files([]).add_user_message("Question").build()

    user_msg = messages[1]["content"]
    assert "<EDITABLE_FILES>" not in user_msg
    assert "Question" in user_msg


@pytest.mark.asyncio
async def test_no_base_path_for_repository_context():
    """Test repository context with no base_path."""
    messages = await MessageBuilder(system_prompt="Test", base_path=None).add_repository_context().add_user_message("Question").build()

    user_msg = messages[1]["content"]
    assert "<REPOSITORY_CONTEXT>" not in user_msg
    assert "Question" in user_msg
