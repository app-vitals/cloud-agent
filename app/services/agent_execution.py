"""Agent execution service with business logic."""

import logging
from pathlib import Path
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
                logger.warning(f"Failed to install claude-toolkit: {result.stderr}")
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

            # Restore files and session from parent task if resuming
            resume_session_id = None
            if task.parent_task_id:
                logger.info(f"Resuming from parent task {task.parent_task_id}")
                parent_task = TaskService.get_task_by_id(task.parent_task_id)
                resume_session_id = parent_task.session_id

                # Restore files from parent task
                parent_files_dir = (
                    Path("logs/tasks") / str(task.parent_task_id) / "files"
                )
                if parent_files_dir.exists():
                    logger.info(f"Restoring files from {parent_files_dir}")
                    for file_path in parent_files_dir.rglob("*"):
                        if file_path.is_file():
                            relative_path = file_path.relative_to(parent_files_dir)
                            content = file_path.read_text()
                            sandbox.files.write(
                                f"/home/user/repo/{relative_path}", content
                            )
                            logger.info(f"Restored file: {relative_path}")
                else:
                    logger.info("No files to restore from parent task")

                # Restore session file for conversation resumption
                if resume_session_id:
                    parent_session_file = (
                        Path("logs/tasks") / str(task.parent_task_id) / "session.jsonl"
                    )
                    if parent_session_file.exists():
                        logger.info(f"Restoring session file for {resume_session_id}")
                        session_content = parent_session_file.read_text()
                        # Write to Claude's session directory
                        session_dir = "/home/user/.claude/projects/-home-user-repo"
                        sandbox.files.write(
                            f"{session_dir}/{resume_session_id}.jsonl", session_content
                        )
                        logger.info("Restored session file to Claude's directory")
                    else:
                        logger.warning(
                            f"No session file found at {parent_session_file}"
                        )

            # Run agent with the prompt
            output = SandboxService.run_agent(
                sandbox,
                task_id=task_id,
                prompt=task.prompt,
                resume_session_id=resume_session_id,
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

            # Extract files from sandbox if task completed
            if status == "completed":
                logger.info(f"Extracting files for task {task_id}")

                # Check for any modified or new files
                status_result = SandboxService.run_command(
                    sandbox, "cd /home/user/repo && git status --porcelain"
                )

                if status_result.stdout.strip():
                    # Create task files directory
                    task_dir = Path("logs/tasks") / str(task_id) / "files"
                    task_dir.mkdir(parents=True, exist_ok=True)

                    # Extract each modified/new file
                    for line in status_result.stdout.strip().split("\n"):
                        # Parse file path (skip first 3 chars: status prefix)
                        file_path = line[3:].strip()

                        try:
                            # Read file from sandbox
                            content = sandbox.files.read(f"/home/user/repo/{file_path}")

                            # Save locally preserving directory structure
                            local_file = task_dir / file_path
                            local_file.parent.mkdir(parents=True, exist_ok=True)
                            local_file.write_text(content)

                            logger.info(f"Extracted file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to extract {file_path}: {e}")

                    logger.info(f"Extracted files to {task_dir}")
                else:
                    logger.info("No files to extract")

            # Update task with final status
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
