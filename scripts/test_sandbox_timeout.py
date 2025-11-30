#!/usr/bin/env python3
"""Test that timeout handling works with SDK and we can still capture logs.

This verifies that when the agent times out, we can still read partial logs.

Usage:
    uv run python scripts/test_sandbox_timeout.py
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

from app.services.sandbox import SandboxService

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def test_timeout_with_logs():
    """Test that we can capture logs even when timeout kills the process."""
    print("=" * 60)
    print("Test 3: Timeout handling and log capture")
    print("=" * 60)

    sandbox = None

    try:
        # Create sandbox
        print("\n1. Creating sandbox...")
        sandbox = SandboxService.create_sandbox(
            repository_url="",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            claude_code_oauth_token=os.getenv("CLAUDE_CODE_OAUTH_TOKEN"),
            github_token=os.getenv("GITHUB_TOKEN"),
        )
        print(f"✅ Created sandbox: {sandbox.sandbox_id}")

        # Upload sandbox_agent.py
        print("\n2. Uploading sandbox_agent.py...")
        script_path = Path(__file__).parent / "sandbox_agent.py"
        script_content = script_path.read_text()
        sandbox.files.write("/tmp/sandbox_agent.py", script_content)
        print("✅ Uploaded script")

        # Write a task that will take a long time (to trigger timeout)
        print("\n3. Writing task that will timeout...")
        task_input = {
            "prompt": "Create 100 files named file_1.txt through file_100.txt, each containing a unique poem about that number. Take your time and make each poem creative and different."
        }
        sandbox.files.write("/tmp/task_input.json", json.dumps(task_input))
        print(f"✅ Task: {task_input['prompt']}")

        # Run with timeout using bash timeout command (like current implementation)
        timeout_seconds = 30  # Give it time to start and run a bit
        print(f"\n4. Running with {timeout_seconds}s timeout...")
        print("   Using bash timeout wrapper to capture logs...")

        result = SandboxService.run_command(
            sandbox,
            f"timeout {timeout_seconds} uv run /tmp/sandbox_agent.py",
            timeout=timeout_seconds + 30  # Outer timeout buffer
        )

        print(f"\n5. Command completed with exit code: {result.exit_code}")

        # Exit code 124 means bash timeout killed it
        if result.exit_code == 124:
            print("✅ Timeout triggered (exit code 124)")
        else:
            print(f"⚠️  Expected exit code 124, got {result.exit_code}")

        # Check stdout/stderr
        print(f"\n6. Checking captured output...")
        print(f"   STDOUT length: {len(result.stdout)} bytes")
        print(f"   STDERR length: {len(result.stderr)} bytes")

        if result.stdout:
            print(f"   STDOUT preview:\n{result.stdout[:500]}")

        if result.stderr:
            print(f"   STDERR preview:\n{result.stderr[:500]}")

        # Try to read the output files (might be partial)
        print(f"\n7. Checking if partial output files exist...")

        try:
            output_json = sandbox.files.read("/tmp/task_output.json")
            output = json.loads(output_json)
            print(f"✅ task_output.json exists (might be incomplete)")
            print(f"   Session ID: {output.get('session_id', 'N/A')}")
            print(f"   Result: {output.get('result', 'N/A')[:100] if output.get('result') else 'N/A'}")
        except Exception as e:
            print(f"⚠️  task_output.json not found or incomplete: {e}")

        try:
            logs_json = sandbox.files.read("/tmp/task_logs.json")
            logs = json.loads(logs_json)
            print(f"✅ task_logs.json exists: {len(logs)} messages captured before timeout")

            # Show message types
            msg_types = [log.get("type") for log in logs[:10]]
            print(f"   First message types: {msg_types}")
        except Exception as e:
            print(f"⚠️  task_logs.json not found or incomplete: {e}")

        print("\n" + "=" * 60)
        if result.exit_code == 124:
            print("✅ Test 3: Timeout handling works!")
            print("=" * 60)
            print("\nFindings:")
            print("- Bash timeout command (exit 124) works as expected")
            print("- Can capture stdout/stderr even after timeout")
            print("- Output files may be incomplete (expected)")
            print("\nNote: We need to handle incomplete output gracefully")
            return True
        else:
            print("❌ Test 3: Unexpected behavior")
            print("=" * 60)
            return False

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if sandbox:
            print(f"\n8. Cleaning up sandbox {sandbox.sandbox_id}...")
            try:
                sandbox.kill()
                print("✅ Sandbox killed")
            except Exception as e:
                print(f"⚠️ Failed to kill sandbox: {e}")


if __name__ == "__main__":
    import sys
    success = test_timeout_with_logs()
    sys.exit(0 if success else 1)
