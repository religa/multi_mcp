"""Pytest configuration for multi_mcp tests."""

import os
import shutil
from pathlib import Path

import pytest

# Load CLI mock fixtures
# CLI mocks removed - tests now use CLIExecutor directly
# pytest_plugins = ["tests.fixtures.cli_mocks"]

# ============================================================================
# Integration Test Configuration
# ============================================================================

# Default model for integration tests (cheap, fast model)
# Can be overridden via INTEGRATION_TEST_MODEL environment variable
DEFAULT_INTEGRATION_TEST_MODEL = os.getenv("INTEGRATION_TEST_MODEL", "gpt-5-nano")

# Multi-model test configurations
DEFAULT_COMPARE_MODELS = [DEFAULT_INTEGRATION_TEST_MODEL, "gemini-2.5-flash"]
DEFAULT_DEBATE_MODELS = ["gpt-5-nano", "gemini-2.5-flash"]  # Different models for real debate diversity


@pytest.fixture(autouse=True)
async def clear_conversation_store():
    """Clear conversation store between tests to prevent state leakage."""
    yield  # Run the test first

    # Clear the global store after each test
    from multi_mcp.memory.store import _threads

    _threads.clear()


# NOTE: Integration test timeout is set via MODEL_TIMEOUT_SECONDS env var
# This is done in Makefile (line 100) and should not be set in fixtures
# to avoid race conditions in parallel test execution with pytest-xdist


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with standard structure."""
    project = tmp_path / "test_project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "README.md").write_text("# Test Project\n")
    return project


@pytest.fixture
def integration_test_model():
    """Get the model to use for integration tests.

    Returns the model name configured for integration tests.
    Can be overridden via INTEGRATION_TEST_MODEL environment variable.

    Example:
        INTEGRATION_TEST_MODEL=gpt-5-mini pytest tests/integration/
    """
    return DEFAULT_INTEGRATION_TEST_MODEL


@pytest.fixture
def compare_models():
    """Get models to use for compare/debate tests."""
    return DEFAULT_COMPARE_MODELS.copy()


@pytest.fixture
def debate_models():
    """Get models to use for debate tests."""
    return DEFAULT_DEBATE_MODELS.copy()


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Provide mock environment variables for testing."""
    test_vars = {
        "OPENAI_API_KEY": "sk-test-key-12345",
        "DEFAULT_MODEL": "gpt-5-mini",
        "LOG_LEVEL": "INFO",
    }
    for key, value in test_vars.items():
        monkeypatch.setenv(key, value)
    return test_vars


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (>5s)")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location."""
    for item in items:
        # Auto-mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        # Auto-mark unit tests
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)


# ============================================================================
# CLI Test Fixtures
# ============================================================================


@pytest.fixture
def has_gemini_cli():
    """Check if Gemini CLI is available."""
    return shutil.which("gemini") is not None


@pytest.fixture
def has_codex_cli():
    """Check if Codex CLI is available."""
    return shutil.which("codex") is not None


@pytest.fixture
def has_claude_cli():
    """Check if Claude CLI is available."""
    return shutil.which("claude") is not None


@pytest.fixture
def skip_if_no_gemini_cli():
    """Skip test if Gemini CLI not available."""
    if not shutil.which("gemini"):
        pytest.skip("Gemini CLI not installed - install via: npm install -g @google/generative-ai-cli")


@pytest.fixture
def skip_if_no_codex_cli():
    """Skip test if Codex CLI not available."""
    if not shutil.which("codex"):
        pytest.skip("Codex CLI not installed - install via: npm install -g @anthropic-ai/codex-cli")


@pytest.fixture
def skip_if_no_claude_cli():
    """Skip test if Claude CLI not available."""
    if not shutil.which("claude"):
        pytest.skip("Claude CLI not installed - install via: pip install anthropic-cli")


@pytest.fixture
def skip_if_no_any_cli(has_gemini_cli, has_codex_cli, has_claude_cli):
    """Skip test if no CLI is available."""
    if not (has_gemini_cli or has_codex_cli or has_claude_cli):
        pytest.skip("No CLI models available - install at least one CLI tool")


# ============================================================================
# Dynamic CLI Fixtures (New Pattern - Testing Strategy V2)
# ============================================================================

CLI_TOOLS = {
    "gemini": {
        "install": "npm install -g @google/generative-ai-cli",
        "check": "gemini",
    },
    "codex": {
        "install": "npm install -g @anthropic-ai/codex-cli",
        "check": "codex",
    },
    "claude": {
        "install": "pip install anthropic-cli",
        "check": "claude",
    },
}


