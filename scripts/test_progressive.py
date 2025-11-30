#!/usr/bin/env python3
"""Progressive testing to find where SDK breaks in sandbox."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from e2b import Sandbox

load_dotenv()

# Configure for Novita
os.environ["E2B_API_KEY"] = os.getenv("NOVITA_API_KEY")
os.environ["E2B_DOMAIN"] = "sandbox.novita.ai"

# Read sandbox_agent.py
script_path = Path(__file__).parent / "sandbox_agent.py"
script_content = script_path.read_text()

def test_task(sandbox, task_name, prompt):
    """Test a single task."""
    print(f"\n{'='*60}")
    print(f"Testing: {task_name}")
    print(f"{'='*60}")
    print(f"Prompt: {prompt}")

    # Write input
    task_input = {"prompt": prompt}
    sandbox.files.write("/tmp/task_input.json", json.dumps(task_input))

    # Run agent
    try:
        result = sandbox.commands.run(
            "cd /home/user/repo && uv run /tmp/sandbox_agent.py",
            timeout=120  # 2 minute timeout
        )

        print(f"✅ Exit code: {result.exit_code}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout[:500]}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr[:500]}")

        # Read output
        try:
            output_json = sandbox.files.read("/tmp/task_output.json")
            output = json.loads(output_json)
            print(f"✅ Result: {output.get('result', 'None')[:100]}")
            print(f"   Cost: ${output.get('cost', 0):.4f}")
            print(f"   Turns: {output.get('num_turns', 0)}")
            return True
        except Exception as e:
            print(f"❌ Failed to read output: {e}")
            return False

    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def main():
    """Run progressive tests."""
    print("="*60)
    print("Progressive SDK Testing in Novita Sandbox")
    print("="*60)

    # Create sandbox
    print("\n1. Creating sandbox...")
    try:
        envs = {}
        # Prefer OAuth token over API key (uses subscription instead of pay-per-use)
        if os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
            envs["CLAUDE_CODE_OAUTH_TOKEN"] = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        elif os.getenv("ANTHROPIC_API_KEY"):
            envs["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")

        if os.getenv("GITHUB_TOKEN"):
            envs["GITHUB_TOKEN"] = os.getenv("GITHUB_TOKEN")

        sandbox = Sandbox.create(
            template="cloud-agent-v1",
            envs=envs,
            timeout=600,
        )
        print(f"✅ Created sandbox: {sandbox.sandbox_id}")
    except Exception as e:
        print(f"❌ Failed to create sandbox: {e}")
        return 1

    try:
        # Upload script
        print("\n2. Uploading sandbox_agent.py...")
        sandbox.files.write("/tmp/sandbox_agent.py", script_content)
        print("✅ Uploaded script")

        # Clone a simple repo
        print("\n3. Cloning test repository...")
        result = sandbox.commands.run(
            "git clone https://github.com/anthropics/anthropic-sdk-python.git /home/user/repo"
        )
        if result.exit_code != 0:
            print(f"❌ Failed to clone: {result.stderr}")
            return 1
        print("✅ Cloned repository")

        # Test 1: Simple question (no tools)
        success = test_task(
            sandbox,
            "Test 1: Simple question (no tools)",
            "What is 2+2? Just respond with the number."
        )
        if not success:
            print("\n❌ Test 1 failed - stopping")
            return 1

        # Test 2: Read a file (Read tool)
        success = test_task(
            sandbox,
            "Test 2: Read README (Read tool)",
            "Read the README.md file and tell me what this repository is about in one sentence."
        )
        if not success:
            print("\n❌ Test 2 failed - stopping")
            return 1

        # Test 3: List files (Bash tool)
        success = test_task(
            sandbox,
            "Test 3: List files (Bash tool)",
            "Run 'ls -la' and tell me how many Python files are in the root directory."
        )
        if not success:
            print("\n❌ Test 3 failed - stopping")
            return 1

        # Test 4: Create a simple file (Write tool)
        success = test_task(
            sandbox,
            "Test 4: Create file (Write tool)",
            "Create a file called test.txt with the text 'Hello World'."
        )
        if not success:
            print("\n❌ Test 4 failed - stopping")
            return 1

        # Test 5: Multiple tool calls
        success = test_task(
            sandbox,
            "Test 5: Multiple tools",
            "Create a file called math.py with a function that adds two numbers, then read it back to verify."
        )
        if not success:
            print("\n❌ Test 5 failed - stopping")
            return 1

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)

    finally:
        print(f"\nCleaning up sandbox {sandbox.sandbox_id}...")
        sandbox.kill()
        print("✅ Sandbox killed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
