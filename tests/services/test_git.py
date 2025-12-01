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


def test_normalize_repo_url_org_name_format():
    """Test normalize_repo_url with org/name format."""
    result = GitService.normalize_repo_url("myorg/myrepo")
    assert result == "https://github.com/myorg/myrepo.git"


def test_normalize_repo_url_org_name_with_hyphens():
    """Test normalize_repo_url with org/name containing hyphens."""
    result = GitService.normalize_repo_url("my-org/my-repo")
    assert result == "https://github.com/my-org/my-repo.git"


def test_normalize_repo_url_org_name_with_underscores():
    """Test normalize_repo_url with org/name containing underscores."""
    result = GitService.normalize_repo_url("my_org/my_repo")
    assert result == "https://github.com/my_org/my_repo.git"


def test_normalize_repo_url_org_name_with_dots():
    """Test normalize_repo_url with org/name containing dots."""
    result = GitService.normalize_repo_url("my.org/my.repo")
    assert result == "https://github.com/my.org/my.repo.git"


def test_normalize_repo_url_https_with_git_extension():
    """Test normalize_repo_url with full HTTPS URL ending in .git."""
    result = GitService.normalize_repo_url("https://github.com/myorg/myrepo.git")
    assert result == "https://github.com/myorg/myrepo.git"


def test_normalize_repo_url_https_without_git_extension():
    """Test normalize_repo_url with full HTTPS URL without .git extension."""
    result = GitService.normalize_repo_url("https://github.com/myorg/myrepo")
    assert result == "https://github.com/myorg/myrepo.git"


def test_normalize_repo_url_http_with_git_extension():
    """Test normalize_repo_url with HTTP URL (converts to HTTPS)."""
    result = GitService.normalize_repo_url("http://github.com/myorg/myrepo.git")
    assert result == "https://github.com/myorg/myrepo.git"


def test_normalize_repo_url_http_without_git_extension():
    """Test normalize_repo_url with HTTP URL without .git extension."""
    result = GitService.normalize_repo_url("http://github.com/myorg/myrepo")
    assert result == "https://github.com/myorg/myrepo.git"


def test_normalize_repo_url_ssh_with_git_extension():
    """Test normalize_repo_url with SSH URL."""
    result = GitService.normalize_repo_url("git@github.com:myorg/myrepo.git")
    assert result == "https://github.com/myorg/myrepo.git"


def test_normalize_repo_url_ssh_without_git_extension():
    """Test normalize_repo_url with SSH URL without .git extension."""
    result = GitService.normalize_repo_url("git@github.com:myorg/myrepo")
    assert result == "https://github.com/myorg/myrepo.git"


def test_normalize_repo_url_complex_org_name():
    """Test normalize_repo_url with complex org/repo names."""
    result = GitService.normalize_repo_url("my-org.test_123/my-repo.test_456")
    assert result == "https://github.com/my-org.test_123/my-repo.test_456.git"


def test_normalize_repo_url_invalid_url_raises_error():
    """Test normalize_repo_url with invalid URL raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        GitService.normalize_repo_url("https://gitlab.com/myorg/myrepo.git")
    assert "Could not parse GitHub repo from URL" in str(exc_info.value)


def test_parse_github_url_https_with_git():
    """Test parse_github_url with HTTPS URL ending in .git."""
    url, org_repo = GitService.parse_github_url("https://github.com/myorg/myrepo.git")
    assert url == "https://github.com/myorg/myrepo.git"
    assert org_repo == "myorg/myrepo"


def test_parse_github_url_https_without_git():
    """Test parse_github_url with HTTPS URL without .git extension."""
    url, org_repo = GitService.parse_github_url("https://github.com/myorg/myrepo")
    assert url == "https://github.com/myorg/myrepo.git"
    assert org_repo == "myorg/myrepo"


def test_parse_github_url_http_with_git():
    """Test parse_github_url with HTTP URL (still returns HTTPS)."""
    url, org_repo = GitService.parse_github_url("http://github.com/myorg/myrepo.git")
    assert url == "https://github.com/myorg/myrepo.git"
    assert org_repo == "myorg/myrepo"


def test_parse_github_url_ssh_with_git():
    """Test parse_github_url with SSH URL."""
    url, org_repo = GitService.parse_github_url("git@github.com:myorg/myrepo.git")
    assert url == "https://github.com/myorg/myrepo.git"
    assert org_repo == "myorg/myrepo"


def test_parse_github_url_ssh_without_git():
    """Test parse_github_url with SSH URL without .git extension."""
    url, org_repo = GitService.parse_github_url("git@github.com:myorg/myrepo")
    assert url == "https://github.com/myorg/myrepo.git"
    assert org_repo == "myorg/myrepo"


def test_parse_github_url_with_special_characters():
    """Test parse_github_url with org/repo names containing special characters."""
    url, org_repo = GitService.parse_github_url(
        "https://github.com/my-org.test_123/my-repo.test_456.git"
    )
    assert url == "https://github.com/my-org.test_123/my-repo.test_456.git"
    assert org_repo == "my-org.test_123/my-repo.test_456"


def test_parse_github_url_invalid_not_github():
    """Test parse_github_url with non-GitHub URL raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        GitService.parse_github_url("https://gitlab.com/myorg/myrepo.git")
    assert "Could not parse GitHub repo from URL" in str(exc_info.value)


def test_parse_github_url_invalid_missing_org_repo():
    """Test parse_github_url with URL missing org/repo raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        GitService.parse_github_url("https://github.com/")
    assert "Could not parse GitHub repo from URL" in str(exc_info.value)


def test_parse_github_url_invalid_only_org():
    """Test parse_github_url with URL containing only org raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        GitService.parse_github_url("https://github.com/myorg")
    assert "Could not parse GitHub repo from URL" in str(exc_info.value)


def test_parse_github_url_invalid_malformed():
    """Test parse_github_url with malformed URL raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        GitService.parse_github_url("not-a-url")
    assert "Could not parse GitHub repo from URL" in str(exc_info.value)
