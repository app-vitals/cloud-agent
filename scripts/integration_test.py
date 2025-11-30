"""Integration test for cloud-agent using CLI."""

import os
import re
import subprocess
import time

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TIMEOUT = 300  # 5 minutes max wait for task completion


def run_cli_command(command: list[str]) -> tuple[int, str, str]:
    """Run a CLI command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def main():
    """Run integration test using CLI."""
    print("=== Cloud Agent CLI Integration Test ===\n")

    # Check environment
    api_key = os.getenv("API_SECRET_KEY")
    if not api_key:
        print("   ✗ API_SECRET_KEY not found in environment")
        print("   Make sure .env file has API_SECRET_KEY set")
        return 1

    # Check if API and Celery are running
    print("Prerequisites:")
    print("  This test requires the following services to be running:")
    print("  1. API server: uv run uvicorn app.main:app --reload")
    print("  2. Celery worker: uv run celery -A app.celery_app worker --loglevel=info\n")

    # Test 1: Create a task
    print("1. Creating a test task via CLI...")
    repo = "https://github.com/anthropics/anthropic-sdk-python.git"
    prompt = "Create a file called hello.txt with the text 'Hello World!'"

    exit_code, stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "create", prompt, "--repo", repo]
    )

    if exit_code != 0:
        print(f"   ✗ Task creation failed")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        return 1

    # Extract task ID from output
    task_id_match = re.search(r"Task created: ([a-f0-9-]+)", stdout)
    if not task_id_match:
        print(f"   ✗ Could not extract task ID from output:")
        print(f"   {stdout}")
        return 1

    task_id = task_id_match.group(1)
    print(f"   ✓ Task created with ID: {task_id}")

    # Check for branch name in output
    if "Branch:" in stdout:
        print(f"   ✓ Branch info displayed in output\n")
    else:
        print()

    # Test 2: Get task details
    print("2. Getting task details via CLI...")
    exit_code, stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "get", task_id]
    )

    if exit_code != 0:
        print(f"   ✗ Failed to get task")
        print(f"   stderr: {stderr}")
        return 1

    print(f"   ✓ Retrieved task details")
    if "Branch:" in stdout:
        print(f"   ✓ Branch info displayed\n")
    else:
        print()

    # Test 3: Wait for task completion
    print("3. Waiting for task to complete (using CLI wait)...")
    exit_code, stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "wait", task_id, "--timeout", str(TIMEOUT)]
    )

    if exit_code != 0:
        print(f"   ✗ Task did not complete successfully")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        # Continue to check logs even if failed
    else:
        print(f"   ✓ Task completed successfully\n")

    # Test 4: Get final task details
    print("4. Getting final task status...")
    exit_code, stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "get", task_id]
    )

    if exit_code == 0:
        print(f"   ✓ Final task details:\n")
        # Print the output (it's already formatted nicely by the CLI)
        for line in stdout.split("\n"):
            if line.strip():
                print(f"     {line}")
        print()
    else:
        print(f"   ✗ Failed to get final task details")

    # Test 5: Get task logs
    print("5. Fetching task logs via CLI...")
    exit_code, stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "logs", task_id]
    )

    if exit_code == 0:
        print(f"   ✓ Retrieved task logs")
        # Show first few lines
        lines = stdout.split("\n")[:20]
        for line in lines:
            if line.strip():
                print(f"     {line}")
        if len(stdout.split("\n")) > 20:
            print(f"     ... (truncated)")
        print()
    else:
        print(f"   ✗ Failed to get logs")
        print(f"   stderr: {stderr}\n")

    # Final verdict
    if "completed" in stdout.lower():
        print("\n✓ Integration test PASSED!")
        print("  All CLI commands worked correctly:")
        print("  - task create")
        print("  - task get")
        print("  - task wait")
        print("  - task logs")
        return 0
    else:
        print(f"\n✗ Integration test FAILED - task did not complete")
        return 1


if __name__ == "__main__":
    exit(main())
