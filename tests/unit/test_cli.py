"""Unit tests for the command-line interface (multi_mcp.cli).

Covers file collection (extension/size/hidden/excluded-dir filtering) and the
main() entry point exit codes and output formatting. run_review is mocked so no
real model calls are made.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from multi_mcp.cli import collect_files, main


class TestCollectFiles:
    """Tests for collect_files() discovery and filtering."""

    def test_collects_supported_files_in_dir(self, tmp_path):
        (tmp_path / "a.py").write_text("print(1)")
        (tmp_path / "b.ts").write_text("const x = 1")
        (tmp_path / "notes.md").write_text("# notes")
        result = collect_files([str(tmp_path)])
        assert {Path(f).name for f in result} == {"a.py", "b.ts", "notes.md"}

    def test_skips_unsupported_extension_in_dir(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        result = collect_files([str(tmp_path)])
        assert all(not f.endswith(".png") for f in result)

    def test_skips_hidden_files_and_excluded_dirs(self, tmp_path):
        (tmp_path / ".hidden.py").write_text("x")
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "dep.py").write_text("x")
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "cfg.py").write_text("x")
        (tmp_path / "keep.py").write_text("x")
        result = collect_files([str(tmp_path)])
        assert {Path(f).name for f in result} == {"keep.py"}

    def test_explicit_file_with_unsupported_ext_skipped(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_text("x")
        assert collect_files([str(f)]) == []

    def test_explicit_hidden_file_skipped(self, tmp_path):
        f = tmp_path / ".secret.py"
        f.write_text("x")
        assert collect_files([str(f)]) == []

    def test_nonexistent_path_ignored(self, tmp_path):
        assert collect_files([str(tmp_path / "nope.py")]) == []

    def test_dedup_and_sorted(self, tmp_path):
        a = tmp_path / "a.py"
        a.write_text("x")
        b = tmp_path / "b.py"
        b.write_text("x")
        result = collect_files([str(a), str(b), str(a)])
        assert result == sorted(set(result))
        assert len(result) == 2

    def test_oversized_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr("multi_mcp.cli.settings.max_file_size_kb", 0)
        big = tmp_path / "big.py"
        big.write_text("print('x')")  # non-empty -> exceeds 0-byte limit
        assert collect_files([str(big)]) == []


class TestMain:
    """Tests for the main() entry point: exit codes and output formatting."""

    @pytest.fixture
    def src_dir(self, tmp_path):
        (tmp_path / "a.py").write_text("print(1)")
        return tmp_path

    def test_no_files_found_returns_1(self, tmp_path, monkeypatch):
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.setattr(sys, "argv", ["multi", str(empty)])
        assert main() == 1

    def test_over_max_files_returns_1(self, src_dir, monkeypatch):
        (src_dir / "b.py").write_text("x")
        monkeypatch.setattr("multi_mcp.cli.settings.max_files_per_review", 1)
        monkeypatch.setattr(sys, "argv", ["multi", str(src_dir)])
        assert main() == 1

    def test_error_status_returns_2(self, src_dir, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["multi", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.return_value = {"status": "error", "summary": "boom"}
            assert main() == 2

    def test_issues_found_text_returns_3(self, src_dir, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["multi", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.return_value = {
                "status": "complete",
                "summary": "Found problems",
                "results": [{"issues_found": [{"severity": "high", "location": "a.py:1", "description": "bad"}]}],
            }
            rc = main()
        out = capsys.readouterr().out
        assert rc == 3
        assert "Found problems" in out
        assert "a.py:1" in out

    def test_no_issues_text_returns_0(self, src_dir, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["multi", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.return_value = {"status": "complete", "summary": "All clean", "results": []}
            rc = main()
        assert rc == 0
        assert "All clean" in capsys.readouterr().out

    def test_top_level_issues_found_branch_returns_3(self, src_dir, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["multi", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.return_value = {
                "status": "complete",
                "summary": "s",
                "issues_found": [{"severity": "critical", "location": "y", "description": "z"}],
            }
            rc = main()
        assert rc == 3
        assert "z" in capsys.readouterr().out

    def test_json_output_with_issues_returns_3(self, src_dir, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["multi", "--json", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.return_value = {
                "status": "complete",
                "summary": "s",
                "results": [{"issues_found": [{"severity": "low", "location": "x", "description": "d"}]}],
            }
            rc = main()
        data = json.loads(capsys.readouterr().out)
        assert rc == 3
        assert data["issues_count"] == 1
        assert data["status"] == "complete"
        assert data["files_reviewed"] == 1

    def test_json_output_no_issues_returns_0(self, src_dir, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["multi", "--json", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.return_value = {"status": "complete", "summary": "s", "results": []}
            rc = main()
        data = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert data["issues_count"] == 0

    def test_json_error_status_returns_2(self, src_dir, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["multi", "--json", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.return_value = {"status": "error", "summary": "bad thing"}
            rc = main()
        data = json.loads(capsys.readouterr().out)
        assert rc == 2
        assert data["status"] == "error"
        assert data["error"] == "bad thing"

    def test_runtime_exception_returns_2(self, src_dir, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["multi", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.side_effect = RuntimeError("kaboom")
            assert main() == 2

    def test_keyboard_interrupt_returns_2(self, src_dir, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["multi", str(src_dir)])
        with patch("multi_mcp.cli.run_review", new_callable=AsyncMock) as mock_rev:
            mock_rev.side_effect = KeyboardInterrupt()
            assert main() == 2
