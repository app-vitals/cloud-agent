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
        - Claude Agent SDK installation (avoids uv overhead)
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

        # Install Claude Agent SDK globally using uv (avoid inline script overhead)
        logger.info("Installing Claude Agent SDK...")
        result = SandboxService.run_command(
            sandbox,
            "uv pip install --system claude-agent-sdk",
            timeout=60
        )
        if result.exit_code != 0:
            error = f"Failed to install Claude Agent SDK: {result.stderr}"
            logger.error(error)
            raise RuntimeError(error)
        logger.info("Successfully installed Claude Agent SDK")

        # Install claude-toolkit (provides /review-pr and other commands)
        logger.info("Installing claude-toolkit...")
        # Configure git credential helper to use environment variable
        SandboxService.run_command(
            sandbox,
            'git config --global credential.helper "!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f"',
        )
        result = SandboxService.run_command(
            sandbox,
            "git clone https://github.com/app-vitals/claude-toolkit.git /home/user/.claude-toolkit",
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

            # Create or checkout task branch
            if task.branch_name:
                # Resuming - checkout existing branch
                branch_name = task.branch_name
                logger.info(f"Checking out existing branch {branch_name}")
                result = SandboxService.run_command(
                    sandbox, f"cd /home/user/repo && git checkout {branch_name}"
                )
                if result.exit_code != 0:
                    error = f"Failed to checkout branch {branch_name}: {result.stderr}"
                    logger.error(error)
                    TaskService.update_task_status(task_id, "failed", result=error)
                    return {"status": "failed", "error": error}
            else:
                # New task - create new branch
                branch_name = f"ca/task/{task_id}"
                logger.info(f"Creating branch {branch_name}")
                result = SandboxService.run_command(
                    sandbox, f"cd /home/user/repo && git checkout -b {branch_name}"
                )
                if result.exit_code != 0:
                    error = f"Failed to create branch {branch_name}: {result.stderr}"
                    logger.error(error)
                    TaskService.update_task_status(task_id, "failed", result=error)
                    return {"status": "failed", "error": error}
                logger.info(f"Created and checked out branch {branch_name}")

            # Run agent with the prompt
            output = SandboxService.run_agent(
                sandbox,
                task_id=task_id,
                prompt=task.prompt,
                resume_session_id=task.session_id,  # Resume if session exists
            )

            # Extract results
            session_id = output.get("session_id")
            agent_result = output.get("result")
            timed_out = output.get("timed_out", False)

            # Determine final status
            if timed_out:
                status = "failed"
                result = f"Task timed out. Partial result: {agent_result or 'None'}"
            elif agent_result:
                status = "completed"
                result = agent_result
            else:
                status = "failed"
                result = "Task failed - no result returned"

            # Commit and push changes if task completed
            if status == "completed":
                logger.info(f"Committing and pushing changes for task {task_id}")

                # Stage all changes
                SandboxService.run_command(sandbox, "cd /home/user/repo && git add -A")

                # Check if there are changes to commit
                status_result = SandboxService.run_command(
                    sandbox, "cd /home/user/repo && git status --porcelain"
                )

                if status_result.stdout.strip():
                    # Commit changes
                    commit_msg = f"Task {task_id}: {task.prompt[:50]}"
                    commit_result = SandboxService.run_command(
                        sandbox,
                        f'cd /home/user/repo && git commit -m "{commit_msg}"'
                    )

                    if commit_result.exit_code == 0:
                        # Push to remote
                        push_result = SandboxService.run_command(
                            sandbox,
                            f"cd /home/user/repo && git push -u origin {branch_name}"
                        )

                        if push_result.exit_code == 0:
                            logger.info(f"Successfully pushed branch {branch_name}")
                        else:
                            logger.warning(f"Failed to push branch: {push_result.stderr}")
                    else:
                        logger.warning(f"Failed to commit changes: {commit_result.stderr}")
                else:
                    logger.info("No changes to commit")

            # Update task with final status
            # Only persist branch_name and session_id if task completed successfully
            if status == "completed":
                TaskService.update_task_status(
                    task_id,
                    status,
                    result=result,
                    session_id=session_id,
                    branch_name=branch_name,
                )
            else:
                TaskService.update_task_status(
                    task_id, status, result=result, session_id=session_id
                )

            logger.info(f"Task {task_id} completed with status {status}")
            return {"status": status, "session_id": session_id}

        finally:
            # Clean up sandbox
            try:
                sandbox.kill()
                logger.info(f"Sandbox {sandbox.sandbox_id} killed")
            except Exception as e:
                logger.error(f"Error killing sandbox: {e}")
