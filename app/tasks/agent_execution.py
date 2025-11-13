"""Agent execution Celery task."""

import logging
from uuid import UUID

from app.celery_app import app
from app.services import AgentExecutionService, TaskService

logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    name="app.tasks.agent_execution.execute_agent_task",
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=5,
    retry_jitter=True,
)
def execute_agent_task(self, task_id: str):
    """Execute an agent task in a Novita sandbox.

    This is a thin Celery wrapper around AgentExecutionService.

    Args:
        task_id: UUID of the task to execute
    """
    task_uuid = UUID(task_id)

    try:
        return AgentExecutionService.execute_task(task_uuid)
    except Exception as exc:
        logger.error(f"Error executing task {task_id}: {exc}")

        # On final retry, mark as failed in database
        if self.request.retries >= self.max_retries:
            TaskService.update_task_status(
                task_uuid, "failed", result=f"Error: {exc!s}"
            )

        raise exc
