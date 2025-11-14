"""Tests for TaskService."""

import json

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.encryption import decrypt_data
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


def test_create_task_with_api_keys(mocker):
    """Test creating a task with API keys encrypts them."""
    # Mock the encryption key
    encryption_key = Fernet.generate_key().decode()
    mocker.patch.object(settings, "encryption_key", encryption_key)

    prompt = "Test task with API keys"
    repository_url = "https://github.com/test/repo.git"
    api_keys = {
        "ANTHROPIC_API_KEY": "sk-ant-test123",
        "GITHUB_TOKEN": "ghp_test456",
    }

    task = TaskService.create_task(
        prompt=prompt, repository_url=repository_url, api_keys=api_keys
    )

    # Verify task was created
    assert task.id is not None
    assert task.prompt == prompt
    assert task.repository_url == repository_url
    assert task.status == "pending"

    # Verify API keys were encrypted and stored
    assert task.encrypted_api_keys is not None
    assert task.encrypted_api_keys != json.dumps(api_keys)

    # Verify encrypted data can be decrypted back to original
    decrypted_json = decrypt_data(task.encrypted_api_keys, encryption_key)
    decrypted_keys = json.loads(decrypted_json)
    assert decrypted_keys == api_keys


def test_create_task_without_api_keys():
    """Test creating a task without API keys."""
    prompt = "Test task without API keys"
    repository_url = "https://github.com/test/repo.git"

    task = TaskService.create_task(prompt=prompt, repository_url=repository_url)

    # Verify task was created without encrypted keys
    assert task.id is not None
    assert task.encrypted_api_keys is None


def test_create_task_with_api_keys_no_encryption_key(mocker):
    """Test creating a task with API keys when encryption key is not set."""
    # Mock no encryption key
    mocker.patch.object(settings, "encryption_key", None)

    prompt = "Test task"
    repository_url = "https://github.com/test/repo.git"
    api_keys = {"ANTHROPIC_API_KEY": "sk-ant-test123"}

    task = TaskService.create_task(
        prompt=prompt, repository_url=repository_url, api_keys=api_keys
    )

    # Verify task was created but API keys were not encrypted
    assert task.id is not None
    assert task.encrypted_api_keys is None


def test_create_task_api_keys_not_exposed_in_response(mocker):
    """Test that raw API keys are not stored in task object."""
    # Mock the encryption key
    encryption_key = Fernet.generate_key().decode()
    mocker.patch.object(settings, "encryption_key", encryption_key)

    api_keys = {
        "ANTHROPIC_API_KEY": "sk-ant-secret-key",
        "GITHUB_TOKEN": "ghp_secret_token",
    }

    task = TaskService.create_task(
        prompt="Test",
        repository_url="https://github.com/test/repo.git",
        api_keys=api_keys,
    )

    # Verify raw API keys are not in any task field
    # Convert UUID to string for JSON serialization
    task_dict = task.model_dump()
    task_dict["id"] = str(task_dict["id"])
    task_dict["created_at"] = task_dict["created_at"].isoformat()
    task_dict["updated_at"] = task_dict["updated_at"].isoformat()
    task_json = json.dumps(task_dict)

    assert "sk-ant-secret-key" not in task_json
    assert "ghp_secret_token" not in task_json
    assert task.encrypted_api_keys is not None


def test_create_task_with_empty_api_keys_dict(mocker):
    """Test creating a task with empty API keys dictionary."""
    encryption_key = Fernet.generate_key().decode()
    mocker.patch.object(settings, "encryption_key", encryption_key)

    task = TaskService.create_task(
        prompt="Test",
        repository_url="https://github.com/test/repo.git",
        api_keys={},
    )

    # Empty dict is falsy in Python, so it won't be encrypted
    # The condition `if api_keys and settings.encryption_key:` evaluates to False
    assert task.encrypted_api_keys is None


def test_create_task_with_multiple_api_keys(mocker):
    """Test creating a task with multiple API keys."""
    encryption_key = Fernet.generate_key().decode()
    mocker.patch.object(settings, "encryption_key", encryption_key)

    api_keys = {
        "ANTHROPIC_API_KEY": "sk-ant-key1",
        "GITHUB_TOKEN": "ghp_token1",
        "OPENAI_API_KEY": "sk-openai-key1",
        "CUSTOM_API_KEY": "custom-key-123",
    }

    task = TaskService.create_task(
        prompt="Test",
        repository_url="https://github.com/test/repo.git",
        api_keys=api_keys,
    )

    # Verify all keys were encrypted and can be decrypted
    assert task.encrypted_api_keys is not None
    decrypted_json = decrypt_data(task.encrypted_api_keys, encryption_key)
    decrypted_keys = json.loads(decrypted_json)
    assert len(decrypted_keys) == 4
    assert decrypted_keys == api_keys
