"""End-to-end integration tests for error handling."""

import os

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_codereview_with_nonexistent_files(integration_test_model, tmp_path):
    """Test codereview handles non-existent files gracefully."""
    import uuid

    from multi_mcp.tools.codereview import codereview_impl

    thread_id = str(uuid.uuid4())

    # Pass non-existent file paths
    fake_file = str(tmp_path / "nonexistent.py")

    response = await codereview_impl(
        name="Review with missing files",
        content="Review non-existent files",
        step_number=1,
        next_action="stop",
        relevant_files=[fake_file],
        base_path=str(tmp_path),
        models=[integration_test_model],
        thread_id=thread_id,
    )

    # Should handle gracefully - either return in_progress asking for files,
    # or success with message about missing files
    assert response["status"] in ["in_progress", "success"]
    assert response["thread_id"] == thread_id
    assert "summary" in response

    print(f"\n✓ Non-existent files test completed: {thread_id}")
    print(f"✓ Status: {response['status']}")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_codereview_with_empty_files_list(integration_test_model, tmp_path):
    """Test codereview handles empty files list."""
    import uuid

    from multi_mcp.tools.codereview import codereview_impl

    thread_id = str(uuid.uuid4())

    response = await codereview_impl(
        name="Review with no files",
        content="Review code",
        step_number=1,
        next_action="stop",
        relevant_files=[],
        base_path=str(tmp_path),
        models=[integration_test_model],
        thread_id=thread_id,
    )

    # Should return in_progress status asking for files
    assert response["status"] == "in_progress"
    assert response["thread_id"] == thread_id
    assert "summary" in response

    # Summary should indicate files are needed
    summary = response["summary"].lower()
    assert "file" in summary or "code" in summary, f"Expected message about needing files, got: {summary}"

    print(f"\n✓ Empty files list test completed: {thread_id}")
    print(f"✓ Message: {response['summary'][:100]}...")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_codereview_exceeds_file_limit(integration_test_model, tmp_path):
    """Test codereview enforces max files limit via Pydantic validation."""
    import uuid

    from pydantic import ValidationError

    from multi_mcp.schemas.codereview import CodeReviewRequest

    # Create 101 files (assuming max is 100)
    files = []
    for i in range(101):
        test_file = tmp_path / f"file_{i}.py"
        test_file.write_text(f"# File {i}\nprint('hello')")
        files.append(str(test_file))

    thread_id = str(uuid.uuid4())

    # Should raise ValidationError because too many files
    with pytest.raises(ValidationError) as exc_info:
        CodeReviewRequest(
            name="Review too many files",
            content="Review all files",
            step_number=1,
            next_action="stop",
            relevant_files=files,
            base_path=str(tmp_path),
            model=integration_test_model,
            thread_id=thread_id,
        )

    # Check error message mentions too many files
    error_str = str(exc_info.value).lower()
    assert "too many" in error_str or "maximum" in error_str, f"Expected file limit error, got: {error_str}"

    print("\n✓ File limit validation test completed")
    print(f"✓ Correctly rejected {len(files)} files")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_compare_with_invalid_model(integration_test_model):
    """Test compare handles invalid model gracefully."""
    import uuid

    from multi_mcp.tools.compare import compare_impl

    thread_id = str(uuid.uuid4())

    response = await compare_impl(
        name="Test invalid model",
        content="What is 2+2?",
        step_number=1,
        next_action="stop",
        models=[integration_test_model, "invalid-model-xyz"],  # One valid, one invalid
        base_path="/tmp",
        thread_id=thread_id,
    )

    # Should return partial status with one success, one error
    assert response["status"] in ["success", "partial", "error"]
    assert response["thread_id"] == thread_id
    assert "results" in response
    assert len(response["results"]) == 2

    # At least one should have an error
    errors = [r for r in response["results"] if r["status"] == "error"]
    assert len(errors) >= 1, "Expected at least one model to error"

    # At least one should succeed (gpt-5-nano)
    successes = [r for r in response["results"] if r["status"] == "success"]
    assert len(successes) >= 1, "Expected at least one model to succeed"

    print(f"\n✓ Invalid model test completed: {thread_id}")
    print(f"✓ Status: {response['status']}")
    print(f"✓ Successes: {len(successes)}, Errors: {len(errors)}")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_debate_with_all_invalid_models(integration_test_model):
    """Test debate handles complete failure gracefully."""
    import uuid

    from multi_mcp.tools.debate import debate_impl

    thread_id = str(uuid.uuid4())

    response = await debate_impl(
        name="Test all invalid models",
        content="What is 2+2?",
        step_number=1,
        next_action="stop",
        models=["invalid-model-1", "invalid-model-2"],
        base_path="/tmp",
        thread_id=thread_id,
    )

    # Should return error status
    assert response["status"] == "error"
    assert response["thread_id"] == thread_id
    # Error responses may have 'summary' instead of 'content'
    assert "summary" in response or "content" in response

    # All results should be errors
    assert len(response["results"]) == 2
    for result in response["results"]:
        assert result["status"] == "error"
        assert "error" in result  # Should have error message

    print(f"\n✓ All invalid models test completed: {thread_id}")
    print(f"✓ Status: {response['status']}")
    print("✓ All models failed as expected")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_chat_with_binary_file(integration_test_model, tmp_path):
    """Test chat handles binary files gracefully."""
    import uuid

    from multi_mcp.tools.chat import chat_impl

    # Create a binary file (simulated with null bytes)
    binary_file = tmp_path / "binary.dat"
    binary_file.write_bytes(b"\x00\x01\x02\x03\x04\xff\xfe")

    thread_id = str(uuid.uuid4())

    response = await chat_impl(
        name="Analyze binary file",
        content="What's in this file?",
        step_number=1,
        next_action="stop",
        base_path=str(tmp_path),
        model=integration_test_model,
        thread_id=thread_id,
        relevant_files=[str(binary_file)],
    )

    # Should succeed but skip the binary file
    assert response["status"] in ["success", "in_progress"]
    assert response["thread_id"] == thread_id
    assert "content" in response

    # Response should exist (even if file was skipped)
    assert len(response["content"]) > 0

    print(f"\n✓ Binary file test completed: {thread_id}")
    print(f"✓ Status: {response['status']}")
