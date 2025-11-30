#!/usr/bin/env python3
"""Test streaming output from the agent using E2B streaming callbacks.

This tests if we can get real-time logs as the agent runs.

Usage:
    uv run python scripts/test_sandbox_streaming.py
"""

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv

from app.services.sandbox import SandboxService

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def test_streaming():
    """Test streaming output from the agent."""
    print("=" * 60)
    print("Test 5: Streaming agent output")
    print("=" * 60)

    sandbox = None
    stdout_lines = []
    stderr_lines = []

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

        # Write a task
        print("\n3. Writing task...")
        task_input = {
            "prompt": "List the files in the current directory and tell me what you see."
        }
        sandbox.files.write("/tmp/task_input.json", json.dumps(task_input))
        print(f"✅ Task: {task_input['prompt']}")

        # Define streaming callbacks
        def on_stdout(output):
            timestamp = time.strftime("%H:%M:%S")
            line = output if isinstance(output, str) else str(output)
            print(f"   [{timestamp}] STDOUT: {line}")
            stdout_lines.append(line)

        def on_stderr(output):
            timestamp = time.strftime("%H:%M:%S")
            line = output if isinstance(output, str) else str(output)
            print(f"   [{timestamp}] STDERR: {line}")
            stderr_lines.append(line)

        # Run with streaming
        print(f"\n4. Running with streaming callbacks...")
        print("   (watch for real-time output below)")
        print("   " + "-" * 56)

        # Use sandbox.commands.run with callbacks
        # Note: We're NOT using SandboxService.run_command wrapper here
        # because we need direct access to the streaming API
        process = sandbox.commands.run(
            "uv run /tmp/sandbox_agent.py",
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            timeout=60
        )

        print("   " + "-" * 56)
        print(f"\n5. Command completed with exit code: {process.exit_code}")

        # Show what we captured
        print(f"\n6. Streaming capture summary:")
        print(f"   STDOUT lines captured: {len(stdout_lines)}")
        print(f"   STDERR lines captured: {len(stderr_lines)}")

        if stderr_lines:
            print(f"\n   First few STDERR lines:")
            for line in stderr_lines[:5]:
                print(f"     - {line[:80]}")

        # Also check the files
        print(f"\n7. Checking output files...")
        try:
            output_json = sandbox.files.read("/tmp/task_output.json")
            output = json.loads(output_json)
            print(f"✅ task_output.json exists")
            print(f"   Session ID: {output.get('session_id', 'N/A')}")
            print(f"   Result: {output.get('result', 'N/A')[:100] if output.get('result') else 'N/A'}...")
        except Exception as e:
            print(f"❌ task_output.json not found: {e}")

        try:
            logs_json = sandbox.files.read("/tmp/task_logs.json")
            logs = json.loads(logs_json)
            print(f"✅ task_logs.json exists: {len(logs)} messages")
        except Exception as e:
            print(f"❌ task_logs.json not found: {e}")

        print("\n" + "=" * 60)
        if len(stdout_lines) > 0 or len(stderr_lines) > 0:
            print("✅ Test 5 PASSED: Streaming works!")
            print("=" * 60)
            print("\nFindings:")
            print("- Can capture real-time stdout/stderr with callbacks")
            print("- See output as it happens (useful for monitoring)")
            print("- Still have file-based logs for persistence")
            print("\nPotential use:")
            print("- Stream logs to database as they arrive")
            print("- Show live progress in API/UI")
            print("- No need to wait for completion to see logs")
            return True
        else:
            print("⚠️  Test 5: No streaming output captured")
            print("=" * 60)
            print("\nEither:")
            print("- Task completed too quickly")
            print("- Streaming doesn't work as expected")
            print("- All output went to files instead")
            return False

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print(f"   Exception type: {type(e).__name__}")
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
    success = test_streaming()
    sys.exit(0 if success else 1)
