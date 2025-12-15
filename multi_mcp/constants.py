"""Constants used throughout the application.

This module centralizes magic numbers and configuration constants
that don't belong in Settings (which handles environment-based config).
"""

# LLM response limits
DEFAULT_MAX_TOKENS: int = 32768
"""Default max_tokens for LLM responses when not specified in model config.
Allows for very long code review responses with many issues and detailed fixes."""

# Parallel execution
DEFAULT_MAX_CONCURRENCY: int = 5
"""Default maximum concurrent LLM calls in parallel execution."""

# Error output truncation
ERROR_PREVIEW_MAX_LENGTH: int = 500
"""Maximum characters to include in error preview messages."""

DEBUG_LOG_MAX_LENGTH: int = 1000
"""Maximum characters to include in debug log output."""

# File size conversion
BYTES_PER_KB: int = 1024
"""Bytes per kilobyte for file size calculations."""

# Artifact filename limits
ARTIFACT_NAME_MAX_LENGTH: int = 15
"""Maximum length for artifact name slugs."""

ARTIFACT_NAME_MAX_WORDS: int = 2
"""Maximum number of words in artifact name slugs."""
