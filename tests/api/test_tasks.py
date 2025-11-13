"""Tests for task API endpoints."""

from app.services import TaskService
from tests.conftest import create_test_task


def test_create_task(test_client):
    """Test POST /v1/tasks endpoint."""
    response = test_client.post(
        "/v1/tasks",
        json={
            "prompt": "Test task via API",
            "repository_url": "https://github.com/test/repo.git",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["prompt"] == "Test task via API"
    assert data["repository_url"] == "https://github.com/test/repo.git"
    assert data["status"] == "pending"
    assert data["result"] is None
    assert data["sandbox_id"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_task(test_client):
    """Test GET /v1/tasks/{task_id} endpoint."""
    task = create_test_task(prompt="Task to retrieve via API")

    response = test_client.get(f"/v1/tasks/{task.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task.id)
    assert data["prompt"] == task.prompt
    assert data["status"] == task.status


def test_get_task_not_found(test_client):
    """Test GET /v1/tasks/{task_id} with non-existent ID."""
    from uuid import uuid4

    non_existent_id = uuid4()
    response = test_client.get(f"/v1/tasks/{non_existent_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_list_tasks_empty(test_client):
    """Test GET /v1/tasks with no tasks."""
    response = test_client.get("/v1/tasks")

    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["total"] == 0
    assert data["limit"] == 100
    assert data["offset"] == 0


def test_list_tasks(test_client):
    """Test GET /v1/tasks endpoint."""
    # Create multiple tasks
    task1 = create_test_task(prompt="Task 1")
    task2 = create_test_task(prompt="Task 2")
    task3 = create_test_task(prompt="Task 3")

    response = test_client.get("/v1/tasks")

    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 3
    assert data["total"] == 3
    assert data["limit"] == 100
    assert data["offset"] == 0

    # Tasks should be in reverse chronological order
    assert data["tasks"][0]["id"] == str(task3.id)
    assert data["tasks"][1]["id"] == str(task2.id)
    assert data["tasks"][2]["id"] == str(task1.id)


def test_list_tasks_with_pagination(test_client):
    """Test GET /v1/tasks with pagination."""
    # Create multiple tasks
    for i in range(5):
        create_test_task(prompt=f"Task {i}")

    # Get first page
    response = test_client.get("/v1/tasks?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Get second page
    response = test_client.get("/v1/tasks?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 2


def test_health_check(test_client):
    """Test GET /health endpoint."""
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_task_logs(test_client):
    """Test GET /v1/tasks/{task_id}/logs endpoint."""
    task = create_test_task(prompt="Task with logs")

    # Store some logs
    stdout = '{"type":"system","subtype":"init"}\n{"type":"assistant","message":"test"}'
    stderr = "Some error"
    TaskService.store_task_logs(task.id, stdout, stderr)

    response = test_client.get(f"/v1/tasks/{task.id}/logs")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # 2 stdout + 1 stderr
    assert len(data["logs"]) == 3
    assert data["limit"] == 100
    assert data["offset"] == 0

    # Check first log
    assert data["logs"][0]["task_id"] == str(task.id)
    assert data["logs"][0]["stream"] == "stdout"
    assert data["logs"][0]["format"] == "json"
    assert "id" in data["logs"][0]
    assert "created_at" in data["logs"][0]


def test_get_task_logs_pagination(test_client):
    """Test GET /v1/tasks/{task_id}/logs with pagination."""
    task = create_test_task(prompt="Task with many logs")

    # Create multiple log lines
    stdout = "\n".join([f'{{"line":{i}}}' for i in range(10)])
    TaskService.store_task_logs(task.id, stdout, "")

    # Get first page
    response = test_client.get(f"/v1/tasks/{task.id}/logs?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 5
    assert data["total"] == 10
    assert data["limit"] == 5
    assert data["offset"] == 0

    # Get second page
    response = test_client.get(f"/v1/tasks/{task.id}/logs?limit=5&offset=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 5
    assert data["total"] == 10


def test_get_task_logs_not_found(test_client):
    """Test GET /v1/tasks/{task_id}/logs with non-existent task."""
    from uuid import uuid4

    non_existent_id = uuid4()
    response = test_client.get(f"/v1/tasks/{non_existent_id}/logs")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_task_logs_empty(test_client):
    """Test GET /v1/tasks/{task_id}/logs with no logs."""
    task = create_test_task(prompt="Task without logs")

    response = test_client.get(f"/v1/tasks/{task.id}/logs")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["logs"]) == 0
