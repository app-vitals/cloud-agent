#!/usr/bin/env python3
"""
Test if the Novita template is ready and working.

Usage:
    python scripts/test_template.py
"""

import os
import sys
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox

load_dotenv()

def test_template():
    """Test the cloud-agent-v1 template."""
    print("=" * 60)
    print("Testing Novita Template: cloud-agent-v1")
    print("=" * 60)
    print()

    # Configure for Novita
    api_key = os.getenv("NOVITA_API_KEY") or os.getenv("E2B_API_KEY")
    if not api_key:
        print("❌ ERROR: NOVITA_API_KEY not found")
        sys.exit(1)

    if os.getenv("NOVITA_API_KEY"):
        os.environ["E2B_API_KEY"] = os.getenv("NOVITA_API_KEY")
        os.environ["E2B_DOMAIN"] = "sandbox.novita.ai"

    template_name = "cloud-agent-v1"
    print(f"Creating sandbox from template: {template_name}")
    print()

    try:
        # Try to create sandbox from template
        sandbox = Sandbox.create(template=template_name)
        print(f"✓ Sandbox created successfully!")
        print(f"  Sandbox ID: {sandbox.sandbox_id}")
        print()

        # Test if Claude Code is pre-installed
        print("Testing if Claude Code is pre-installed...")
        result = sandbox.commands.run("claude --version")
        if result.exit_code == 0:
            print(f"✓ Claude Code installed: {result.stdout.strip()}")
            # Also check the binary location
            result2 = sandbox.commands.run("which claude")
            if result2.exit_code == 0:
                print(f"  Binary location: {result2.stdout.strip()}")
        else:
            print(f"⚠️  Claude Code not found")
            print(f"   Exit code: {result.exit_code}")

        # Test if gh CLI is pre-installed
        print("\nTesting if gh CLI is pre-installed...")
        result = sandbox.commands.run("which gh")
        if result.exit_code == 0:
            print(f"✓ gh CLI found at: {result.stdout.strip()}")
        else:
            print(f"⚠️  gh CLI not found")

        # Cleanup
        print("\n🧹 Cleaning up...")
        sandbox.kill()
        print("✓ Sandbox killed")

        print()
        print("=" * 60)
        print("✅ Template is working!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if "not found" in str(e).lower() or "404" in str(e):
            print("\n💡 Template may still be building.")
            print("   Building can take 5-10 minutes for this template.")
            print("   You can check status in Novita dashboard:")
            print("   https://novita.ai/dashboard")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_template()
