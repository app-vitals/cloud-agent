#!/usr/bin/env python3
"""Check what attributes messages have."""
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
from claude_agent_sdk import query

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

async def check_message_structure():
    if os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")

    async for message in query(prompt="Hello"):
        print(f"\nMessage type: {type(message).__name__}")
        print(f"Has 'role'? {hasattr(message, 'role')}")
        print(f"Has '__class__.__name__'? {hasattr(message.__class__, '__name__')}")
        print(f"Attributes: {[a for a in dir(message) if not a.startswith('_')]}")

        # Check if we can use match/case (Python 3.10+)
        match message:
            case m if type(m).__name__ == "SystemMessage":
                print("✓ Match works with type().__name__")
            case _:
                pass
        break

asyncio.run(check_message_structure())
