#!/usr/bin/env python3
"""Test basic SDK functionality in a Novita sandbox (no repo needed).

This verifies that sandbox_agent.py works in the sandbox environment.

Usage:
    uv run python scripts/test_sandbox_basic.py
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from app.services.sandbox import SandboxService

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def test_basic_sdk_in_sandbox():
    """Test that sandbox_agent.py works in a sandbox without cloning a repo."""
    print("=" * 60)
    print("Test 1: Basic SDK functionality in sandbox (no repo)")
    print("=" * 60)

    sandbox = None
    try:
        # Create sandbox (no repo needed for this basic test)
        print("\n1. Creating sandbox...")
        sandbox = SandboxService.create_sandbox(
            repository_url="",  # Not cloning a repo for this test
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            claude_code_oauth_token=os.getenv("CLAUDE_CODE_OAUTH_TOKEN"),
            github_token=os.getenv("GITHUB_TOKEN"),
        )
        print(f"✅ Created sandbox: {sandbox.sandbox_id}")

        # Upload sandbox_agent.py script
        print("\n2. Uploading sandbox_agent.py...")
        script_path = Path(__file__).parent / "sandbox_agent.py"
        script_content = script_path.read_text()
        sandbox.files.write("/tmp/sandbox_agent.py", script_content)
        print("✅ Uploaded script to /tmp/sandbox_agent.py")

        # Write task input (simple prompt)
        print("\n3. Writing task input...")
        task_input = {"prompt": "What is 2+2? Just give me the answer."}
        sandbox.files.write("/tmp/task_input.json", json.dumps(task_input))
        print(f"✅ Wrote task input: {task_input}")

        # Run the agent script
        print("\n4. Running uv run /tmp/sandbox_agent.py...")
        result = SandboxService.run_command(
            sandbox,
            "uv run /tmp/sandbox_agent.py",
            timeout=300  # 5 minutes should be plenty
        )

        if result.exit_code != 0:
            print(f"❌ Script failed with exit code {result.exit_code}")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            return False

        print(f"✅ Script completed successfully")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")

        # Read output files
        print("\n5. Reading output files...")

        # Read task_output.json
        try:
            output_json = sandbox.files.read("/tmp/task_output.json")
            output = json.loads(output_json)
            print("✅ task_output.json:")
            print(json.dumps(output, indent=2))
        except Exception as e:
            print(f"❌ Failed to read task_output.json: {e}")
            return False

        # Read task_logs.json
        try:
            logs_json = sandbox.files.read("/tmp/task_logs.json")
            logs = json.loads(logs_json)
            print(f"\n✅ task_logs.json: {len(logs)} messages")
            # Print first few message types
            msg_types = [log.get("type") for log in logs[:5]]
            print(f"First message types: {msg_types}")
        except Exception as e:
            print(f"❌ Failed to read task_logs.json: {e}")
            return False

        # Verify expected fields
        print("\n6. Verifying output structure...")
        required_fields = ["session_id", "result", "cost", "duration_ms", "num_turns"]
        missing = [f for f in required_fields if f not in output]
        if missing:
            print(f"❌ Missing fields: {missing}")
            return False

        print("✅ All required fields present")

        # Check that we got a session ID
        if not output.get("session_id"):
            print("❌ No session_id captured")
            return False

        print(f"✅ Session ID: {output['session_id']}")

        # Check that we got a result
        if not output.get("result"):
            print("❌ No result captured")
            return False

        print(f"✅ Result: {output['result'][:100]}...")

        print("\n" + "=" * 60)
        print("✅ Test 1 PASSED: SDK works in sandbox!")
        print("=" * 60)
        print(f"\nSession ID: {output['session_id']}")
        print(f"Cost: ${output['cost']:.6f}")
        print(f"Duration: {output['duration_ms']}ms")
        print(f"Turns: {output['num_turns']}")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        if sandbox:
            print(f"\n7. Cleaning up sandbox {sandbox.sandbox_id}...")
            try:
                sandbox.kill()
                print("✅ Sandbox killed")
            except Exception as e:
                print(f"⚠️ Failed to kill sandbox: {e}")


if __name__ == "__main__":
    success = test_basic_sdk_in_sandbox()
    sys.exit(0 if success else 1)
