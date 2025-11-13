"""Tests for TaskService."""

import pytest

from app.core.errors import NotFoundError
from app.services import TaskService
from tests.conftest import create_test_task


def test_create_task():
    """Test creating a task."""
    prompt = "Test task for creation"
    repository_url = "https://github.com/test/repo.git"
    task = TaskService.create_task(prompt=prompt, repository_url=repository_url)

    assert task.id is not None
    assert task.prompt == prompt
    assert task.repository_url == repository_url
    assert task.status == "pending"
    assert task.result is None
    assert task.sandbox_id is None
    assert task.created_at is not None
    assert task.updated_at is not None


def test_get_task_by_id():
    """Test getting a task by ID."""
    created_task = create_test_task(prompt="Test task for retrieval")

    retrieved_task = TaskService.get_task_by_id(created_task.id)

    assert retrieved_task.id == created_task.id
    assert retrieved_task.prompt == created_task.prompt
    assert retrieved_task.status == created_task.status


def test_get_task_by_id_not_found():
    """Test getting a non-existent task."""
    from uuid import uuid4

    non_existent_id = uuid4()

    with pytest.raises(NotFoundError) as exc_info:
        TaskService.get_task_by_id(non_existent_id)

    assert f"Task with id {non_existent_id} not found" in str(exc_info.value)


def test_list_tasks():
    """Test listing tasks with pagination."""
    # Create multiple tasks
    create_test_task(prompt="Task 1")
    create_test_task(prompt="Task 2")
    create_test_task(prompt="Task 3")

    # List all tasks
    tasks, total = TaskService.list_tasks(limit=10, offset=0)

    assert len(tasks) == 3
    assert total == 3
    assert tasks[0].prompt == "Task 3"  # Most recent first
    assert tasks[1].prompt == "Task 2"
    assert tasks[2].prompt == "Task 1"


def test_list_tasks_pagination():
    """Test task list pagination."""
    # Create multiple tasks
    for i in range(5):
        create_test_task(prompt=f"Task {i}")

    # Get first page
    tasks_page1, total = TaskService.list_tasks(limit=2, offset=0)
    assert len(tasks_page1) == 2
    assert total == 5

    # Get second page
    tasks_page2, total = TaskService.list_tasks(limit=2, offset=2)
    assert len(tasks_page2) == 2
    assert total == 5

    # Ensure pages are different
    assert tasks_page1[0].id != tasks_page2[0].id


def test_update_task_status():
    """Test updating task status."""
    task = create_test_task(prompt="Task to update")

    updated_task = TaskService.update_task_status(
        task.id, status="running", result="Task is running"
    )

    assert updated_task.id == task.id
    assert updated_task.status == "running"
    assert updated_task.result == "Task is running"
    assert updated_task.updated_at > task.updated_at


def test_update_task_status_not_found():
    """Test updating status of non-existent task."""
    from uuid import uuid4

    non_existent_id = uuid4()

    with pytest.raises(NotFoundError) as exc_info:
        TaskService.update_task_status(non_existent_id, status="completed")

    assert f"Task with id {non_existent_id} not found" in str(exc_info.value)


def test_store_task_logs():
    """Test storing task logs."""
    task = create_test_task(prompt="Task with logs")

    stdout = '{"type":"system","subtype":"init"}\n{"type":"assistant","message":"test"}'
    stderr = "Some error output"

    TaskService.store_task_logs(task.id, stdout, stderr)

    logs, total = TaskService.get_task_logs(task.id)

    assert total == 3  # 2 stdout lines + 1 stderr
    assert logs[0].stream == "stdout"
    assert logs[0].format == "json"
    assert logs[1].stream == "stdout"
    assert logs[1].format == "json"
    assert logs[2].stream == "stderr"
    assert logs[2].format == "text"
    assert logs[2].content == stderr


def test_get_task_logs_pagination():
    """Test getting task logs with pagination."""
    task = create_test_task(prompt="Task with many logs")

    # Create multiple log lines
    stdout = "\n".join([f'{{"line":{i}}}' for i in range(10)])
    TaskService.store_task_logs(task.id, stdout, "")

    # Get first page
    logs_page1, total = TaskService.get_task_logs(task.id, limit=5, offset=0)
    assert len(logs_page1) == 5
    assert total == 10

    # Get second page
    logs_page2, total = TaskService.get_task_logs(task.id, limit=5, offset=5)
    assert len(logs_page2) == 5
    assert total == 10

    # Ensure pages are different
    assert logs_page1[0].id != logs_page2[0].id


def test_get_task_logs_empty():
    """Test getting logs for task with no logs."""
    task = create_test_task(prompt="Task without logs")

    logs, total = TaskService.get_task_logs(task.id)

    assert total == 0
    assert len(logs) == 0
