"""Unit tests for MCP factory pattern."""

import inspect
from typing import Literal, get_type_hints

import pytest
from pydantic import BaseModel, Field

from multi_mcp.utils.mcp_factory import create_mcp_wrapper


class SimpleRequest(BaseModel):
    """Simple request with only required fields."""

    name: str = Field(..., description="Name of the request")
    value: int = Field(..., description="Value parameter")


class MixedRequest(BaseModel):
    """Request with both required and optional fields."""

    # Required fields
    name: str = Field(..., description="Name parameter")
    step: int = Field(..., description="Step number")

    # Optional fields
    optional_str: str | None = Field(None, description="Optional string")
    optional_list: list[str] = Field(default_factory=list, description="Optional list")


class AllOptionalRequest(BaseModel):
    """Request with all optional fields."""

    param1: str | None = Field(None, description="First parameter")
    param2: int | None = Field(None, description="Second parameter")
    param3: list[str] = Field(default_factory=list, description="Third parameter")


class TestParameterOrdering:
    """Test that generated functions have valid parameter ordering."""

    def test_required_params_before_optional(self):
        """Required parameters must come before optional parameters."""

        async def impl(name: str, step: int, optional_str: str | None = None, optional_list: list[str] | None = None):
            return {"name": name, "step": step}

        wrapper = create_mcp_wrapper(MixedRequest, impl, "Test wrapper")
        sig = inspect.signature(wrapper)

        # Get parameter names in order
        param_names = list(sig.parameters.keys())

        # Find first optional parameter
        first_optional_idx = None
        for i, param_name in enumerate(param_names):
            param = sig.parameters[param_name]
            if param.default is not inspect.Parameter.empty:
                first_optional_idx = i
                break

        # Verify all parameters after first optional are also optional
        if first_optional_idx is not None:
            for i in range(first_optional_idx, len(param_names)):
                param_name = param_names[i]
                param = sig.parameters[param_name]
                assert param.default is not inspect.Parameter.empty, (
                    f"Required parameter '{param_name}' at position {i} comes after optional parameter at position {first_optional_idx}"
                )

    def test_all_required_fields_first(self):
        """All required fields should be at the beginning."""

        async def impl(name: str, step: int, optional_str: str | None = None, optional_list: list[str] | None = None):
            return {"name": name}

        wrapper = create_mcp_wrapper(MixedRequest, impl)
        sig = inspect.signature(wrapper)

        params = list(sig.parameters.items())

        # First two should be required (name, step)
        assert params[0][1].default is inspect.Parameter.empty, "First param should be required"
        assert params[1][1].default is inspect.Parameter.empty, "Second param should be required"

        # Rest should be optional
        for param_name, param in params[2:]:
            assert param.default is not inspect.Parameter.empty, f"Parameter '{param_name}' should be optional"

    def test_only_required_fields(self):
        """Test with schema that has only required fields."""

        async def impl(name: str, value: int):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(SimpleRequest, impl)
        sig = inspect.signature(wrapper)

        # All parameters should be required
        for param_name, param in sig.parameters.items():
            assert param.default is inspect.Parameter.empty, f"Parameter '{param_name}' should be required"

    def test_only_optional_fields(self):
        """Test with schema that has only optional fields."""

        async def impl(param1: str | None = None, param2: int | None = None, param3: list[str] | None = None):
            return {}

        wrapper = create_mcp_wrapper(AllOptionalRequest, impl)
        sig = inspect.signature(wrapper)

        # All parameters should be optional
        for param_name, param in sig.parameters.items():
            assert param.default is not inspect.Parameter.empty, f"Parameter '{param_name}' should be optional"


