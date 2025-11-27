"""Agent execution service with business logic."""

import logging
from uuid import UUID

from app.services.sandbox import SandboxService
from app.services.task import TaskService

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Service for agent execution business logic."""

    @staticmethod
    def setup_sandbox_environment(sandbox) -> None:
        """Set up complete sandbox environment for task execution.

        This includes:
        - Git configuration
        - Claude toolkit installation (custom slash commands)

        Args:
            sandbox: The Novita sandbox instance
        """
        logger.info("Setting up sandbox environment...")

        # Configure git
        SandboxService.run_command(
            sandbox, 'git config --global user.email "agent@cloudagent.dev"'
        )
        SandboxService.run_command(
            sandbox, 'git config --global user.name "Cloud Agent"'
        )
        logger.info("Git configured")

        # Install claude-toolkit (provides /review-pr and other commands)
        logger.info("Installing claude-toolkit...")
        result = SandboxService.run_command(
            sandbox,
            "git clone https://github.com/dmcaulay/claude-toolkit.git /home/user/.claude-toolkit",
        )

        if result.exit_code == 0:
            # Run install script
            result = SandboxService.run_command(
                sandbox, "cd /home/user/.claude-toolkit/commands && ./install.sh"
            )

            if result.exit_code == 0:
                logger.info("Successfully installed claude-toolkit")
            else:
                logger.warning(
                    f"Failed to install claude-toolkit: {result.stderr}"
                )
        else:
            logger.warning(f"Failed to clone claude-toolkit: {result.stderr}")

    @staticmethod
    def execute_task(task_id: UUID) -> dict[str, str | int]:
        """Execute an agent task.

        Args:
            task_id: UUID of the task to execute

        Returns:
            Dict with status and exit_code

        Raises:
            NotFoundError: If task not found
        """
        # Get task from database
        task = TaskService.get_task_by_id(task_id)

        # Update status to running
        TaskService.update_task_status(task_id, "running")

        # Create sandbox
        logger.info(f"Creating sandbox for task {task_id}")
        sandbox = SandboxService.create_sandbox(repository_url=task.repository_url)

        try:
            # Update task with sandbox ID
            TaskService.update_task_status(
                task_id, "running", sandbox_id=sandbox.sandbox_id
            )

            # Set up sandbox environment (git, toolkit, etc.)
            AgentExecutionService.setup_sandbox_environment(sandbox)

            # Clone repository
            logger.info(f"Cloning repository {task.repository_url}")
            result = SandboxService.run_command(
                sandbox, f"git clone {task.repository_url} /home/user/repo"
            )

            if result.exit_code != 0:
                error = f"Failed to clone repo: {result.stderr}"
                logger.error(error)
                TaskService.update_task_status(task_id, "failed", result=error)
                return {"status": "failed", "error": error}

            logger.info(f"Cloned repository {task.repository_url}")

            # Run Claude Code with the prompt
            exit_code, stdout, stderr = SandboxService.run_claude_code(
                sandbox, task.prompt
            )

            # Store logs from execution
            TaskService.store_task_logs(task_id, stdout, stderr)

            # Determine final status
            if exit_code == 0:
                status = "completed"
                result = "Task completed successfully"
            else:
                status = "failed"
                result = f"Task failed with exit code {exit_code}"

            # Update task with final status
            TaskService.update_task_status(task_id, status, result=result)

            logger.info(f"Task {task_id} completed with status {status}")
            return {"status": status, "exit_code": exit_code}

        finally:
            # Clean up sandbox
            try:
                sandbox.kill()
                logger.info(f"Sandbox {sandbox.sandbox_id} killed")
            except Exception as e:
                logger.error(f"Error killing sandbox: {e}")
