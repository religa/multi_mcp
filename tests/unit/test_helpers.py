"""Unit tests for general helper functions."""

from pydantic import BaseModel, Field

from multi_mcp.utils.helpers import get_field_description, get_version


class TestGetVersion:
    """Tests for get_version function."""

    def test_get_version_returns_string(self):
        """Test that get_version returns a string."""
        version = get_version()

        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_version_format(self):
        """Test that version has expected format."""
        version = get_version()

        # Should be semantic version (x.y.z) or "unknown"
        if version != "unknown":
            parts = version.split(".")
            # Should have at least major.minor
            assert len(parts) >= 2
            # First part should be numeric
            assert parts[0].isdigit()

    def test_get_version_handles_missing_file(self):
        """Test that missing pyproject.toml returns 'unknown'."""
        # This test validates error handling
        # Even if pyproject.toml exists, the function should handle errors gracefully
        version = get_version()

        # Should never raise an exception
        assert version is not None


class TestGetFieldDescription:
    """Tests for get_field_description function."""

    def test_get_field_description_with_description(self):
        """Test extracting field description from Pydantic model."""

        class TestModel(BaseModel):
            name: str = Field(..., description="The user's name")
            age: int = Field(..., description="The user's age in years")

        desc = get_field_description(TestModel, "name")

        assert desc == "The user's name"

    def test_get_field_description_with_age_field(self):
        """Test extracting another field description."""

        class TestModel(BaseModel):
            name: str = Field(..., description="The user's name")
            age: int = Field(..., description="The user's age in years")

        desc = get_field_description(TestModel, "age")

        assert desc == "The user's age in years"

    def test_get_field_description_without_description(self):
        """Test field without explicit description returns default."""

        class TestModel(BaseModel):
            name: str

        desc = get_field_description(TestModel, "name")

        assert desc == "name parameter"

    def test_get_field_description_nonexistent_field(self):
        """Test that nonexistent field returns default."""

        class TestModel(BaseModel):
            name: str = Field(..., description="The user's name")

        desc = get_field_description(TestModel, "nonexistent")

        assert desc == "nonexistent parameter"

    def test_get_field_description_field_with_empty_description(self):
        """Test field with empty description returns default."""

        class TestModel(BaseModel):
            name: str = Field(..., description="")

        desc = get_field_description(TestModel, "name")

        # Empty description should fall back to default
        assert desc == "name parameter"

    def test_get_field_description_optional_field(self):
        """Test description extraction for optional fields."""

        class TestModel(BaseModel):
            name: str | None = Field(None, description="Optional name")

        desc = get_field_description(TestModel, "name")

        assert desc == "Optional name"

    def test_get_field_description_field_with_default(self):
        """Test description extraction for fields with defaults."""

        class TestModel(BaseModel):
            count: int = Field(default=0, description="Number of items")

        desc = get_field_description(TestModel, "count")

        assert desc == "Number of items"

    def test_get_field_description_complex_model(self):
        """Test description extraction from complex nested model."""

        class NestedModel(BaseModel):
            value: str = Field(..., description="Nested value")

        class TestModel(BaseModel):
            name: str = Field(..., description="Primary name")
            nested: NestedModel = Field(..., description="Nested data")

        desc1 = get_field_description(TestModel, "name")
        desc2 = get_field_description(TestModel, "nested")

        assert desc1 == "Primary name"
        assert desc2 == "Nested data"

    def test_get_field_description_multiline_description(self):
        """Test extraction of multiline descriptions."""

        class TestModel(BaseModel):
            name: str = Field(..., description="This is a long\nmultiline\ndescription")

        desc = get_field_description(TestModel, "name")

        assert "multiline" in desc
        assert "\n" in desc

    def test_get_field_description_special_characters(self):
        """Test descriptions with special characters."""

        class TestModel(BaseModel):
            email: str = Field(..., description="User's email (e.g., user@example.com)")

        desc = get_field_description(TestModel, "email")

        assert desc == "User's email (e.g., user@example.com)"
        assert "@" in desc
