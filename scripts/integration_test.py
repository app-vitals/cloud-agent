"""Integration test for cloud-agent using CLI."""

import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TIMEOUT = 300  # 5 minutes max wait for task completion


def run_cli_command(command: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a CLI command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
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
    print(
        "  2. Celery worker: uv run celery -A app.celery_app worker --loglevel=info\n"
    )

    # Test 1: Create a task
    print("1. Creating a test task via CLI...")
    repo = "https://github.com/anthropics/anthropic-sdk-python.git"
    prompt = "Create a file called hello.txt with the text 'Hello World!'"

    exit_code, stdout, stderr = run_cli_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "app.cli",
            "task",
            "create",
            prompt,
            "--repo",
            repo,
        ]
    )

    if exit_code != 0:
        print("   ✗ Task creation failed")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        return 1

    # Extract task ID from output
    task_id_match = re.search(r"Task created: ([a-f0-9-]+)", stdout)
    if not task_id_match:
        print("   ✗ Could not extract task ID from output:")
        print(f"   {stdout}")
        return 1

    task_id = task_id_match.group(1)
    print(f"   ✓ Task created with ID: {task_id}")

    # Check for branch name in output
    if "Branch:" in stdout:
        print("   ✓ Branch info displayed in output\n")
    else:
        print()

    # Test 2: Get task details
    print("2. Getting task details via CLI...")
    exit_code, stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "get", task_id]
    )

    if exit_code != 0:
        print("   ✗ Failed to get task")
        print(f"   stderr: {stderr}")
        return 1

    print("   ✓ Retrieved task details")
    if "Branch:" in stdout:
        print("   ✓ Branch info displayed\n")
    else:
        print()

    # Test 3: Wait for task completion
    print("3. Waiting for task to complete (using CLI wait)...")
    exit_code, stdout, stderr = run_cli_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "app.cli",
            "task",
            "wait",
            task_id,
            "--timeout",
            str(TIMEOUT),
        ],
        timeout=TIMEOUT + 10,  # Give subprocess.run extra time beyond the wait timeout
    )

    if exit_code != 0:
        print("   ✗ Task did not complete successfully")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        # Continue to check logs even if failed
    else:
        print("   ✓ Task completed successfully\n")

    # Test 4: Get final task details
    print("4. Getting final task status...")
    exit_code, task_status_stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "get", task_id]
    )

    if exit_code == 0:
        print("   ✓ Final task details:\n")
        # Print the output (it's already formatted nicely by the CLI)
        for line in task_status_stdout.split("\n"):
            if line.strip():
                print(f"     {line}")
        print()
    else:
        print("   ✗ Failed to get final task details")

    # Test 5: Get task logs
    print("5. Fetching task logs via CLI...")
    exit_code, stdout, stderr = run_cli_command(
        ["uv", "run", "python", "-m", "app.cli", "task", "logs", task_id]
    )

    if exit_code == 0:
        print("   ✓ Retrieved task logs")
        # Show first few lines
        lines = stdout.split("\n")[:20]
        for line in lines:
            if line.strip():
                print(f"     {line}")
        if len(stdout.split("\n")) > 20:
            print("     ... (truncated)")
        print()
    else:
        print("   ✗ Failed to get logs")
        print(f"   stderr: {stderr}\n")

    # Test 6: Resume task
    print("6. Resuming task to append to the file...")
    resume_prompt = "Append a line to the file saying 'My favorite color is blue'"
    exit_code, stdout, stderr = run_cli_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "app.cli",
            "task",
            "resume",
            task_id,
            resume_prompt,
        ]
    )

    if exit_code != 0:
        print("   ✗ Failed to resume task")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        return 1

    # Extract resumed task ID
    resume_match = re.search(r"Resumed task created: ([a-f0-9\-]+)", stdout)
    if not resume_match:
        print("   ✗ Could not extract resumed task ID")
        return 1

    resumed_task_id = resume_match.group(1)
    print(f"   ✓ Resumed task created: {resumed_task_id}\n")

    # Test 7: Wait for resumed task
    print("7. Waiting for resumed task to complete...")
    exit_code, stdout, stderr = run_cli_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "app.cli",
            "task",
            "wait",
            resumed_task_id,
            "--timeout",
            str(TIMEOUT),
        ],
        timeout=TIMEOUT + 10,
    )

    if exit_code != 0:
        print("   ✗ Resumed task did not complete")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        return 1

    print("   ✓ Resumed task completed successfully\n")

    # Test 8: Verify file was updated
    print("8. Verifying file restoration and session resumption...")
    resumed_file = Path("logs/tasks") / resumed_task_id / "files" / "hello.txt"
    if not resumed_file.exists():
        print(f"   ✗ File not found: {resumed_file}")
        return 1

    content = resumed_file.read_text()

    # Check for both original and appended content
    has_original = "Hello World!" in content
    has_appended = "My favorite color is blue" in content

    if has_original and has_appended:
        print("   ✓ File restoration worked (original content present)")
        print("   ✓ Session resumption worked (appended new content)")
        print(f"   Content:\n     {content.strip()}\n")
    else:
        print("   ✗ File content incorrect:")
        print(f"     Has original: {has_original}")
        print(f"     Has appended: {has_appended}")
        print(f"   Content: {content}")
        return 1

    # Final verdict
    print("\n✓ Integration test PASSED!")
    print("  All CLI commands worked correctly:")
    print("  - task create")
    print("  - task get")
    print("  - task wait")
    print("  - task logs")
    print("  - task resume (with session and file restoration)")
    return 0


if __name__ == "__main__":
    exit(main())
