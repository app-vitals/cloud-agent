"""Task API endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import verify_api_key
from app.core.errors import NotFoundError
from app.services import TaskService

router = APIRouter()


class TaskCreate(BaseModel):
    """Request model for creating a task."""

    prompt: str
    repository_url: str
    session_id: str | None = None
    branch_name: str | None = None


class TaskResponse(BaseModel):
    """Response model for task data."""

    id: str
    prompt: str
    repository_url: str
    status: str
    result: str | None
    sandbox_id: str | None
    session_id: str | None
    branch_name: str | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Response model for list of tasks."""

    tasks: list[TaskResponse]
    total: int
    limit: int
    offset: int


class TaskLogResponse(BaseModel):
    """Response model for a task log entry (SDK message)."""

    type: str
    data: dict


class TaskLogListResponse(BaseModel):
    """Response model for list of task logs."""

    logs: list[TaskLogResponse]
    total: int
    limit: int
    offset: int


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task_data: TaskCreate, api_key: str = Depends(verify_api_key)):
    """Create a new task."""
    task = TaskService.create_task(
        prompt=task_data.prompt,
        repository_url=task_data.repository_url,
        session_id=task_data.session_id,
        branch_name=task_data.branch_name,
    )

    return TaskResponse(
        id=str(task.id),
        prompt=task.prompt,
        status=task.status,
        result=task.result,
        sandbox_id=task.sandbox_id,
        session_id=task.session_id,
        branch_name=task.branch_name,
        repository_url=task.repository_url,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: UUID, api_key: str = Depends(verify_api_key)):
    """Get a task by ID."""
    try:
        task = TaskService.get_task_by_id(task_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return TaskResponse(
        id=str(task.id),
        prompt=task.prompt,
        status=task.status,
        result=task.result,
        sandbox_id=task.sandbox_id,
        session_id=task.session_id,
        branch_name=task.branch_name,
        repository_url=task.repository_url,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    limit: int = 100, offset: int = 0, api_key: str = Depends(verify_api_key)
):
    """List all tasks with pagination."""
    tasks, total = TaskService.list_tasks(limit=limit, offset=offset)

    task_responses = [
        TaskResponse(
            id=str(task.id),
            prompt=task.prompt,
            status=task.status,
            result=task.result,
            sandbox_id=task.sandbox_id,
            session_id=task.session_id,
            branch_name=task.branch_name,
            repository_url=task.repository_url,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        for task in tasks
    ]

    return TaskListResponse(
        tasks=task_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/{task_id}/logs", response_model=TaskLogListResponse)
def get_task_logs(
    task_id: UUID,
    limit: int = 100,
    offset: int = 0,
    api_key: str = Depends(verify_api_key),
):
    """Get logs for a task from filesystem with pagination."""
    try:
        # Get logs from filesystem
        logs, total = TaskService.get_task_logs(task_id, limit=limit, offset=offset)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    log_responses = [
        TaskLogResponse(
            type=log.get("type", "unknown"),
            data=log.get("data", {}),
        )
        for log in logs
    ]

    return TaskLogListResponse(
        logs=log_responses,
        total=total,
        limit=limit,
        offset=offset,
    )
