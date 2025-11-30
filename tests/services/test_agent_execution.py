"""Tests for AgentExecutionService."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

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
        "app.services.agent_execution.SandboxService.run_agent",
        return_value={
            "session_id": "test-session-123",
            "result": "Task completed successfully",
            "cost": 0.01,
            "duration_ms": 1000,
            "num_turns": 2,
            "timed_out": False,
            "logs": [],
        },
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "completed"
    assert result["session_id"] == "test-session-123"

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
        "app.services.agent_execution.SandboxService.run_agent",
        return_value={
            "session_id": "test-session-123",
            "result": None,
            "cost": 0.01,
            "duration_ms": 500,
            "num_turns": 1,
            "timed_out": False,
            "logs": [],
        },
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "failed"
    assert (
        "no result" in result.get("error", "").lower()
        or result.get("session_id") is not None
    )

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
    assert any(
        "git config" in str(call) and "user.email" in str(call) for call in calls
    )
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
    non_existent_id = uuid4()

    with pytest.raises(NotFoundError):
        AgentExecutionService.execute_task(non_existent_id)


def test_execute_task_timeout(mocker):
    """Test task execution with timeout."""
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

    # Mock run_command for successful git clone and branch creation
    mock_result = MagicMock()
    mock_result.exit_code = 0
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        return_value=mock_result,
    )

    # Mock run_agent to return timeout
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_agent",
        return_value={
            "session_id": "test-session-123",
            "result": "Partial work done",
            "cost": 0.01,
            "duration_ms": 300000,
            "num_turns": 5,
            "timed_out": True,
            "logs": [],
        },
    )

    # Execute the task
    result = AgentExecutionService.execute_task(task.id)

    # Verify result
    assert result["status"] == "failed"

    # Verify sandbox was killed
    mock_sandbox.kill.assert_called_once()


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

    # Mock run_command for successful git clone and branch creation
    mock_result = MagicMock()
    mock_result.exit_code = 0
    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        return_value=mock_result,
    )

    mocker.patch(
        "app.services.agent_execution.SandboxService.run_agent",
        return_value={
            "session_id": "test-session-123",
            "result": "Task completed successfully",
            "cost": 0.01,
            "duration_ms": 1000,
            "num_turns": 2,
            "timed_out": False,
            "logs": [],
        },
    )

    # Execute the task - should not raise even though cleanup fails
    result = AgentExecutionService.execute_task(task.id)

    # Verify result is still successful
    assert result["status"] == "completed"
    assert result["session_id"] == "test-session-123"


def test_execute_task_file_extraction(mocker):
    """Test file extraction logic is triggered when task completes with changes."""
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

    # Track run_command calls
    run_command_calls = []

    def mock_run_command_side_effect(sandbox, command, **kwargs):
        run_command_calls.append(command)
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.stdout = ""

        if "git status --porcelain" in command:
            # Simulate modified files
            mock_result.stdout = " M test.txt\n"

        return mock_result

    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        side_effect=mock_run_command_side_effect,
    )

    # Mock sandbox.files.read
    mock_sandbox.files.read.return_value = "test content"

    mocker.patch(
        "app.services.agent_execution.SandboxService.run_agent",
        return_value={
            "session_id": "test-session-123",
            "result": "Task completed successfully",
            "timed_out": False,
        },
    )

    try:
        # Execute the task
        result = AgentExecutionService.execute_task(task.id)

        # Verify result
        assert result["status"] == "completed"

        # Verify git status was called to check for changes
        assert any("git status --porcelain" in cmd for cmd in run_command_calls)

        # Verify sandbox.files.read was called to extract file
        assert mock_sandbox.files.read.call_count >= 1

    finally:
        # Clean up
        task_log_dir = Path("logs/tasks") / str(task.id)
        if task_log_dir.exists():
            shutil.rmtree(task_log_dir, ignore_errors=True)


def test_execute_task_with_parent_file_restoration(mocker, tmp_path):
    """Test file and session restoration when resuming from parent task."""
    # Create parent task
    parent_task = create_test_task()
    TaskService.update_task_status(
        parent_task.id, "completed", session_id="parent-session-123"
    )

    # Create parent task files
    parent_files_dir = Path("logs/tasks") / str(parent_task.id) / "files"
    parent_files_dir.mkdir(parents=True, exist_ok=True)
    (parent_files_dir / "existing.txt").write_text("Existing content")

    # Create parent session file
    parent_session_file = Path("logs/tasks") / str(parent_task.id) / "session.jsonl"
    parent_session_file.write_text('{"type":"test","data":"session data"}\n')

    # Create child task
    child_task = create_test_task(parent_task_id=parent_task.id)

    # Mock sandbox service methods
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "test-sandbox-456"

    mocker.patch(
        "app.services.agent_execution.SandboxService.create_sandbox",
        return_value=mock_sandbox,
    )

    # Mock setup_sandbox_environment
    mocker.patch(
        "app.services.agent_execution.AgentExecutionService.setup_sandbox_environment"
    )

    # Mock run_command
    def mock_run_command_side_effect(sandbox, command, **kwargs):
        mock_result = MagicMock()
        if "git clone" in command:
            mock_result.exit_code = 0
        elif "git status --porcelain" in command:
            mock_result.exit_code = 0
            mock_result.stdout = ""  # No new files
        return mock_result

    mocker.patch(
        "app.services.agent_execution.SandboxService.run_command",
        side_effect=mock_run_command_side_effect,
    )

    # Track sandbox.files.write calls
    write_calls = []

    def mock_files_write(file_path, content):
        write_calls.append((file_path, content))

    mock_sandbox.files.write.side_effect = mock_files_write

    mocker.patch(
        "app.services.agent_execution.SandboxService.run_agent",
        return_value={
            "session_id": "child-session-123",
            "result": "Task resumed successfully",
            "cost": 0.02,
            "duration_ms": 2000,
            "num_turns": 3,
            "timed_out": False,
            "logs": [],
        },
    )

    try:
        # Execute the child task
        result = AgentExecutionService.execute_task(child_task.id)

        # Verify result
        assert result["status"] == "completed"

        # Verify files were restored
        repo_writes = [call for call in write_calls if "/home/user/repo/" in call[0]]
        assert len(repo_writes) >= 1
        assert any("existing.txt" in call[0] for call in repo_writes)
        assert any("Existing content" in call[1] for call in repo_writes)

        # Verify session file was restored
        session_writes = [call for call in write_calls if ".claude/projects" in call[0]]
        assert len(session_writes) == 1
        assert "parent-session-123.jsonl" in session_writes[0][0]
        assert "session data" in session_writes[0][1]

    finally:
        # Clean up
        shutil.rmtree(Path("logs/tasks") / str(parent_task.id), ignore_errors=True)
        shutil.rmtree(Path("logs/tasks") / str(child_task.id), ignore_errors=True)
