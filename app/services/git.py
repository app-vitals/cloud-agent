"""Git service for repository operations."""

import re
import subprocess


class GitError(Exception):
    """Raised when git operations fail."""

    pass


class GitService:
    """Service for git-related operations."""

    @staticmethod
    def get_current_repo() -> tuple[str, str]:
        """Get current git repository URL and org/name.

        Returns:
            tuple[str, str]: (repository_url, org/name)

        Raises:
            GitError: If not in a git repository or no remote found
        """
        try:
            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            remote_url = result.stdout.strip()

            # Parse org/name from URL
            # Handles both HTTPS and SSH URLs:
            # - https://github.com/org/repo.git
            # - git@github.com:org/repo.git
            match = re.search(r"github\.com[:/](.+/.+?)(?:\.git)?$", remote_url)
            if not match:
                raise GitError(
                    f"Could not parse GitHub repo from remote URL: {remote_url}"
                )

            org_repo = match.group(1)

            # Convert to HTTPS URL for use with GitHub token authentication
            # SSH URLs (git@github.com:org/repo.git) won't work with token auth
            repository_url = f"https://github.com/{org_repo}.git"

            return repository_url, org_repo

        except subprocess.CalledProcessError as e:
            raise GitError("Not in a git repository or no remote 'origin' found") from e
