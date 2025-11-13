#!/usr/bin/env python3
"""
Test Claude Code's ability to create a GitHub PR in a Novita sandbox.

This script:
1. Creates a sandbox from our custom template
2. Sets up Anthropic and GitHub credentials
3. Asks Claude to execute a custom prompt

Usage:
    python scripts/test_claude_github.py [prompt] [--verbose] [--stream-json]

Examples:
    # Use default PR creation prompt
    python scripts/test_claude_github.py

    # Custom prompt
    python scripts/test_claude_github.py "List all Python files in the repo"

    # With verbose output
    python scripts/test_claude_github.py "Create a PR" --verbose

    # With streaming JSON output
    python scripts/test_claude_github.py "Create a PR" --stream-json
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox

load_dotenv()


def test_claude_github(prompt=None, verbose=False, stream_json=False):
    """Test Claude Code + GitHub integration."""
    print("=" * 60)
    print("Testing Claude Code + GitHub Integration")
    print("=" * 60)
    print()

    # Get required API keys
    novita_key = os.getenv("NOVITA_API_KEY")
    anthropic_key = os.getenv("SYSTEM_ANTHROPIC_API_KEY")
    github_token = os.getenv("SYSTEM_GITHUB_TOKEN")

    if not novita_key:
        print("❌ ERROR: NOVITA_API_KEY not found")
        sys.exit(1)
    if not anthropic_key:
        print("❌ ERROR: SYSTEM_ANTHROPIC_API_KEY not found")
        sys.exit(1)
    if not github_token:
        print("❌ ERROR: SYSTEM_GITHUB_TOKEN not found")
        sys.exit(1)

    # Configure for Novita
    os.environ["E2B_API_KEY"] = novita_key
    os.environ["E2B_DOMAIN"] = "sandbox.novita.ai"

    template_name = "cloud-agent-v1"
    print(f"Creating sandbox from template: {template_name}")
    print()

    try:
        # Create sandbox with environment variables
        sandbox = Sandbox.create(
            template=template_name,
            envs={
                "ANTHROPIC_API_KEY": anthropic_key,
                "GITHUB_TOKEN": github_token,
            },
        )
        print("✓ Sandbox created successfully!")
        print(f"  Sandbox ID: {sandbox.sandbox_id}")
        print()

        # Set up git config (gh CLI will use GITHUB_TOKEN env var automatically)
        print("Setting up git config...")
        sandbox.commands.run('git config --global user.email "test@cloudagent.dev"')
        sandbox.commands.run('git config --global user.name "Cloud Agent Test"')
        print("✓ Git configured")
        print()

        # Clone the repo first
        print("Cloning repository...")
        result = sandbox.commands.run(
            "git clone https://github.com/app-vitals/cloud-agent.git /home/user/cloud-agent"
        )
        if result.exit_code != 0:
            print(f"❌ Failed to clone repo: {result.stderr}")
            sys.exit(1)
        print("✓ Repository cloned")
        print()

        # Prepare the prompt
        if prompt is None:
            prompt = "Create a new branch called 'add-test-file', add a simple test.py file with a hello world function, commit it with a descriptive message, push the branch, and create a pull request with title 'Add test.py file'"

        print(f"Running Claude Code with prompt: {prompt[:100]}...")
        if len(prompt) > 100:
            print(f"  (full prompt: {len(prompt)} characters)")
        print("(this may take a few minutes...)")
        print("-" * 60)

        # Build Claude command
        # -p/--print: non-interactive mode (skips workspace trust dialog)
        # --dangerously-skip-permissions: bypass all permission checks (safe in sandbox)
        claude_flags = "-p --dangerously-skip-permissions"

        # stream-json requires verbose
        if stream_json:
            claude_flags += " --verbose --output-format stream-json"
        elif verbose:
            claude_flags += " --verbose"

        # Escape the prompt for shell
        escaped_prompt = prompt.replace('"', '\\"')
        claude_command = f'cd /home/user/cloud-agent && echo "{escaped_prompt}" | claude {claude_flags}'

        result = sandbox.commands.run(claude_command, timeout=0)

        print("Claude Code output:")
        print(result.stdout)
        if result.stderr:
            print("\nStderr:")
            print(result.stderr)

        print("-" * 60)
        print()

        print(f"Exit code: {result.exit_code}")
        print()

        # Cleanup
        print("🧹 Cleaning up...")
        sandbox.kill()
        print("✓ Sandbox killed")

        print()
        print("=" * 60)
        print("✅ Test completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test Claude Code + GitHub integration in Novita sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default PR creation prompt
  python scripts/test_claude_github.py

  # Custom prompt
  python scripts/test_claude_github.py "List all Python files in the repo"

  # With verbose output to see intermediate steps
  python scripts/test_claude_github.py "Create a PR" --verbose

  # With streaming JSON output
  python scripts/test_claude_github.py "Create a PR" --stream-json
        """,
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Prompt to send to Claude Code (default: create a test PR)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output to see Claude's intermediate steps",
    )
    parser.add_argument(
        "--stream-json", action="store_true", help="Enable streaming JSON output format"
    )

    args = parser.parse_args()
    test_claude_github(
        prompt=args.prompt, verbose=args.verbose, stream_json=args.stream_json
    )
