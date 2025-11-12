#!/usr/bin/env python3
"""
Test Claude Code's ability to create a GitHub PR in a Novita sandbox.

This script:
1. Creates a sandbox from our custom template
2. Sets up Anthropic and GitHub credentials
3. Asks Claude to clone the repo and create a simple PR

Usage:
    python scripts/test_claude_github.py
"""

import os
import sys
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox

load_dotenv()


def test_claude_github():
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
        # Create sandbox
        sandbox = Sandbox.create(template=template_name)
        print(f"✓ Sandbox created successfully!")
        print(f"  Sandbox ID: {sandbox.sandbox_id}")
        print()

        # Set up git config
        print("Setting up git and GitHub CLI...")
        sandbox.commands.run('git config --global user.email "test@cloudagent.dev"')
        sandbox.commands.run('git config --global user.name "Cloud Agent Test"')
        sandbox.commands.run(f'echo "{github_token}" | gh auth login --with-token')
        print("✓ Git and GitHub configured")
        print()

        # Run Claude Code with task
        print("Running Claude Code to create a PR...")
        print("-" * 60)

        # Use ANTHROPIC_API_KEY env var and run Claude Code
        claude_command = f"""export ANTHROPIC_API_KEY="{anthropic_key}" && \
claude --model claude-sonnet-4-5 "Clone https://github.com/app-vitals/cloud-agent, create a new branch called 'test-claude-integration', add a line to the README mentioning this PR was created by Claude Code in a sandbox, commit it, and create a pull request with title 'Test: Claude Code integration'" </dev/null"""

        result = sandbox.commands.run(claude_command, timeout=180)

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
    test_claude_github()
