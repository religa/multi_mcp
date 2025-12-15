"""Unit tests for multi-model consolidation."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from multi_mcp.schemas.codereview import CodeReviewModelResult
from multi_mcp.utils.consolidation import (
    _build_consolidation_messages,
    _extract_issues_from_content,
    consolidate_model_results,
)


class TestConsolidateModelResults:
    """Test consolidate_model_results function."""

    @pytest.mark.asyncio
    async def test_consolidate_multiple_models(self):
        """Consolidate 3 model results into 1."""
        mock_response = Mock(
            status="success",
            content='{"status": "success", "message": "Consolidated analysis of code quality", "issues_found": [{"severity": "high", "location": "auth.py:45", "description": "SQL injection vulnerability", "found_by": ["gpt-5-mini", "claude-sonnet-4.5"]}]}',
            error=None,
            metadata=Mock(
                total_tokens=500,
                prompt_tokens=400,
                completion_tokens=100,
                latency_ms=2000,
                artifacts=None,
            ),
        )

        with patch("multi_mcp.utils.consolidation.execute_single", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_response

            results = [
                Mock(
                    status="success",
                    content='{"status": "review_complete", "issues_found": [{"severity": "high", "location": "test.py:1"}]}',
                    metadata=Mock(
                        model="gpt-5-mini",
                        total_tokens=1000,
                        prompt_tokens=800,
                        completion_tokens=200,
                        latency_ms=5000,
                    ),
                ),
                Mock(
                    status="success",
                    content='{"status": "review_complete", "issues_found": [{"severity": "high", "location": "test.py:1"}]}',
                    metadata=Mock(
                        model="claude-sonnet-4.5",
                        total_tokens=1200,
                        prompt_tokens=900,
                        completion_tokens=300,
                        latency_ms=8000,
                    ),
                ),
                Mock(
                    status="success",
                    content='{"status": "review_complete", "issues_found": []}',
                    metadata=Mock(
                        model="gemini-3-pro-preview",
                        total_tokens=1100,
                        prompt_tokens=850,
                        completion_tokens=250,
                        latency_ms=6000,
                    ),
                ),
            ]

            consolidated = await consolidate_model_results(results)

            # Verify it's a typed CodeReviewModelResult
            assert isinstance(consolidated, CodeReviewModelResult)
            assert consolidated.status == "success"

            # Verify model names are comma-separated
            assert consolidated.metadata.model == "gpt-5-mini, claude-sonnet-4.5, gemini-3-pro-preview"

            # Verify content is consolidated
            assert "Consolidated analysis" in consolidated.content

            # Verify issues are deduplicated
            assert len(consolidated.issues_found) == 1
            assert consolidated.issues_found[0]["found_by"] == ["gpt-5-mini", "claude-sonnet-4.5"]

            # Verify metadata consolidation fields
            assert consolidated.metadata.source_models == [
                "gpt-5-mini",
                "claude-sonnet-4.5",
                "gemini-3-pro-preview",
            ]

            # Verify token aggregation (sum of all tokens including consolidation)
            assert consolidated.metadata.total_tokens == 3800  # 1000 + 1200 + 1100 + 500
            assert consolidated.metadata.prompt_tokens == 2950  # 800 + 900 + 850 + 400
            assert consolidated.metadata.completion_tokens == 850  # 200 + 300 + 250 + 100

            # Verify latency calculation (max of sources + consolidation)
            # max(5000, 8000, 6000) + 2000 = 8000 + 2000 = 10000
            assert consolidated.metadata.latency_ms == 10000

            # Consolidation model should be the default model from settings
            from multi_mcp.settings import settings

            assert consolidated.metadata.consolidation_model == settings.default_model

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        """All models fail - return error summary."""
        results = [
            Mock(status="error", metadata=Mock(model="gpt-5-mini")),
            Mock(status="error", metadata=Mock(model="claude-sonnet-4.5")),
        ]

        consolidated = await consolidate_model_results(results)

        # Verify it's a typed CodeReviewModelResult
        assert isinstance(consolidated, CodeReviewModelResult)
        assert consolidated.status == "error"
        assert consolidated.metadata.model == "gpt-5-mini, claude-sonnet-4.5"
        assert "failed" in consolidated.content.lower()
        assert consolidated.issues_found == []
        assert consolidated.error == "All models failed"

    @pytest.mark.asyncio
    async def test_consolidation_failure_fallback(self):
        """On consolidation failure, return first successful result."""
        with patch("multi_mcp.models.litellm_client.LiteLLMClient.execute", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("API timeout")

            results = [
                Mock(
                    status="success",
                    content='{"status": "success", "issues_found": [{"severity": "low", "location": "test.py:1", "description": "Minor issue"}]}',
                    metadata=Mock(
                        model="gpt-5-mini",
                        total_tokens=500,
                        prompt_tokens=400,
                        completion_tokens=100,
                        latency_ms=2000,
                        artifacts=None,
                    ),
                ),
            ]

            consolidated = await consolidate_model_results(results)

            # Should fallback to first result
            assert isinstance(consolidated, CodeReviewModelResult)
            assert consolidated.metadata.model == "gpt-5-mini"
            assert consolidated.status == "success"
            assert len(consolidated.issues_found) == 1

    @pytest.mark.asyncio
    async def test_partial_success(self):
        """Some models succeed, some fail - consolidate successful ones."""
        mock_response = Mock(
            status="success",
            content='{"status": "success", "message": "Analysis from successful models", "issues_found": []}',
            error=None,
            metadata=Mock(
                total_tokens=300,
                prompt_tokens=200,
                completion_tokens=100,
                latency_ms=1000,
                artifacts=None,
            ),
        )

        with patch("multi_mcp.utils.consolidation.execute_single", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_response

            results = [
                Mock(
                    status="success",
                    content='{"status": "review_complete"}',
                    metadata=Mock(
                        model="gpt-5-mini",
                        total_tokens=1000,
                        prompt_tokens=800,
                        completion_tokens=200,
                        latency_ms=3000,
                    ),
                ),
                Mock(status="error", metadata=Mock(model="claude-sonnet-4.5")),
            ]

            consolidated = await consolidate_model_results(results)

            # Only successful model in result
            assert isinstance(consolidated, CodeReviewModelResult)
            assert consolidated.metadata.model == "gpt-5-mini"
            assert consolidated.metadata.source_models == ["gpt-5-mini"]

    @pytest.mark.asyncio
    async def test_invalid_json_response_fallback(self):
        """LLM returns invalid JSON - fallback to first result."""
        mock_response = Mock(
            status="success",
            content="This is not JSON",
            error=None,
            metadata=Mock(
                total_tokens=100,
                prompt_tokens=50,
                completion_tokens=50,
                latency_ms=500,
                artifacts=None,
            ),
        )

        with patch("multi_mcp.utils.consolidation.execute_single", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_response

            results = [
                Mock(
                    status="success",
                    content='{"status": "success", "issues_found": []}',
                    metadata=Mock(
                        model="gpt-5-mini",
                        total_tokens=500,
                        prompt_tokens=400,
                        completion_tokens=100,
                        latency_ms=2000,
                    ),
                ),
            ]

            # Should fallback due to parse error
            consolidated = await consolidate_model_results(results)

            assert isinstance(consolidated, CodeReviewModelResult)
            assert consolidated.metadata.model == "gpt-5-mini"
            assert consolidated.status == "success"

    @pytest.mark.asyncio
    async def test_non_dict_response_fallback(self):
        """LLM returns non-dict JSON - fallback to first result."""
        mock_response = Mock(
            status="success",
            content='["array", "not", "dict"]',
            error=None,
            metadata=Mock(
                total_tokens=100,
                prompt_tokens=50,
                completion_tokens=50,
                latency_ms=500,
                artifacts=None,
            ),
        )

        with patch("multi_mcp.utils.consolidation.execute_single", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_response

            results = [
                Mock(
                    status="success",
                    content='{"status": "success", "issues_found": []}',
                    metadata=Mock(
                        model="gpt-5-mini",
                        total_tokens=500,
                        prompt_tokens=400,
                        completion_tokens=100,
                        latency_ms=2000,
                    ),
                ),
            ]

            consolidated = await consolidate_model_results(results)

            # Should fallback
            assert isinstance(consolidated, CodeReviewModelResult)
            assert consolidated.metadata.model == "gpt-5-mini"
            assert consolidated.status == "success"


class TestBuildConsolidationMessages:
    """Test _build_consolidation_messages function."""

    def test_messages_contains_model_data(self):
        """Messages array includes all model responses in user message."""
        results = [
            Mock(
                metadata=Mock(model="gpt-5-mini"),
                content="Analysis from GPT",
            ),
            Mock(
                metadata=Mock(model="claude-sonnet-4.5"),
                content="Analysis from Claude",
            ),
        ]

        messages = _build_consolidation_messages(results)

        # Should return array of messages
        assert isinstance(messages, list)
        assert len(messages) == 2

        # First message should be system prompt
        assert messages[0]["role"] == "system"
        assert "consolidation" in messages[0]["content"].lower()

        # Second message should be user message with model data
        assert messages[1]["role"] == "user"
        user_content = messages[1]["content"]
        assert "gpt-5-mini" in user_content
        assert "claude-sonnet-4.5" in user_content
        assert "Analysis from GPT" in user_content
        assert "Analysis from Claude" in user_content

    def test_messages_structure(self):
        """Messages have correct structure with system and user roles."""
        results = [
            Mock(metadata=Mock(model="gpt-5-mini"), content="Test content"),
        ]

        messages = _build_consolidation_messages(results)

        # Check messages structure
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "<MODEL_RESPONSES>" in messages[1]["content"]
        assert '<MODEL name="gpt-5-mini">' in messages[1]["content"]
        assert "</MODEL>" in messages[1]["content"]


class TestExtractIssuesFromContent:
    """Test _extract_issues_from_content fallback function."""

    def test_extract_from_valid_json(self):
        """Extract issues from valid JSON content."""
        content = '{"status": "review_complete", "issues_found": [{"severity": "high", "location": "test.py:1", "description": "Issue"}]}'

        issues = _extract_issues_from_content(content)

        assert len(issues) == 1
        assert issues[0]["severity"] == "high"

    def test_extract_from_invalid_json(self):
        """Return empty list for invalid JSON."""
        content = "Not valid JSON"

        issues = _extract_issues_from_content(content)

        assert issues == []

    def test_extract_from_json_without_issues(self):
        """Return empty list when no issues_found field."""
        content = '{"status": "success", "other_field": "value"}'

        issues = _extract_issues_from_content(content)

        assert issues == []

    def test_extract_from_non_dict_json(self):
        """Return empty list for non-dict JSON."""
        content = '["array", "content"]'

        issues = _extract_issues_from_content(content)

        assert issues == []


class TestInvalidJsonFiltering:
    """Test filtering of invalid JSON responses during consolidation."""

    @pytest.mark.asyncio
    async def test_filter_invalid_json_before_consolidation(self, caplog):
        """Test that invalid JSON responses are filtered out before consolidation."""
        mock_consolidation = Mock(
            status="success",
            content='{"status": "success", "message": "Consolidated", "issues_found": [{"severity": "high", "location": "test.py:1", "description": "Issue"}]}',
            error=None,
            metadata=Mock(
                total_tokens=100,
                prompt_tokens=50,
                completion_tokens=50,
                latency_ms=500,
                artifacts=None,
            ),
        )

        with patch("multi_mcp.utils.consolidation.execute_single", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_consolidation

            # Mix of valid and invalid JSON
            results = [
                Mock(
                    status="success",
                    content='{"status": "success", "issues_found": [{"severity": "high", "location": "test.py:1"}]}',
                    metadata=Mock(
                        model="gpt-5-mini",
                        total_tokens=500,
                        prompt_tokens=400,
                        completion_tokens=100,
                        latency_ms=2000,
                    ),
                ),
                Mock(
                    status="success",
                    content="This is not valid JSON at all!",  # Invalid JSON
                    metadata=Mock(
                        model="claude-sonnet-4.5",
                        total_tokens=600,
                        prompt_tokens=500,
                        completion_tokens=100,
                        latency_ms=3000,
                    ),
                ),
                Mock(
                    status="success",
                    content='{"status": "success", "issues_found": [{"severity": "medium", "location": "test.py:5"}]}',
                    metadata=Mock(
                        model="gemini-2.5-flash",
                        total_tokens=550,
                        prompt_tokens=450,
                        completion_tokens=100,
                        latency_ms=2500,
                    ),
                ),
            ]

            consolidated = await consolidate_model_results(results)

            # Check that warning was logged for invalid JSON
            assert any(
                "Filtering out claude-sonnet-4.5" in record.message and "invalid JSON" in record.message
                for record in caplog.records
                if record.levelname == "WARNING"
            )

            # Check that only valid models are in source_models
            assert consolidated.metadata.source_models == ["gpt-5-mini", "gemini-2.5-flash"]
            assert "claude-sonnet-4.5" not in consolidated.metadata.model

            # Check that tokens only count valid results
            # gpt-5-mini (500) + gemini (550) + consolidation (100) = 1150
            assert consolidated.metadata.total_tokens == 1150

    @pytest.mark.asyncio
    async def test_all_invalid_json_returns_error(self):
        """Test that all invalid JSON responses returns error."""
        results = [
            Mock(
                status="success",
                content="Not JSON",
                metadata=Mock(model="model1"),
            ),
            Mock(
                status="success",
                content="Also not JSON",
                metadata=Mock(model="model2"),
            ),
        ]

        consolidated = await consolidate_model_results(results)

        # Should return error
        assert isinstance(consolidated, CodeReviewModelResult)
        assert consolidated.status == "error"
        assert "unparseable JSON" in consolidated.content
        assert consolidated.error == "All models returned invalid JSON"
        assert consolidated.issues_found == []

    @pytest.mark.asyncio
    async def test_single_valid_among_invalid(self):
        """Test that single valid result among invalid ones is used."""
        mock_response = Mock(
            status="success",
            content='{"status": "success", "message": "One model worked", "issues_found": []}',
            error=None,
            metadata=Mock(
                total_tokens=100,
                prompt_tokens=50,
                completion_tokens=50,
                latency_ms=500,
                artifacts=None,
            ),
        )

        with patch("multi_mcp.utils.consolidation.execute_single", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_response

            results = [
                Mock(
                    status="success",
                    content='{"status": "success", "issues_found": []}',
                    metadata=Mock(
                        model="gpt-5-mini",
                        total_tokens=500,
                        prompt_tokens=400,
                        completion_tokens=100,
                        latency_ms=2000,
                    ),
                ),
                Mock(
                    status="success",
                    content="Invalid JSON 1",
                    metadata=Mock(model="model2"),
                ),
                Mock(
                    status="success",
                    content="Invalid JSON 2",
                    metadata=Mock(model="model3"),
                ),
            ]

            consolidated = await consolidate_model_results(results)

            # Should consolidate with just the one valid model
            assert isinstance(consolidated, CodeReviewModelResult)
            assert consolidated.status == "success"
            assert consolidated.metadata.source_models == ["gpt-5-mini"]


class TestSortIssuesByLocation:
    """Test _sort_issues_by_location helper function."""

    def test_sort_issues_by_location(self):
        """Verify issues are sorted alphabetically by location."""
        from multi_mcp.utils.consolidation import _sort_issues_by_location

        unsorted_issues = [
            {"location": "utils.py:50", "severity": "high", "description": "Issue 1"},
            {"location": "auth.py:10", "severity": "critical", "description": "Issue 2"},
            {"location": "utils.py:20", "severity": "medium", "description": "Issue 3"},
            {"location": "auth.py", "severity": "low", "description": "Issue 4"},
            {"location": "db.py:100-105", "severity": "high", "description": "Issue 5"},
        ]

        sorted_issues = _sort_issues_by_location(unsorted_issues)

        # Verify alphabetical order by location field
        assert sorted_issues[0]["location"] == "auth.py"
        assert sorted_issues[1]["location"] == "auth.py:10"
        assert sorted_issues[2]["location"] == "db.py:100-105"
        assert sorted_issues[3]["location"] == "utils.py:20"
        assert sorted_issues[4]["location"] == "utils.py:50"

    def test_sort_issues_by_location_edge_cases(self):
        """Verify sorting handles edge cases gracefully."""
        from multi_mcp.utils.consolidation import _sort_issues_by_location

        edge_cases = [
            {"location": None, "description": "Missing location"},
            {"location": "", "description": "Empty location"},
            {"location": "a.py:10", "description": "First alphabetically"},
            {"location": "z.py:5", "description": "Last alphabetically"},
        ]

        # Should not raise exception
        sorted_issues = _sort_issues_by_location(edge_cases)
        assert len(sorted_issues) == 4

        # Empty string sorts first (empty string < any char)
        assert sorted_issues[0]["location"] == ""
        # Then alphabetical order
        assert sorted_issues[1]["location"] == "a.py:10"
        assert sorted_issues[2]["location"] == "z.py:5"
        # None sorts last (using "~" fallback which comes after most chars)
        assert sorted_issues[3]["location"] is None

    def test_sort_issues_empty_list(self):
        """Verify sorting handles empty list."""
        from multi_mcp.utils.consolidation import _sort_issues_by_location

        assert _sort_issues_by_location([]) == []

    def test_sort_issues_single_item(self):
        """Verify sorting handles single item list."""
        from multi_mcp.utils.consolidation import _sort_issues_by_location

        single_issue = [{"location": "file.py:10", "description": "Single"}]
        assert _sort_issues_by_location(single_issue) == single_issue
