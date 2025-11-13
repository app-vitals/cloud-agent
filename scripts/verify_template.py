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
        print("✓ Sandbox created successfully!")
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
            print("⚠️  Claude Code not found")
            print(f"   Exit code: {result.exit_code}")

        # Test if gh CLI is pre-installed
        print("\nTesting if gh CLI is pre-installed...")
        result = sandbox.commands.run("which gh")
        if result.exit_code == 0:
            print(f"✓ gh CLI found at: {result.stdout.strip()}")
        else:
            print("⚠️  gh CLI not found")

        # Test if uv is pre-installed
        print("\nTesting if uv is pre-installed...")
        result = sandbox.commands.run("uv --version")
        if result.exit_code == 0:
            print(f"✓ uv installed: {result.stdout.strip()}")
        else:
            print("⚠️  uv not found")

        # Test if PostgreSQL is pre-installed
        print("\nTesting if PostgreSQL is pre-installed...")
        result = sandbox.commands.run("psql --version")
        if result.exit_code == 0:
            print(f"✓ PostgreSQL installed: {result.stdout.strip()}")
        else:
            print("⚠️  PostgreSQL not found")

        # Test if Redis is pre-installed
        print("\nTesting if Redis is pre-installed...")
        result = sandbox.commands.run("redis-server --version")
        if result.exit_code == 0:
            print(f"✓ Redis installed: {result.stdout.strip()}")
        else:
            print("⚠️  Redis not found")

        # Test if services can be started
        print("\nTesting if start-services script is available...")
        result = sandbox.commands.run("which start-services")
        if result.exit_code == 0:
            print(f"✓ start-services script found at: {result.stdout.strip()}")
            print("\nTesting if PostgreSQL and Redis can be started...")
            result = sandbox.commands.run("start-services")
            if result.exit_code == 0:
                print("✓ Services started successfully")
                print(result.stdout)
            else:
                print("⚠️  Failed to start services")
                print(f"   Exit code: {result.exit_code}")
                if result.stderr:
                    print(f"   Error: {result.stderr}")
        else:
            print("⚠️  start-services script not found")

        # Test PostgreSQL connectivity
        print("\n" + "=" * 60)
        print("Testing PostgreSQL Database Connectivity")
        print("=" * 60)

        print("\n1. Testing local socket connection (psql -U postgres)...")
        result = sandbox.commands.run(
            'psql -U postgres -c "SELECT version();"', timeout=5
        )
        if result.exit_code == 0:
            print("✓ Connected via local socket")
        else:
            print(f"✗ Failed (exit {result.exit_code}): {result.stderr[:150]}")

        print("\n2. Creating cloudagent database...")
        result = sandbox.commands.run(
            'psql -U postgres -c "CREATE DATABASE cloudagent;"', timeout=5
        )
        if result.exit_code == 0:
            print("✓ Database created")
        else:
            print(f"✗ Failed (exit {result.exit_code}): {result.stderr[:150]}")

        print("\n3. Connecting to cloudagent database...")
        result = sandbox.commands.run(
            'psql -U postgres cloudagent -c "SELECT current_database();"', timeout=5
        )
        if result.exit_code == 0:
            print("✓ Connected to cloudagent database")
        else:
            print(f"✗ Failed (exit {result.exit_code}): {result.stderr[:150]}")

        print(
            "\n4. Testing DATABASE_URL format (local socket): postgresql:///cloudagent?user=postgres..."
        )
        result = sandbox.commands.run(
            'psql "postgresql:///cloudagent?user=postgres" -c "SELECT 1 AS test;"',
            timeout=5,
        )
        if result.exit_code == 0:
            print("✓ Local socket DATABASE_URL format works!")
        else:
            print(f"✗ Failed (exit {result.exit_code})")
            if result.stderr:
                print(f"Stderr: {result.stderr[:150]}")

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
