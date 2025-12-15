"""Tests for artifact logging utility."""

import json

import pytest
import yaml

from multi_mcp.utils.artifacts import generate_filename, save_artifact_files, slugify


def test_slugify():
    """Test slugify function."""
    assert slugify("Initial Analysis") == "initial-analysis"
    assert slugify("Fix SQL-Injection!") == "fix-sql-injection"
    assert slugify("GPT-5 Mini") == "gpt-5-mini"
    assert slugify("Test@#$%^&*()") == "test"
    assert slugify("Multiple   Spaces") == "multiple-spaces"
    assert slugify("   Leading Trailing   ") == "leading-trailing"


def test_generate_filename():
    """Test filename generation."""
    filename = generate_filename(
        name="Initial Analysis",
        workflow="codereview",
        model="gpt-5-mini",
        step_number=1,
        extension="md",
    )

    # Check format (exact timestamp will vary)
    # Name is shortened to first 2 words, max 15 chars: "initial-analysi"
    assert filename.startswith("initial-analysi-codereview-gpt-5-mini-")
    assert filename.endswith(".md")
    # Example: initial-analysi-codereview-gpt-5-mini-20250127_123456.md
    assert "codereview" in filename


def test_generate_filename_no_step():
    """Test filename generation (step number is always omitted)."""
    filename = generate_filename(
        name="General Question",
        workflow="chat",
        model="claude-sonnet-4-5",
        step_number=None,
        extension="md",
    )

    assert "step" not in filename
    # Name is shortened to first 2 words, max 15 chars: "general-questio"
    assert filename.startswith("general-questio-chat-claude-sonnet-4-5-")
    assert filename.endswith(".md")


def test_generate_filename_json():
    """Test JSON filename generation."""
    filename = generate_filename(
        name="Security Review",
        workflow="codereview",
        model="gpt-5-mini",
        step_number=2,
        extension="json",
    )

    assert filename.startswith("security-review-codereview-gpt-5-mini-")
    assert filename.endswith(".json")


def test_generate_filename_removes_duplicate_workflow():
    """Test that workflow name is removed from filename if it appears in name."""
    # "Chat Query" should become "query-chat-..." not "chat-query-chat-..."
    filename = generate_filename(
        name="Chat Query",
        workflow="chat",
        model="gpt-5-mini",
        step_number=1,
        extension="md",
    )

    assert filename.startswith("query-chat-gpt-5-mini-")
    # Ensure 'chat' doesn't appear twice before the model name
    parts = filename.split("-")
    chat_indices = [i for i, part in enumerate(parts) if part == "chat"]
    assert len(chat_indices) == 1, f"'chat' should appear only once, found at indices: {chat_indices}"

    # Test with compare
    filename2 = generate_filename(
        name="Compare Test",
        workflow="compare",
        model="gpt-5-mini",
        step_number=1,
        extension="md",
    )

    assert filename2.startswith("test-compare-gpt-5-mini-")
    parts2 = filename2.split("-")
    compare_indices = [i for i, part in enumerate(parts2) if part == "compare"]
    assert len(compare_indices) == 1, f"'compare' should appear only once, found at indices: {compare_indices}"


def test_generate_filename_workflow_only_name():
    """Test that if name is just the workflow, we use 'request' as fallback."""
    filename = generate_filename(
        name="Chat",
        workflow="chat",
        model="gpt-5-mini",
        step_number=1,
        extension="md",
    )

    # "Chat" -> "chat" -> removed because it matches workflow -> "request"
    assert filename.startswith("request-chat-gpt-5-mini-")


