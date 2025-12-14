"""General helper functions for the server."""

import tomllib
from pathlib import Path

from pydantic import BaseModel
from pydantic.fields import FieldInfo


def get_version() -> str:
    """Read version from pyproject.toml."""
    try:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "unknown"


def get_field_description(model_class: type[BaseModel], field_name: str) -> str:
    """Extract field description from Pydantic model.

    This enables DRY principle: field descriptions are defined once in the schema
    and automatically extracted for MCP tool documentation.

    Args:
        model_class: Pydantic model class
        field_name: Name of the field to get description for

    Returns:
        Field description string, or default message if not found
    """
    field_info = model_class.model_fields.get(field_name)
    if field_info and isinstance(field_info, FieldInfo):
        return field_info.description or f"{field_name} parameter"
    return f"{field_name} parameter"