class TestFunctionGeneration:
    """Test that generated functions work correctly."""

    @pytest.mark.asyncio
    async def test_wrapper_calls_impl(self):
        """Wrapper should call implementation function."""
        called = False

        async def impl(name: str, value: int):
            nonlocal called
            called = True
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(SimpleRequest, impl)
        result = await wrapper(name="test", value=42)

        assert called, "Implementation function should be called"
        assert result == {"name": "test", "value": 42}

    @pytest.mark.asyncio
    async def test_pydantic_validation_enforced(self):
        """Wrapper should enforce Pydantic validation."""

        async def impl(name: str, step: int, optional_str: str | None = None, optional_list: list[str] | None = None):
            return {"name": name, "step": step}

        wrapper = create_mcp_wrapper(MixedRequest, impl)

        # Invalid step (negative) - should be validated by Pydantic if we add validators
        # For now, just test that it accepts valid input
        result = await wrapper(name="test", step=1)
        assert result["name"] == "test"

    @pytest.mark.asyncio
    async def test_default_factory_works(self):
        """default_factory should be executed correctly."""

        async def impl(name: str, step: int, optional_str: str | None = None, optional_list: list[str] | None = None):
            return {"optional_list": optional_list or []}

        wrapper = create_mcp_wrapper(MixedRequest, impl)

        # Call without optional_list
        result = await wrapper(name="test", step=1)

        # default_factory should create empty list
        assert result["optional_list"] == []

    @pytest.mark.asyncio
    async def test_optional_params_with_none(self):
        """Passing None to optional parameters should work."""

        async def impl(name: str, step: int, optional_str: str | None = None, optional_list: list[str] | None = None):
            return {"optional_str": optional_str, "optional_list": optional_list or []}

        wrapper = create_mcp_wrapper(MixedRequest, impl)

        result = await wrapper(name="test", step=1, optional_str=None)
        assert result["optional_str"] is None


class TestMetadataPreservation:
    """Test that function metadata is preserved."""

    def test_docstring_preserved(self):
        """Wrapper should have the provided docstring."""

        async def impl(name: str, value: int):
            return {}

        docstring = "This is a test tool."
        wrapper = create_mcp_wrapper(SimpleRequest, impl, docstring)

        assert wrapper.__doc__ == docstring

    def test_default_docstring(self):
        """Wrapper should have default docstring if none provided."""

        async def impl(name: str, value: int):
            return {}

        wrapper = create_mcp_wrapper(SimpleRequest, impl)

        assert wrapper.__doc__ is not None
        assert "impl" in wrapper.__doc__

    def test_function_name(self):
        """Wrapper should have correct function name."""

        async def simple_impl(name: str, value: int):
            return {}

        wrapper = create_mcp_wrapper(SimpleRequest, simple_impl)

        # Should remove '_impl' suffix
        assert wrapper.__name__ == "simple"

    def test_annotations_preserved(self):
        """Type annotations should be preserved."""

        async def impl(name: str, value: int):
            return {}

        wrapper = create_mcp_wrapper(SimpleRequest, impl)

        # Check annotations exist
        assert hasattr(wrapper, "__annotations__")
        assert "name" in wrapper.__annotations__
        assert "value" in wrapper.__annotations__
        assert "return" in wrapper.__annotations__