@pytest.fixture
def require_cli():
    """Dynamic CLI requirement checker.

    Usage:
        async def test_something(require_cli):
            require_cli("gemini")
            # Test runs only if gemini CLI is installed

    Example:
        def test_gemini_execution(require_cli):
            require_cli("gemini")
            # ... test code
    """

    def _check(cli_name: str):
        if cli_name not in CLI_TOOLS:
            raise ValueError(f"Unknown CLI: {cli_name}. Known CLIs: {list(CLI_TOOLS.keys())}")

        if not shutil.which(CLI_TOOLS[cli_name]["check"]):
            install_hint = CLI_TOOLS[cli_name]["install"]
            pytest.skip(f"{cli_name} CLI not installed - install via: {install_hint}")

    return _check


@pytest.fixture
def available_clis():
    """Return list of installed CLIs.

    Usage:
        async def test_multi_cli(available_clis):
            if len(available_clis) < 2:
                pytest.skip("Need at least 2 CLIs")
            # Use available_clis[0], available_clis[1], etc.

    Example:
        def test_compare_clis(available_clis):
            assert len(available_clis) >= 2, "Need 2+ CLIs"
            # ... test with available_clis[0] and available_clis[1]
    """
    return [name for name in CLI_TOOLS.keys() if shutil.which(CLI_TOOLS[name]["check"])]


# ============================================================================
# Mock Helper Fixtures (Reduce Boilerplate - Testing Strategy V2)
# ============================================================================


@pytest.fixture
def mock_cli_success(mocker):
    """Mock successful CLI subprocess execution.

    Reduces 17 lines of mock setup to 1 line.

    Usage:
        def test_something(mock_cli_success):
            mock_cli_success(stdout=b'{"response": "ok"}')
            # Test code...

    Args:
        stdout: Bytes to return as stdout (default: b"")
        stderr: Bytes to return as stderr (default: b"")
        returncode: Exit code to return (default: 0)
        cli_path: Path to CLI binary (default: "/usr/bin/cli")

    Returns:
        Tuple of (mock_subprocess_exec, mock_process)

    Example:
        def test_gemini_success(mock_cli_success):
            mock_exec, mock_process = mock_cli_success(
                stdout=b'{"response": "Hello"}',
                returncode=0
            )

            client = LiteLLMClient()
            result = await client.call_async(...)

            assert result.status == "success"
            mock_exec.assert_called_once()
    """

    def _setup(stdout=b"", stderr=b"", returncode=0, cli_path="/usr/bin/cli"):
        # Mock subprocess execution
        mock_exec = mocker.patch("multi_mcp.models.litellm_client.asyncio.create_subprocess_exec")

        # Mock which() to indicate CLI is installed
        mocker.patch("multi_mcp.models.litellm_client.shutil.which", return_value=cli_path)

        # Create mock process
        mock_process = mocker.Mock()
        mock_process.communicate = mocker.AsyncMock(return_value=(stdout, stderr))
        mock_process.returncode = returncode
        mock_exec.return_value = mock_process

        return mock_exec, mock_process

    return _setup


@pytest.fixture
def mock_cli_failure(mocker):
    """Mock failed CLI subprocess execution.

    Usage:
        def test_something(mock_cli_failure):
            mock_cli_failure("not_found")
            # Test code expecting CLI not found error

    Args:
        error_type: Type of failure ("not_found", "timeout", "exit_code")
        stderr: Error message to return (default: b"Command failed")
        exit_code: Non-zero exit code for "exit_code" type (default: 1)

    Returns:
        Tuple of (mock_subprocess_exec, mock_process) or (None, None) for "not_found"

    Example:
        def test_cli_not_found(mock_cli_failure):
            mock_exec, _ = mock_cli_failure("not_found")

            client = LiteLLMClient()
            result = await client.call_async(...)

            assert result.status == "error"
            assert "not found" in result.error.lower()
    """

    def _setup(error_type="not_found", stderr=b"Command failed", exit_code=1):
        if error_type == "not_found":
            # CLI not installed
            mocker.patch("multi_mcp.models.litellm_client.shutil.which", return_value=None)
            return None, None

        elif error_type == "timeout":
            # CLI execution times out
            mock_exec = mocker.patch("multi_mcp.models.litellm_client.asyncio.create_subprocess_exec")
            mocker.patch("multi_mcp.models.litellm_client.shutil.which", return_value="/usr/bin/cli")

            mock_process = mocker.Mock()
            mock_process.communicate = mocker.AsyncMock(side_effect=TimeoutError())
            mock_exec.return_value = mock_process
            return mock_exec, mock_process

        elif error_type == "exit_code":
            # CLI returns non-zero exit code
            mock_exec = mocker.patch("multi_mcp.models.litellm_client.asyncio.create_subprocess_exec")
            mocker.patch("multi_mcp.models.litellm_client.shutil.which", return_value="/usr/bin/cli")

            mock_process = mocker.Mock()
            mock_process.communicate = mocker.AsyncMock(return_value=(b"", stderr))
            mock_process.returncode = exit_code
            mock_exec.return_value = mock_process
            return mock_exec, mock_process

        else:
            raise ValueError(f"Unknown error_type: {error_type}")

    return _setup


