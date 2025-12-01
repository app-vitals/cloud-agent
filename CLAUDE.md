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

## Development Philosophy

- **Natural language interface**: No predefined task types, user describes intent
- **Testable architecture**: Business logic separated from external service wrappers
- **Coverage over comments**: Thin wrappers excluded, business logic fully tested
- **Fail fast**: Errors bubble up immediately, no silent failures
- **Simple local dev**: Single admin key auth, no complex deployment for Phase 1-3
