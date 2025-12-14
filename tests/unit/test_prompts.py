"""Unit tests for prompt building functions (stateless)."""

from multi_mcp.utils.prompts import build_expert_context, build_issues_section


class TestBuildIssuesSection:
    """Tests for build_issues_section function."""

    def test_empty_issues(self):
        """Test with no issues."""
        result = build_issues_section([])

        assert "<ISSUES_IDENTIFIED>" in result
        assert "No issues identified yet" in result
        assert "</ISSUES_IDENTIFIED>" in result

    def test_single_issue(self):
        """Test with single issue."""
        issues = [
            {
                "severity": "critical",
                "file": "src/auth.py",
                "line": "45",
                "description": "SQL Injection vulnerability",
            }
        ]

        result = build_issues_section(issues)

        assert "<ISSUES_IDENTIFIED>" in result
        assert '<issue severity="critical" file="src/auth.py" line="45">' in result
        assert "SQL Injection vulnerability" in result
        assert "</issue>" in result
        assert "</ISSUES_IDENTIFIED>" in result

    def test_multiple_issues_different_severities(self):
        """Test with multiple issues of different severities."""
        issues = [
            {
                "severity": "critical",
                "file": "src/auth.py",
                "line": "45",
                "description": "SQL Injection",
            },
            {
                "severity": "high",
                "file": "src/utils.py",
                "line": "23",
                "description": "Weak password hashing",
            },
            {
                "severity": "medium",
                "file": "src/api.py",
                "line": "100",
                "description": "Missing input validation",
            },
        ]

        result = build_issues_section(issues)

        assert "SQL Injection" in result
        assert "Weak password hashing" in result
        assert "Missing input validation" in result
        assert 'severity="critical"' in result
        assert 'severity="high"' in result
        assert 'severity="medium"' in result


class TestBuildExpertContext:
    """Tests for build_expert_context function (stateless)."""

    def test_minimal_context(self):
        """Test with minimal required data."""
        result = build_expert_context(
            content="Checking basic security",
            issues_found=[],
        )

        # Check for required sections
        assert "<CODE_REVIEW_REQUEST>" in result
        assert "Checking basic security" in result
        assert "<ISSUES_IDENTIFIED>" in result
        assert "<TASK>" in result

    def test_with_issues(self):
        """Test with issues populated."""
        issues = [
            {
                "severity": "critical",
                "file": "src/auth.py",
                "line": "45",
                "description": "SQL Injection",
            }
        ]

        result = build_expert_context(
            content="Completing the review",
            issues_found=issues,
        )

        # Check all sections present
        assert "<CODE_REVIEW_REQUEST>" in result
        assert "<ISSUES_IDENTIFIED>" in result
        assert "<TASK>" in result

        # Check content
        assert "Completing the review" in result
        assert "SQL Injection" in result

    def test_section_ordering(self):
        """Test that sections appear in correct order."""
        result = build_expert_context(
            content="Test",
            issues_found=[{"severity": "low", "file": "test.py", "line": "1", "description": "test"}],
        )

        # Find positions of each section
        request_pos = result.find("<CODE_REVIEW_REQUEST>")
        issues_pos = result.find("<ISSUES_IDENTIFIED>")
        task_pos = result.find("<TASK>")

        # Verify ordering
        assert request_pos < issues_pos
        assert issues_pos < task_pos
