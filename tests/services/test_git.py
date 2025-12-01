"""Tests for GitService."""

import subprocess

import pytest

from app.services.git import GitError, GitService


def test_get_current_repo_https_url(mocker):
    """Test getting current repo with HTTPS URL."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="https://github.com/test-org/test-repo.git\n",
        returncode=0,
    )

    repo_url, org_repo = GitService.get_current_repo()

    assert repo_url == "https://github.com/test-org/test-repo.git"
    assert org_repo == "test-org/test-repo"
    mock_run.assert_called_once_with(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )


def test_get_current_repo_ssh_url(mocker):
    """Test getting current repo with SSH URL."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="git@github.com:test-org/test-repo.git\n",
        returncode=0,
    )

    repo_url, org_repo = GitService.get_current_repo()

    # Should convert SSH to HTTPS
    assert repo_url == "https://github.com/test-org/test-repo.git"
    assert org_repo == "test-org/test-repo"


def test_get_current_repo_https_url_without_git_extension(mocker):
    """Test getting current repo with HTTPS URL without .git extension."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="https://github.com/test-org/test-repo\n",
        returncode=0,
    )

    repo_url, org_repo = GitService.get_current_repo()

    assert repo_url == "https://github.com/test-org/test-repo.git"
    assert org_repo == "test-org/test-repo"


def test_get_current_repo_ssh_url_without_git_extension(mocker):
    """Test getting current repo with SSH URL without .git extension."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="git@github.com:test-org/test-repo\n",
        returncode=0,
    )

    repo_url, org_repo = GitService.get_current_repo()

    # Should convert SSH to HTTPS and add .git
    assert repo_url == "https://github.com/test-org/test-repo.git"
    assert org_repo == "test-org/test-repo"


def test_get_current_repo_no_git_repository(mocker):
    """Test getting current repo when not in a git repository."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=128,
        cmd=["git", "remote", "get-url", "origin"],
        stderr="fatal: not a git repository",
    )

    with pytest.raises(GitError) as exc_info:
        GitService.get_current_repo()

    assert "Not in a git repository or no remote 'origin' found" in str(exc_info.value)


def test_get_current_repo_no_remote_origin(mocker):
    """Test getting current repo when no remote 'origin' exists."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=128,
        cmd=["git", "remote", "get-url", "origin"],
        stderr="fatal: No such remote 'origin'",
    )

    with pytest.raises(GitError) as exc_info:
        GitService.get_current_repo()

    assert "Not in a git repository or no remote 'origin' found" in str(exc_info.value)


def test_get_current_repo_invalid_url_format(mocker):
    """Test getting current repo with invalid URL format."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="https://gitlab.com/test-org/test-repo.git\n",
        returncode=0,
    )

    with pytest.raises(GitError) as exc_info:
        GitService.get_current_repo()

    assert "Could not parse GitHub repo from remote URL" in str(exc_info.value)


def test_get_current_repo_with_org_containing_dots(mocker):
    """Test getting current repo with org/repo name containing dots."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="https://github.com/test.org/test.repo.git\n",
        returncode=0,
    )

    repo_url, org_repo = GitService.get_current_repo()

    assert repo_url == "https://github.com/test.org/test.repo.git"
    assert org_repo == "test.org/test.repo"


def test_get_current_repo_with_org_containing_hyphens(mocker):
    """Test getting current repo with org/repo name containing hyphens."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="https://github.com/test-org/test-repo.git\n",
        returncode=0,
    )

    repo_url, org_repo = GitService.get_current_repo()

    assert repo_url == "https://github.com/test-org/test-repo.git"
    assert org_repo == "test-org/test-repo"


def test_get_current_repo_with_org_containing_underscores(mocker):
    """Test getting current repo with org/repo name containing underscores."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        stdout="https://github.com/test_org/test_repo.git\n",
        returncode=0,
    )

    repo_url, org_repo = GitService.get_current_repo()

    assert repo_url == "https://github.com/test_org/test_repo.git"
    assert org_repo == "test_org/test_repo"
