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

    # Mock setup_sandbox_environment (orchestration logic)
    mocker.patch(
        "app.services.agent_execution.AgentExecutionService.setup_sandbox_environment"
    )

    # Mock run_command for git clone
    mock_result = MagicMock()
    mock_result.exit_code = 0
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        return_value=mock_result,
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
    # Mock setup_sandbox_environment
    mocker.patch(
        "app.services.agent_execution.AgentExecutionService.setup_sandbox_environment"
    )

    # Mock run_command to return failure for git clone
    mock_result = MagicMock()
    mock_result.exit_code = 1
    mock_result.stderr = "repository not found"
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        return_value=mock_result,
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

    # Mock setup_sandbox_environment
    mocker.patch(
        "app.services.agent_execution.AgentExecutionService.setup_sandbox_environment"
    )

    # Mock run_command for successful git clone
    mock_result = MagicMock()
    mock_result.exit_code = 0
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        return_value=mock_result,
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


def test_setup_sandbox_environment_success(mocker):
    """Test successful sandbox environment setup."""
    mock_sandbox = MagicMock()

    # Mock run_command to return success
    mock_result = MagicMock()
    mock_result.exit_code = 0
    mock_run_command = mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        return_value=mock_result,
    )

    # Call setup
    AgentExecutionService.setup_sandbox_environment(mock_sandbox)

    # Verify git config was called (2 commands)
    assert mock_run_command.call_count >= 2

    # Verify git config commands
    calls = [str(call) for call in mock_run_command.call_args_list]
    assert any("git config" in str(call) and "user.email" in str(call) for call in calls)
    assert any("git config" in str(call) and "user.name" in str(call) for call in calls)

    # Verify toolkit clone was attempted
    assert any("claude-toolkit" in str(call) for call in calls)


def test_setup_sandbox_environment_toolkit_clone_failure(mocker):
    """Test sandbox setup when toolkit clone fails."""
    mock_sandbox = MagicMock()

    # Mock run_command: git config succeeds, toolkit clone fails
    call_count = [0]

    def mock_run_command_side_effect(sandbox, command, **kwargs):
        call_count[0] += 1
        mock_result = MagicMock()
        # First two calls (git config) succeed
        if call_count[0] <= 2:
            mock_result.exit_code = 0
        else:
            # Toolkit clone fails
            mock_result.exit_code = 1
            mock_result.stderr = "Failed to clone"
        return mock_result

    mock_run_command = mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        side_effect=mock_run_command_side_effect,
    )

    # Call setup - should not raise despite toolkit failure
    AgentExecutionService.setup_sandbox_environment(mock_sandbox)

    # Verify git config was still called
    assert mock_run_command.call_count >= 2


def test_setup_sandbox_environment_toolkit_install_failure(mocker):
    """Test sandbox setup when toolkit install script fails."""
    mock_sandbox = MagicMock()

    call_count = [0]

    def mock_run_command_side_effect(sandbox, command, **kwargs):
        call_count[0] += 1
        mock_result = MagicMock()
        # Git config + clone succeed
        if call_count[0] <= 3:
            mock_result.exit_code = 0
        else:
            # Install script fails
            mock_result.exit_code = 1
            mock_result.stderr = "Install failed"
        return mock_result

    mock_run_command = mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        side_effect=mock_run_command_side_effect,
    )

    # Call setup - should not raise despite install failure
    AgentExecutionService.setup_sandbox_environment(mock_sandbox)

    # Verify install was attempted
    assert mock_run_command.call_count >= 4


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

    # Mock setup_sandbox_environment
    mocker.patch(
        "app.services.agent_execution.AgentExecutionService.setup_sandbox_environment"
    )

    # Mock run_command for successful git clone
    mock_result = MagicMock()
    mock_result.exit_code = 0
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        return_value=mock_result,
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
