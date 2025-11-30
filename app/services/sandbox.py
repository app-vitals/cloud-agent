"""Sandbox service for Novita sandbox operations."""

import json
import logging
import os
from pathlib import Path
from uuid import UUID

from e2b import CommandExitException, TimeoutException
from e2b_code_interpreter import Sandbox

from app.core.config import settings

logger = logging.getLogger(__name__)


class SandboxService:
    """Service for Novita sandbox operations."""

    @staticmethod
    def create_sandbox(
        repository_url: str,
        anthropic_api_key: str | None = None,
        claude_code_oauth_token: str | None = None,
        github_token: str | None = None,
    ) -> Sandbox:
        """Create a new Novita sandbox with environment variables."""
        # Configure for Novita
        os.environ["E2B_API_KEY"] = settings.novita_api_key or ""
        os.environ["E2B_DOMAIN"] = "sandbox.novita.ai"

        # Use settings as fallback
        final_anthropic_key = anthropic_api_key or settings.anthropic_api_key
        final_claude_code_oauth_token = (
            claude_code_oauth_token or settings.claude_code_oauth_token
        )
        final_github_token = github_token or settings.github_token

        if not final_anthropic_key and not final_claude_code_oauth_token:
            raise ValueError(
                "Either ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN is required"
            )
        if not final_github_token:
            raise ValueError("GITHUB_TOKEN is required")

        # Create sandbox with environment variables and timeout
        # Only include non-None environment variables
        envs = {}
        if final_anthropic_key is not None:
            envs["ANTHROPIC_API_KEY"] = final_anthropic_key
        if final_claude_code_oauth_token is not None:
            envs["CLAUDE_CODE_OAUTH_TOKEN"] = final_claude_code_oauth_token
        if final_github_token is not None:
            envs["GITHUB_TOKEN"] = final_github_token

        sandbox = Sandbox.create(
            template="cloud-agent-v1",
            timeout=settings.sandbox_timeout,
            envs=envs,
        )

        logger.info(
            f"Created sandbox {sandbox.sandbox_id} with {settings.sandbox_timeout}s timeout"
        )

        # Start PostgreSQL and Redis services
        logger.info("Starting PostgreSQL and Redis services...")
        result = sandbox.commands.run("start-services", timeout=30)
        if result.exit_code == 0:
            logger.info("Services started successfully")
        else:
            logger.warning(
                f"Failed to start services (exit {result.exit_code}): {result.stderr}"
            )

        return sandbox

    @staticmethod
    def run_command(sandbox: Sandbox, command: str, timeout: int | None = None) -> any:
        """Run a command in the sandbox.

        Thin wrapper around sandbox.commands.run() that catches exceptions
        and returns result with exit_code, stdout, stderr.

        Args:
            sandbox: The sandbox instance
            command: Command to run
            timeout: Optional timeout in seconds

        Returns:
            Command result object with exit_code, stdout, stderr
            (even for non-zero exit codes)
        """
        try:
            return sandbox.commands.run(command, timeout=timeout)
        except CommandExitException as e:
            # E2B raises exception for non-zero exit codes, but we can still get the output
            # Return a result-like object with the error details
            class CommandResult:
                def __init__(self, exit_code, stdout, stderr):
                    self.exit_code = exit_code
                    self.stdout = stdout
                    self.stderr = stderr

            return CommandResult(
                exit_code=e.exit_code,
                stdout=e.stdout if hasattr(e, "stdout") else "",
                stderr=e.stderr if hasattr(e, "stderr") else str(e),
            )

    @staticmethod
    def run_agent(
        sandbox: Sandbox,
        task_id: UUID,
        prompt: str,
        resume_session_id: str | None = None,
        timeout: int | None = None,
    ) -> dict:
        """Run agent task using Claude Agent SDK.

        Args:
            sandbox: The Novita sandbox instance
            task_id: UUID of the task (for filesystem storage)
            prompt: The prompt to send to the agent
            resume_session_id: Optional session ID to resume from
            timeout: Command timeout in seconds (None = use default from settings)

        Returns:
            Dict with keys:
                - session_id: Claude session ID for resumption
                - result: Final result from agent
                - cost: Total cost in USD
                - duration_ms: Duration in milliseconds
                - num_turns: Number of conversation turns
                - timed_out: True if task timed out
                - logs: List of message log entries
        """
        # Use default timeout from settings if not provided
        if timeout is None:
            timeout = settings.claude_code_timeout

        logger.info(
            f"Running agent task {task_id} with prompt: {prompt[:100]}... (timeout: {timeout}s)"
        )

        # Read sandbox_agent.py script content
        script_path = Path(__file__).parent.parent.parent / "scripts" / "sandbox_agent.py"
        script_content = script_path.read_text()

        # Write script to sandbox
        sandbox.files.write("/tmp/sandbox_agent.py", script_content)

        # Write task input
        task_input = {"prompt": prompt}
        if resume_session_id:
            task_input["resume_session_id"] = resume_session_id
        sandbox.files.write("/tmp/task_input.json", json.dumps(task_input))

        # Run agent with timeout (using system python3, SDK is pre-installed)
        timed_out = False
        try:
            result = sandbox.commands.run(
                "cd /home/user/repo && python3 /tmp/sandbox_agent.py",
                timeout=timeout
            )
            exit_code = result.exit_code
            logger.info(f"Agent task {task_id} completed with exit code {exit_code}")
        except TimeoutException:
            logger.warning(f"Agent task {task_id} timed out after {timeout}s")
            timed_out = True
        except Exception as e:
            logger.error(f"Agent task {task_id} failed with exception: {e}")
            raise

        # Read outputs from sandbox (exist even if timed out due to progressive flushing)
        try:
            output_json = sandbox.files.read("/tmp/task_output.json")
            output = json.loads(output_json)
        except Exception as e:
            logger.error(f"Failed to read task output: {e}")
            output = {
                "session_id": None,
                "result": f"Error: Failed to read output - {e}",
                "cost": 0,
                "duration_ms": 0,
                "num_turns": 0,
            }

        # Store session file (serves as logs - no separate log file needed!)
        task_dir = Path("logs/tasks") / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        session_id = output.get("session_id")
        if session_id:
            try:
                # Session files are in ~/.claude/projects/<normalized-path>/{session_id}.jsonl
                # The repo is cloned to /home/user/repo
                session_file_path = f"/home/user/.claude/projects/-home-user-repo/{session_id}.jsonl"
                session_jsonl = sandbox.files.read(session_file_path)
                (task_dir / "session.jsonl").write_text(session_jsonl)
                logger.info(f"Stored session file for task {task_id}")
            except Exception as e:
                logger.warning(f"Failed to store session file: {e}")
                # Create empty session file if not found
                (task_dir / "session.jsonl").write_text("")
        else:
            # No session created (likely errored early), create empty file
            (task_dir / "session.jsonl").write_text("")

        # Add timed_out flag to output
        output["timed_out"] = timed_out

        return output
