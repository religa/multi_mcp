"""Unit tests for schemas (base.py and codereview.py)."""

import pytest
from pydantic import ValidationError

from src.schemas.base import BaseToolRequest, ModelResponseMetadata, NextAction, SingleToolRequest, SingleToolResponse
from src.schemas.chat import ChatRequest
from src.schemas.codereview import CodeReviewRequest, CodeReviewResponse
from src.schemas.compare import CompareRequest


class TestBaseToolRequest:
    """Tests for BaseToolRequest workflow_name property."""

    def test_workflow_name_base(self):
        """Test workflow_name for BaseToolRequest."""
        # BaseToolRequest -> 'basetool'
        request = BaseToolRequest(
            name="Test",
            content="Test content",
            step_number=1,
            next_action="continue",
            base_path="/tmp/test",
        )
        assert request.workflow_name == "basetool"

    def test_workflow_name_chat(self):
        """Test workflow_name for ChatRequest."""
        # ChatRequest -> 'chat'
        request = ChatRequest(
            name="Test",
            content="Test content",
            step_number=1,
            next_action="continue",
            base_path="/tmp/test",
            model="gpt-5-mini",
        )
        assert request.workflow_name == "chat"

    def test_workflow_name_codereview(self):
        """Test workflow_name for CodeReviewRequest."""
        # CodeReviewRequest -> 'codereview'
        request = CodeReviewRequest(
            name="Test",
            content="Test content",
            step_number=1,
            next_action="continue",
            base_path="/tmp/test",
            model="gpt-5-mini",
        )
        assert request.workflow_name == "codereview"

    def test_workflow_name_compare(self):
        """Test workflow_name for CompareRequest."""
        # CompareRequest -> 'compare'
        request = CompareRequest(
            name="Test",
            content="Test content",
            step_number=1,
            next_action="continue",
            base_path="/tmp/test",
            models=["gpt-5-mini", "claude-haiku-4-5-20251001"],
        )
        assert request.workflow_name == "compare"


class TestToolRequest:
    """Tests for ToolRequest base model."""

    def test_valid_request(self):
        """Test creating a valid ToolRequest."""
        request = SingleToolRequest(
            name="Starting code review",
            content="Analyzing authentication code",
            step_number=1,
            next_action="continue",
            model="gpt-5-mini",
            base_path="/path/to/project",
            thread_id="test-123",
        )

        assert request.thread_id == "test-123"
        assert request.content == "Analyzing authentication code"
        assert request.step_number == 1
        assert request.next_action == "continue"

    def test_next_action_values(self):
        """Test that next_action accepts only 2 values: continue and stop."""
        for action in ["continue", "stop"]:
            request = SingleToolRequest(
                name="Test", content="Test content", step_number=1, next_action=action, model="gpt-5-mini", base_path="/tmp/test"
            )
            assert request.next_action == action

    def test_step_number_validation(self):
        """Test that step_number must be >= 1."""
        with pytest.raises(ValidationError):
            SingleToolRequest(
                name="Test",
                content="Test content",
                step_number=0,  # Invalid - must be >= 1
                next_action="stop",
                model="gpt-5-mini",
                base_path="/tmp/test",
            )

    def test_file_lists_default(self):
        """Test that CodeReviewRequest file tracking lists default to None."""
        request = CodeReviewRequest(
            name="Test", content="Test content", step_number=1, next_action="stop", model="gpt-5-mini", base_path="/tmp/test"
        )

        assert request.relevant_files is None
        assert request.issues_found is None


class TestNextAction:
    """Tests for NextAction model."""

    def test_valid_next_action(self):
        """Test creating a valid NextAction."""
        action = NextAction(action="stop", reason="Analysis complete")

        assert action.action == "stop"
        assert action.reason == "Analysis complete"

    def test_invalid_action(self):
        """Test that invalid action is rejected."""
        with pytest.raises(ValidationError):
            NextAction(
                action="invalid",  # Not in Literal
                reason="Test",
            )


