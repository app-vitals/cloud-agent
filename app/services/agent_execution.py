"""Agent execution service with business logic."""

import logging
from uuid import UUID

from app.services.sandbox import SandboxService
from app.services.task import TaskService

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Service for agent execution business logic."""

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

            # Set up git
            SandboxService.setup_git_config(sandbox)

            # Clone repository
            success, error = SandboxService.clone_repository(
                sandbox, task.repository_url
            )
            if not success:
                TaskService.update_task_status(task_id, "failed", result=error)
                return {"status": "failed", "error": error}

            # Run Claude Code with the prompt
            exit_code, stdout, stderr = SandboxService.run_claude_code(
                sandbox, task.prompt
            )

            # Determine final status
            if exit_code == 0:
                status = "completed"
                result = stdout
            else:
                status = "failed"
                result = f"Exit code {exit_code}:\n{stderr}\n{stdout}"

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
