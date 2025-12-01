"""Task service for business logic."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select

from app.core.database import get_session
from app.core.errors import NotFoundError
from app.models import Task

logger = logging.getLogger(__name__)


@dataclass
class TaskFile:
    """Represents a file from a task."""

    path: str
    content: str
    size: int


class TaskService:
    """Service for task-related business logic."""

    @staticmethod
    def create_task(
        prompt: str,
        repository_url: str,
        parent_task_id: UUID | None = None,
    ) -> Task:
        """Create a new task and queue it for execution."""
        with get_session() as session:
            task = Task(
                prompt=prompt,
                repository_url=repository_url,
                status="pending",
                parent_task_id=parent_task_id,
            )
            session.add(task)
            session.commit()
            session.refresh(task)

            # Queue task for execution
            from app.tasks import execute_agent_task

            execute_agent_task.delay(str(task.id))

            return task

    @staticmethod
    def get_task_by_id(task_id: UUID) -> Task:
        """Get task by ID."""
        with get_session() as session:
            statement = select(Task).where(Task.id == task_id)
            result = session.execute(statement)
            task = result.scalar_one_or_none()

            if task is None:
                raise NotFoundError(f"Task with id {task_id} not found")

            return task

    @staticmethod
    def list_tasks(limit: int = 100, offset: int = 0) -> tuple[list[Task], int]:
        """List all tasks with pagination."""
        with get_session() as session:
            # Get total count
            count_statement = select(func.count()).select_from(Task)
            total = session.execute(count_statement).scalar()

            # Get paginated results ordered by created_at desc
            statement = (
                select(Task)
                .order_by(Task.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            tasks = session.execute(statement).scalars().all()

            return list(tasks), total

    @staticmethod
    def update_task_status(
        task_id: UUID,
        status: str,
        result: str | None = None,
        sandbox_id: str | None = None,
        session_id: str | None = None,
    ) -> Task:
        """Update task status and result."""
        with get_session() as session:
            statement = select(Task).where(Task.id == task_id)
            task = session.execute(statement).scalar_one_or_none()

            if task is None:
                raise NotFoundError(f"Task with id {task_id} not found")

            task.status = status
            task.updated_at = datetime.now(UTC)
            if result is not None:
                task.result = result
            if sandbox_id is not None:
                task.sandbox_id = sandbox_id
            if session_id is not None:
                task.session_id = session_id

            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    @staticmethod
    def get_task_logs(
        task_id: UUID, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict], int]:
        """Get logs for a task from filesystem with pagination.

        Reads from session.jsonl file (JSONL format - one JSON object per line).
        Streams line-by-line to avoid loading entire file into memory.

        Args:
            task_id: UUID of the task
            limit: Maximum number of log lines to return
            offset: Number of log lines to skip

        Returns:
            Tuple of (logs, total_count)
        """
        # Verify task exists
        TaskService.get_task_by_id(task_id)

        # Read logs from session file (JSONL format)
        log_file = Path("logs/tasks") / str(task_id) / "session.jsonl"
        if not log_file.exists():
            logger.warning(f"No logs found for task {task_id}")
            return [], 0

        try:
            logs = []
            total = 0
            line_num = 0

            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    total += 1

                    # Skip lines before offset
                    if line_num < offset:
                        line_num += 1
                        continue

                    # Stop if we've collected enough
                    if len(logs) >= limit:
                        # Continue counting total but don't parse
                        continue

                    # Parse and add to results
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse log line {line_num}: {e}")
                        logs.append({"error": "Failed to parse", "raw": line})

                    line_num += 1

            return logs, total
        except Exception as e:
            logger.error(f"Failed to read logs for task {task_id}: {e}")
            return [], 0

    @staticmethod
    def get_task_files(task_id: UUID) -> list[TaskFile]:
        """Get modified files from a completed task.

        Args:
            task_id: Task UUID

        Returns:
            List of TaskFile objects with path, content, and size

        Raises:
            NotFoundError: If task not found
            ValueError: If task is not completed
        """
        task = TaskService.get_task_by_id(task_id)

        if task.status != "completed":
            raise ValueError("Task must be completed to retrieve files")

        files_dir = Path("logs/tasks") / str(task_id) / "files"
        if not files_dir.exists():
            return []

        files = []
        for file_path in files_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(files_dir)
                content = file_path.read_text()
                files.append(
                    TaskFile(
                        path=str(relative_path),
                        content=content,
                        size=len(content),
                    )
                )

        return files

    @staticmethod
    def get_task_session(task_id: UUID) -> tuple[str, str]:
        """Get session data for resuming a task locally.

        Args:
            task_id: Task UUID

        Returns:
            Tuple of (session_id, session_data)

        Raises:
            NotFoundError: If task or session file not found
        """
        task = TaskService.get_task_by_id(task_id)

        session_file = Path("logs/tasks") / str(task_id) / "session.jsonl"
        if not session_file.exists():
            raise NotFoundError(f"Session file not found for task {task_id}")

        session_data = session_file.read_text()

        return task.session_id or "", session_data
