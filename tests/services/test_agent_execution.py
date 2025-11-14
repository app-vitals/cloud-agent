"""Tests for AgentExecutionService."""

import json
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.encryption import encrypt_data
from app.core.errors import NotFoundError
from app.services import AgentExecutionService, TaskService
from tests.conftest import create_test_task


def test_execute_task_success(mocker):
    """Test successful task execution."""
    # Create a test task
    task = create_test_task(
        prompt="Add hello world function",
        repository_url="https://github.com/test/repo.git",
    )

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"

    mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(True, ""),
    )
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_claude_code",
        return_value=(0, "Success output", ""),
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "completed"
    assert result["exit_code"] == 0

    # Verify sandbox was killed
    mock_sandbox.kill.assert_called_once()


def test_execute_task_clone_failure(mocker):
    """Test task execution with repository clone failure."""
    # Create a test task
    task = create_test_task()

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"

    mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(False, "Failed to clone: repository not found"),
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "failed"
    assert "Failed to clone" in result["error"]

    # Verify sandbox was killed
    mock_sandbox.kill.assert_called_once()


def test_execute_task_claude_failure(mocker):
    """Test task execution with Claude Code failure."""
    # Create a test task
    task = create_test_task()

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"

    mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(True, ""),
    )
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_claude_code",
        return_value=(1, "Partial output", "Error: command failed"),
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "failed"
    assert result["exit_code"] == 1

    # Verify sandbox was killed
    mock_sandbox.kill.assert_called_once()


def test_execute_task_not_found(mocker):
    """Test execution of non-existent task."""
    from uuid import uuid4

    non_existent_id = uuid4()

    with pytest.raises(NotFoundError):
        AgentExecutionService.execute_task(non_existent_id)


def test_execute_task_sandbox_cleanup_error(mocker):
    """Test that sandbox cleanup errors are logged but don't fail the task."""
    # Create a test task
    task = create_test_task()

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"
    mock_sandbox.kill.side_effect = Exception("Sandbox already killed")

    mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(True, ""),
    )
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_claude_code",
        return_value=(0, "Success", ""),
    )

    # Execute the task - should not raise even though cleanup fails
    result = AgentExecutionService.execute_task(task.id)

    # Verify result is still successful
    assert result["status"] == "completed"
    assert result["exit_code"] == 0


def test_execute_task_with_encrypted_api_keys(mocker):
    """Test that encrypted API keys are decrypted and passed to sandbox."""
    # Setup encryption key
    encryption_key = Fernet.generate_key().decode()
    mocker.patch.object(settings, "encryption_key", encryption_key)

    # Create task with encrypted API keys
    api_keys = {
        "ANTHROPIC_API_KEY": "sk-ant-test123",
        "GITHUB_TOKEN": "ghp_test456",
    }
    api_keys_json = json.dumps(api_keys)
    encrypted_keys = encrypt_data(api_keys_json, encryption_key)

    # Create task manually to set encrypted_api_keys
    task = create_test_task()
    TaskService.update_task_status(task.id, "pending")
    # Update the task in the database with encrypted keys
    from app.core.database import get_session
    from app.models import Task

    with get_session() as session:
        db_task = session.get(Task, task.id)
        db_task.encrypted_api_keys = encrypted_keys
        session.add(db_task)
        session.commit()

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"

    mock_create_sandbox = mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(True, ""),
    )
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_claude_code",
        return_value=(0, "Success", ""),
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "completed"

    # Verify create_sandbox was called with decrypted API keys
    mock_create_sandbox.assert_called_once()
    call_kwargs = mock_create_sandbox.call_args.kwargs
    assert "api_keys" in call_kwargs
    assert call_kwargs["api_keys"] == api_keys


def test_execute_task_without_api_keys(mocker):
    """Test task execution without API keys."""
    # Create task without API keys
    task = create_test_task()

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"

    mock_create_sandbox = mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(True, ""),
    )
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_claude_code",
        return_value=(0, "Success", ""),
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "completed"

    # Verify create_sandbox was called with None for api_keys
    mock_create_sandbox.assert_called_once()
    call_kwargs = mock_create_sandbox.call_args.kwargs
    assert "api_keys" in call_kwargs
    assert call_kwargs["api_keys"] is None


def test_execute_task_decryption_failure(mocker):
    """Test that decryption failures are handled gracefully."""
    # Setup encryption key
    encryption_key = Fernet.generate_key().decode()
    mocker.patch.object(settings, "encryption_key", encryption_key)

    # Create task with invalid encrypted data
    task = create_test_task()
    from app.core.database import get_session
    from app.models import Task

    with get_session() as session:
        db_task = session.get(Task, task.id)
        db_task.encrypted_api_keys = "invalid-encrypted-data"
        session.add(db_task)
        session.commit()

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"

    mock_create_sandbox = mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(True, ""),
    )
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_claude_code",
        return_value=(0, "Success", ""),
    )

    # Execute the task - should continue without custom API keys
    result = AgentExecutionService.execute_task(task.id)

    # Verify result is still successful
    assert result["status"] == "completed"

    # Verify create_sandbox was called without API keys (due to decryption failure)
    mock_create_sandbox.assert_called_once()
    call_kwargs = mock_create_sandbox.call_args.kwargs
    assert call_kwargs["api_keys"] is None


def test_execute_task_no_encryption_key_set(mocker):
    """Test execution when encryption key is not configured."""
    # Mock no encryption key
    mocker.patch.object(settings, "encryption_key", None)

    # Create task with encrypted_api_keys field set (shouldn't happen in practice)
    task = create_test_task()
    from app.core.database import get_session
    from app.models import Task

    with get_session() as session:
        db_task = session.get(Task, task.id)
        db_task.encrypted_api_keys = "some-encrypted-data"
        session.add(db_task)
        session.commit()

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-123"

    mock_create_sandbox = mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )
    mocker.patch("app.services.agent_execution.SandboxService.setup_git_config")
    mocker.patch(
        "app.services.agent_execution.SandboxService.clone_repository",
        return_value=(True, ""),
    )
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_claude_code",
        return_value=(0, "Success", ""),
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "completed"

    # Verify create_sandbox was called without API keys (no encryption key configured)
    mock_create_sandbox.assert_called_once()
    call_kwargs = mock_create_sandbox.call_args.kwargs
    assert call_kwargs["api_keys"] is None
