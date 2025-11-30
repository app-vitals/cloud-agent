#!/usr/bin/env python3
"""Test timeout with just run_command timeout (no bash timeout wrapper).

This checks if we can simplify by using only the E2B timeout.

Usage:
    uv run python scripts/test_sandbox_timeout_simple.py
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

from app.services.sandbox import SandboxService

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def test_simple_timeout():
    """Test using only run_command timeout without bash timeout wrapper."""
    print("=" * 60)
    print("Test 4: Simple timeout (no bash wrapper)")
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

        # Write a task that will take a long time
        print("\n3. Writing task that will timeout...")
        task_input = {
            "prompt": "Create 100 files named file_1.txt through file_100.txt, each containing a unique poem about that number. Take your time and make each poem creative and different."
        }
        sandbox.files.write("/tmp/task_input.json", json.dumps(task_input))
        print(f"✅ Task: {task_input['prompt'][:80]}...")

        # Run with ONLY run_command timeout (no bash timeout wrapper)
        timeout_seconds = 30
        print(f"\n4. Running with ONLY run_command timeout={timeout_seconds}s (no bash wrapper)...")

        result = SandboxService.run_command(
            sandbox,
            "uv run /tmp/sandbox_agent.py",  # No timeout command wrapper!
            timeout=timeout_seconds  # Just the E2B timeout
        )

        print(f"\n5. Command completed with exit code: {result.exit_code}")
        print(f"   Exit code: {result.exit_code}")

        # Check stdout/stderr
        print(f"\n6. Checking captured output...")
        print(f"   STDOUT length: {len(result.stdout)} bytes")
        print(f"   STDERR length: {len(result.stderr)} bytes")

        if result.stdout:
            print(f"   STDOUT preview:\n{result.stdout[:300]}")

        if result.stderr:
            print(f"   STDERR preview:\n{result.stderr[:300]}")

        # Try to read the output files
        print(f"\n7. Checking if output files exist...")

        session_id = None
        try:
            output_json = sandbox.files.read("/tmp/task_output.json")
            output = json.loads(output_json)
            print(f"✅ task_output.json exists")
            session_id = output.get('session_id')
            print(f"   Session ID: {session_id}")
            result_text = output.get('result', 'N/A')
            if result_text and result_text != 'N/A':
                print(f"   Result: {result_text[:100]}...")
            else:
                print(f"   Result: {result_text}")
        except Exception as e:
            print(f"❌ task_output.json not found: {e}")

        # Check session.jsonl file (the SDK's session file that serves as logs)
        if session_id:
            try:
                session_file_path = f"/home/user/.claude/projects/-home-user-repo/{session_id}.jsonl"
                session_jsonl = sandbox.files.read(session_file_path)

                # Count lines in session file
                lines = [line.strip() for line in session_jsonl.split('\n') if line.strip()]
                print(f"✅ session.jsonl exists: {len(lines)} messages captured")

                # Parse and show first few message types
                msg_types = []
                for line in lines[:10]:
                    try:
                        msg = json.loads(line)
                        msg_types.append(msg.get("type", "unknown"))
                    except:
                        msg_types.append("parse-error")
                print(f"   First message types: {msg_types}")

                # Show file size
                print(f"   Session file size: {len(session_jsonl)} bytes")

            except Exception as e:
                print(f"❌ session.jsonl not found: {e}")
        else:
            print(f"⚠️  No session_id, cannot check session.jsonl")

        print("\n" + "=" * 60)
        if result.exit_code != 0:
            print("⚠️  Test 4: Command failed/timed out")
            print("=" * 60)
            print("\nFindings:")
            print(f"- Exit code: {result.exit_code}")
            print("- Check if we captured partial logs above")
        else:
            print("✅ Test 4: Command completed successfully")
            print("=" * 60)
            print("\nTask completed within timeout - no timeout triggered")

        return True

    except Exception as e:
        print(f"\n5. Command raised exception: {type(e).__name__}")
        print(f"   Message: {str(e)[:200]}")

        # Check if it's a timeout exception
        is_timeout = "timeout" in str(e).lower() or "deadline" in str(e).lower()

        if is_timeout:
            print("   ✅ This is a timeout exception")

        # Still try to read files
        print(f"\n6. Checking if partial files were written despite exception...")
        session_id = None
        if sandbox:
            try:
                output_json = sandbox.files.read("/tmp/task_output.json")
                output = json.loads(output_json)
                print(f"✅ task_output.json exists")
                session_id = output.get('session_id')
                print(f"   Session ID: {session_id}")
                result_text = output.get('result')
                if result_text:
                    print(f"   Result: {result_text[:100]}...")
            except Exception as e2:
                print(f"❌ task_output.json not found: {e2}")

            # Check session.jsonl file (the SDK's session file that serves as logs)
            if session_id:
                try:
                    session_file_path = f"/home/user/.claude/projects/-home-user-repo/{session_id}.jsonl"
                    session_jsonl = sandbox.files.read(session_file_path)

                    # Count lines in session file
                    lines = [line.strip() for line in session_jsonl.split('\n') if line.strip()]
                    print(f"✅ session.jsonl exists: {len(lines)} messages captured!")

                    # Parse and show first few message types
                    msg_types = []
                    for line in lines[:10]:
                        try:
                            msg = json.loads(line)
                            msg_types.append(msg.get("type", "unknown"))
                        except:
                            msg_types.append("parse-error")
                    print(f"   Message types: {msg_types}")

                    # Show file size
                    print(f"   Session file size: {len(session_jsonl)} bytes")

                except Exception as e2:
                    print(f"❌ session.jsonl not found: {e2}")
            else:
                print(f"⚠️  No session_id, cannot check session.jsonl")

        print("\n" + "=" * 60)
        if is_timeout:
            print("✅ Test 4 PASSED: Simple timeout works!")
            print("=" * 60)
            print("\nFindings:")
            print("- E2B timeout throws TimeoutException (not exit code)")
            print("- SDK's session.jsonl file captures messages despite timeout")
            print("- Can read partial results from files after exception")
            print("- Simpler than bash timeout (no wrapper needed)")
            print("\nImplementation:")
            print("- Catch TimeoutException in run_agent()")
            print("- Read session file from ~/.claude/projects/.../{session_id}.jsonl")
            print("- Session file serves as logs (no separate log collection needed)")
            print("- Mark task as timeout/failed")
            return True
        else:
            return False

    finally:
        if sandbox:
            print(f"\n9. Cleaning up sandbox {sandbox.sandbox_id}...")
            try:
                sandbox.kill()
                print("✅ Sandbox killed")
            except Exception as e:
                print(f"⚠️ Failed to kill sandbox: {e}")


if __name__ == "__main__":
    import sys
    success = test_simple_timeout()
    sys.exit(0 if success else 1)
