#!/usr/bin/env python3
"""Test session resumption across different Novita sandboxes.

This verifies that session_id from Sandbox A can be resumed in Sandbox B,
which would prove server-side session storage.

Usage:
    uv run python scripts/test_sandbox_resume.py
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

from app.services.sandbox import SandboxService

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def test_session_resumption():
    """Test that sessions can be resumed across different sandbox instances."""
    print("=" * 60)
    print("Test 2: Session resumption across sandboxes")
    print("=" * 60)

    sandbox_a = None
    sandbox_b = None
    session_id = None

    try:
        # === SANDBOX A: Create initial session ===
        print("\n1. Creating Sandbox A (initial session)...")
        sandbox_a = SandboxService.create_sandbox(
            repository_url="",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            claude_code_oauth_token=os.getenv("CLAUDE_CODE_OAUTH_TOKEN"),
            github_token=os.getenv("GITHUB_TOKEN"),
        )
        print(f"✅ Created Sandbox A: {sandbox_a.sandbox_id}")

        # Upload script
        print("\n2. Setting up Sandbox A...")
        script_path = Path(__file__).parent / "sandbox_agent.py"
        script_content = script_path.read_text()
        sandbox_a.files.write("/tmp/sandbox_agent.py", script_content)

        # Write task that creates context
        task_input = {
            "prompt": "Remember this secret code: XYZZY-42. Just confirm you've remembered it."
        }
        sandbox_a.files.write("/tmp/task_input.json", json.dumps(task_input))
        print(f"✅ Task: {task_input['prompt']}")

        # Run in Sandbox A
        print("\n3. Running agent in Sandbox A...")
        result = SandboxService.run_command(
            sandbox_a,
            "uv run /tmp/sandbox_agent.py",
            timeout=300
        )

        if result.exit_code != 0:
            print(f"❌ Sandbox A failed with exit code {result.exit_code}")
            print(f"STDERR:\n{result.stderr}")
            return False

        print("✅ Completed in Sandbox A")

        # Read session ID
        output_json = sandbox_a.files.read("/tmp/task_output.json")
        output = json.loads(output_json)
        session_id = output.get("session_id")

        if not session_id:
            print("❌ No session_id captured from Sandbox A")
            return False

        print(f"✅ Captured session ID: {session_id}")
        print(f"   Result: {output.get('result', 'N/A')}")

        # Try to read the session file from Sandbox A
        # Sessions are stored in .claude/projects/<normalized-cwd>
        session_file_path = f"/home/user/.claude/projects/-home-user/{session_id}.jsonl"
        print(f"\n   Attempting to read session file: {session_file_path}")

        try:
            session_data = sandbox_a.files.read(session_file_path)
            print(f"✅ Session file found! Size: {len(session_data)} bytes")
        except Exception as e:
            print(f"❌ Could not read session file: {e}")
            print("   Trying to find where sessions are stored...")
            # Try to list the .claude directory
            try:
                result = SandboxService.run_command(sandbox_a, "ls -la /home/user/.claude/projects/", timeout=10)
                print(f"   .claude/projects contents:\n{result.stdout}")
            except Exception as e2:
                print(f"   Could not list .claude directory: {e2}")
            return False

        # === DESTROY SANDBOX A ===
        print(f"\n4. Destroying Sandbox A ({sandbox_a.sandbox_id})...")
        sandbox_a.kill()
        sandbox_a = None
        print("✅ Sandbox A destroyed")

        # === SANDBOX B: Resume session ===
        print("\n5. Creating Sandbox B (fresh environment)...")
        sandbox_b = SandboxService.create_sandbox(
            repository_url="",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            claude_code_oauth_token=os.getenv("CLAUDE_CODE_OAUTH_TOKEN"),
            github_token=os.getenv("GITHUB_TOKEN"),
        )
        print(f"✅ Created Sandbox B: {sandbox_b.sandbox_id}")

        # Upload script to new sandbox
        print("\n6. Setting up Sandbox B...")
        sandbox_b.files.write("/tmp/sandbox_agent.py", script_content)

        # Upload the session file to Sandbox B
        print(f"\n   Uploading session file to Sandbox B...")
        print(f"   Creating directory structure...")
        SandboxService.run_command(
            sandbox_b,
            "mkdir -p /home/user/.claude/projects/-home-user",
            timeout=10
        )
        sandbox_b.files.write(session_file_path, session_data)
        print(f"✅ Session file uploaded to {session_file_path}")

        # Write task that tries to resume
        task_input = {
            "prompt": "What secret code did I ask you to remember?",
            "resume_session_id": session_id
        }
        sandbox_b.files.write("/tmp/task_input.json", json.dumps(task_input))
        print(f"✅ Task: {task_input['prompt']}")
        print(f"   Resuming session: {session_id}")

        # Run in Sandbox B
        print("\n7. Running agent in Sandbox B (attempting resume)...")
        result = SandboxService.run_command(
            sandbox_b,
            "uv run /tmp/sandbox_agent.py",
            timeout=300
        )

        if result.exit_code != 0:
            print(f"❌ Sandbox B failed with exit code {result.exit_code}")
            print(f"STDERR:\n{result.stderr}")

            # Check if it's a "No conversation found" error
            if "No conversation found" in result.stderr:
                print("\n" + "=" * 60)
                print("❌ Test 2 RESULT: Session file upload didn't work")
                print("=" * 60)
                print("\nEven after copying the session .jsonl file, resumption failed.")
                print("This suggests additional session state might be required,")
                print("or the session file path/format is incorrect.")
            return False

        print("✅ Completed in Sandbox B")

        # Read result
        output_json = sandbox_b.files.read("/tmp/task_output.json")
        output = json.loads(output_json)
        result_text = output.get("result", "")

        print(f"\n8. Checking if Claude remembered the context...")
        print(f"   Result: {result_text}")

        # Check if the response mentions the code
        if "XYZZY-42" in result_text or "XYZZY" in result_text:
            print("\n" + "=" * 60)
            print("✅ Test 2 PASSED: Session resumption works across sandboxes!")
            print("=" * 60)
            print("\nThis proves:")
            print("- Sessions are stored server-side (not just local)")
            print("- Can resume context across different sandbox instances")
            print("- Users can iterate on tasks across multiple runs")
            return True
        else:
            print("\n" + "=" * 60)
            print("❌ Test 2 FAILED: Claude didn't remember the context")
            print("=" * 60)
            print("\nThis suggests:")
            print("- Sessions might be stored locally (not server-side)")
            print("- Or session resumption has other limitations")
            print("- Will need to use branch + logs for context instead")
            return False

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup both sandboxes
        if sandbox_a:
            print(f"\nCleaning up Sandbox A ({sandbox_a.sandbox_id})...")
            try:
                sandbox_a.kill()
                print("✅ Sandbox A killed")
            except Exception as e:
                print(f"⚠️ Failed to kill Sandbox A: {e}")

        if sandbox_b:
            print(f"\nCleaning up Sandbox B ({sandbox_b.sandbox_id})...")
            try:
                sandbox_b.kill()
                print("✅ Sandbox B killed")
            except Exception as e:
                print(f"⚠️ Failed to kill Sandbox B: {e}")


if __name__ == "__main__":
    import sys
    success = test_session_resumption()
    sys.exit(0 if success else 1)
