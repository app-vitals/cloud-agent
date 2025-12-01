# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cloud Agent is a service that executes AI-powered development tasks in isolated Novita sandbox environments. Users submit natural language prompts via API, and Claude Code determines what actions to take.

**Core concept**: No predefined task types - users describe what they want in natural language, and the agent figures out how to accomplish it (e.g., "Fix issue #123", "Add tests for auth module").

## Architecture

### Three-Layer Service Architecture

1. **API Layer** (`app/api/`): FastAPI routes that accept HTTP requests
2. **Service Layer** (`app/services/`): Business logic split into:
   - **Business Logic Services**: Testable logic with mocked dependencies (e.g., `AgentExecutionService`)
   - **Thin Wrapper Services**: External API wrappers excluded from coverage (e.g., `SandboxService`)
3. **Task Layer** (`app/tasks/`): Celery task wrappers with retry logic (excluded from coverage)

### Async Task Processing Flow

```
Client → FastAPI → TaskService.create_task()
                      ↓
                   Celery.delay() → Redis Queue
                                      ↓
                                   Celery Worker
                                      ↓
                              AgentExecutionService
                                      ↓
                                 SandboxService
                                      ↓
                              Novita Sandbox (E2B-compatible)
                                      ↓
                                  Claude Code
```

**Key points:**
- Tasks are queued to Celery immediately on creation (errors bubble up to return 500)
- Business logic lives in `AgentExecutionService` (fully tested with mocked sandbox calls)
- `SandboxService` is a thin wrapper around E2B API (excluded from coverage)
- Celery tasks have 3 auto-retries with exponential backoff (5s + jitter)
- Failed tasks are marked in database after final retry

### Session Logs and Task Storage

**Log Storage:**
- Session logs are stored in filesystem: `logs/tasks/{task_id}/session.jsonl`
- Logs are extracted from Claude's session directory: `~/.claude/projects/-home-user-repo/`
- Session files are discovered by listing `.jsonl` files in Claude's directory (one session per sandbox)
- This works for both successful and timed-out tasks

**File Extraction:**
- Modified files from completed tasks stored in: `logs/tasks/{task_id}/files/`
- Only files detected by `git status --porcelain` are extracted
- Files over 10MB are skipped

**Session Resumption:**
- Parent task's session file is restored to Claude's directory before running
- Session ID is passed to Claude Code via `--resume` flag
- Allows continuation of conversation context across tasks

## Common Commands

### Development Setup
```bash
# Install dependencies
uv sync

# Copy environment template
cp .env.example .env
# Then edit .env with your API keys

# Run database migrations
uv run alembic upgrade head
```

### Running Services (requires 2 terminals)
```bash
# Terminal 1: API Server
uv run uvicorn app.main:app --reload

# Terminal 2: Celery Worker
uv run celery -A app.celery_app worker --loglevel=info --queues=agent_execution
```

### Testing
```bash
# Set up test database (run once, or when you need to reset)
psql -U postgres -c "CREATE DATABASE cloudagent;"
uv run alembic upgrade head

# Run all tests with coverage (must meet 90% threshold)
uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
uv run pytest tests/services/test_agent_execution.py -v

# Run single test
uv run pytest tests/services/test_agent_execution.py::test_execute_task_success -v

# Run integration test (requires API and Celery worker running)
uv run python scripts/integration_test.py
```

**Note for Novita Sandboxes**: The default `DATABASE_URL` uses local socket connection (`postgresql:///cloudagent?user=postgres`) which requires no password. Simply create the database as shown above and run migrations.

### Code Quality
```bash
# Lint and format check
uv run ruff check .
uv run ruff format --check .

# Auto-fix issues
uv run ruff check --fix .
uv run ruff format .
```

### Database Migrations
```bash
# Create new migration
uv run alembic revision --autogenerate -m "Description of changes"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```

## Testing Architecture

### Test Organization
- Tests mirror `app/` structure: `tests/api/`, `tests/services/`, etc.
- Use pytest with `pytest-mock` for mocking (prefer `mocker` fixture over `unittest.mock`)

### Global Test Fixtures (tests/conftest.py)
- `mock_celery_task`: Auto-mocks Celery task queueing for all tests
- `clean_db`: Automatically creates tables and cleans database before each test
- `test_client`: FastAPI TestClient for API tests
- `create_test_task()`: Helper to create test tasks with defaults

### Coverage Configuration
- **Minimum**: 90% coverage required
- **Excluded from coverage**:
  - `app/tasks/*` (thin Celery wrappers)
  - `app/services/sandbox.py` (thin E2B wrapper)
- **Philosophy**: Test business logic thoroughly, exclude thin wrappers around external services

### Writing Tests
```python
# Use mocker fixture (not unittest.mock.patch)
def test_example(mocker):
    mocker.patch("app.services.agent_execution.SandboxService.create_sandbox")
    # ... test code

# Use create_test_task helper for task setup
def test_example():
    task = create_test_task(
        prompt="Test prompt",
        repository_url="https://github.com/test/repo.git"
    )
```

## Key Implementation Patterns

### Service Layer Pattern
When adding new business logic:
1. Create service in `app/services/` with static methods
2. Write comprehensive tests with mocked external dependencies
3. If wrapping external API, consider excluding from coverage (add to pyproject.toml)

### Task Model Fields
- `repository_url`: **Required** - GitHub repo URL to clone
- `prompt`: Natural language description of what to do
- `status`: pending → running → completed/failed
- `sandbox_id`: Set when sandbox is created
- `result`: Final output or error message

