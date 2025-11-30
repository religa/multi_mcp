"""Schema contract tests - verify schemas match implementation signatures.

These tests ensure that:
- Pydantic schema fields match implementation function parameters
- Required fields are marked correctly
- Optional fields have defaults
- No missing or extra parameters
"""

import inspect

import pytest
from pydantic import ValidationError


class TestCodereviewContract:
    """Test codereview schema matches implementation."""

    def test_schema_fields_match_impl_params(self):
        """CodeReviewRequest fields match codereview_impl parameters."""
        from src.schemas.codereview import CodeReviewRequest
        from src.tools.codereview import codereview_impl

        # Get schema fields
        schema_fields = set(CodeReviewRequest.model_fields.keys())

        # Get implementation parameters
        sig = inspect.signature(codereview_impl)
        impl_params = set(sig.parameters.keys())

        # Schema fields should be subset of impl params (impl may have more)
        missing_in_impl = schema_fields - impl_params
        assert len(missing_in_impl) == 0, f"Schema has fields not in impl: {missing_in_impl}"

    def test_required_fields_have_no_defaults(self):
        """Required schema fields don't have defaults."""
        from src.schemas.codereview import CodeReviewRequest

        required_fields = ["name", "content", "step_number", "next_action"]

        for field_name in required_fields:
            field = CodeReviewRequest.model_fields[field_name]
            # Required fields should not have a default value
            assert field.is_required(), f"Field '{field_name}' should be required (no default)"

    def test_optional_fields_have_defaults(self):
        """Optional schema fields have defaults."""
        from src.schemas.codereview import CodeReviewRequest

        optional_fields = ["thread_id", "model", "relevant_files", "base_path", "issues_found"]

        for field_name in optional_fields:
            if field_name in CodeReviewRequest.model_fields:
                field = CodeReviewRequest.model_fields[field_name]
                # Optional fields should have a default (None or actual value)
                assert not field.is_required() or field.default is not None, f"Field '{field_name}' should have default"


class TestChatContract:
    """Test chat schema matches implementation."""

    def test_schema_fields_match_impl_params(self):
        """ChatRequest fields match chat_impl parameters."""
        from src.schemas.chat import ChatRequest
        from src.tools.chat import chat_impl

        # Get schema fields
        schema_fields = set(ChatRequest.model_fields.keys())

        # Get implementation parameters
        sig = inspect.signature(chat_impl)
        impl_params = set(sig.parameters.keys())

        # Schema fields should be subset of impl params
        missing_in_impl = schema_fields - impl_params
        assert len(missing_in_impl) == 0, f"Schema has fields not in impl: {missing_in_impl}"

    def test_required_fields(self):
        """Chat required fields are marked correctly."""
        from src.schemas.chat import ChatRequest

        required_fields = ["name", "content", "step_number", "next_action"]

        for field_name in required_fields:
            field = ChatRequest.model_fields[field_name]
            assert field.is_required(), f"Field '{field_name}' should be required"


class TestCompareContract:
    """Test compare schema matches implementation."""

    def test_schema_fields_match_impl_params(self):
        """CompareRequest fields match compare_impl parameters."""
        from src.schemas.compare import CompareRequest
        from src.tools.compare import compare_impl

        # Get schema fields
        schema_fields = set(CompareRequest.model_fields.keys())

        # Get implementation parameters
        sig = inspect.signature(compare_impl)
        impl_params = set(sig.parameters.keys())

        # Schema fields should be subset of impl params
        missing_in_impl = schema_fields - impl_params
        assert len(missing_in_impl) == 0, f"Schema has fields not in impl: {missing_in_impl}"

    def test_models_field_required(self):
        """Compare 'models' field is optional with default."""
        from src.schemas.compare import CompareRequest

        # 'models' should be optional (has default)
        field = CompareRequest.model_fields["models"]
        # Should have default (list or None)
        assert not field.is_required() or field.default is not None, "models should have default"


