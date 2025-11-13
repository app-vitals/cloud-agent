"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

# Create Celery app
app = Celery("cloud-agent")

# Configure Celery
app.conf.update(
    # Broker configuration
    broker_url=settings.celery_broker_url,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Result backend - disabled (fire-and-forget pattern, state tracked in PostgreSQL)
    result_backend=None,
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Task execution
    task_track_started=True,
    task_acks_late=True,  # Acknowledge after task completion
    worker_prefetch_multiplier=1,  # Only fetch one task at a time
    # Task routing
    task_routes={
        "app.tasks.agent_execution.*": {"queue": "agent_execution"},
    },
)

# Auto-discover tasks from app.tasks module
app.autodiscover_tasks(["app.tasks"])