### Error Handling Philosophy
- Let errors bubble up naturally (no silent failures)
- Celery handles retries automatically (3 attempts with exponential backoff)
- Failed tasks marked in database on final retry
- Sandbox cleanup happens in `finally` block

## Novita Sandbox Integration

### Custom Template
The project uses a custom `cloud-agent-v1` template with pre-installed:
- Claude Code 2.0
- GitHub CLI (gh)
- uv (Python package manager)
- PostgreSQL 14
- Redis 6
- Node.js 20

Services are started in sandbox with: `start-services`

### Environment Setup

**Required Environment Variables:**
- `NOVITA_API_KEY`: Required for sandbox creation
- `CLAUDE_CODE_OAUTH_TOKEN`: **Preferred** authentication for Claude Code in sandboxes
- `ANTHROPIC_API_KEY`: Alternative to OAuth token (not recommended)
- `GITHUB_TOKEN`: Required for git operations

**Why OAuth Token is Preferred:**
- **Uses Claude Pro/Max subscription** instead of paying per API request
- OAuth tokens are system-level credentials that work across all Claude Code instances
- They provide better integration with Claude's authentication system

**How Authentication Works:**
- E2B environment variables are set automatically by `SandboxService`:
  ```python
  os.environ["E2B_API_KEY"] = settings.novita_api_key
  os.environ["E2B_DOMAIN"] = "sandbox.novita.ai"
  ```
- Claude Code credentials are passed to sandbox as environment variables:
  - `CLAUDE_CODE_OAUTH_TOKEN` (preferred) OR `ANTHROPIC_API_KEY`
  - `GITHUB_TOKEN` for repository access

## API Conventions

### Request/Response Models
- Use Pydantic `BaseModel` for all API schemas
- `repository_url` is required in task creation
- Response models should match database model fields
- Use `str` for UUID serialization in responses

### Endpoint Structure
```
POST   /v1/tasks                - Create task (queues to Celery)
GET    /v1/tasks                - List tasks with pagination
GET    /v1/tasks/{id}           - Get task by ID
GET    /v1/tasks/{id}/logs      - Get task execution logs
GET    /v1/tasks/{id}/files     - Get modified files from completed task
GET    /v1/tasks/{id}/session   - Get session data for local resumption
GET    /health                  - Health check
```

### Task Workflow

**Creating Tasks:**
- Tasks are immediately queued to Celery upon creation
- Each task runs independently in its own sandbox
- Tasks can specify a `parent_task_id` to resume from a previous task

**Task Resumption:**
- **IMPORTANT**: Parent task must be in `completed` status before creating a resume task
- Resume tasks continue from the parent's conversation context
- Use `ca task wait <task-id>` to wait for parent completion before resuming
- Workflow: `ca task create` → `ca task wait` → `ca task resume`

**Best Practice: Branch-Based Workflow vs Session Resumption**

For multi-step work on a PR, there are two approaches:

1. **Session Resumption** (`ca task resume`):
   - ✅ Maintains full conversation context
   - ❌ High overhead: Loads all parent conversation history (can be 80K+ tokens)
   - ❌ Slower: Context loading adds significant time
   - **Use when**: You need the agent to remember specific decisions or reasoning from previous steps

2. **Branch-Based Workflow** (Recommended for most cases):
   - ✅ No context overhead: Fresh start each time
   - ✅ Faster: No need to load parent conversation
   - ✅ Still builds on previous work: Just checkout the PR branch
   - ❌ No conversation memory: Agent doesn't remember previous discussion
   - **Use when**: Work can be described independently (most refactoring, incremental features)

**Example Branch-Based Workflow:**
```bash
# Task 1: Initial work
ca task create "Create UserService in app/services/user.py with get_user() method. Create PR."

# Task 2: Add to same PR (no resume needed!)
ca task create "Use 'gh pr checkout 14' to checkout the PR. Add update_user() method to UserService. Add tests. Push your commit to the PR branch."

# Task 3: More additions
ca task create "Use 'gh pr checkout 14' to checkout the PR. Add delete_user() method to UserService. Add tests. Push your commit to the PR branch."

# Final: Update PR description with all changes
ca task create "Use 'gh pr checkout 14' to checkout the PR. Update PR title and description to summarize all UserService methods added."
```

**CRITICAL Best Practices:**

1. **Use gh CLI for PR checkout** - Say "Use 'gh pr checkout N'" instead of specifying branch names
   - Branch names can be wrong or change
   - gh CLI ensures you're always on the correct PR branch
   - Prevents accidentally creating duplicate branches

2. **Always explicitly say "Push your commit to the PR branch"**
   - If you only say "Commit changes", the agent will commit locally but NOT push
   - Work is lost when the sandbox terminates if not pushed
   - Be explicit in every task prompt that should update a PR

**Why Branch-Based is Better:**
- Each task runs in ~3-5 minutes vs 5+ minutes with resume
- No risk of timeout due to context loading
- Simpler prompts - just describe what to add
- Agent reads current code state from files, not conversation history

## Development Philosophy

- **Natural language interface**: No predefined task types, user describes intent
- **Testable architecture**: Business logic separated from external service wrappers
- **Coverage over comments**: Thin wrappers excluded, business logic fully tested
- **Fail fast**: Errors bubble up immediately, no silent failures
- **Simple local dev**: Single admin key auth, no complex deployment for Phase 1-3