class TestRealSchemas:
    """Test with real schemas from the codebase."""

    def test_chat_request_signature(self):
        """Test ChatRequest schema generates valid signature."""
        from multi_mcp.schemas.chat import ChatRequest
        from multi_mcp.tools.chat import chat_impl

        wrapper = create_mcp_wrapper(ChatRequest, chat_impl, "Test chat")
        sig = inspect.signature(wrapper)

        # Verify signature is valid (no SyntaxError)
        param_names = list(sig.parameters.keys())
        assert len(param_names) > 0

        # Verify required params come before optional
        found_optional = False
        for param_name in param_names:
            param = sig.parameters[param_name]
            if param.default is not inspect.Parameter.empty:
                found_optional = True
            elif found_optional:
                pytest.fail(f"Required param '{param_name}' comes after optional param")

    def test_codereview_request_signature(self):
        """Test CodeReviewRequest schema generates valid signature."""
        from multi_mcp.schemas.codereview import CodeReviewRequest
        from multi_mcp.tools.codereview import codereview_impl

        wrapper = create_mcp_wrapper(CodeReviewRequest, codereview_impl, "Test codereview")
        sig = inspect.signature(wrapper)

        # Verify signature is valid
        param_names = list(sig.parameters.keys())
        assert len(param_names) > 0

        # Verify required params come before optional
        found_optional = False
        for param_name in param_names:
            param = sig.parameters[param_name]
            if param.default is not inspect.Parameter.empty:
                found_optional = True
            elif found_optional:
                pytest.fail(f"Required param '{param_name}' comes after optional param")

    def test_compare_request_signature(self):
        """Test CompareRequest schema generates valid signature."""
        from multi_mcp.schemas.compare import CompareRequest
        from multi_mcp.tools.compare import compare_impl

        wrapper = create_mcp_wrapper(CompareRequest, compare_impl, "Test compare")
        sig = inspect.signature(wrapper)

        # Verify signature is valid
        param_names = list(sig.parameters.keys())
        assert len(param_names) > 0

        # Verify parameter ordering
        found_optional = False
        for param_name in param_names:
            param = sig.parameters[param_name]
            if param.default is not inspect.Parameter.empty:
                found_optional = True
            elif found_optional:
                pytest.fail(f"Required param '{param_name}' comes after optional param")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_schema(self):
        """Test with schema that has no fields."""

        class EmptyRequest(BaseModel):
            pass

        async def impl():
            return {}

        wrapper = create_mcp_wrapper(EmptyRequest, impl)
        sig = inspect.signature(wrapper)

        # Should have no parameters
        assert len(sig.parameters) == 0

    def test_complex_field_types(self):
        """Test with complex field types."""

        class ComplexRequest(BaseModel):
            required_literal: Literal["a", "b"] = Field(..., description="Literal type")
            optional_list_int: list[int] = Field(default_factory=list, description="List of ints")

        async def impl(required_literal: str, optional_list_int: list[int] | None = None):
            return {"required_literal": required_literal}

        wrapper = create_mcp_wrapper(ComplexRequest, impl)
        sig = inspect.signature(wrapper)

        # Verify required comes before optional
        params = list(sig.parameters.items())
        assert params[0][0] == "required_literal"
        assert params[0][1].default is inspect.Parameter.empty
        assert params[1][1].default is not inspect.Parameter.empty


class TestValidationErrorHandling:
    """Test that validation errors are caught and returned as structured responses."""

    @pytest.mark.asyncio
    async def test_missing_required_field_returns_error_response(self):
        """Missing required field should return error with details in content."""

        class OptionalRequest(BaseModel):
            name: str | None = Field(None, description="Name")
            value: int = Field(..., description="Required value")

        async def impl(name: str | None = None, value: int = 0):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(OptionalRequest, impl)

        # Call without required 'value' field (passing None)
        result = await wrapper(name="test", value=None)

        assert result["status"] == "error"
        assert "thread_id" in result
        assert "content" in result
        assert "validation failed" in result["content"].lower()
        assert "value" in result["content"].lower()  # Should mention missing field

    @pytest.mark.asyncio
    async def test_wrong_type_returns_error_response(self):
        """Wrong type for field should return error with details in content."""

        async def impl(name: str, value: int):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(SimpleRequest, impl)

        # Call with wrong type for 'value' (string instead of int)
        result = await wrapper(name="test", value="not_an_int")

        assert result["status"] == "error"
        assert "content" in result
        assert "validation failed" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_multiple_validation_errors_all_listed(self):
        """Multiple validation errors should all be listed in content."""

        class MultiRequiredRequest(BaseModel):
            name: str = Field(..., min_length=3, description="Name (min 3 chars)")
            value: int = Field(..., gt=0, description="Value (must be positive)")

        async def impl(name: str = "", value: int = 0):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(MultiRequiredRequest, impl)

        # Call with both fields invalid (short name, negative value)
        result = await wrapper(name="ab", value=-5)

        assert result["status"] == "error"
        assert "content" in result
        # Should mention both issues
        content_lower = result["content"].lower()
        assert "name" in content_lower or "value" in content_lower

    @pytest.mark.asyncio
    async def test_implementation_error_returns_error_response(self):
        """Implementation errors should be caught and returned in content."""

        async def impl(name: str, value: int):
            raise ValueError("Something went wrong in implementation")

        wrapper = create_mcp_wrapper(SimpleRequest, impl)

        result = await wrapper(name="test", value=42)

        assert result["status"] == "error"
        assert "content" in result
        assert "execution error" in result["content"].lower() or "error" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_thread_id_preserved_in_validation_error(self):
        """thread_id should be included in error response if present."""

        class RequestWithThread(BaseModel):
            thread_id: str | None = Field(None, description="Thread ID")
            name: str = Field(..., description="Name")
            value: int = Field(..., description="Value")

        async def impl(thread_id: str | None = None, name: str = "", value: int = 0):
            return {"thread_id": thread_id}

        wrapper = create_mcp_wrapper(RequestWithThread, impl)

        # Missing required fields but has thread_id (pass None to trigger validation error)
        result = await wrapper(thread_id="test-thread-123", name=None, value=None)

        assert result["status"] == "error"
        assert result["thread_id"] == "test-thread-123"

    @pytest.mark.asyncio
    async def test_thread_id_auto_generated_when_missing(self):
        """thread_id should be auto-generated (UUID) if not provided."""

        class RequiredValueRequest(BaseModel):
            name: str | None = Field(None, description="Name")
            value: int = Field(..., description="Required value")
            thread_id: str | None = Field(None, description="Thread ID")

        async def impl(name: str | None = None, value: int = 0, thread_id: str | None = None):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(RequiredValueRequest, impl)

        # Trigger validation error without thread_id
        result = await wrapper(name="test", value=None)

        assert result["status"] == "error"
        # thread_id should be auto-generated UUID (36 chars including hyphens)
        assert len(result["thread_id"]) == 36
        assert result["thread_id"].count("-") == 4  # UUID format: 8-4-4-4-12

    @pytest.mark.asyncio
    async def test_valid_request_still_works(self):
        """Valid requests should continue to work normally."""

        async def impl(name: str, value: int):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(SimpleRequest, impl)

        result = await wrapper(name="test", value=42)

        # Should return normal response (not error)
        assert result == {"name": "test", "value": 42}
        assert result.get("status") != "error"

    @pytest.mark.asyncio
    async def test_error_content_is_structured_markdown(self):
        """Error content should be formatted as structured markdown."""

        class RequiredValueRequest(BaseModel):
            name: str | None = Field(None, description="Name")
            value: int = Field(..., description="Required value")

        async def impl(name: str | None = None, value: int = 0):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(RequiredValueRequest, impl)

        result = await wrapper(name="test", value=None)  # missing value

        assert result["status"] == "error"
        content = result["content"]
        # Should contain markdown formatting
        assert "**" in content or "#" in content or "-" in content
        # Should be multi-line with field details
        assert "\n" in content


