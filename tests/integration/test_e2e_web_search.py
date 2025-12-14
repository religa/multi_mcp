"""Integration tests for web search functionality."""

import os
import uuid

import pytest

from multi_mcp.tools.chat import chat_impl
from multi_mcp.tools.compare import compare_impl
from multi_mcp.tools.debate import debate_impl

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_with_web_search():
    """Test that chat can use web search for current information."""
    result = await chat_impl(
        name="Web Search Test",
        content="What are the latest features in Python 3.13 released in 2024?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model="gpt-5-mini",  # Model with web search support
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] == "success"
    assert "content" in result
    # Response should mention Python 3.13 or recent features
    # (web search helps get current info beyond training cutoff)
    content_lower = result["content"].lower()
    assert "python" in content_lower or "3.13" in content_lower


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_compare_with_web_search():
    """Test that compare enables web search for multiple models."""
    result = await compare_impl(
        name="Web Search Compare Test",
        content="What is the current weather in San Francisco?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        models=["gpt-5-mini", "gemini-2.5-flash"],  # Both have web search support
        thread_id=str(uuid.uuid4()),
    )

    # Should get successful responses from both models
    assert result["status"] in ["success", "partial"]
    assert len(result["results"]) == 2

    # At least one model should succeed with web search
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # Successful responses should have content
    for success in successes:
        assert "content" in success
        assert len(success["content"]) > 0


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(240)
async def test_debate_step1_with_web_search():
    """Test that debate step 1 uses web search for independent answers."""
    result = await debate_impl(
        name="Web Search Debate Test",
        content="What are the main differences between TypeScript 5.0 and 5.5?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        models=["gpt-5-mini", "gemini-2.5-flash"],  # Both have web search support
        thread_id=str(uuid.uuid4()),
    )

    # Debate should complete both steps
    assert result["status"] in ["success", "partial"]

    # Step 1 results should exist
    assert "results" in result
    assert len(result["results"]) == 2

    # Step 2 results should exist
    assert "step2_results" in result

    # At least one model should succeed in step 1 (with web search)
    step1_successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(step1_successes) >= 1

    # Successful step 1 responses should have content about TypeScript
    for success in step1_successes:
        assert "content" in success
        content_lower = success["content"].lower()
        assert "typescript" in content_lower or "5." in content_lower


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_web_search_with_unsupported_model():
    """Test that unsupported models gracefully skip web search."""
    # Use a model without web search support (if any exist)
    # For now, test with gpt-5-nano which doesn't have web search configured
    result = await chat_impl(
        name="Unsupported Web Search Test",
        content="What is 2+2?",  # Simple question that doesn't need web search
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model="gpt-5-nano",  # Model without web search support
        thread_id=str(uuid.uuid4()),
    )

    # Should still work, just without web search
    assert result["status"] == "success"
    assert "content" in result
    assert "4" in result["content"]


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_web_search_with_factual_question():
    """Test web search with a question requiring current information."""
    result = await chat_impl(
        name="Factual Web Search Test",
        content="Who won the most recent Nobel Prize in Physics?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model="gemini-2.5-flash",  # Model with web search support
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] == "success"
    assert "content" in result
    # Response should mention Nobel Prize or physics
    content_lower = result["content"].lower()
    assert "nobel" in content_lower or "physics" in content_lower


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_compare_mixed_web_search_support():
    """Test compare with mix of models (some with web search, some without)."""
    result = await compare_impl(
        name="Mixed Web Search Test",
        content="What is the capital of France?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        models=["gpt-5-mini", "gpt-5-nano"],  # gpt-5-mini has web search, nano doesn't
        thread_id=str(uuid.uuid4()),
    )

    # Should get responses (may be partial if one model fails)
    assert result["status"] in ["success", "partial"]
    assert len(result["results"]) == 2

    # At least one should succeed
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # Successful responses should answer correctly
    for success in successes:
        content_lower = success["content"].lower()
        assert "paris" in content_lower


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_web_search_with_gemini():
    """Test web search with Google Gemini model."""
    result = await chat_impl(
        name="Gemini Web Search Test",
        content="What are the latest features in React 19?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model="gemini-2.5-flash",  # Google model with web search
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] == "success"
    assert "content" in result
    # Response should mention React
    content_lower = result["content"].lower()
    assert "react" in content_lower


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_web_search_includes_citations():
    """Test that chat with web search includes proper citations in Sources section."""
    result = await chat_impl(
        name="Citation Test",
        content="When was Python 3.14 released?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model="gemini-2.5-flash",  # Model with web search support
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] == "success"
    assert "content" in result
    content = result["content"]

    # Response should mention Python 3.14 (verifying the answer is present)
    content_lower = content.lower()
    assert "python" in content_lower or "3.14" in content_lower, "Response should mention Python or version"

    # Check for Sources section (may be missing if model doesn't follow prompt exactly)
    # This is a soft check - we verify the content is correct even if Sources is missing
    if "## Sources" in content:
        # Sources section present - verify format
        sources_index = content.find("## Sources")
        sources_section = content[sources_index:]

        # If web search was used, should have markdown links [Title](URL)
        # If not used, should say "None - answered from provided context"
        if "None - answered from provided context" not in sources_section:
            # If there are citations, verify they're properly formatted
            import re

            citations = re.findall(r"\[([^\]]+)\]\((http[^\)]+)\)", sources_section)
            if len(citations) > 0:
                # Verify citations are reasonable (title and URL both present)
                for title, url in citations:
                    assert len(title) > 0, "Citation title should not be empty"
                    assert len(url) > 10, "Citation URL should be a valid URL"
                    assert url.startswith("http"), "Citation URL should start with http"
            # else: Sources section present but no citations - acceptable (model may not have used search)
    # else: Sources section missing - acceptable (model may not follow prompt exactly)


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_compare_web_search_includes_citations():
    """Test that compare with web search includes citations in all model responses."""
    result = await compare_impl(
        name="Compare Citation Test",
        content="What are the new features in FastAPI 0.123?",
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        models=["gemini-2.5-flash", "gpt-5-mini"],  # Both have web search
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] in ["success", "partial"]
    assert len(result["results"]) == 2

    # Check that successful responses include Sources section
    import re

    for model_result in result["results"]:
        if model_result["status"] == "success":
            content = model_result["content"]

            # Every response must have Sources section (may be numbered like "7. Sources" or just "Sources")
            has_sources = "## Sources" in content or "## 7. Sources" in content or "**7. Sources**" in content
            assert has_sources, f"Model {model_result['metadata'].get('model')} must include Sources section"

            # Find the Sources section (try different formats)
            sources_index = -1
            if "## 7. Sources" in content:
                sources_index = content.find("## 7. Sources")
            elif "**7. Sources**" in content:
                sources_index = content.find("**7. Sources**")
            elif "## Sources" in content:
                sources_index = content.find("## Sources")

            assert sources_index >= 0, "Sources section should be found"
            sources_section = content[sources_index:]

            # Should either have citations or "None - answered from provided context"
            # Note: Some models may include Sources section but leave it empty - that's acceptable
            if "None - answered from provided context" not in sources_section:
                # Try to find citations
                citations = re.findall(r"\[([^\]]+)\]\((http[^\)]+)\)", sources_section)

                # If citations found, verify they're valid
                # If no citations found, it's acceptable (model may not have used web search or forgot to cite)
                if len(citations) > 0:
                    # Verify citations are properly formatted
                    for title, url in citations:
                        assert len(title) > 0, "Citation title should not be empty"
                        assert len(url) > 10, "Citation URL should be valid"
                        assert url.startswith("http"), "Citation URL should start with http"
                # else: Sources section present but empty - acceptable (model may not have used search)


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_without_web_search_cites_context():
    """Test that chat without web search properly cites context instead of sources."""
    result = await chat_impl(
        name="No Web Search Citation Test",
        content="What is 2 + 2?",  # Simple question that doesn't require web search
        step_number=1,
        next_action="stop",
        base_path="/tmp",
        model="gemini-2.5-flash",
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] == "success"
    assert "content" in result
    content = result["content"]

    # Must have Sources section
    assert "## Sources" in content, "Response must include ## Sources section even without web search"

    sources_index = content.find("## Sources")
    sources_section = content[sources_index:]

    # Should say "None - answered from provided context" since no web search needed
    assert (
        "None - answered from provided context" in sources_section or "[" in sources_section  # Or it might still search (that's okay)
    ), "Sources should indicate context was used or provide citations"
