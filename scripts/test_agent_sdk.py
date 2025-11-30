#!/usr/bin/env python3
"""Test Agent SDK basic functionality.

This script tests the Claude Agent SDK to understand how it works
before integrating into the main codebase.

Usage:
    uv run scripts/test_agent_sdk.py
"""
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "claude-agent-sdk",
#     "python-dotenv",
# ]
# ///

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import query, ClaudeAgentOptions

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def test_basic_query():
    """Test basic query without options."""
    print("Testing basic query...")
    print("-" * 50)

    session_id = None
    async for message in query(prompt="Hello! What's 2+2?"):
        msg_type = type(message).__name__
        print(f"📩 {msg_type}")

        if msg_type == "SystemMessage":
            session_id = message.data.get("session_id")
            print(f"   Session ID: {session_id}")
            print(f"   Claude Code version: {message.data.get('claude_code_version')}")

        elif msg_type == "AssistantMessage":
            for block in message.content:
                if hasattr(block, 'text'):
                    print(f"   💬 {block.text}")

        elif msg_type == "ResultMessage":
            print(f"   ✅ Result: {message.result}")
            print(f"   ⏱️  Duration: {message.duration_ms}ms")
            print(f"   💰 Cost: ${message.total_cost_usd:.6f}")
            print(f"   📊 Turns: {message.num_turns}")
            print(f"   🔑 Session: {message.session_id}")

        print()

    return session_id


async def test_with_working_directory():
    """Test that SDK respects working directory."""
    print("\nTesting working directory...")
    print("-" * 50)

    async for message in query(
        prompt="What is the current working directory? List the files in it."
    ):
        msg_type = type(message).__name__

        if msg_type == "AssistantMessage":
            for block in message.content:
                if hasattr(block, 'text'):
                    print(f"💬 {block.text}")

        elif msg_type == "ResultMessage":
            print(f"\n✅ Completed in {message.duration_ms}ms")

        print()


async def test_file_operations():
    """Test that SDK can perform file operations."""
    print("\nTesting file operations...")
    print("-" * 50)

    async for message in query(
        prompt="Create a file called /tmp/test_agent_sdk.txt with 'Hello from Agent SDK' and then read it back to me."
    ):
        msg_type = type(message).__name__

        if msg_type == "AssistantMessage":
            for block in message.content:
                if hasattr(block, 'text'):
                    print(f"💬 {block.text}")

        elif msg_type == "ResultMessage":
            print(f"\n✅ Success: {message.result[:100]}...")
            print(f"⏱️  Duration: {message.duration_ms}ms")

        print()


async def main():
    """Run all tests."""
    # Check for required environment variables
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
        print("Error: Set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in .env")
        return

    try:
        session_id = await test_basic_query()
        await test_with_working_directory()
        await test_file_operations()

        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        print(f"📝 Session ID: {session_id}")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
