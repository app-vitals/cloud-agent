"""Task log model for storing execution logs."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlmodel import Field, SQLModel


class TaskLog(SQLModel, table=True):
    """Log entry for task execution."""

    __tablename__ = "task_logs"

    # Primary key and timestamps
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the log entry",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True)),
        description="Timestamp when the log entry was created",
    )

    # Foreign key to task
    task_id: UUID = Field(
        sa_column=Column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True),
        description="ID of the task this log belongs to",
    )

    # Log fields
    stream: str = Field(
        sa_column=Column(String, index=True),
        description="Output stream: stdout or stderr",
    )
    format: str = Field(
        sa_column=Column(String, index=True),
        description="Content format: json, text, or logfmt",
    )
    content: str = Field(
        sa_column=Column(Text),
        description="Raw log content (JSON line from Claude Code or plain text)",
    )
