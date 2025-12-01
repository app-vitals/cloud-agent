"""Tests for ApiClientService."""

import os

import httpx
import pytest

from app.services.api_client import ApiClientService


def test_get_client_default_values(mocker):
    """Test get_client with default values from environment."""
    mocker.patch.dict(
        os.environ,
        {"CLOUD_AGENT_URL": "http://test.example.com", "API_SECRET_KEY": "test-key"},
    )

    client = ApiClientService.get_client()

    assert isinstance(client, httpx.Client)
    assert str(client.base_url) == "http://test.example.com"
    assert client.headers["X-API-Key"] == "test-key"
    assert client.timeout.read == 30.0
    client.close()


def test_get_client_with_explicit_values():
    """Test get_client with explicitly provided values."""
    client = ApiClientService.get_client(
        base_url="http://custom.example.com", api_key="custom-key"
    )

    assert isinstance(client, httpx.Client)
    assert str(client.base_url) == "http://custom.example.com"
    assert client.headers["X-API-Key"] == "custom-key"
    assert client.timeout.read == 30.0
    client.close()


def test_get_client_fallback_defaults(mocker):
    """Test get_client falls back to defaults when env vars not set."""
    # Set environment to have empty API key (httpx doesn't allow None in headers)
    mocker.patch.dict(
        os.environ, {"CLOUD_AGENT_URL": "http://localhost:8000", "API_SECRET_KEY": ""}
    )

    client = ApiClientService.get_client()

    assert isinstance(client, httpx.Client)
    assert str(client.base_url) == "http://localhost:8000"
    assert client.headers["X-API-Key"] == ""
    client.close()


def test_create_task_success(mocker):
    """Test creating a task successfully."""
    # Mock httpx.Client
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "id": "task-123",
        "prompt": "Test prompt",
        "repository_url": "https://github.com/test/repo.git",
        "status": "pending",
    }

    mock_client = mocker.Mock(spec=httpx.Client)
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = mocker.Mock(return_value=mock_client)
    mock_client.__exit__ = mocker.Mock(return_value=False)

    mocker.patch.object(ApiClientService, "get_client", return_value=mock_client)

    task = ApiClientService.create_task(
        prompt="Test prompt", repository_url="https://github.com/test/repo.git"
    )

    assert task["id"] == "task-123"
    assert task["prompt"] == "Test prompt"
    assert task["status"] == "pending"
    mock_client.post.assert_called_once_with(
        "/v1/tasks",
        json={
            "prompt": "Test prompt",
            "repository_url": "https://github.com/test/repo.git",
        },
    )
    mock_response.raise_for_status.assert_called_once()


def test_create_task_with_parent_task_id(mocker):
    """Test creating a task with parent_task_id."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "id": "task-456",
        "prompt": "Resume task",
        "repository_url": "https://github.com/test/repo.git",
        "status": "pending",
        "parent_task_id": "task-123",
    }

    mock_client = mocker.Mock(spec=httpx.Client)
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = mocker.Mock(return_value=mock_client)
    mock_client.__exit__ = mocker.Mock(return_value=False)

    mocker.patch.object(ApiClientService, "get_client", return_value=mock_client)

    task = ApiClientService.create_task(
        prompt="Resume task",
        repository_url="https://github.com/test/repo.git",
        parent_task_id="task-123",
    )

    assert task["id"] == "task-456"
    assert task["parent_task_id"] == "task-123"
    mock_client.post.assert_called_once_with(
        "/v1/tasks",
        json={
            "prompt": "Resume task",
            "repository_url": "https://github.com/test/repo.git",
            "parent_task_id": "task-123",
        },
    )


def test_create_task_with_provided_client(mocker):
    """Test creating a task with a provided client (should not close it)."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "id": "task-789",
        "prompt": "Test",
        "repository_url": "https://github.com/test/repo.git",
        "status": "pending",
    }

    mock_client = mocker.Mock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    task = ApiClientService.create_task(
        prompt="Test",
        repository_url="https://github.com/test/repo.git",
        client=mock_client,
    )

    assert task["id"] == "task-789"
    # Client.close() should NOT be called when client is provided
    mock_client.close.assert_not_called()