class TestToolResponse:
    """Tests for ToolResponse base model."""

    def test_valid_response(self):
        """Test creating a valid ToolResponse."""
        response = SingleToolResponse(
            thread_id="test-123",
            content="Review complete",
            status="success",
            metadata=ModelResponseMetadata(model="gpt-5-mini"),
        )

        assert response.thread_id == "test-123"
        assert response.status == "success"
        assert response.next_action is None  # Default

    def test_response_with_next_action(self):
        """Test ToolResponse with NextAction."""
        next_action = NextAction(action="stop", reason="Complete")
        response = SingleToolResponse(
            thread_id="test-123",
            content="Review complete",
            status="success",
            next_action=next_action,
            metadata=ModelResponseMetadata(model="gpt-5-mini"),
        )

        assert response.next_action is not None
        assert response.next_action.action == "stop"

    def test_invalid_status(self):
        """Test that invalid status is rejected."""
        with pytest.raises(ValidationError):
            SingleToolResponse(
                thread_id="test-123",
                content="Test",
                status="invalid_status",  # Not 'success' or 'error'
            )


class TestCodeReviewRequest:
    """Tests for CodeReviewRequest model."""

    def test_valid_codereview_request(self):
        """Test creating a valid CodeReviewRequest."""
        request = CodeReviewRequest(
            name="Analyzing for SQL injection",
            content="Checking user input sanitization",
            step_number=1,
            next_action="continue",
            model="gpt-5-mini",
            base_path="/path/to/project",
            thread_id="test-123",
            relevant_files=["src/auth.py"],
            issues_found=[
                {
                    "file": "src/auth.py",
                    "line": 42,
                    "severity": "critical",
                    "title": "SQL Injection",
                    "description": "Unsanitized user input",
                }
            ],
        )

        assert len(request.relevant_files) == 1
        assert len(request.issues_found) == 1
        assert request.issues_found[0]["severity"] == "critical"

    def test_default_empty_lists(self):
        """Test that file and issue lists default to None."""
        request = CodeReviewRequest(
            name="Test", content="Test content", step_number=1, next_action="stop", model="gpt-5-mini", base_path="/tmp/test"
        )

        assert request.relevant_files is None
        assert request.issues_found is None


class TestCodeReviewResponse:
    """Tests for CodeReviewResponse model."""

    def test_valid_codereview_response(self):
        """Test creating a valid CodeReviewResponse with model results."""
        from src.schemas.base import ModelResponseMetadata
        from src.schemas.codereview import CodeReviewModelResult

        response = CodeReviewResponse(
            thread_id="test-123",
            status="success",
            summary="1/1 models succeeded. Found 2 issues: 1 high, 1 medium. See `results` for details.",
            results=[
                CodeReviewModelResult(
                    content="Review complete",
                    status="success",
                    metadata=ModelResponseMetadata(model="gpt-5-mini"),
                    issues_found=[
                        {
                            "file": "test.py",
                            "line": 10,
                            "severity": "high",
                            "title": "Issue 1",
                            "description": "Desc 1",
                            "model": "gpt-5-mini",
                        },
                        {
                            "file": "test.py",
                            "line": 20,
                            "severity": "medium",
                            "title": "Issue 2",
                            "description": "Desc 2",
                            "model": "gpt-5-mini",
                        },
                    ],
                )
            ],
        )

        assert len(response.results) == 1
        assert len(response.results[0].issues_found) == 2
        assert response.status == "success"
        assert response.summary == "1/1 models succeeded. Found 2 issues: 1 high, 1 medium. See `results` for details."

    def test_default_empty_lists(self):
        """Test that results defaults to empty list."""
        response = CodeReviewResponse(
            thread_id="test-123",
            status="success",
            summary="No issues found",
        )

        assert response.results == []


