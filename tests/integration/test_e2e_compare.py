"""Integration tests for compare tool with real API calls."""

import os
import tempfile
import uuid
from pathlib import Path

import pytest

from src.tools.compare import compare_impl

# Skip all tests in this module if RUN_E2E is not set
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E") != "1",
    reason="Integration tests only run with RUN_E2E=1",
)


# ============================================================================
# Basic Functionality Tests
# ============================================================================


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_with_real_files(compare_models):
    """Test compare with actual files and API calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "example.py"
        test_file.write_text("def add(a, b):\n    return a + b")

        result = await compare_impl(
            name="Code Review Test",
            content="Review this function for best practices",
            step_number=1,
            next_action="stop",
            models=compare_models,
            base_path=tmpdir,
            thread_id=str(uuid.uuid4()),
            relevant_files=[str(test_file)],
        )

        # Verify overall success
        assert result["status"] in ["success", "partial"]
        assert len(result["results"]) == 2

        # Verify at least one model succeeded
        successes = [r for r in result["results"] if r["status"] == "success"]
        assert len(successes) >= 1

        # Verify successful models provided content
        for model_result in successes:
            assert len(model_result["content"]) > 0
            assert model_result["metadata"]["total_tokens"] > 0


# ============================================================================
# P0: Output Structure Validation (7-section template)
# ============================================================================


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_output_structure_7_sections(compare_models):
    """P0: Verify responses follow the 7-section markdown template.

    The compare prompt specifies this structure:
    1. Question → 2. Overview → 3. Evidence → 4. Analysis →
    5. Trade-offs → 6. Confidence → 7. Sources
    """
    result = await compare_impl(
        name="Structure Test",
        content="Compare Redis vs Memcached for session caching. Be concise.",
        step_number=1,
        next_action="stop",
        models=compare_models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] in ["success", "partial"]

    # Check successful responses for section structure
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1, "At least one model should succeed"

    # Required sections (flexible matching - headers or inline mentions)
    # Models may use ## headers or inline text
    section_patterns = {
        "question": ["question", "## 1", "**1."],
        "overview": ["overview", "## 2", "**2.", "summary"],
        "evidence": ["evidence", "## 3", "**3."],
        "analysis": ["analysis", "## 4", "**4.", "comparison"],
        "trade-offs": ["trade-off", "tradeoff", "## 5", "**5.", "pros", "cons"],
        "confidence": ["confidence", "## 6", "**6."],
        "sources": ["sources", "## 7", "**7.", "none - "],
    }

    # At least one model should follow the structure (models may have different styles)
    any_model_follows_structure = False
    best_sections_found = 0
    best_model = None

    for model_result in successes:
        content = model_result["content"]
        content_lower = content.lower()

        sections_found = sum(1 for patterns in section_patterns.values() if any(p in content_lower for p in patterns))

        if sections_found > best_sections_found:
            best_sections_found = sections_found
            best_model = model_result["metadata"]["model"]

        # Require at least 5 of 7 sections
        if sections_found >= 5:
            any_model_follows_structure = True

    assert any_model_follows_structure, (
        f"No model followed the 7-section structure. Best was {best_model} with {best_sections_found}/7 sections."
    )


# ============================================================================
# P0: Required Structure Elements
# ============================================================================


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_required_structure_elements(compare_models):
    """P0: Verify responses include recommendation, quantitative data, and confidence.

    The REQUIRED STRUCTURE section specifies:
    1. One-line recommendation with conditional rule
    2. Quantitative comparison table with units
    3. Top 3 assumptions & data sources
    4. PoC checklist + rollback/exit criteria
    5. Confidence (Low/Medium/High) with key risks
    """
    result = await compare_impl(
        name="Required Elements Test",
        content="Compare PostgreSQL vs MySQL for a new e-commerce platform. Be concise but complete.",
        step_number=1,
        next_action="stop",
        models=compare_models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] in ["success", "partial"]

    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # Required markers for structure elements
    recommendation_markers = [
        "choose",
        "recommend",
        "use",
        "prefer",
        "select",
        "go with",
        "suggest",
        "if you need",
        "when",
    ]
    quantitative_markers = [
        "$",
        "ms",
        "latency",
        "throughput",
        "qps",
        "tps",
        "performance",
        "cost",
        "faster",
        "slower",
        "%",
        "gb",
        "mb",
        "connections",
    ]
    confidence_markers = ["confidence", "high", "medium", "low", "certain", "uncertain"]

    # At least one model should have all required elements
    any_model_has_all = False
    best_elements = 0
    best_model = None

    for model_result in successes:
        content = model_result["content"]
        content_lower = content.lower()
        model_name = model_result["metadata"]["model"]

        has_recommendation = any(m in content_lower for m in recommendation_markers)
        has_quantitative = any(m in content_lower for m in quantitative_markers)
        has_confidence = any(m in content_lower for m in confidence_markers)

        elements_found = sum([has_recommendation, has_quantitative, has_confidence])

        if elements_found > best_elements:
            best_elements = elements_found
            best_model = model_name

        if has_recommendation and has_quantitative and has_confidence:
            any_model_has_all = True

    assert any_model_has_all, f"No model had all required structure elements. Best was {best_model} with {best_elements}/3 elements."


# ============================================================================
# P1: Archetype Recognition Tests
# ============================================================================


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_archetype_infrastructure_db(compare_models):
    """P1: Verify Infrastructure/DB archetype produces cost tables and migration discussion."""
    result = await compare_impl(
        name="Infrastructure Archetype Test",
        content="Compare DynamoDB vs PostgreSQL for our user service handling 10k requests/sec.",
        step_number=1,
        next_action="stop",
        models=compare_models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] in ["success", "partial"]
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # Infrastructure archetype should discuss: cost, performance, scalability, migration
    infra_markers = ["cost", "$", "pricing", "performance", "latency", "scale", "migration"]

    # At least one model should cover infrastructure dimensions
    any_model_passes = False
    best_count = 0
    best_model = None

    for model_result in successes:
        content_lower = model_result["content"].lower()
        model_name = model_result["metadata"]["model"]

        markers_found = sum(1 for m in infra_markers if m in content_lower)

        if markers_found > best_count:
            best_count = markers_found
            best_model = model_name

        if markers_found >= 3:
            any_model_passes = True

    assert any_model_passes, f"No model covered infrastructure dimensions adequately. Best was {best_model} with {best_count}/7 markers."


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_archetype_cicd_pipeline(compare_models):
    """P1: Verify CI/CD Pipeline archetype produces feature matrix and cost projections."""
    result = await compare_impl(
        name="CI/CD Archetype Test",
        content="Compare GitHub Actions vs CircleCI for a Python monorepo with 15 developers.",
        step_number=1,
        next_action="stop",
        models=compare_models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] in ["success", "partial"]
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # CI/CD archetype should discuss: build time, cost, parallelization, features
    cicd_markers = [
        "build",
        "pipeline",
        "parallel",
        "cost",
        "minute",
        "runner",
        "cache",
        "workflow",
        "action",
        "orb",
    ]

    # At least one model should cover CI/CD dimensions
    any_model_passes = False
    best_count = 0
    best_model = None

    for model_result in successes:
        content_lower = model_result["content"].lower()
        model_name = model_result["metadata"]["model"]

        markers_found = sum(1 for m in cicd_markers if m in content_lower)

        if markers_found > best_count:
            best_count = markers_found
            best_model = model_name

        if markers_found >= 4:
            any_model_passes = True

    assert any_model_passes, f"No model covered CI/CD dimensions adequately. Best was {best_model} with {best_count}/10 markers."


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_archetype_build_vs_buy(compare_models):
    """P1: Verify Build vs Buy archetype produces TCO analysis and risk assessment."""
    result = await compare_impl(
        name="Build vs Buy Archetype Test",
        content="Should we build our own authentication system or use Auth0 for our B2B SaaS?",
        step_number=1,
        next_action="stop",
        models=compare_models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] in ["success", "partial"]
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # Build vs Buy archetype should discuss: time, cost, maintenance, risk, vendor
    bvb_markers = [
        "build",
        "buy",
        "cost",
        "time",
        "maintenance",
        "risk",
        "vendor",
        "lock-in",
        "auth0",
        "custom",
        "develop",
    ]

    # At least one model should cover Build vs Buy dimensions
    any_model_passes = False
    best_count = 0
    best_model = None

    for model_result in successes:
        content_lower = model_result["content"].lower()
        model_name = model_result["metadata"]["model"]

        markers_found = sum(1 for m in bvb_markers if m in content_lower)

        if markers_found > best_count:
            best_count = markers_found
            best_model = model_name

        if markers_found >= 4:
            any_model_passes = True

    assert any_model_passes, f"No model covered Build vs Buy dimensions adequately. Best was {best_model} with {best_count}/11 markers."


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_archetype_ai_ml_selection(compare_models):
    """P1: Verify AI/ML Model Selection archetype produces benchmarks and cost projections."""
    result = await compare_impl(
        name="AI/ML Archetype Test",
        content="Compare GPT-4 vs Claude for our customer support chatbot handling 50k messages/day.",
        step_number=1,
        next_action="stop",
        models=compare_models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    assert result["status"] in ["success", "partial"]
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # AI/ML archetype should discuss: quality, latency, cost, tokens, context
    aiml_markers = [
        "token",
        "cost",
        "latency",
        "quality",
        "context",
        "api",
        "gpt",
        "claude",
        "response",
        "accuracy",
    ]

    # At least one model should cover AI/ML dimensions
    any_model_passes = False
    best_count = 0
    best_model = None

    for model_result in successes:
        content_lower = model_result["content"].lower()
        model_name = model_result["metadata"]["model"]

        markers_found = sum(1 for m in aiml_markers if m in content_lower)

        if markers_found > best_count:
            best_count = markers_found
            best_model = model_name

        if markers_found >= 4:
            any_model_passes = True

    assert any_model_passes, f"No model covered AI/ML dimensions adequately. Best was {best_model} with {best_count}/10 markers."


# ============================================================================
# P2: Web Search for Pricing
# ============================================================================


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_compare_web_search_for_pricing():
    """P2: Verify web search is triggered for current pricing questions.

    Uses only gemini-2.5-flash and gpt-5-mini as specified.
    The compare prompt says: "For cost/pricing: MUST search for current provider pricing"

    Note: This test may fail due to web search timeouts in CI environments.
    Web search is inherently slower and may be rate-limited.
    """
    # Use specific models for web search test
    models = ["gemini-2.5-flash", "gpt-5-mini"]

    result = await compare_impl(
        name="Web Search Pricing Test",
        content="Compare current AWS Lambda vs Google Cloud Functions pricing for a serverless API. I need the latest 2024/2025 pricing.",
        step_number=1,
        next_action="stop",
        models=models,
        base_path="/tmp",
        thread_id=str(uuid.uuid4()),
    )

    # Web search can be slow/rate-limited - allow graceful degradation
    # If all models timed out, skip the test rather than fail
    if result["status"] == "error":
        all_timeouts = all("timed out" in str(r.get("error", "")).lower() for r in result.get("results", []))
        if all_timeouts:
            pytest.skip("All models timed out during web search - likely rate limiting")

    assert result["status"] in ["success", "partial"]
    successes = [r for r in result["results"] if r["status"] == "success"]
    assert len(successes) >= 1

    # Check that at least one model provided pricing info
    pricing_found = False

    for model_result in successes:
        content = model_result["content"]
        content_lower = content.lower()

        # Check for pricing indicators
        pricing_markers = ["$", "price", "cost", "per million", "free tier", "gb-second"]
        if any(m in content_lower for m in pricing_markers):
            pricing_found = True
            break

    assert pricing_found, "No model provided pricing information"
