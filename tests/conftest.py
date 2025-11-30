"""Pytest configuration and fixtures."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.core.database import clean_database, close_db, get_engine
from app.main import app
from app.models import Task
from app.services import TaskService

# Set test environment
os.environ["APP_ENV"] = "test"


def create_test_task(
    prompt: str = "Test task prompt",
    repository_url: str = "https://github.com/test/repo.git",
) -> Task:
    """Helper function to create a test task with default values."""
    return TaskService.create_task(prompt=prompt, repository_url=repository_url)


@pytest.fixture(autouse=True, scope="function")
def mock_celery_task(mocker):
    """Mock Celery task execution for all tests."""
    mocker.patch("app.tasks.agent_execution.execute_agent_task.delay")


@pytest.fixture(autouse=True, scope="function")
def clean_db():
    """Initialize and clean database for each test."""
    # Create tables
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

    # Clean all tables before test to ensure isolation
    clean_database()

    yield

    # Close DB connections
    close_db()


@pytest.fixture(scope="function")
def test_client():
    """Create a test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def auth_headers():
    """Provide authentication headers for API requests."""
    from app.core.config import settings

    return {"X-API-Key": settings.api_secret_key}
