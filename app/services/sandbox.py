"""Sandbox service for Novita sandbox operations."""

import json
import logging
import os
import shlex
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
        """Run agent task using Claude CLI directly.

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
                - timed_out: True if task timed out
        """
        # Use default timeout from settings if not provided
        if timeout is None:
            timeout = settings.claude_code_timeout

        logger.info(
            f"Running agent task {task_id} with prompt: {prompt[:100]}... (timeout: {timeout}s)"
        )

        # Build Claude command using shlex.quote() for safe escaping
        # Pipe prompt via stdin (like original CLI wrapper)
        # -p: non-interactive mode (skips workspace trust dialog)
        # --dangerously-skip-permissions: bypass all permission checks (safe in sandbox)
        # --output-format json: get structured JSON response with session_id and result
        claude_cmd = f"cd /home/user/repo && echo {shlex.quote(prompt)} | claude -p --dangerously-skip-permissions"

        if resume_session_id:
            claude_cmd += f" --resume {shlex.quote(resume_session_id)}"

        claude_cmd += " --output-format json"

        # Run Claude with E2B timeout (no need for bash timeout wrapper)
        timed_out = False
        session_id = None
        result_text = None

        try:
            result = SandboxService.run_command(sandbox, claude_cmd, timeout=timeout)
            exit_code = result.exit_code
            stdout = result.stdout
            logger.info(f"Agent task {task_id} completed with exit code {exit_code}")

            # Parse JSON response to extract session_id and result
            if stdout.strip():
                try:
                    response = json.loads(stdout)
                    session_id = response.get("session_id")
                    result_text = response.get("result")
                    logger.info(f"Session ID: {session_id}")
                    logger.info(
                        f"Result: {result_text[:100] if result_text else 'None'}..."
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Stdout: {stdout[:500]}")

        except TimeoutException:
            logger.warning(f"Agent task {task_id} timed out after {timeout}s")
            timed_out = True
        except Exception as e:
            logger.error(f"Agent task {task_id} failed with exception: {e}")
            raise

        # Store session file from Claude's project directory
        # Always read from filesystem instead of relying on JSON output
        # (which may not be available on timeout)
        task_dir = Path("logs/tasks") / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Claude stores sessions in ~/.claude/projects/<normalized-path>/
            session_dir = "/home/user/.claude/projects/-home-user-repo"

            # List all .jsonl files in the session directory
            # There should be exactly one session file per sandbox (one task per sandbox)
            ls_result = SandboxService.run_command(
                sandbox, f"ls -1 {session_dir}/*.jsonl 2>/dev/null || true"
            )

            session_files = [
                f.strip() for f in ls_result.stdout.strip().split("\n") if f.strip()
            ]

            if session_files:
                # Use the first (and should be only) session file
                session_file_path = session_files[0]
                session_filename = Path(session_file_path).name
                discovered_session_id = session_filename.replace(".jsonl", "")

                # Read session content
                session_jsonl = sandbox.files.read(session_file_path)
                (task_dir / "session.jsonl").write_text(session_jsonl)

                # Update session_id if we didn't get it from JSON output
                if not session_id:
                    session_id = discovered_session_id
                    logger.info(f"Discovered session ID from filesystem: {session_id}")

                logger.info(
                    f"Stored session file for task {task_id} ({len(session_jsonl)} bytes)"
                )
            else:
                logger.warning(f"No session files found in {session_dir}")
                # Create empty session file
                (task_dir / "session.jsonl").write_text("")
        except Exception as e:
            logger.warning(f"Failed to store session file: {e}")
            # Create empty session file if extraction failed
            (task_dir / "session.jsonl").write_text("")

        return {
            "session_id": session_id,
            "result": result_text or ("Task timed out" if timed_out else "No result"),
            "timed_out": timed_out,
        }