def test_create_task_http_error(mocker):
    """Test creating a task with HTTP error."""
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=mocker.Mock(), response=mocker.Mock(status_code=404)
    )

    mock_client = mocker.Mock(spec=httpx.Client)
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = mocker.Mock(return_value=mock_client)
    mock_client.__exit__ = mocker.Mock(return_value=False)

    mocker.patch.object(ApiClientService, "get_client", return_value=mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        ApiClientService.create_task(
            prompt="Test", repository_url="https://github.com/test/repo.git"
        )


def test_get_task_success(mocker):
    """Test getting a task successfully."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "id": "task-123",
        "prompt": "Test task",
        "repository_url": "https://github.com/test/repo.git",
        "status": "completed",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:05:00Z",
    }

    mock_client = mocker.Mock(spec=httpx.Client)
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = mocker.Mock(return_value=mock_client)
    mock_client.__exit__ = mocker.Mock(return_value=False)

    mocker.patch.object(ApiClientService, "get_client", return_value=mock_client)

    task = ApiClientService.get_task("task-123")

    assert task["id"] == "task-123"
    assert task["status"] == "completed"
    mock_client.get.assert_called_once_with("/v1/tasks/task-123")
    mock_response.raise_for_status.assert_called_once()


def test_get_task_with_provided_client(mocker):
    """Test getting a task with a provided client (should not close it)."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "id": "task-456",
        "prompt": "Test",
        "status": "pending",
    }

    mock_client = mocker.Mock(spec=httpx.Client)
    mock_client.get.return_value = mock_response

    task = ApiClientService.get_task("task-456", client=mock_client)

    assert task["id"] == "task-456"
    # Client.close() should NOT be called when client is provided
    mock_client.close.assert_not_called()


def test_get_task_not_found(mocker):
    """Test getting a non-existent task."""
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=mocker.Mock(), response=mocker.Mock(status_code=404)
    )

    mock_client = mocker.Mock(spec=httpx.Client)
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = mocker.Mock(return_value=mock_client)
    mock_client.__exit__ = mocker.Mock(return_value=False)

    mocker.patch.object(ApiClientService, "get_client", return_value=mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        ApiClientService.get_task("non-existent-id")


def test_wait_for_task_completed_immediately(mocker):
    """Test wait_for_task when task is already completed."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_get_task.return_value = {
        "id": "task-123",
        "status": "completed",
        "prompt": "Test task",
        "result": "Task completed successfully",
    }

    result = ApiClientService.wait_for_task("task-123")

    assert result["id"] == "task-123"
    assert result["status"] == "completed"
    mock_get_task.assert_called_once_with("task-123")


def test_wait_for_task_failed_immediately(mocker):
    """Test wait_for_task when task has already failed."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_get_task.return_value = {
        "id": "task-456",
        "status": "failed",
        "prompt": "Test task",
        "result": "Task failed with error",
    }

    result = ApiClientService.wait_for_task("task-456")

    assert result["id"] == "task-456"
    assert result["status"] == "failed"
    mock_get_task.assert_called_once_with("task-456")


def test_wait_for_task_cancelled_immediately(mocker):
    """Test wait_for_task when task is cancelled."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_get_task.return_value = {
        "id": "task-789",
        "status": "cancelled",
        "prompt": "Test task",
    }

    result = ApiClientService.wait_for_task("task-789")

    assert result["id"] == "task-789"
    assert result["status"] == "cancelled"
    mock_get_task.assert_called_once_with("task-789")


def test_wait_for_task_polling_until_completed(mocker):
    """Test wait_for_task polls until task completes."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_sleep = mocker.patch("time.sleep")

    # Simulate task progression: pending -> running -> completed
    mock_get_task.side_effect = [
        {"id": "task-123", "status": "pending"},
        {"id": "task-123", "status": "running"},
        {"id": "task-123", "status": "completed", "result": "Success"},
    ]

    result = ApiClientService.wait_for_task("task-123", poll_interval=5)

    assert result["id"] == "task-123"
    assert result["status"] == "completed"
    assert result["result"] == "Success"
    assert mock_get_task.call_count == 3
    # Should sleep twice (after first two polls)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(5)


