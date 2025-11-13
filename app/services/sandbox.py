"""Sandbox service for Novita sandbox operations."""

import logging
import os

from e2b_code_interpreter import Sandbox

from app.core.config import settings

logger = logging.getLogger(__name__)


class SandboxService:
    """Service for Novita sandbox operations."""

    @staticmethod
    def create_sandbox(
        repository_url: str,
        anthropic_api_key: str | None = None,
        github_token: str | None = None,
    ) -> Sandbox:
        """Create a new Novita sandbox with environment variables."""
        # Configure for Novita
        os.environ["E2B_API_KEY"] = settings.novita_api_key or ""
        os.environ["E2B_DOMAIN"] = "sandbox.novita.ai"

        # Use system keys as fallback
        final_anthropic_key = anthropic_api_key or settings.system_anthropic_api_key
        final_github_token = github_token or settings.system_github_token

        if not final_anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        if not final_github_token:
            raise ValueError("GITHUB_TOKEN is required")

        # Create sandbox with environment variables
        sandbox = Sandbox.create(
            template="cloud-agent-v1",
            envs={
                "ANTHROPIC_API_KEY": final_anthropic_key,
                "GITHUB_TOKEN": final_github_token,
            },
        )

        logger.info(f"Created sandbox {sandbox.sandbox_id}")
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
        sandbox: Sandbox, prompt: str, timeout: int = 0
    ) -> tuple[int, str, str]:
        """Run Claude Code with the given prompt.

        Args:
            sandbox: The Novita sandbox instance
            prompt: The prompt to send to Claude Code
            timeout: Command timeout in seconds (0 = no timeout)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        # Escape the prompt for shell
        escaped_prompt = prompt.replace('"', '\\"')

        # Build Claude command
        # -p/--print: non-interactive mode (skips workspace trust dialog)
        # --dangerously-skip-permissions: bypass all permission checks (safe in sandbox)
        claude_command = (
            f"cd /home/user/repo && "
            f'echo "{escaped_prompt}" | '
            f"claude -p --dangerously-skip-permissions"
        )

        logger.info(f"Running Claude Code with prompt: {prompt[:100]}...")
        result = sandbox.commands.run(claude_command, timeout=timeout)

        logger.info(f"Claude Code completed with exit code {result.exit_code}")
        return result.exit_code, result.stdout, result.stderr
