"""Cloud Agent CLI - Simple command-line interface for cloud-agent API."""

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load .env file from project root (parent of app/ directory)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

app = typer.Typer(help="Cloud Agent CLI")
task_app = typer.Typer(help="Task management commands")
pr_app = typer.Typer(help="PR review commands")
app.add_typer(task_app, name="task")
app.add_typer(pr_app, name="pr")

console = Console()

# Configuration
API_BASE_URL = os.getenv("CLOUD_AGENT_URL", "http://localhost:8000")
API_KEY = os.getenv("API_SECRET_KEY")


def get_client() -> httpx.Client:
    """Get configured HTTP client."""
    return httpx.Client(
        base_url=API_BASE_URL,
        headers={"X-API-Key": API_KEY},
        timeout=30.0,
    )


def get_current_repo() -> tuple[str, str]:
    """Get current git repository URL and org/name.

    Returns:
        tuple[str, str]: (repository_url, org/name)

    Raises:
        typer.Exit: If not in a git repository or no remote found
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
            console.print("[red]✗[/red] Could not parse GitHub repo from remote URL")
            console.print(f"  Remote: {remote_url}")
            raise typer.Exit(1)

        org_repo = match.group(1)

        # Ensure it ends with .git for repository_url
        if not remote_url.endswith(".git"):
            remote_url = f"{remote_url}.git"

        return remote_url, org_repo

    except subprocess.CalledProcessError:
        console.print(
            "[red]✗[/red] Not in a git repository or no remote 'origin' found"
        )
        console.print("  Either run from a git repo or specify --repo explicitly")
        raise typer.Exit(1) from None


@task_app.command("create")
def create_task(
    prompt: str = typer.Argument(..., help="Natural language prompt for the task"),
    repo: str = typer.Option(
        None, "--repo", help="Repository URL (defaults to current git repo)"
    ),
):
    """Create a new task."""
    # If no repo specified, detect from current directory
    if repo is None:
        repo_url, _ = get_current_repo()
    else:
        repo_url = repo

    with get_client() as client:
        response = client.post(
            "/v1/tasks",
            json={"prompt": prompt, "repository_url": repo_url},
        )
        response.raise_for_status()
        task = response.json()

    console.print(f"[green]✓[/green] Task created: [bold]{task['id']}[/bold]")
    console.print(f"  Status: {task['status']}")
    console.print(f"  Repository: {task['repository_url']}")

    if task.get("branch_name"):
        console.print(f"  Branch: [cyan]{task['branch_name']}[/cyan]")


@task_app.command("resume")
def resume_task(
    parent_task_id: str = typer.Argument(..., help="Parent task ID to resume from"),
    prompt: str = typer.Argument(..., help="Natural language prompt for continuation"),
):
    """Resume a task from a previous task."""
    # Get parent task to get repository URL
    with get_client() as client:
        response = client.get(f"/v1/tasks/{parent_task_id}")
        response.raise_for_status()
        parent_task = response.json()

    # Create new task with parent_task_id
    with get_client() as client:
        response = client.post(
            "/v1/tasks",
            json={
                "prompt": prompt,
                "repository_url": parent_task["repository_url"],
                "parent_task_id": parent_task_id,
            },
        )
        response.raise_for_status()
        task = response.json()

    console.print(f"[green]✓[/green] Resumed task created: [bold]{task['id']}[/bold]")
    console.print(f"  Parent: [dim]{parent_task_id}[/dim]")
    console.print(f"  Status: {task['status']}")
    console.print(f"  Repository: {task['repository_url']}")


@task_app.command("list")
def list_tasks(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of tasks to show"),
):
    """List recent tasks."""
    with get_client() as client:
        response = client.get("/v1/tasks", params={"limit": limit})
        response.raise_for_status()
        data = response.json()

    tasks = data["tasks"]

    if not tasks:
        console.print("[yellow]No tasks found[/yellow]")
        return

    table = Table(title=f"Recent Tasks (showing {len(tasks)} of {data['total']})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Prompt", style="white")
    table.add_column("Created", style="dim")

    for task in tasks:
        # Truncate prompt for display
        prompt = (
            task["prompt"][:50] + "..." if len(task["prompt"]) > 50 else task["prompt"]
        )
        created = task["created_at"][:10]  # Just the date

        table.add_row(
            task["id"][:8],  # Show first 8 chars of UUID
            task["status"],
            prompt,
            created,
        )

    console.print(table)


@task_app.command("get")
def get_task(task_id: str = typer.Argument(..., help="Task ID")):
    """Get task details."""
    with get_client() as client:
        response = client.get(f"/v1/tasks/{task_id}")
        response.raise_for_status()
        task = response.json()

    # Calculate duration
    created = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00"))
    updated = datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00"))
    duration = updated - created
    duration_str = f"{duration.total_seconds():.1f}s"

    console.print(f"[bold]Task {task['id']}[/bold]")
    console.print(f"  Status: {task['status']}")
    console.print(f"  Repository: {task['repository_url']}")
    console.print(f"  Created: {task['created_at']}")
    console.print(f"  Updated: {task['updated_at']}")
    console.print(f"  Duration: {duration_str}")

    if task.get("branch_name"):
        console.print(f"  Branch: [cyan]{task['branch_name']}[/cyan]")

    if task.get("session_id"):
        console.print(f"  Session: {task['session_id']}")

    console.print(f"\n[bold]Prompt:[/bold]\n{task['prompt']}")

    if task.get("result"):
        console.print(f"\n[bold]Result:[/bold]\n{task['result']}")


@task_app.command("logs")
def get_logs(
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Get task logs."""
    with get_client() as client:
        response = client.get(f"/v1/tasks/{task_id}/logs")
        response.raise_for_status()
        data = response.json()

    logs = data["logs"]

    if not logs:
        console.print("[yellow]No logs found[/yellow]")
        return

    console.print(f"[bold]Logs for task {task_id}[/bold] ({data['total']} messages)\n")

    # Print raw logs as JSON for simplicity and future-proofing
    import json

    for i, log in enumerate(logs, 1):
        console.print(f"[dim]Message {i}:[/dim]")
        console.print(json.dumps(log, indent=2))
        console.print()  # Blank line between messages


