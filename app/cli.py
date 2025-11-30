"""Cloud Agent CLI - Simple command-line interface for cloud-agent API."""

import os
import time
from pathlib import Path
from typing import Optional

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


@task_app.command("create")
def create_task(
    prompt: str = typer.Argument(..., help="Natural language prompt for the task"),
    repo: str = typer.Option(..., "--repo", help="Repository URL"),
):
    """Create a new task."""
    with get_client() as client:
        response = client.post(
            "/v1/tasks",
            json={"prompt": prompt, "repository_url": repo},
        )
        response.raise_for_status()
        task = response.json()

    console.print(f"[green]✓[/green] Task created: [bold]{task['id']}[/bold]")
    console.print(f"  Status: {task['status']}")
    console.print(f"  Repository: {task['repository_url']}")

    if task.get("branch_name"):
        console.print(f"  Branch: [cyan]{task['branch_name']}[/cyan]")


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
        prompt = task["prompt"][:50] + "..." if len(task["prompt"]) > 50 else task["prompt"]
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

    console.print(f"[bold]Task {task['id']}[/bold]")
    console.print(f"  Status: {task['status']}")
    console.print(f"  Repository: {task['repository_url']}")
    console.print(f"  Created: {task['created_at']}")

    if task.get("branch_name"):
        console.print(f"  Branch: [cyan]{task['branch_name']}[/cyan]")

    if task.get("session_id"):
        console.print(f"  Session: {task['session_id'][:8]}...")

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

    console.print(f"[bold]Logs for task {task_id[:8]}[/bold] ({data['total']} messages)\n")

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
                    console.print(f"[green]✓[/green] Task completed")
                else:
                    console.print(f"[red]✗[/red] Task {status}")
                    if task.get("result"):
                        console.print(f"  {task['result']}")
                break

            time.sleep(5)


@pr_app.command("review")
def review_pr(
    pr_number: int = typer.Argument(..., help="PR number to review"),
    repo: str = typer.Option("ok-wow/ok-wow-ai", "--repo", help="GitHub repo (org/name)"),
):
    """Review a GitHub pull request."""

    repo_url = f"https://github.com/{repo}.git"
    pr_url = f"https://github.com/{repo}/pull/{pr_number}"

    prompt = f"""Review pull request #{pr_number}:

1. Use the /review-pr command:
   /review-pr {pr_url}

2. The review will be saved to PR_REVIEW_{pr_number}.md

Provide comprehensive review with actionable feedback.
"""

    console.print(f"[bold]Creating PR review task for {repo}#{pr_number}[/bold]")

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
