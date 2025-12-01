"""Tests for task API endpoints."""

from pathlib import Path
from uuid import uuid4

from app.services import TaskService
from tests.conftest import create_test_task


def test_create_task(test_client, auth_headers):
    """Test POST /v1/tasks endpoint."""
    response = test_client.post(
        "/v1/tasks",
        json={
            "prompt": "Test task via API",
            "repository_url": "https://github.com/test/repo.git",
        },
        headers=auth_headers,
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


def test_get_task(test_client, auth_headers):
    """Test GET /v1/tasks/{task_id} endpoint."""
    task = create_test_task(prompt="Task to retrieve via API")

    response = test_client.get(f"/v1/tasks/{task.id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task.id)
    assert data["prompt"] == task.prompt
    assert data["status"] == task.status


def test_get_task_not_found(test_client, auth_headers):
    """Test GET /v1/tasks/{task_id} with non-existent ID."""
    non_existent_id = uuid4()
    response = test_client.get(f"/v1/tasks/{non_existent_id}", headers=auth_headers)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_list_tasks_empty(test_client, auth_headers):
    """Test GET /v1/tasks with no tasks."""
    response = test_client.get("/v1/tasks", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["total"] == 0
    assert data["limit"] == 100
    assert data["offset"] == 0


def test_list_tasks(test_client, auth_headers):
    """Test GET /v1/tasks endpoint."""
    # Create multiple tasks
    task1 = create_test_task(prompt="Task 1")
    task2 = create_test_task(prompt="Task 2")
    task3 = create_test_task(prompt="Task 3")

    response = test_client.get("/v1/tasks", headers=auth_headers)

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


def test_list_tasks_with_pagination(test_client, auth_headers):
    """Test GET /v1/tasks with pagination."""
    # Create multiple tasks
    for i in range(5):
        create_test_task(prompt=f"Task {i}")

    # Get first page
    response = test_client.get("/v1/tasks?limit=2&offset=0", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Get second page
    response = test_client.get("/v1/tasks?limit=2&offset=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 2


def test_health_check(test_client, auth_headers):
    """Test GET /health endpoint."""
    response = test_client.get("/health", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_task_logs(test_client, auth_headers, mocker):
    """Test GET /v1/tasks/{task_id}/logs endpoint."""
    task = create_test_task(prompt="Task with logs")

    # Mock filesystem logs
    mock_logs = [
        {"type": "SystemMessage", "data": {"session_id": "test-123"}},
        {"type": "AssistantMessage", "data": {"content": "Hello"}},
        {"type": "ResultMessage", "data": {"result": "Done"}},
    ]
    mocker.patch(
        "app.services.task.TaskService.get_task_logs",
        return_value=(mock_logs, 3),
    )

    response = test_client.get(f"/v1/tasks/{task.id}/logs", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["logs"]) == 3
    assert data["limit"] == 100
    assert data["offset"] == 0

    # Check first log
    assert data["logs"][0]["type"] == "SystemMessage"
    assert "session_id" in data["logs"][0]["data"]


def test_get_task_logs_not_found(test_client, auth_headers):
    """Test GET /v1/tasks/{task_id}/logs with non-existent task."""
    non_existent_id = uuid4()
    response = test_client.get(
        f"/v1/tasks/{non_existent_id}/logs", headers=auth_headers
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_task_logs_empty(test_client, auth_headers, mocker):
    """Test GET /v1/tasks/{task_id}/logs with no logs."""
    task = create_test_task(prompt="Task without logs")

    # Mock empty logs
    mocker.patch(
        "app.services.task.TaskService.get_task_logs",
        return_value=([], 0),
    )

    response = test_client.get(f"/v1/tasks/{task.id}/logs", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["logs"]) == 0


def test_get_task_files(test_client, auth_headers, mocker):
    """Test GET /v1/tasks/{task_id}/files."""
    task = create_test_task(prompt="Test task")
    TaskService.update_task_status(task.id, "completed")

    # Mock files directory
    files_dir = Path("logs/tasks") / str(task.id) / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "test.py").write_text("print('hello')")
    (files_dir / "subdir").mkdir()
    (files_dir / "subdir" / "test2.py").write_text("print('world')")

    try:
        response = test_client.get(f"/v1/tasks/{task.id}/files", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == str(task.id)
        assert data["total"] == 2
        assert len(data["files"]) == 2

        # Check file contents
        file_paths = {f["path"] for f in data["files"]}
        assert "test.py" in file_paths
        assert "subdir/test2.py" in file_paths or "subdir\\test2.py" in file_paths
    finally:
        # Cleanup
        import shutil

        shutil.rmtree(files_dir.parent, ignore_errors=True)


def test_get_task_files_not_completed(test_client, auth_headers):
    """Test GET /v1/tasks/{task_id}/files with non-completed task."""
    task = create_test_task(prompt="Running task")
    TaskService.update_task_status(task.id, "running")

    response = test_client.get(f"/v1/tasks/{task.id}/files", headers=auth_headers)

    assert response.status_code == 400
    assert "must be completed" in response.json()["detail"]


def test_get_task_files_no_files(test_client, auth_headers):
    """Test GET /v1/tasks/{task_id}/files with no files."""
    task = create_test_task(prompt="Test task")
    TaskService.update_task_status(task.id, "completed")

    response = test_client.get(f"/v1/tasks/{task.id}/files", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["files"]) == 0


def test_get_task_session(test_client, auth_headers):
    """Test GET /v1/tasks/{task_id}/session."""
    task = create_test_task(prompt="Test task")
    TaskService.update_task_status(task.id, "completed", session_id="test-session-123")

    # Mock session file
    session_dir = Path("logs/tasks") / str(task.id)
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.jsonl"
    session_content = '{"test": "data"}\n'
    session_file.write_text(session_content)

    try:
        response = test_client.get(f"/v1/tasks/{task.id}/session", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == str(task.id)
        assert data["session_id"] == "test-session-123"
        assert data["session_data"] == session_content
    finally:
        # Cleanup
        import shutil

        shutil.rmtree(session_dir, ignore_errors=True)


def test_get_task_session_not_found(test_client, auth_headers):
    """Test GET /v1/tasks/{task_id}/session with missing session file."""
    task = create_test_task(prompt="Test task")
    TaskService.update_task_status(task.id, "completed")

    response = test_client.get(f"/v1/tasks/{task.id}/session", headers=auth_headers)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