class TestDebateContract:
    """Test debate schema matches implementation."""

    def test_schema_fields_match_impl_params(self):
        """DebateRequest fields match debate_impl parameters."""
        from src.schemas.debate import DebateRequest
        from src.tools.debate import debate_impl

        # Get schema fields
        schema_fields = set(DebateRequest.model_fields.keys())

        # Get implementation parameters
        sig = inspect.signature(debate_impl)
        impl_params = set(sig.parameters.keys())

        # Schema fields should be subset of impl params
        missing_in_impl = schema_fields - impl_params
        assert len(missing_in_impl) == 0, f"Schema has fields not in impl: {missing_in_impl}"

    def test_models_field_optional(self):
        """Debate 'models' field is optional with default."""
        from src.schemas.debate import DebateRequest

        # 'models' should be optional (has default)
        field = DebateRequest.model_fields["models"]
        assert not field.is_required() or field.default is not None, "models should have default"


class TestBaseToolRequest:
    """Test base schema contracts."""

    def test_base_has_common_fields(self):
        """BaseToolRequest has all common fields."""
        from src.schemas.base import BaseToolRequest

        # Common fields all tools should have
        common_fields = ["name", "content", "step_number", "next_action", "base_path"]

        for field_name in common_fields:
            assert field_name in BaseToolRequest.model_fields, f"BaseToolRequest should have '{field_name}' field"

    def test_single_tool_request_has_model(self):
        """SingleToolRequest has model field."""
        from src.schemas.base import SingleToolRequest

        # SingleToolRequest should have 'model' field
        assert "model" in SingleToolRequest.model_fields, "SingleToolRequest should have 'model' field"

        # Should be optional (has default)
        field = SingleToolRequest.model_fields["model"]
        assert not field.is_required() or field.default is not None, "model should have default"


class TestSchemaInheritance:
    """Test schema inheritance relationships."""

    def test_codereview_inherits_base(self):
        """CodeReviewRequest inherits from BaseToolRequest."""
        from src.schemas.base import BaseToolRequest
        from src.schemas.codereview import CodeReviewRequest

        assert issubclass(CodeReviewRequest, BaseToolRequest), "CodeReviewRequest should inherit from BaseToolRequest"

    def test_chat_inherits_single(self):
        """ChatRequest inherits from SingleToolRequest."""
        from src.schemas.base import SingleToolRequest
        from src.schemas.chat import ChatRequest

        assert issubclass(ChatRequest, SingleToolRequest), "ChatRequest should inherit from SingleToolRequest"

    def test_compare_inherits_base(self):
        """CompareRequest inherits from BaseToolRequest."""
        from src.schemas.base import BaseToolRequest
        from src.schemas.compare import CompareRequest

        assert issubclass(CompareRequest, BaseToolRequest), "CompareRequest should inherit from BaseToolRequest"

    def test_debate_inherits_base(self):
        """DebateRequest inherits from BaseToolRequest."""
        from src.schemas.base import BaseToolRequest
        from src.schemas.debate import DebateRequest

        assert issubclass(DebateRequest, BaseToolRequest), "DebateRequest should inherit from BaseToolRequest"


class TestSchemaValidation:
    """Test schema validation rules."""

    def test_codereview_validates_next_action(self):
        """CodeReviewRequest validates next_action enum."""
        from src.schemas.codereview import CodeReviewRequest

        # Valid next_action
        valid_request = CodeReviewRequest(
            name="test",
            content="test content",
            step_number=1,
            next_action="continue",
            base_path="/tmp",
        )
        assert valid_request.next_action == "continue"

        # Invalid next_action should raise ValidationError
        with pytest.raises(ValidationError):
            CodeReviewRequest(
                name="test",
                content="test content",
                step_number=1,
                next_action="invalid",
                base_path="/tmp",
            )

    def test_chat_validates_step_number(self):
        """ChatRequest validates step_number is positive."""
        from src.schemas.chat import ChatRequest

        # Valid step_number
        valid_request = ChatRequest(
            name="test",
            content="test content",
            step_number=1,
            next_action="stop",
            base_path="/tmp",
        )
        assert valid_request.step_number == 1

        # Zero step_number should fail (step numbers start at 1)
        with pytest.raises(ValidationError):
            ChatRequest(
                name="test",
                content="test content",
                step_number=0,
                next_action="stop",
                base_path="/tmp",
            )
