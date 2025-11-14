"""Sandbox service for Novita sandbox operations."""

import logging
import os

from e2b.sandbox.commands.command_handle import CommandExitException
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

        # Use system keys as fallback
        final_anthropic_key = anthropic_api_key or settings.system_anthropic_api_key
        final_claude_code_oauth_token = (
            claude_code_oauth_token or settings.system_claude_code_oauth_token
        )
        final_github_token = github_token or settings.system_github_token

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
    def setup_git_config(sandbox: Sandbox) -> None:
        """Set up git configuration in the sandbox."""
        sandbox.commands.run('git config --global user.email "agent@cloudagent.dev"')
        sandbox.commands.run('git config --global user.name "Cloud Agent"')
        logger.info("Git configured in sandbox")

    @staticmethod
    def clone_repository(sandbox: Sandbox, repository_url: str) -> tuple[bool, str]:
        """Clone repository into the sandbox.

        Returns:
            Tuple of (success, error_message)
        """
        result = sandbox.commands.run(f"git clone {repository_url} /home/user/repo")

        if result.exit_code != 0:
            error_msg = f"Failed to clone repo: {result.stderr}"
            logger.error(error_msg)
            return False, error_msg

        logger.info(f"Cloned repository {repository_url}")
        return True, ""

    @staticmethod
    def run_claude_code(
        sandbox: Sandbox, prompt: str, timeout: int | None = None
    ) -> tuple[int, str, str]:
        """Run Claude Code with the given prompt.

        Args:
            sandbox: The Novita sandbox instance
            prompt: The prompt to send to Claude Code
            timeout: Command timeout in seconds (None = use default from settings)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        # Use default timeout from settings if not provided
        if timeout is None:
            timeout = settings.claude_code_timeout

        # Escape for bash -c with double quotes:
        # Need to escape: double quotes, dollar signs, backticks, and backslashes
        # Single quotes are safe inside double quotes and don't need escaping
        escaped_prompt = (
            prompt.replace("\\", "\\\\")  # Escape backslashes first
            .replace('"', '\\"')  # Escape double quotes
            .replace("$", "\\$")  # Escape dollar signs
            .replace("`", "\\`")  # Escape backticks
        )

        # Build Claude command with timeout
        # -p/--print: non-interactive mode (skips workspace trust dialog)
        # --dangerously-skip-permissions: bypass all permission checks (safe in sandbox)
        # --verbose --output-format stream-json: get structured output with logs
        # timeout command: kills process after specified seconds, sends SIGTERM then SIGKILL
        # Using bash -c with double quotes to avoid complex single quote escaping
        claude_command = (
            f"cd /home/user/repo && "
            f'timeout {timeout} bash -c "echo \\"{escaped_prompt}\\" | '
            f'claude -p --dangerously-skip-permissions --verbose --output-format stream-json"'
        )

        logger.info(
            f"Running Claude Code with prompt: {prompt[:100]}... (timeout: {timeout}s)"
        )

        # Use a long timeout for sandbox.commands.run since we're handling timeout with bash
        try:
            result = sandbox.commands.run(claude_command, timeout=timeout + 30)
            exit_code = result.exit_code
            stdout = result.stdout
            stderr = result.stderr
        except CommandExitException as e:
            # E2B raises exception for non-zero exit codes, but we can still get the output
            exit_code = e.exit_code
            stdout = e.stdout if hasattr(e, "stdout") else ""
            stderr = e.stderr if hasattr(e, "stderr") else str(e)
            logger.info(f"Claude Code exited with non-zero code {exit_code}")

        logger.info(f"Claude Code completed with exit code {exit_code}")

        # Exit code 124 means timeout killed the process
        if exit_code == 124:
            error_msg = f"Claude Code timed out after {timeout}s"
            logger.warning(error_msg)
            return 124, stdout, stderr + f"\n\n{error_msg}"

        return exit_code, stdout, stderr