@pytest.mark.asyncio
async def test_save_artifact_files_disabled(tmp_path, monkeypatch):
    """Test that no artifacts are saved when ARTIFACTS_DIR is empty."""
    monkeypatch.setenv("ARTIFACTS_DIR", "")

    # Reload settings
    from multi_mcp.settings import Settings
    from multi_mcp.utils import artifacts

    artifacts.settings = Settings()

    metadata = {
        "thread_id": "thread_123",
        "workflow": "codereview",
        "step_number": 1,
        "model": "gpt-5-mini",
        "timestamp": "2025-01-15T10:30:45Z",
        "request": {"name": "Test", "message": "Test message"},
    }

    created_files = await save_artifact_files(
        base_path=str(tmp_path),
        name="Test",
        workflow="codereview",
        model="gpt-5-mini",
        content="Test content",
        issues_found=[],
        metadata=metadata,
        step_number=1,
    )

    assert created_files == []
    assert not any(tmp_path.glob("**/*"))


@pytest.mark.asyncio
async def test_save_artifact_files_markdown(tmp_path, monkeypatch):
    """Test saving markdown artifact."""
    monkeypatch.setenv("ARTIFACTS_DIR", "tmp")

    # Reload settings to pick up env var
    from multi_mcp.settings import Settings
    from multi_mcp.utils import artifacts

    artifacts.settings = Settings()

    metadata = {
        "thread_id": "thread_123",
        "workflow": "codereview",
        "step_number": 1,
        "model": "gpt-5-mini",
        "timestamp": "2025-01-15T10:30:45Z",
        "request": {"name": "Test Analysis", "message": "Test message"},
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "duration_ms": 1500,
    }

    created_files = await save_artifact_files(
        base_path=str(tmp_path),
        name="Test Analysis",
        workflow="codereview",
        model="gpt-5-mini",
        content="This is the LLM response content.",
        issues_found=None,
        metadata=metadata,
        step_number=1,
    )

    assert len(created_files) == 1
    assert created_files[0].suffix == ".md"

    # Verify content
    content = created_files[0].read_text()
    assert "This is the LLM response content." in content
    assert "---" in content
    assert "```yaml" in content
    assert "metadata:" in content

    # Verify YAML parsing (extract from code block)
    parts = content.split("---")
    yaml_section = parts[-1].strip()
    # Remove ```yaml and ``` markers
    yaml_part = yaml_section.replace("```yaml", "").replace("```", "").strip()
    parsed = yaml.safe_load(yaml_part)
    assert parsed["metadata"]["thread_id"] == "thread_123"
    assert parsed["metadata"]["usage"]["total_tokens"] == 150


@pytest.mark.asyncio
async def test_save_artifact_files_json(tmp_path, monkeypatch):
    """Test saving JSON artifact."""
    monkeypatch.setenv("ARTIFACTS_DIR", "tmp")

    # Reload settings
    from multi_mcp.settings import Settings
    from multi_mcp.utils import artifacts

    artifacts.settings = Settings()

    metadata = {
        "thread_id": "thread_123",
        "workflow": "codereview",
        "step_number": 1,
        "model": "gpt-5-mini",
        "timestamp": "2025-01-15T10:30:45Z",
        "request": {"name": "Test Analysis", "message": "Test message"},
    }

    issues = [{"severity": "high", "location": "auth.py:45", "description": "SQL injection"}]

    created_files = await save_artifact_files(
        base_path=str(tmp_path),
        name="Test Analysis",
        workflow="codereview",
        model="gpt-5-mini",
        content=None,
        issues_found=issues,
        metadata=metadata,
        step_number=1,
    )

    assert len(created_files) == 1
    assert created_files[0].suffix == ".json"

    # Verify JSON content
    data = json.loads(created_files[0].read_text())
    assert data["issues_found"][0]["severity"] == "high"
    assert data["metadata"]["thread_id"] == "thread_123"