@task_app.command("wait")
def wait_task(
    task_id: str = typer.Argument(..., help="Task ID"),
    timeout: int = typer.Option(600, "--timeout", "-t", help="Timeout in seconds"),
):
    """Wait for task to complete."""
    start_time = time.time()

    with get_client() as client:
        while True:
            if time.time() - start_time > timeout:
                console.print(f"[red]✗[/red] Timeout after {timeout}s")
                raise typer.Exit(1)

            response = client.get(f"/v1/tasks/{task_id}")
            response.raise_for_status()
            task = response.json()

            status = task["status"]
            console.print(f"Status: {status}...", end="\r")

            if status in ["completed", "failed", "cancelled"]:
                console.print()  # New line
                if status == "completed":
                    console.print("[green]✓[/green] Task completed")
                else:
                    console.print(f"[red]✗[/red] Task {status}")
                    if task.get("result"):
                        console.print(f"  {task['result']}")
                break

            time.sleep(5)


@task_app.command("apply")
def apply_task(
    task_id: str = typer.Argument(..., help="Task ID to apply"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be applied"),
    no_resume: bool = typer.Option(False, "--no-resume", help="Skip resuming Claude"),
):
    """Apply task results to local directory and resume Claude session."""
    import subprocess
    from pathlib import Path

    # 1. Fetch task to verify it's completed
    with get_client() as client:
        response = client.get(f"/v1/tasks/{task_id}")
        response.raise_for_status()
        task = response.json()

    if task["status"] != "completed":
        console.print("[red]✗[/red] Task must be completed to apply")
        console.print(f"  Current status: {task['status']}")
        raise typer.Exit(1)

    console.print(f"[bold]Applying task {task_id}[/bold]\n")

    # 2. Fetch files
    with get_client() as client:
        response = client.get(f"/v1/tasks/{task_id}/files")
        response.raise_for_status()
        files_data = response.json()

    files = files_data["files"]

    if not files:
        console.print("[yellow]No files to apply[/yellow]\n")
    elif dry_run:
        console.print(f"[bold]Would apply {len(files)} files:[/bold]")
        for file in files:
            console.print(f"  {file['path']} ({file['size']} bytes)")
        console.print()
    else:
        # 3. Copy files to current directory
        for file in files:
            local_path = Path.cwd() / file["path"]
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(file["content"])
            console.print(f"[green]✓[/green] {file['path']}")

        console.print(f"\n[green]Applied {len(files)} files[/green]\n")

    # 4. Fetch session data
    try:
        with get_client() as client:
            response = client.get(f"/v1/tasks/{task_id}/session")
            response.raise_for_status()
            session_data = response.json()
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not fetch session: {e}\n")
        return

    session_id = session_data["session_id"]
    session_content = session_data["session_data"]

    if not session_id:
        console.print("[yellow]⚠[/yellow] No session ID available\n")
        return

    if dry_run:
        console.print(f"[bold]Would resume Claude session:[/bold] {session_id}")
        return

    # 5. Write session to Claude's directory
    # Determine project name from current directory
    cwd = Path.cwd()
    project_slug = str(cwd).replace("/", "-")

    # Write to Claude's session directory
    claude_dir = Path.home() / ".claude" / "projects" / project_slug
    claude_dir.mkdir(parents=True, exist_ok=True)
    session_file = claude_dir / f"{session_id}.jsonl"
    session_file.write_text(session_content)

    console.print(f"[dim]Session saved: {session_file}[/dim]\n")

    # 6. Launch Claude in resume mode (if not --no-resume)
    if not no_resume:
        console.print(f"[bold]Resuming Claude session {session_id}...[/bold]\n")
        try:
            # Launch Claude without headless mode or output format flags
            # This opens interactive Claude UI
            subprocess.run(["claude", "--resume", session_id], cwd=cwd, check=True)
        except FileNotFoundError as e:
            console.print(
                "[red]✗[/red] Claude CLI not found. Install it first:\n"
                "  https://claude.com/claude-code"
            )
            raise typer.Exit(1) from e
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗[/red] Claude failed with exit code {e.returncode}")
            raise typer.Exit(1) from e


@pr_app.command("review")
def review_pr(
    pr_number: int = typer.Argument(..., help="PR number to review"),
    repo: str = typer.Option(
        None, "--repo", help="GitHub repo (org/name, defaults to current git repo)"
    ),
):
    """Review a GitHub pull request."""
    # If no repo specified, detect from current directory
    if repo is None:
        repo_url, org_repo = get_current_repo()
    else:
        repo_url = f"https://github.com/{repo}.git"
        org_repo = repo

    pr_url = f"https://github.com/{org_repo}/pull/{pr_number}"

    prompt = f"""Review pull request #{pr_number}:

1. Use the /review-pr command:
   /review-pr {pr_url}

2. The review will be saved to PR_REVIEW_{pr_number}.md

Provide comprehensive review with actionable feedback.
"""

    console.print(f"[bold]Creating PR review task for {org_repo}#{pr_number}[/bold]")

    with get_client() as client:
        response = client.post(
            "/v1/tasks",
            json={"prompt": prompt, "repository_url": repo_url},
        )
        response.raise_for_status()
        task = response.json()

    task_id = task["id"]
    console.print(f"[green]✓[/green] Task created: [bold]{task_id}[/bold]")
    console.print(f"\n[dim]Check status with:[/dim] ca task get {task_id}")
    console.print(f"[dim]View logs with:[/dim] ca task logs {task_id}")


if __name__ == "__main__":
    app()