def test_wait_for_task_polling_until_failed(mocker):
    """Test wait_for_task polls until task fails."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_sleep = mocker.patch("time.sleep")

    # Simulate task progression: pending -> running -> failed
    mock_get_task.side_effect = [
        {"id": "task-456", "status": "pending"},
        {"id": "task-456", "status": "running"},
        {"id": "task-456", "status": "failed", "result": "Error occurred"},
    ]

    result = ApiClientService.wait_for_task("task-456", poll_interval=3)

    assert result["id"] == "task-456"
    assert result["status"] == "failed"
    assert result["result"] == "Error occurred"
    assert mock_get_task.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(3)


def test_wait_for_task_custom_poll_interval(mocker):
    """Test wait_for_task respects custom poll interval."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_sleep = mocker.patch("time.sleep")

    mock_get_task.side_effect = [
        {"id": "task-123", "status": "pending"},
        {"id": "task-123", "status": "completed"},
    ]

    ApiClientService.wait_for_task("task-123", poll_interval=10)

    mock_sleep.assert_called_once_with(10)


def test_wait_for_task_timeout(mocker):
    """Test wait_for_task raises TimeoutError when timeout exceeded."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_sleep = mocker.patch("time.sleep")
    mock_time = mocker.patch("time.time")

    # Simulate time progression to exceed timeout
    # Start time: 0, first check: 5, second check: 11 (exceeds timeout of 10)
    mock_time.side_effect = [0, 5, 11]

    mock_get_task.return_value = {"id": "task-123", "status": "running"}

    with pytest.raises(TimeoutError) as exc_info:
        ApiClientService.wait_for_task("task-123", timeout=10, poll_interval=5)

    assert "Task task-123 did not complete within 10s" in str(exc_info.value)
    # Should check once, sleep, then timeout before second check
    assert mock_get_task.call_count == 1
    mock_sleep.assert_called_once_with(5)


def test_wait_for_task_timeout_on_first_check(mocker):
    """Test wait_for_task raises TimeoutError immediately if already timed out."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_time = mocker.patch("time.time")

    # Simulate already exceeded timeout
    mock_time.side_effect = [0, 11]

    with pytest.raises(TimeoutError) as exc_info:
        ApiClientService.wait_for_task("task-123", timeout=10)

    assert "Task task-123 did not complete within 10s" in str(exc_info.value)
    # Should not call get_task if timeout already exceeded
    mock_get_task.assert_not_called()


def test_wait_for_task_default_timeout(mocker):
    """Test wait_for_task uses default timeout of 600 seconds."""
    mocker.patch.object(ApiClientService, "get_task")
    mock_time = mocker.patch("time.time")

    # Simulate time progression to exceed default timeout
    mock_time.side_effect = [0, 601]

    with pytest.raises(TimeoutError) as exc_info:
        ApiClientService.wait_for_task("task-123")

    assert "Task task-123 did not complete within 600s" in str(exc_info.value)


def test_wait_for_task_http_error(mocker):
    """Test wait_for_task propagates HTTP errors from get_task."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_get_task.side_effect = httpx.HTTPStatusError(
        "Internal Server Error",
        request=mocker.Mock(),
        response=mocker.Mock(status_code=500),
    )

    with pytest.raises(httpx.HTTPStatusError):
        ApiClientService.wait_for_task("task-123")


def test_wait_for_task_many_polls(mocker):
    """Test wait_for_task handles many polling iterations."""
    mock_get_task = mocker.patch.object(ApiClientService, "get_task")
    mock_sleep = mocker.patch("time.sleep")

    # Simulate 10 polls before completion
    pending_responses = [{"id": "task-123", "status": "running"}] * 9
    completed_response = {"id": "task-123", "status": "completed"}
    mock_get_task.side_effect = [*pending_responses, completed_response]

    result = ApiClientService.wait_for_task("task-123", poll_interval=2)

    assert result["status"] == "completed"
    assert mock_get_task.call_count == 10
    assert mock_sleep.call_count == 9
    mock_sleep.assert_called_with(2)