@pytest.mark.asyncio
async def test_save_artifact_files_both(tmp_path, monkeypatch):
    """Test saving both markdown and JSON artifacts."""
    monkeypatch.setenv("ARTIFACTS_DIR", "tmp")

    # Reload settings
    from multi_mcp.settings import Settings
    from multi_mcp.utils import artifacts

    artifacts.settings = Settings()

    metadata = {
        "thread_id": "thread_123",
        "workflow": "codereview",
        "step_number": 1,
        "model": "gpt-5-mini",
        "timestamp": "2025-01-15T10:30:45Z",
        "request": {"name": "Test Analysis", "message": "Test message"},
    }

    issues = [{"severity": "high", "location": "auth.py:45", "description": "SQL injection"}]

    created_files = await save_artifact_files(
        base_path=str(tmp_path),
        name="Test Analysis",
        workflow="codereview",
        model="gpt-5-mini",
        content="LLM response content",
        issues_found=issues,
        metadata=metadata,
        step_number=1,
    )

    assert len(created_files) == 2
    assert any(f.suffix == ".md" for f in created_files)
    assert any(f.suffix == ".json" for f in created_files)


@pytest.mark.asyncio
async def test_save_artifact_files_absolute_path(tmp_path, monkeypatch):
    """Test that absolute ARTIFACTS_DIR is supported."""
    # Create an absolute path for artifacts
    abs_artifacts_dir = tmp_path / "global_artifacts"
    monkeypatch.setenv("ARTIFACTS_DIR", str(abs_artifacts_dir))

    # Reload settings
    from multi_mcp.settings import Settings
    from multi_mcp.utils import artifacts

    artifacts.settings = Settings()

    metadata = {
        "thread_id": "thread_123",
        "workflow": "codereview",
        "step_number": 1,
        "model": "gpt-5-mini",
        "timestamp": "2025-01-15T10:30:45Z",
        "request": {"name": "Test", "message": "Test"},
    }

    # Should succeed with absolute path
    created_files = await save_artifact_files(
        base_path=str(tmp_path / "project"),  # Different base_path
        name="Test",
        workflow="codereview",
        model="gpt-5-mini",
        content="Test content",
        issues_found=None,
        metadata=metadata,
        step_number=1,
    )

    # Files should be created in the absolute path, not relative to base_path
    assert len(created_files) == 1
    assert created_files[0].exists()
    assert abs_artifacts_dir.exists()
    assert created_files[0].parent == abs_artifacts_dir


@pytest.mark.asyncio
async def test_save_artifact_files_rejects_path_traversal(tmp_path, monkeypatch):
    """Test that path traversal attempts are rejected."""
    monkeypatch.setenv("ARTIFACTS_DIR", "../../../tmp")

    # Reload settings
    from multi_mcp.settings import Settings
    from multi_mcp.utils import artifacts

    artifacts.settings = Settings()

    metadata = {
        "thread_id": "thread_123",
        "workflow": "codereview",
        "step_number": 1,
        "model": "gpt-5-mini",
        "timestamp": "2025-01-15T10:30:45Z",
        "request": {"name": "Test", "message": "Test"},
    }

    # Should raise ValueError for path traversal
    with pytest.raises(ValueError, match="escapes base_path"):
        await save_artifact_files(
            base_path=str(tmp_path),
            name="Test",
            workflow="codereview",
            model="gpt-5-mini",
            content="Test",
            issues_found=None,
            metadata=metadata,
            step_number=1,
        )


@pytest.mark.asyncio
async def test_save_artifact_files_creates_directory(tmp_path, monkeypatch):
    """Test that artifact directory is created if it doesn't exist."""
    monkeypatch.setenv("ARTIFACTS_DIR", "artifacts/logs")

    # Reload settings
    from multi_mcp.settings import Settings
    from multi_mcp.utils import artifacts

    artifacts.settings = Settings()

    metadata = {
        "thread_id": "thread_123",
        "workflow": "codereview",
        "step_number": 1,
        "model": "gpt-5-mini",
        "timestamp": "2025-01-15T10:30:45Z",
        "request": {"name": "Test", "message": "Test"},
    }

    created_files = await save_artifact_files(
        base_path=str(tmp_path),
        name="Test",
        workflow="codereview",
        model="gpt-5-mini",
        content="Test",
        issues_found=None,
        metadata=metadata,
        step_number=1,
    )

    # Directory should be created
    artifacts_dir = tmp_path / "artifacts" / "logs"
    assert artifacts_dir.exists()
    assert artifacts_dir.is_dir()
    assert len(created_files) == 1