class TestModelResponseMetadata:
    """Tests for ModelResponseMetadata model."""

    def test_valid_metadata(self):
        """Test creating valid ModelResponseMetadata."""
        metadata = ModelResponseMetadata(model="gpt-5-mini", prompt_tokens=100, completion_tokens=50, total_tokens=150, latency_ms=1234)

        assert metadata.model == "gpt-5-mini"
        assert metadata.prompt_tokens == 100
        assert metadata.completion_tokens == 50
        assert metadata.total_tokens == 150
        assert metadata.latency_ms == 1234

    def test_metadata_required_fields(self):
        """Test that only model is required, other fields have defaults."""
        # Only model is required - token/latency fields have defaults
        metadata = ModelResponseMetadata(model="gpt-5-mini")
        assert metadata.model == "gpt-5-mini"
        assert metadata.prompt_tokens == 0
        assert metadata.completion_tokens == 0
        assert metadata.total_tokens == 0
        assert metadata.latency_ms == 0

        # Missing model should raise
        with pytest.raises(ValidationError):
            ModelResponseMetadata()  # Missing required model field

    def test_response_with_metadata(self):
        """Test ToolResponse with metadata."""
        metadata = ModelResponseMetadata(model="gpt-5-mini", prompt_tokens=100, completion_tokens=50, total_tokens=150, latency_ms=500)
        response = SingleToolResponse(thread_id="test-123", content="Review complete", status="success", metadata=metadata)

        assert response.metadata is not None
        assert response.metadata.model == "gpt-5-mini"
        assert response.metadata.total_tokens == 150

    def test_response_without_metadata(self):
        """Test ToolResponse with default metadata (non-LLM step)."""
        response = SingleToolResponse(
            thread_id="test-123", content="Initial checklist", status="in_progress", metadata=ModelResponseMetadata.error_metadata()
        )

        # Metadata is now required, but can use zero values for non-LLM steps
        assert response.metadata is not None
        assert response.metadata.model == "unknown"
        assert response.metadata.total_tokens == 0

    def test_exclude_none_removes_metadata(self):
        """Test that exclude_none=True keeps metadata (now required)."""
        response = SingleToolResponse(
            thread_id="test-123", content="Initial checklist", status="in_progress", metadata=ModelResponseMetadata.error_metadata()
        )

        data = response.model_dump(exclude_none=True)
        # Metadata is now required, so it should always be present
        assert "metadata" in data
        assert "next_action" not in data

    def test_exclude_none_keeps_metadata(self):
        """Test that exclude_none=True keeps non-null metadata."""
        metadata = ModelResponseMetadata(model="gpt-5-mini", prompt_tokens=100, completion_tokens=50, total_tokens=150, latency_ms=500)
        response = SingleToolResponse(thread_id="test-123", content="Review complete", status="success", metadata=metadata)

        data = response.model_dump(exclude_none=True)
        assert "metadata" in data
        assert data["metadata"]["model"] == "gpt-5-mini"

    def test_metadata_with_artifacts(self):
        """Test ModelResponseMetadata with artifacts field."""
        metadata = ModelResponseMetadata(
            model="gpt-5-mini",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=500,
            artifacts=["/path/to/artifact1.md", "/path/to/artifact2.json"],
        )

        assert metadata.artifacts is not None
        assert len(metadata.artifacts) == 2
        assert metadata.artifacts[0] == "/path/to/artifact1.md"
        assert metadata.artifacts[1] == "/path/to/artifact2.json"

    def test_metadata_without_artifacts(self):
        """Test ModelResponseMetadata without artifacts (defaults to None)."""
        metadata = ModelResponseMetadata(model="gpt-5-mini")

        assert metadata.artifacts is None

    def test_metadata_artifacts_excluded_when_none(self):
        """Test that artifacts field is excluded when None with exclude_none=True."""
        metadata = ModelResponseMetadata(model="gpt-5-mini", artifacts=None)
        data = metadata.model_dump(exclude_none=True)

        assert "artifacts" not in data

    def test_metadata_artifacts_included_when_present(self):
        """Test that artifacts field is included when present."""
        metadata = ModelResponseMetadata(model="gpt-5-mini", artifacts=["/path/to/file.md"])
        data = metadata.model_dump(exclude_none=True)

        assert "artifacts" in data
        assert data["artifacts"] == ["/path/to/file.md"]
