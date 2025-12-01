# Task Apply Feature Plan

## Overview

Add `ca task apply <task_id>` command to copy task results to local working directory and resume Claude session locally.

## User Workflow

```bash
# 1. Create task remotely (runs in cloud sandbox)
ca task create "Fix the authentication bug" --repo https://github.com/myorg/myapp.git

# 2. Wait for completion
ca task wait <task-id>

# 3. Apply results locally (copies files + resumes session)
cd ~/projects/myapp
ca task apply <task-id>
```

## What `apply` Does

1. **Fetch task details** - Verify task exists and is completed
2. **Download files** - GET `/v1/tasks/{task_id}/files` to fetch modified files
3. **Copy files locally** - Write to current working directory, preserving structure
4. **Download session** - GET `/v1/tasks/{task_id}/session` to fetch session.jsonl
5. **Resume Claude locally** - Launch `claude --resume <session_id>` in current directory

## API Endpoints (New)

### GET /v1/tasks/{task_id}/files

Returns list of modified files with their contents.

```json
{
  "task_id": "uuid",
  "files": [
    {
      "path": "src/auth.py",
      "content": "...",
      "size": 1234
    },
    {
      "path": "tests/test_auth.py",
      "content": "...",
      "size": 567
    }
  ],
  "total": 2
}
```

**Implementation:**
- Read from `logs/tasks/{task_id}/files/` directory
- Return file contents as JSON
- Only works for completed tasks with extracted files

### GET /v1/tasks/{task_id}/session

Returns session JSONL data for resumption.

```json
{
  "task_id": "uuid",
  "session_id": "session-uuid",
  "session_data": "... JSONL content ..."
}
```

**Implementation:**
- Read from `logs/tasks/{task_id}/session.jsonl`
- Return session ID (extracted from first message) and raw JSONL
- Only works for completed tasks

## CLI Command: `ca task apply`

```bash
ca task apply <task-id> [OPTIONS]
```

**Options:**
- `--dry-run` - Show what would be applied without making changes
- `--no-resume` - Skip launching Claude (just copy files)
- `--target-dir <path>` - Apply to specific directory (default: current directory)

**Workflow:**

```python
def apply_task(task_id: str, dry_run: bool = False, no_resume: bool = False):
    # 1. Fetch task to verify it's completed
    task = client.get(f"/v1/tasks/{task_id}")
    if task["status"] != "completed":
        console.print("[red]Task must be completed to apply[/red]")
        return

    # 2. Fetch files
    files_response = client.get(f"/v1/tasks/{task_id}/files")
    files = files_response["files"]

    if dry_run:
        console.print(f"[bold]Would apply {len(files)} files:[/bold]")
        for file in files:
            console.print(f"  {file['path']} ({file['size']} bytes)")
        return

    # 3. Copy files to current directory
    for file in files:
        local_path = Path.cwd() / file["path"]
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(file["content"])
        console.print(f"[green]✓[/green] {file['path']}")

    console.print(f"\n[green]Applied {len(files)} files[/green]")

    # 4. Fetch session data
    session_response = client.get(f"/v1/tasks/{task_id}/session")
    session_id = session_response["session_id"]
    session_data = session_response["session_data"]

    # 5. Write session to Claude's directory
    # Determine project name from current directory
    cwd = Path.cwd()
    project_slug = cwd.name.replace(" ", "-").replace("/", "-")

    # Write to Claude's session directory
    claude_dir = Path.home() / ".claude" / "projects" / f"-{project_slug}"
    claude_dir.mkdir(parents=True, exist_ok=True)
    session_file = claude_dir / f"{session_id}.jsonl"
    session_file.write_text(session_data)

    console.print(f"\n[dim]Session saved: {session_file}[/dim]")

    # 6. Launch Claude in resume mode (if not --no-resume)
    if not no_resume:
        console.print(f"\n[bold]Resuming Claude session...[/bold]")
        # Launch Claude without headless mode or output format flags
        # This opens interactive Claude UI
        subprocess.run(["claude", "--resume", session_id], cwd=cwd)
```

## Implementation Steps

### 1. Add API Endpoints

**File: `app/api/tasks.py`**

