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
