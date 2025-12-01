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

    @staticmethod
    def normalize_repo_url(repo: str) -> str:
        """Normalize repository input to HTTPS GitHub URL.

        Handles multiple input formats:
        - org/name format: "myorg/myrepo"
        - Full HTTPS URL: "https://github.com/myorg/myrepo.git"
        - Full HTTP URL: "http://github.com/myorg/myrepo.git"
        - SSH URL: "git@github.com:myorg/myrepo.git"

        Args:
            repo: Repository in any of the supported formats

        Returns:
            str: Normalized HTTPS URL ending with .git
        """
        # If repo doesn't start with http/git, assume it's org/name format
        if not repo.startswith(("http://", "https://", "git@")):
            return f"https://github.com/{repo}.git"

        # Parse org/repo from full URL and normalize to HTTPS
        org_repo = GitService.parse_github_url(repo)[1]
        return f"https://github.com/{org_repo}.git"

    @staticmethod
    def parse_github_url(repo: str) -> tuple[str, str]:
        """Parse GitHub repository URL to extract org/repo.

        Handles both HTTPS and SSH URLs:
        - https://github.com/org/repo.git
        - git@github.com:org/repo.git

        Args:
            repo: GitHub repository URL

        Returns:
            tuple[str, str]: (normalized_https_url, org/repo)

        Raises:
            ValueError: If URL cannot be parsed as a GitHub repository
        """
        match = re.search(r"github\.com[:/](.+/.+?)(?:\.git)?$", repo)
        if not match:
            raise ValueError(f"Could not parse GitHub repo from URL: {repo}")

        org_repo = match.group(1)
        repo_url = f"https://github.com/{org_repo}.git"

        return repo_url, org_repo
