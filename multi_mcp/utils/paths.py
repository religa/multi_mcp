"""Path resolution and validation utilities."""

from pathlib import Path

# Project root: multi_mcp/utils/paths.py -> ../../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"

# Create logs directory once at import time
LOGS_DIR.mkdir(exist_ok=True)


def resolve_path(file_path: str, base_path: str) -> str:
    """Resolve and validate file path within base_path.

    Security: Path.resolve() follows symlinks, then relative_to() ensures
    the final resolved path is within base_path (prevents traversal attacks).

    Args:
        file_path: File path (absolute or relative)
        base_path: Base directory path (absolute)

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If resolved path escapes base_path
    """
    base = Path(base_path).resolve()

    if Path(file_path).is_absolute():
        resolved = Path(file_path).resolve()
    else:
        resolved = (base / file_path).resolve()

    # Security: Ensure resolved path is within base_path
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(f"Path {file_path} escapes base_path {base_path}") from None

    return str(resolved)
