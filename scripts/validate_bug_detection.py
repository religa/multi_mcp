"""Validate bug detection capabilities on test repositories."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from multi_mcp.tools.codereview import codereview_impl


async def validate_sql_injection_detection():
    """Test detection of SQL injection and password security issues."""
    print("=" * 70)
    print("Bug Detection Validation: SQL Injection Example")
    print("=" * 70)
    print()

    # Path to test repo
    test_repo = Path(__file__).parent.parent / "tests" / "data" / "repos" / "sql_injection_example"
    auth_file = test_repo / "auth.py"

    if not auth_file.exists():
        print(f"❌ Test file not found: {auth_file}")
        return False

    print(f"📁 Test Repository: {test_repo}")
    print(f"📄 Test File: {auth_file}")
    print()

    # Expected vulnerabilities
    expected_issues = [
        "SQL Injection",
        "Parameterized queries",
        "Password hashing",
        "Plain text password",
        "SELECT *",
        "Password policy",
        "Input validation",
    ]

    print("🎯 Expected Security Issues:")
    for i, issue in enumerate(expected_issues, 1):
        print(f"  {i}. {issue}")
    print()

    # Run code review
    print("🔍 Running security code review...")
    print()

    try:
        response = await codereview_impl(
            name="Security Review",
            message="Perform comprehensive security review focusing on SQL injection, password security, input validation, OWASP Top 10",
            step_number=1,
            next_action="stop",
            relevant_files=[str(auth_file)],
            base_path=str(test_repo),
            model="gpt-5-mini",
        )

        print("✅ Code review completed!")
        print()

        # Analyze results
        message = response["message"]
        issues_found = response.get("issues_found", [])

        print("-" * 70)
        print("📊 Results Summary")
        print("-" * 70)
        print(f"Status: {response['status']}")
        print(f"Thread ID: {response['thread_id']}")
        print(f"Issues Found: {len(issues_found)}")
        print(f"Response Length: {len(message):,} characters")
        print()

        # Check which expected issues were found
        found_count = 0
        message_lower = message.lower()

        print("-" * 70)
        print("🔎 Issue Detection Results")
        print("-" * 70)

        for issue in expected_issues:
            found = issue.lower() in message_lower
            status = "✓" if found else "✗"
            if found:
                found_count += 1
            print(f"  {status} {issue}")

        print()
        print(f"Detection Rate: {found_count}/{len(expected_issues)} ({found_count / len(expected_issues) * 100:.0f}%)")
        print()

        # Show reported issues
        if issues_found:
            print("-" * 70)
            print("🐛 Reported Issues")
            print("-" * 70)
            for i, issue in enumerate(issues_found, 1):
                severity = issue.get("severity", "unknown").upper()
                title = issue.get("title", "Untitled")
                line = issue.get("line", "?")
                print(f"  {i}. [{severity}] {title} (line {line})")
            print()

        # Show excerpt of analysis
        print("-" * 70)
        print("📝 Analysis Excerpt (first 500 chars)")
        print("-" * 70)
        print(message[:500] + ("..." if len(message) > 500 else ""))
        print()

        # Determine success
        success_threshold = 0.5  # Need at least 50% detection rate
        success = found_count / len(expected_issues) >= success_threshold

        if success:
            print("=" * 70)
            print("✅ VALIDATION PASSED")
            print("=" * 70)
            print(f"Successfully detected {found_count}/{len(expected_issues)} security issues")
            print()
        else:
            print("=" * 70)
            print("⚠️  VALIDATION NEEDS IMPROVEMENT")
            print("=" * 70)
            print(f"Only detected {found_count}/{len(expected_issues)} security issues")
            print(f"Target: {int(success_threshold * 100)}% detection rate")
            print()

        return success

    except Exception as e:
        print(f"❌ Error during validation: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all validation tests."""
    print()
    print("🧪 Multi-MCP Bug Detection Validation")
    print()

    # Check for API key
    import os

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set")
        print()
        print("Set your API key:")
        print("  export OPENAI_API_KEY=sk-...")
        print()
        return 1

    # Run validation
    success = await validate_sql_injection_detection()

    if success:
        print("All validation tests passed! 🎉")
        return 0
    else:
        print("Some validation tests failed. See details above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
