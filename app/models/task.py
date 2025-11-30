"""Task model for agent execution."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


class Task(SQLModel, table=True):
    """Task for agent execution."""

    __tablename__ = "tasks"

    # Primary key and timestamps
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the task",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True)),
        description="Timestamp when the task was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True)),
        description="Timestamp when the task was last updated",
    )

    # Task fields
    prompt: str = Field(
        description="Natural language prompt describing the task to execute"
    )
    status: str = Field(
        default="pending",
        sa_column=Column(String, index=True),
        description="Task status: pending, running, completed, failed",
    )
    result: str | None = Field(
        default=None, description="Task execution result or error message"
    )
    sandbox_id: str | None = Field(
        default=None, description="ID of the sandbox where the task is running"
    )
    session_id: str | None = Field(
        default=None, description="Claude session ID for resumption"
    )
    parent_task_id: UUID | None = Field(
        default=None,
        foreign_key="tasks.id",
        description="Parent task ID to resume from",
    )
    repository_url: str = Field(
        description="GitHub repository URL to clone and work on"
    )
