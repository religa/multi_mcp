#!/usr/bin/env python3
"""Multi-MCP CLI - Code review from command line."""

import argparse
import asyncio
import json
import logging
import sys
import warnings
from pathlib import Path

from multi_mcp.constants import BYTES_PER_KB
from multi_mcp.settings import settings
from multi_mcp.tools.codereview import codereview_impl

# Suppress LiteLLM async cleanup warning (harmless)
warnings.filterwarnings("ignore", message="coroutine 'close_litellm_async_clients' was never awaited")

logger = logging.getLogger(__name__)

# Directories to always exclude (non-hidden ones that rglob would find)
EXCLUDE_DIRS = {"__pycache__", "venv", "node_modules", "build", "dist", "eggs"}

# Supported file extensions
CODE_EXTENSIONS = {
    ".py",
    ".toml",  # Python
    ".js",
    ".jsx",
    ".ts",
    ".tsx",  # JavaScript/TypeScript
    ".go",
    ".rs",
    ".rb",
    ".java",  # Other languages
    ".c",
    ".cpp",
    ".h",  # C/C++
    ".sh",  # Shell
    ".json",
    ".yaml",
    ".yml",  # Config
    ".md",
    ".txt",  # Docs
}


def collect_files(paths: list[str]) -> list[str]:
    """Collect code files from paths."""
    files = []
    max_size = settings.max_file_size_kb * BYTES_PER_KB

    for p in paths:
        path = Path(p).resolve()
        if not path.exists():
            continue

        if path.is_file():
            if path.name.startswith("."):
                continue
            if path.suffix.lower() not in CODE_EXTENSIONS:
                logger.warning(f"Skipping '{path}': extension '{path.suffix}' not in supported types")
                continue
            if path.stat().st_size <= max_size:
                files.append(str(path))
        elif path.is_dir():
            for f in path.rglob("*"):
                if not f.is_file() or f.is_symlink():
                    continue
                if f.suffix.lower() not in CODE_EXTENSIONS:
                    continue
                if any(part in EXCLUDE_DIRS or part.startswith(".") for part in f.relative_to(path).parts):
                    continue
                try:
                    if f.stat().st_size > max_size:
                        continue
                except OSError:
                    continue
                files.append(str(f))

    return sorted(set(files))


async def run_review(files: list[str], model: str, base_path: str) -> dict:
    """Run code review on files.

    Args:
        files: List of file paths to review
        model: Model name to use
        base_path: Base path for the project

    Returns:
        Review result dictionary
    """
    import uuid

    return await codereview_impl(
        name="CLI Review",
        content="Review the provided files for issues",
        step_number=2,  # Skip checklist, go straight to review
        next_action="stop",
        models=[model],
        base_path=base_path,
        thread_id=str(uuid.uuid4()),  # Generate thread ID for CLI
        relevant_files=files,
    )


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0=success, 1=CLI error, 2=runtime error, 3=issues found)
    """
    parser = argparse.ArgumentParser(
        description="Multi-MCP Code Review CLI",
        epilog="Examples:\n  multi src/\n  multi src/server.py src/config.py\n  multi --model mini src/\n  multi --base-path /path/to/project src/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to review")
    parser.add_argument("--model", default=settings.default_model, help=f"Model to use (default: {settings.default_model})")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output results as JSON (for CI/pipelines)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase logging verbosity (DEBUG level)")
    parser.add_argument("--base-path", default=".", help="Project root directory for context (default: current directory)")

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    files = collect_files(args.paths)
    if not files:
        logger.error("No code files found to review")
        return 1

    # Check against max files limit
    if len(files) > settings.max_files_per_review:
        logger.error(
            f"Found {len(files)} files, exceeds limit of {settings.max_files_per_review}. "
            "Narrow the scope or increase MAX_FILES_PER_REVIEW."
        )
        return 1

    logger.info(f"Reviewing {len(files)} file(s) with {args.model}...")

    # Resolve base_path to absolute path
    base_path = str(Path(args.base_path).resolve())

    try:
        result = asyncio.run(run_review(files, args.model, base_path))
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 2
    except Exception as e:
        logger.error(f"{e}")
        return 2

    # Check for error status
    if result.get("status") == "error":
        if args.json_output:
            print(json.dumps({"error": result.get("summary", "Unknown error"), "status": "error"}, indent=2))
        else:
            logger.error(result.get("summary", "Unknown error"))
        return 2

    issues = []
    if "results" in result and result["results"]:
        for model_result in result["results"]:
            if model_result.get("issues_found"):
                issues.extend(model_result["issues_found"])
    elif "issues_found" in result:
        issues = result.get("issues_found") or []

    # JSON output mode
    if args.json_output:
        output = {
            "status": result.get("status", "complete"),
            "files_reviewed": len(files),
            "model": args.model,
            "summary": result.get("summary", ""),
            "issues_count": len(issues),
            "issues": issues,
        }
        print(json.dumps(output, indent=2))
        return 3 if issues else 0

    # Human-readable text output
    print(result.get("summary", "No output"))

    if issues:
        print("\n## Issues Found:")
        for issue in issues:
            severity = issue.get("severity", "unknown").upper()
            col = (
                "🔴"
                if severity == "CRITICAL"
                else "🟠"
                if severity == "HIGH"
                else "🟡"
                if severity == "MEDIUM"
                else "🟢"
                if severity == "LOW"
                else " "
            )
            location = issue.get("location", "?")
            desc = issue.get("description", "")
            print(f"[{col} {severity}] {location}: {desc}")
        return 3  # Issues found

    return 0


if __name__ == "__main__":
    sys.exit(main())
