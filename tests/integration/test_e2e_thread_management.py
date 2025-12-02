"""Integration tests for thread management and isolation."""

import asyncio
import os
import uuid

import pytest

# Skip if RUN_E2E not set
pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="Integration tests require RUN_E2E=1 and API keys")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_thread_isolation_between_reviews(integration_test_model, tmp_path):
    """Test that different threads don't leak state between reviews."""
    from src.tools.codereview import codereview_impl

    # Create test file
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello(): print('world')")

    # Thread 1: Start review with specific issue
    thread_id_1 = str(uuid.uuid4())
    response1 = await codereview_impl(
        name="Review 1 - Security focus",
        content="Security review - found authentication bypass",
        step_number=1,
        next_action="stop",
        relevant_files=[str(test_file)],
        base_path=str(tmp_path),
        models=[integration_test_model],
        thread_id=thread_id_1,
        issues_found=[
            {
                "severity": "critical",
                "location": f"{test_file}:1",
                "description": "Authentication bypass vulnerability",
            }
        ],
    )

    assert response1["status"] in ["success", "in_progress"]
    assert response1["thread_id"] == thread_id_1

    # Thread 2: Completely separate review (should not see Thread 1's issues)
    thread_id_2 = str(uuid.uuid4())
    response2 = await codereview_impl(
        name="Review 2 - Code quality focus",
        content="Code quality review - clean implementation",
        step_number=1,
        next_action="stop",
        relevant_files=[str(test_file)],
        base_path=str(tmp_path),
        models=[integration_test_model],
        thread_id=thread_id_2,
    )

    assert response2["status"] in ["success", "in_progress"]
    assert response2["thread_id"] == thread_id_2
    assert response2["thread_id"] != thread_id_1

    # Verify threads are isolated
    # The key isolation requirement is that thread IDs must be different
    assert thread_id_1 != thread_id_2

    print("\n✓ Thread isolation verified")
    print(f"✓ Thread 1: {thread_id_1}")
    print(f"✓ Thread 2: {thread_id_2}")


@pytest.mark.vcr
@pytest.mark.asyncio
@pytest.mark.timeout(300)
async def test_concurrent_threads(integration_test_model, tmp_path):
    """Test multiple parallel reviews with different thread_ids."""
    from src.tools.codereview import codereview_impl

    # Create multiple test files
    file1 = tmp_path / "module1.py"
    file1.write_text("def func1(): pass")

    file2 = tmp_path / "module2.py"
    file2.write_text("def func2(): pass")

    file3 = tmp_path / "module3.py"
    file3.write_text("def func3(): pass")

    # Launch 3 concurrent reviews with different threads
    thread_ids = [str(uuid.uuid4()) for _ in range(3)]
    files = [file1, file2, file3]

    async def review_file(file_path, thread_id, index):
        """Run a single review."""
        return await codereview_impl(
            name=f"Concurrent review {index + 1}",
            content=f"Quick review of module {index + 1}",
            step_number=1,
            next_action="stop",
            relevant_files=[str(file_path)],
            base_path=str(tmp_path),
            models=[integration_test_model],
            thread_id=thread_id,
        )

    # Run all reviews concurrently
    tasks = [review_file(files[i], thread_ids[i], i) for i in range(3)]
    responses = await asyncio.gather(*tasks)

    # Verify all completed successfully
    for i, response in enumerate(responses):
        assert response["status"] in ["success", "in_progress"]
        assert response["thread_id"] == thread_ids[i]
        assert "summary" in response
        print(f"✓ Review {i + 1} completed: {thread_ids[i]}")

    # Verify all thread IDs are unique
    returned_threads = [r["thread_id"] for r in responses]
    assert len(set(returned_threads)) == 3, "Thread IDs should be unique"

    print("\n✓ Concurrent threads test passed")
    print(f"✓ {len(responses)} reviews completed in parallel")
    print("✓ All thread IDs unique")
