"""Task service for business logic."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select

from app.core.database import get_session
from app.core.errors import NotFoundError
from app.models import Task

logger = logging.getLogger(__name__)


class TaskService:
    """Service for task-related business logic."""

    @staticmethod
    def create_task(prompt: str, repository_url: str) -> Task:
        """Create a new task and queue it for execution."""
        with get_session() as session:
            task = Task(prompt=prompt, repository_url=repository_url, status="pending")
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

            session.add(task)
            session.commit()
            session.refresh(task)
            return task
