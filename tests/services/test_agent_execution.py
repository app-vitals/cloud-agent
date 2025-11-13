"""Tests for AgentExecutionService."""

from unittest.mock import MagicMock

import pytest

from app.core.errors import NotFoundError
from app.services import AgentExecutionService
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
