# Cloud Agent

Cloud-hosted agent service that executes AI-powered development tasks in isolated sandbox environments. Users submit **natural language prompts** via API, and Claude Code determines what actions to take.

## Features

- **Natural language interface**: No predefined task types - just describe what you want
- **Powered by Claude Code**: Full agent capabilities for any development task
- **Secure sandboxing**: Each task runs in isolated Novita sandbox
- **CLI Tool**: `ca` command for managing tasks (create, get, logs, wait, resume)
- **Task Resumption**: Continue from previous tasks with full conversation context
- **File Extraction**: Modified files automatically saved locally for review
- **Simple API**: Submit prompt, get task ID, poll for results

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (running locally)
- Redis (running locally)
- Novita API key
- Anthropic API key

### Setup

1. **Clone and install dependencies:**
   ```bash
   cd cloud-agent
   cp .env.example .env
   # Edit .env with your API keys
   uv sync
   ```

2. **Build custom Novita template (one-time setup):**

   Install Novita Sandbox CLI:
   ```bash
   npm install -g novita-sandbox-cli
   ```

   Authenticate and build the template with Claude Code, gh CLI, uv, PostgreSQL, and Redis pre-installed:
   ```bash
   novita-sandbox-cli auth login
   novita-sandbox-cli template build
   ```

   This creates a custom sandbox template (`cloud-agent-v1`) so tools are ready instantly.

3. **Run database migrations:**
   ```bash
   uv run alembic upgrade head
   ```

4. **Start the services:**

   **Terminal 1 - API Server:**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

   **Terminal 2 - Celery Worker:**
   ```bash
   uv run celery -A app.celery_app worker --loglevel=info --queues=agent_execution
   ```

5. **Test the template (optional):**
   ```bash
   uv run python scripts/test_template.py
   ```

   This will verify:
   - Novita sandbox can be created from your custom template
   - Claude Code is pre-installed and accessible
   - GitHub CLI is pre-installed and accessible
   - uv (Python package manager) is pre-installed
   - PostgreSQL and Redis are pre-installed
   - Services can be started with `start-services` command

6. **Run integration test:**
   ```bash
   uv run python scripts/integration_test.py
   ```

   This validates the full end-to-end flow:
   - Creates a task via API
   - Task is queued to Celery
   - Celery worker picks up task
   - Sandbox is created and task executes
   - Results are stored in database

## Project Structure

```
cloud-agent/
    app/
        models/       # SQLModel database models
        api/          # FastAPI routes
        services/     # Business logic
        tasks/        # Celery task definitions
        sandbox/      # Sandbox runner integration
    scripts/          # Utility scripts
    tests/            # Tests (mirrors app structure)
    plan.md           # Detailed project plan
```

## Development Phases

- **Phase 1-3**: Local development (current)
  - Simple admin key auth
  - Novita sandbox only
  - No deployment
- **Phase 4**: Production features + Render deployment
- **Phase 5**: Enhancements (provider switching, web UI, webhooks)

## Sandbox Template Features

The custom `cloud-agent-v1` template includes:

- **Claude Code 2.0**: AI-powered development agent
- **GitHub CLI (gh)**: GitHub integration for PRs and issues
- **uv**: Fast Python package manager
- **PostgreSQL 14**: Full database server
- **Redis 6**: In-memory data store for caching/queues
- **Node.js 20**: JavaScript runtime

Services (PostgreSQL and Redis) can be started in the sandbox with:
```bash
start-services
```

This enables Claude Code to execute complex prompts like:
- "Add a tasks table with SQLModel and Alembic, create CRUD operations with tests"
- "Set up Redis caching for the API endpoints"
- "Create a full-stack feature with database, service layer, and tests"

## Usage

### CLI Tool

```bash
# Create a task
ca task create "Fix the bug in auth module" --repo https://github.com/myorg/myapp.git

# Wait for completion
ca task wait <task-id>

# Get task details and results
ca task get <task-id>

# View execution logs
ca task logs <task-id>

# Resume from a previous task
ca task resume <parent-task-id> "Continue by adding tests for the fix"

# Review a pull request
ca pr review 123 --repo myorg/myapp
```

### API Examples

```bash
# Create a task
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Fix https://github.com/myorg/myapp/issues/123",
    "repository_url": "https://github.com/myorg/myapp.git"
  }'

# Check task status
curl http://localhost:8000/v1/tasks/{task_id}

# Get task logs
curl http://localhost:8000/v1/tasks/{task_id}/logs
```

## Documentation

See [plan.md](plan.md) for the complete project plan, architecture, and implementation phases.

## License

TBD
