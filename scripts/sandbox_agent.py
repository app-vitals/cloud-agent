#!/usr/bin/env python3
"""Agent script that runs inside the sandbox using the Claude Agent SDK.

This script is uploaded to the sandbox and executed to run agent tasks.
It reads configuration from /tmp/task_input.json and writes results to /tmp/task_output.json.

Usage (in sandbox):
    # New session
    echo '{"prompt": "Fix the bug"}' > /tmp/task_input.json
    python3 /tmp/sandbox_agent.py

    # Resume existing session
    echo '{"prompt": "Continue fixing", "resume_session_id": "abc-123"}' > /tmp/task_input.json
    python3 /tmp/sandbox_agent.py

Note: Requires claude-agent-sdk to be installed (done during sandbox setup)
"""

import asyncio
import json
import signal
import sys
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions

# Global state for signal handling
results = {}


def save_partial_results():
    """Save whatever results we have so far (called on timeout/interrupt)."""
    try:
        # Write partial results
        Path("/tmp/task_output.json").write_text(json.dumps(results, indent=2))
        print("Saved partial results before exit", file=sys.stderr)
    except Exception as e:
        print(f"Error saving partial results: {e}", file=sys.stderr)


def signal_handler(signum, frame):
    """Handle SIGTERM from timeout command."""
    print(f"Received signal {signum}, saving partial results...", file=sys.stderr)
    save_partial_results()
    sys.exit(124)  # Exit with same code as timeout command


async def main():
    """Run the agent task and write results to file."""
    global results

    # Register signal handler for SIGTERM (sent by timeout command)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🤖 Agent starting...", flush=True)

    # Read task configuration from input file
    task_input = json.loads(Path("/tmp/task_input.json").read_text())
    prompt = task_input["prompt"]
    resume_session_id = task_input.get("resume_session_id")

    print(f"📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}", flush=True)

    if resume_session_id:
        print(f"🔄 Resuming session: {resume_session_id}", flush=True)

    # Initialize results
    results = {
        "session_id": None,
        "result": None,
        "cost": 0,
        "duration_ms": 0,
        "num_turns": 0,
    }

    # Configure options (with resume if provided)
    options = ClaudeAgentOptions(permission_mode="bypassPermissions")
    if resume_session_id:
        options.resume = resume_session_id

    # Execute agent task
    # Note: We don't collect logs here - the session .jsonl file has everything
    async for message in query(prompt=prompt, options=options):
        msg_type = type(message).__name__

        if msg_type == "SystemMessage":
            # Capture session ID from init message
            results["session_id"] = message.data.get("session_id")
            # Flush results too
            Path("/tmp/task_output.json").write_text(json.dumps(results, indent=2))
            print(f"🆔 Session: {results['session_id']}", flush=True)

        elif msg_type == "AssistantMessage":
            # Print progress indicator for each assistant message
            print(f"💬 Assistant message", flush=True)

        elif msg_type == "ResultMessage":
            # Capture final results
            results["result"] = message.result
            results["cost"] = message.total_cost_usd or 0
            results["duration_ms"] = message.duration_ms
            results["num_turns"] = message.num_turns
            print(f"✅ Task completed! Turns: {results['num_turns']}, Cost: ${results['cost']:.4f}", flush=True)

    # Write results to output file
    Path("/tmp/task_output.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