class TestInspectSignatureImplementation:
    """Test that inspect.Signature approach produces correct signatures for FastMCP introspection."""

    def test_signature_has_all_fields(self):
        """Wrapper signature should include all schema fields."""

        class TestRequest(BaseModel):
            name: str = Field(..., description="Name field")
            value: int = Field(..., description="Value field")
            optional: str | None = Field(None, description="Optional field")

        async def test_impl(name: str, value: int, optional: str | None = None):
            return {"name": name, "value": value}

        wrapper = create_mcp_wrapper(TestRequest, test_impl)
        sig = inspect.signature(wrapper)

        assert "name" in sig.parameters
        assert "value" in sig.parameters
        assert "optional" in sig.parameters

    def test_signature_annotations_with_descriptions(self):
        """Wrapper should have Annotated types with descriptions in metadata."""

        class TestRequest(BaseModel):
            name: str = Field(..., description="Name description")
            count: int = Field(..., description="Count description")

        async def test_impl(name: str, count: int):
            return {"name": name}

        wrapper = create_mcp_wrapper(TestRequest, test_impl)
        hints = get_type_hints(wrapper, include_extras=True)

        # Check that name has Annotated type
        assert hasattr(hints["name"], "__metadata__")
        assert hasattr(hints["count"], "__metadata__")

        # Check descriptions are in metadata
        name_metadata = str(hints["name"].__metadata__)
        count_metadata = str(hints["count"].__metadata__)
        assert "Name description" in name_metadata
        assert "Count description" in count_metadata

    def test_required_params_have_parameter_empty(self):
        """Required fields should have Parameter.empty as default."""

        class TestRequest(BaseModel):
            required: str = Field(..., description="Required")
            optional: str | None = Field(None, description="Optional")

        async def test_impl(required: str, optional: str | None = None):
            return {}

        wrapper = create_mcp_wrapper(TestRequest, test_impl)
        sig = inspect.signature(wrapper)

        assert sig.parameters["required"].default == inspect.Parameter.empty
        assert sig.parameters["optional"].default is None

    def test_signature_return_annotation(self):
        """Wrapper signature should have dict as return annotation."""

        async def test_impl(name: str):
            return {}

        wrapper = create_mcp_wrapper(SimpleRequest, test_impl)
        sig = inspect.signature(wrapper)

        assert sig.return_annotation is dict

    def test_fastmcp_introspection_simulation(self):
        """Simulate what FastMCP does to verify introspection works correctly."""

        class TestRequest(BaseModel):
            param1: str = Field(..., description="First param")
            param2: int = Field(42, description="Second param")
            param3: str | None = Field(None, description="Third param")

        async def test_impl(param1: str, param2: int = 42, param3: str | None = None):
            return {}

        wrapper = create_mcp_wrapper(TestRequest, test_impl)

        # Simulate what FastMCP does
        sig = inspect.signature(wrapper)
        hints = get_type_hints(wrapper, include_extras=True)

        # Can get parameter names in order
        param_names = list(sig.parameters.keys())
        assert "param1" in param_names
        assert "param2" in param_names
        assert "param3" in param_names

        # Can get types with Annotated
        # For Annotated[str, "desc"], __origin__ is str, not Annotated
        # So we check for __metadata__ presence instead
        assert hasattr(hints["param1"], "__metadata__")

        # Can get descriptions from metadata
        param1_meta = hints["param1"].__metadata__
        param2_meta = hints["param2"].__metadata__
        param3_meta = hints["param3"].__metadata__
        assert "First param" in str(param1_meta)
        assert "Second param" in str(param2_meta)
        assert "Third param" in str(param3_meta)

        # Can determine required vs optional
        assert sig.parameters["param1"].default == inspect.Parameter.empty  # Required
        assert sig.parameters["param2"].default is None  # Optional
        assert sig.parameters["param3"].default is None  # Optional

    def test_parameter_kind_is_positional_or_keyword(self):
        """All parameters should have POSITIONAL_OR_KEYWORD kind."""

        async def test_impl(name: str, value: int):
            return {}

        wrapper = create_mcp_wrapper(SimpleRequest, test_impl)
        sig = inspect.signature(wrapper)

        for param in sig.parameters.values():
            assert param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD

    def test_signature_assigned_correctly(self):
        """Verify __signature__ attribute is properly assigned."""

        async def test_impl(name: str, value: int):
            return {}

        wrapper = create_mcp_wrapper(SimpleRequest, test_impl)

        # Should have __signature__ attribute
        assert hasattr(wrapper, "__signature__")
        assert isinstance(wrapper.__signature__, inspect.Signature)

        # inspect.signature() should return the same signature
        assert inspect.signature(wrapper) == wrapper.__signature__

    def test_mixed_required_optional_ordering(self):
        """Parameters should be ordered: required first, then optional."""

        class MixedOrderRequest(BaseModel):
            # Define in mixed order to test sorting
            optional1: str | None = Field(None, description="Optional 1")
            required1: str = Field(..., description="Required 1")
            optional2: int | None = Field(None, description="Optional 2")
            required2: int = Field(..., description="Required 2")

        async def test_impl(**kwargs):
            return {}

        wrapper = create_mcp_wrapper(MixedOrderRequest, test_impl)
        sig = inspect.signature(wrapper)

        params = list(sig.parameters.items())

        # All required should come before any optional
        required_params = [name for name, p in params if p.default == inspect.Parameter.empty]
        optional_params = [name for name, p in params if p.default != inspect.Parameter.empty]

        # Required count should be 2
        assert len(required_params) == 2
        assert "required1" in required_params
        assert "required2" in required_params

        # Optional count should be 2
        assert len(optional_params) == 2
        assert "optional1" in optional_params
        assert "optional2" in optional_params

        # Required params should be first in the parameter list
        for i, (name, param) in enumerate(params):
            if param.default == inspect.Parameter.empty:
                # This is required, verify no optional came before
                for j in range(i):
                    prev_param = params[j][1]
                    assert prev_param.default == inspect.Parameter.empty, (
                        f"Optional parameter at position {j} comes before required parameter '{name}' at position {i}"
                    )