# ============================================================================
# VCR Configuration (Record/Replay Pattern - Testing Strategy V2)
# ============================================================================


def filter_query_parameters(response):
    """Remove API keys from query parameters in request URIs.

    VCR's filter_headers only filters HTTP headers, not query parameters.
    This callback filters sensitive query parameters like ?key=API_KEY.

    Args:
        response: VCR interaction dict

    Returns:
        Modified interaction with filtered query parameters
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    # VCR passes interaction dict with 'request' and 'response' keys
    if not isinstance(response, dict) or "request" not in response:
        return response

    request = response["request"]
    if not isinstance(request, dict) or "uri" not in request:
        return response

    uri = request["uri"]

    # Parse URL
    parsed = urlparse(uri)

    # Parse query string
    params = parse_qs(parsed.query)

    # Remove sensitive parameters
    sensitive_params = ["key", "api_key", "apikey", "token", "access_token", "auth", "refresh_token"]
    for param in sensitive_params:
        if param in params:
            params[param] = ["***REDACTED***"]

    # Rebuild URL with filtered parameters
    new_query = urlencode(params, doseq=True)
    new_parsed = parsed._replace(query=new_query)

    # Modify the request URI in place
    response["request"]["uri"] = urlunparse(new_parsed)

    return response


@pytest.fixture(scope="module")
def vcr_config():
    """VCR configuration for recording API interactions.

    This fixture configures pytest-recording to:
    - Filter out sensitive headers (API keys, auth tokens)
    - Filter out sensitive query parameters (e.g., ?key=API_KEY)
    - Record cassettes once and replay on subsequent runs
    - Store cassettes in tests/cassettes/ directory
    - Match requests by URI, method, and body

    Usage:
        @pytest.mark.vcr  # Uses default config
        async def test_something():
            # Real API call is recorded on first run
            # Replayed from cassette on subsequent runs

    Record modes:
        - "once": Record once, replay thereafter (default)
        - "new_episodes": Record new, replay existing
        - "all": Always record (overwrites cassettes)
        - "none": Never record (always replay)

    To re-record cassettes:
        rm -rf tests/cassettes && RUN_E2E=1 pytest tests/integration/
    """
    return {
        # Security: Filter sensitive headers
        "filter_headers": [
            "authorization",
            "api-key",
            "x-api-key",
            "openai-api-key",
            "anthropic-api-key",
            "google-api-key",
        ],
        # Security: Filter sensitive query parameters (e.g., ?key=API_KEY)
        # Use filter_query_parameters for both request and response URIs
        "before_record_response": filter_query_parameters,
        "filter_query_parameters": ["key", "api_key", "apikey", "token", "access_token", "auth"],
        # Record mode: "once" means record on first run, replay thereafter
        "record_mode": "once",
        # Cassette storage location
        "cassette_library_dir": "tests/cassettes",
        # Match requests by URI, method, and body
        "match_on": ["uri", "method", "body"],
        # Decode compressed responses for readability
        "decode_compressed_response": True,
        # Ignore localhost (for local server tests)
        "ignore_localhost": True,
    }


@pytest.fixture
def vcr_cassette_name(request):
    """Generate unique cassette name from test module and function name.

    Generates cassette filenames like:
        test_e2e_codereview__test_basic_codereview.yaml
        test_e2e_chat__test_chat_with_repository_context.yaml

    This ensures each test gets its own cassette file for isolation.

    Usage:
        Automatic - pytest-recording uses this fixture by default
    """
    # Extract module name (e.g., "test_e2e_codereview")
    module = request.node.module.__name__.split(".")[-1]

    # Extract test function name (e.g., "test_basic_codereview")
    name = request.node.name

    # Return cassette name (e.g., "test_e2e_codereview__test_basic_codereview")
    return f"{module}__{name}"