```python
@router.get("/tasks/{task_id}/files", response_model=TaskFilesResponse)
def get_task_files(task_id: UUID):
    """Get modified files from a completed task."""
    task = TaskService.get_task_by_id(task_id)

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Task must be completed to retrieve files"
        )

    files_dir = Path("logs/tasks") / str(task_id) / "files"
    if not files_dir.exists():
        return {"task_id": str(task_id), "files": [], "total": 0}

    files = []
    for file_path in files_dir.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(files_dir)
            content = file_path.read_text()
            files.append({
                "path": str(relative_path),
                "content": content,
                "size": len(content)
            })

    return {
        "task_id": str(task_id),
        "files": files,
        "total": len(files)
    }


@router.get("/tasks/{task_id}/session", response_model=TaskSessionResponse)
def get_task_session(task_id: UUID):
    """Get session data for resuming a task locally."""
    task = TaskService.get_task_by_id(task_id)

    session_file = Path("logs/tasks") / str(task_id) / "session.jsonl"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = session_file.read_text()

    return {
        "task_id": str(task_id),
        "session_id": task.session_id,
        "session_data": session_data
    }
```

### 2. Add Response Models

**File: `app/api/tasks.py`**

```python
class TaskFileResponse(BaseModel):
    path: str
    content: str
    size: int


class TaskFilesResponse(BaseModel):
    task_id: str
    files: list[TaskFileResponse]
    total: int


class TaskSessionResponse(BaseModel):
    task_id: str
    session_id: str
    session_data: str
```

### 3. Add CLI Command

**File: `app/cli.py`**

```python
@task_app.command("apply")
def apply_task(
    task_id: str = typer.Argument(..., help="Task ID to apply"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be applied"),
    no_resume: bool = typer.Option(False, "--no-resume", help="Skip resuming Claude"),
    target_dir: str = typer.Option(None, "--target-dir", help="Target directory (default: current)"),
):
    """Apply task results to local directory and resume Claude session."""
    # Implementation as described above
```

### 4. Testing

**Manual Test Flow:**

```bash
# Setup
cd ~/projects/test-repo
git init

# Create remote task
ca task create "Create a hello.py file that prints Hello World" \
  --repo https://github.com/myorg/test-repo.git

# Wait and apply
ca task wait <task-id>
ca task apply <task-id>

# Should:
# 1. Create hello.py in current directory
# 2. Launch Claude in resume mode
# 3. Claude should remember creating the file
```

## Edge Cases

1. **Task not completed** - Show error, refuse to apply
2. **No files modified** - Show warning, still allow session resume
3. **File conflicts** - Overwrite without confirmation (user can use git to manage)
4. **Session file missing** - Show error if trying to resume
5. **Wrong directory** - User should be in correct project directory (detected via git remote)
6. **Claude not installed** - Show helpful error message

## Future Enhancements

1. **Git integration** - Auto-detect repo from git remote, warn if mismatch
2. **Diff preview** - Show diffs before applying with `--dry-run`
3. **Selective apply** - `--files "*.py"` to apply only certain files
4. **Conflict resolution** - Interactive prompts for file conflicts
5. **Session merging** - Combine remote session with local session history

## Benefits

1. **Hybrid workflow** - Run expensive tasks in cloud, continue locally
2. **Review before commit** - Apply to local repo, review diffs, test, then commit
3. **Session continuity** - Full conversation context preserved
4. **Cost optimization** - Use cloud for heavy tasks, local for iteration

## Example Use Cases

### PR Review Workflow

```bash
# Review PR remotely
ca pr review 123 --repo myorg/myapp
ca task wait <task-id>

# Apply review locally and continue discussion
cd ~/projects/myapp
ca task apply <task-id>
# Claude opens with full PR review context
# Can ask follow-up questions, make changes, etc.
```

### Bug Fix Workflow

```bash
# Diagnose bug remotely
ca task create "Debug the login failure in production logs" \
  --repo myorg/myapp

# Apply diagnosis and fix locally
ca task wait <task-id>
cd ~/projects/myapp
ca task apply <task-id>
# Claude opens with diagnosis, can now implement fix with full context
```

### Multi-stage Workflow

```bash
# Stage 1: Research (remote)
ca task create "Research best practices for rate limiting"
ca task apply <task-id>  # Get research notes locally

# Stage 2: Implementation (local, with context)
# Claude resumes with research context, implement locally
```

---

## Implementation Checklist

- [ ] Add GET `/v1/tasks/{task_id}/files` endpoint
- [ ] Add GET `/v1/tasks/{task_id}/session` endpoint
- [ ] Add response models (TaskFilesResponse, TaskSessionResponse)
- [ ] Add `ca task apply` CLI command
- [ ] Add `--dry-run`, `--no-resume`, `--target-dir` options
- [ ] Implement file copying logic
- [ ] Implement session file writing to Claude's directory
- [ ] Implement Claude resume launching
- [ ] Add error handling for edge cases
- [ ] Test end-to-end workflow
- [ ] Update README with apply command examples
- [ ] Update CLAUDE.md with deployment considerations
