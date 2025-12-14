"""Unit tests for artifact saving (merged from artifact_helper)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from multi_mcp.schemas.base import BaseToolRequest, ModelResponse, ModelResponseMetadata
from multi_mcp.utils.artifacts import save_tool_artifacts
from multi_mcp.utils.context import clear_context, set_request_context


@pytest.fixture
def base_request():
    """Create a basic request object."""
    return BaseToolRequest(
        thread_id="test-thread-123",
        name="Test Request",
        content="Test content",
        step_number=1,
        next_action="continue",
        base_path="/test/project",
    )


@pytest.fixture
def success_response():
    """Create a successful response object."""
    return ModelResponse(
        content='{"status": "success", "result": "test"}',
        status="success",
        metadata=ModelResponseMetadata(
            model="gpt-5-mini",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=100,
        ),
    )


@pytest.fixture
def error_response():
    """Create an error response object."""
    return ModelResponse(
        content="",
        status="error",
        error="Test error",
        metadata=ModelResponseMetadata(model="gpt-5-mini"),
    )


@pytest.mark.asyncio
async def test_save_tool_artifacts_success(base_request, success_response):
    """Test successful artifact saving."""
    # Set context with all required values
    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            # Return paths under base_path for relative path conversion
            mock_save.return_value = [
                Path("/test/project/.artifacts/artifact1.md"),
                Path("/test/project/.artifacts/artifact2.json"),
            ]

            result = await save_tool_artifacts(response=success_response)

            # Should return relative paths
            assert result == [".artifacts/artifact1.md", ".artifacts/artifact2.json"]
            mock_save.assert_called_once()

            # Verify call arguments
            call_args = mock_save.call_args
            assert call_args.kwargs["base_path"] == "/test/project"
            assert call_args.kwargs["name"] == "Test Request"
            assert call_args.kwargs["workflow"] == "basetool"  # BaseToolRequest.workflow_name
            assert call_args.kwargs["model"] == "gpt-5-mini"
            assert call_args.kwargs["content"] == '{"status": "success", "result": "test"}'
            assert call_args.kwargs["step_number"] == 1

            # Verify metadata structure
            metadata = call_args.kwargs["metadata"]
            assert metadata["thread_id"] == "test-thread-123"
            assert metadata["workflow"] == "basetool"
            assert metadata["step_number"] == 1
            assert metadata["model"] == "gpt-5-mini"
            assert "timestamp" in metadata
            assert metadata["usage"]["prompt_tokens"] == 10
            assert metadata["usage"]["completion_tokens"] == 5
            assert metadata["usage"]["total_tokens"] == 15
            assert metadata["duration_ms"] == 100
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_error_response(base_request, error_response):
    """Test that artifacts are not saved for error responses."""
    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            result = await save_tool_artifacts(response=error_response)

            assert result is None
            mock_save.assert_not_called()
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_empty_content(base_request):
    """Test that artifacts are not saved when response has empty content."""
    response = ModelResponse(
        content="",
        status="success",
        metadata=ModelResponseMetadata(model="gpt-5-mini"),
    )

    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            result = await save_tool_artifacts(response=response)

            assert result is None
            mock_save.assert_not_called()
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_exception_handling(base_request, success_response):
    """Test that exceptions are caught and logged."""
    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = Exception("Test error")

            result = await save_tool_artifacts(response=success_response)

            assert result is None
            mock_save.assert_called_once()
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_no_paths_returned(base_request, success_response):
    """Test when save_artifact_files returns None."""
    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = None

            result = await save_tool_artifacts(response=success_response)

            assert result is None
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_empty_paths_list(base_request, success_response):
    """Test when save_artifact_files returns empty list."""
    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = []

            result = await save_tool_artifacts(response=success_response)

            assert result is None
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_with_zero_metadata_values(base_request):
    """Test artifact saving when metadata has zero values (defaults)."""
    response = ModelResponse(
        content="test content",
        status="success",
        metadata=ModelResponseMetadata(
            model="gpt-5-mini",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=0,
        ),
    )

    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            # Return path under base_path for relative path conversion
            mock_save.return_value = [Path("/test/project/.artifacts/artifact.md")]

            result = await save_tool_artifacts(response=response)

            # Should return relative path
            assert result == [".artifacts/artifact.md"]

            # Verify zero values are preserved
            metadata = mock_save.call_args.kwargs["metadata"]
            assert metadata["usage"]["prompt_tokens"] == 0
            assert metadata["usage"]["completion_tokens"] == 0
            assert metadata["usage"]["total_tokens"] == 0
            assert metadata["duration_ms"] == 0
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_preserves_issues_in_content(base_request):
    """Test that issues embedded in JSON content are preserved in artifacts."""
    response = ModelResponse(
        content='{"status": "review_complete", "issues_found": [{"severity": "high", "description": "SQL injection"}]}',
        status="success",
        metadata=ModelResponseMetadata(
            model="gpt-5-mini",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=100,
        ),
    )

    set_request_context(
        base_path=base_request.base_path,
        workflow=base_request.workflow_name,
        name=base_request.name,
        step_number=base_request.step_number,
        thread_id=base_request.thread_id,
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            # Return path under base_path for relative path conversion
            mock_save.return_value = [Path("/test/project/.artifacts/artifact.json")]

            result = await save_tool_artifacts(response=response)

            # Should return relative path
            assert result == [".artifacts/artifact.json"]

            # Verify the full JSON content (including issues) is saved
            saved_content = mock_save.call_args.kwargs["content"]
            assert "issues_found" in saved_content
            assert "SQL injection" in saved_content
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_missing_context():
    """Test that artifacts are not saved when required context is missing."""
    response = ModelResponse(
        content="test content",
        status="success",
        metadata=ModelResponseMetadata(model="gpt-5-mini"),
    )

    # Set only base_path, missing workflow/name/step_number
    set_request_context(base_path="/test/project")

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            result = await save_tool_artifacts(response=response)

            assert result is None
            mock_save.assert_not_called()
    finally:
        clear_context()


@pytest.mark.asyncio
async def test_save_tool_artifacts_missing_base_path():
    """Test that artifacts are not saved when base_path is missing."""
    response = ModelResponse(
        content="test content",
        status="success",
        metadata=ModelResponseMetadata(model="gpt-5-mini"),
    )

    # Set everything except base_path
    set_request_context(
        workflow="test",
        name="Test",
        step_number=1,
        thread_id="test-123",
    )

    try:
        with patch("multi_mcp.utils.artifacts.save_artifact_files", new_callable=AsyncMock) as mock_save:
            result = await save_tool_artifacts(response=response)

            assert result is None
            mock_save.assert_not_called()
    finally:
        clear_context()
