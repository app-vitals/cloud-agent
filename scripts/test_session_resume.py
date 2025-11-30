#!/usr/bin/env python3
"""Test if SDK sessions can be resumed across different script invocations.

This simulates what would happen when resuming across sandboxes.
"""
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "claude-agent-sdk",
#     "python-dotenv",
# ]
# ///

import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from claude_agent_sdk import query, ClaudeAgentOptions

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

if os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")


async def first_session():
    """Create initial session and save session ID."""
    print("=== First Session ===")
    session_id = None

    async for message in query(prompt="Remember this number: 42. What's 2+2?"):
        if type(message).__name__ == "SystemMessage":
            session_id = message.data.get("session_id")
            print(f"Session ID: {session_id}")
        elif type(message).__name__ == "AssistantMessage":
            for block in message.content:
                if hasattr(block, 'text'):
                    print(f"Response: {block.text}")

    # Save session ID for next run
    Path("/tmp/test_session_id.txt").write_text(session_id)
    print(f"\n✅ Saved session ID: {session_id}")
    print("Run again with 'resume' argument to test resumption\n")


async def resume_session():
    """Try to resume the session from saved ID."""
    print("=== Resuming Session ===")

    # Load session ID from previous run
    session_id = Path("/tmp/test_session_id.txt").read_text().strip()
    print(f"Resuming session: {session_id}\n")

    # Try to resume
    options = ClaudeAgentOptions(resume=session_id)

    try:
        async for message in query(
            prompt="What number did I ask you to remember?",
            options=options
        ):
            if type(message).__name__ == "AssistantMessage":
                for block in message.content:
                    if hasattr(block, 'text'):
                        print(f"Response: {block.text}")
            elif type(message).__name__ == "ResultMessage":
                print(f"\n✅ Resume worked! Claude remembered the context.")
    except Exception as e:
        print(f"\n❌ Resume failed: {e}")
        print("\nThis likely means sessions are stored locally and don't persist")
        print("across different script runs or sandboxes.")


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "resume":
        if not Path("/tmp/test_session_id.txt").exists():
            print("❌ No saved session found. Run without 'resume' first.")
            return
        await resume_session()
    else:
        await first_session()


if __name__ == "__main__":
    asyncio.run(main())
