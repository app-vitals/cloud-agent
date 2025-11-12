# Cloud Agent - Project Plan

## Overview
A cloud-hosted agent service that executes AI-powered development tasks in isolated sandbox environments. Users submit **natural language prompts** via API, and Claude Code determines what actions to take, what tools to use, and how to complete the task.

**Key Features:**
- **Natural language interface**: No predefined task types - just describe what you want
- **Powered by Claude Code**: Full agent capabilities for any development task
- **Secure sandboxing**: Each task runs in isolated environment (Novita/E2B)
- **Simple API**: Submit prompt, get task ID, poll for results
- **Flexible credentials**: Use your own Anthropic API key and GitHub token

**Example Use Cases:**
```bash
# Fix a GitHub issue
curl -X POST https://api.cloudagent.dev/v1/tasks \
  -H "Authorization: Bearer ca_..." \
  -d '{"prompt": "Fix https://github.com/myorg/myapp/issues/123"}'

# Review a PR
curl -X POST https://api.cloudagent.dev/v1/tasks \
  -H "Authorization: Bearer ca_..." \
  -d '{"prompt": "Review this PR and add detailed comments: https://github.com/myorg/myapp/pull/456"}'

# Add tests to a repo
curl -X POST https://api.cloudagent.dev/v1/tasks \
  -H "Authorization: Bearer ca_..." \
  -d '{"prompt": "Clone https://github.com/myorg/myapp and add comprehensive unit tests for the auth module"}'

# Fix TypeScript errors
curl -X POST https://api.cloudagent.dev/v1/tasks \
  -H "Authorization: Bearer ca_..." \
  -d '{"prompt": "Fix all TypeScript errors in https://github.com/myorg/myapp"}'
```

## Tech Stack

### Core Technologies
- **Language**: Python 3.12+
- **Package Manager**: UV
- **Web Framework**: FastAPI (sync endpoints only)
- **Task Queue**: Celery
- **Message Broker**: Redis
- **Database**: PostgreSQL + SQLModel
- **Sandbox**: Novita AI Sandbox (E2B-compatible, 30% cheaper)
- **Agent**: Claude Code SDK or Anthropic Agent SDK

### Deployment Options
- **Primary**: Render (native Celery workers, Postgres, Redis - best reliability)
- **Alternative**: Fly.io (most cost-effective, free tier available)
- **Alternative**: Railway (good UX but higher outage rate)
- Note: Vercel has limitations for long-running Celery workers; better for API-only deployments

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP + API Key
       ▼
┌─────────────────────┐
│   FastAPI Server    │
│  (Sync Endpoints)   │
└──────┬──────────────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│  PostgreSQL │   │    Redis     │
│  (SQLModel) │   │ (Celery Broker)│
└─────────────┘   └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │Celery Workers│
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────────┐
                  │ Novita Sandbox   │
                  │ (E2B-compatible) │
                  │  + Claude API    │
                  └──────────────────┘
```

## API Design Philosophy

**Natural Language Interface:**
Instead of predefined task types (`fix_issue`, `review_pr`), the API accepts natural language prompts. This approach:
- **Maximizes flexibility**: Users can describe any task, not just predefined ones
- **Leverages Claude Code's intelligence**: The agent determines what tools and actions to use
- **Simplifies implementation**: No need to build task-specific handlers
- **Future-proof**: Supports new use cases without API changes
- **Better UX**: Users express intent naturally

### Authentication

**Phase 1-3: Simple Admin Key**
- Single admin key from environment variable (`ADMIN_API_KEY`)
- Header: `Authorization: Bearer <admin_key>`
- Quick and simple for local development

**Phase 4: Full API Key Management**
- API keys stored in database (hashed with bcrypt)
- Multiple keys with expiration and usage limits
- Admin endpoint to generate and manage keys
- Per-key rate limiting and tracking

### Core Endpoints

#### 1. Submit Task
```
POST /api/v1/tasks
Authorization: Bearer <admin_key>  # Phase 1-3: simple admin key, Phase 4: API key

Request:
{
  "prompt": "Fix the issue described in https://github.com/owner/repo/issues/123",
  "anthropic_api_key": "sk-ant-...",  // optional, falls back to system key
  "github_token": "ghp_..."           // optional, falls back to system token
}

Response:
{
  "task_id": "uuid",
  "status": "queued",
  "created_at": "2025-11-12T10:00:00Z"
}
```

**Example prompts:**
- `"Fix the issue described in https://github.com/owner/repo/issues/123"`
- `"Review this PR: https://github.com/owner/repo/pull/456"`
- `"Clone https://github.com/owner/repo and add tests for the authentication module"`
- `"Fix all TypeScript errors in https://github.com/owner/repo"`

Claude Code will determine what actions to take, what tools to use, and how to complete the task based on the natural language prompt.

#### 2. Get Task Status
```
GET /api/v1/tasks/{task_id}
Authorization: Bearer <admin_key>

Response:
{
  "task_id": "uuid",
  "prompt": "Fix the issue described in https://github.com/...",
  "status": "queued" | "running" | "completed" | "failed" | "cancelled",
  "created_at": "2025-11-12T10:00:00Z",
  "started_at": "2025-11-12T10:00:05Z",
  "completed_at": "2025-11-12T10:05:00Z",
  "result": {
    "summary": "Created PR #789 that fixes the authentication bug",
    "artifacts": {
      "pr_url": "https://github.com/owner/repo/pull/789",
      "commits": ["abc123", "def456"]
    }
  },
  "error": "...",  // if failed
  "logs": [
    {"timestamp": "...", "level": "info", "message": "Cloning repository..."},
    {"timestamp": "...", "level": "info", "message": "Running Claude Code agent..."},
    {"timestamp": "...", "level": "info", "message": "Creating pull request..."}
  ]
}
```

#### 3. List Tasks
```
GET /api/v1/tasks?limit=50&offset=0&status=completed
Authorization: Bearer <admin_key>

Response:
{
  "tasks": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### 4. Cancel Task
```
POST /api/v1/tasks/{task_id}/cancel
Authorization: Bearer <admin_key>

Response:
{
  "task_id": "uuid",
  "status": "cancelled"
}
```

#### 5. Admin: Generate API Key (Phase 4)
```
POST /api/v1/admin/api-keys
Authorization: Bearer <admin_api_key>

Request:
{
  "name": "Production Key",
  "expires_at": "2026-01-01T00:00:00Z"  // optional
}

Response:
{
  "api_key": "ca_...",  // shown only once
  "api_key_id": "uuid",
  "name": "Production Key"
}
```

## Database Schema

### Tables

#### api_keys (Phase 4 only)
```python
class APIKey(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    key_hash: str  # bcrypt hash
    key_prefix: str  # first 8 chars for identification
    is_admin: bool = False
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool = True
```

#### tasks
```python
class Task(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    api_key_id: UUID | None = Field(default=None, foreign_key="api_keys.id")  # Phase 4

    # Task definition
    prompt: str  # Natural language task description
    status: str  # queued, running, completed, failed, cancelled
    celery_task_id: str | None = None

    # Results
    result: dict | None = Field(default=None, sa_column=Column(JSON))
    # Structure: {"summary": "...", "artifacts": {...}}
    error: str | None = None

    # Timestamps
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Credentials (encrypted at rest)
    anthropic_api_key_encrypted: str | None = None
    github_token_encrypted: str | None = None
```

#### task_logs
```python
class TaskLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="tasks.id")
    timestamp: datetime
    level: str  # info, warning, error
    message: str
```

## Celery Task Queue

### Configuration
```python
# celery_config.py
broker_url = os.getenv("REDIS_URL")
result_backend = os.getenv("REDIS_URL")
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
task_track_started = True
task_time_limit = 3600  # 1 hour max per task
```

### Task Structure
```python
# tasks/agent_tasks.py
@celery_app.task(bind=True)
def execute_agent_task(self, task_id: str):
    """Execute agent task in sandbox."""
    # 1. Load task from DB
    task = get_task(task_id)

    # 2. Create Novita sandbox (E2B-compatible)
    sandbox = create_sandbox(
        anthropic_api_key=decrypt(task.anthropic_api_key_encrypted),
        github_token=decrypt(task.github_token_encrypted)
    )

    # 3. Run Claude Code agent with natural language prompt
    result = sandbox.commands.run(
        f"claude-code --prompt '{task.prompt}'"
    )

    # 4. Parse result and update task status
    update_task_result(task_id, result)

    # 5. Cleanup sandbox
    sandbox.close()
```

## Sandbox Integration

### Novita AI Sandbox (Primary Choice)
**Why Novita over E2B:**
- **Cost**: 30% cheaper with no $150/month base subscription
  - Novita: $0.0000098/second (1 vCPU)
  - E2B: $0.0000140/second + $150/month base
  - Example: 10-minute task = $0.0059 (Novita) vs $0.0084 + subscription (E2B)
- **Compatibility**: 100% E2B SDK compatible - zero code changes needed
- **Flexibility**: Deploy in your own AWS/GCP VPC (BYOC support)
- **Storage**: 20GB free storage included
- **Sessions**: Up to 24 hours, same as E2B

**Setup**:
```python
# Uses E2B SDK but points to Novita
from e2b import Sandbox
import os

os.environ["E2B_API_URL"] = "https://api.novita.ai"  # Point to Novita
sandbox = Sandbox(template="base", api_key=os.getenv("NOVITA_API_KEY"))
sandbox.commands.run("git clone ...")
# Run Claude Code CLI
sandbox.close()
```

### E2B (Fallback Option)
- **Pros**: Industry standard, used by 50% of Fortune 500, <200ms startup
- **Cons**: $150/month base + 30% higher per-second costs, no BYOC
- **Use case**: Fallback if Novita has issues

### CodeSandbox (Not Recommended)
- **Why not**: Built for web development, not AI agents
- **Pricing**: ~$0.15/hour for VM sandboxes (10x more expensive)
- **Verdict**: Wrong tool for this use case

### Migration Strategy (Phase 5)
Since Novita is E2B-compatible, we can add E2B fallback support later:
1. Phase 1-4: Use Novita only
2. Phase 5: Add environment variable for provider switching
3. Switch between providers with a one-line config change if needed

## Agent Integration

### Option 1: Claude Code CLI (Recommended for MVP)
**Why this approach:**
- Natural language interface - pass user prompts directly to Claude Code
- Claude Code handles all decision-making (which tools, which actions)
- Simpler to implement - no prompt engineering needed
- Users get full power of Claude Code agent

```python
# In Celery task
# Just pass the user's natural language prompt directly
result = sandbox.commands.run(
    f"claude-code '{task.prompt}'"
)
```

**Example prompts that work:**
- `"Fix the issue described in https://github.com/owner/repo/issues/123"`
- `"Review this PR and add comments: https://github.com/owner/repo/pull/456"`
- `"Clone the repo and add comprehensive tests for the auth module"`

Claude Code will:
- Clone repos as needed
- Use gh CLI for GitHub operations
- Create branches, commits, PRs
- Add PR review comments
- Determine the best approach for each task

### Option 2: Anthropic Agent SDK (Future)
- More programmatic control over agent behavior
- Better for custom workflows and integrations
- Requires more integration work and prompt engineering
- Consider for Phase 5 if more control is needed

### Initial Approach
- **Phase 1-4**: Use Claude Code CLI with natural language prompts
- **Phase 5**: Evaluate Agent SDK if we need more control
- Benefit: Users can express tasks naturally without predefined task types

## Security Considerations

### API Key Storage
- Hash keys with bcrypt before storing
- Store key prefix (first 8 chars) for identification
- Never log full API keys

### Credentials Encryption
- Encrypt Anthropic API keys and GitHub tokens at rest
- Use environment variable encryption key
- Consider using AWS Secrets Manager or similar for production

### Sandbox Isolation
- Each task runs in isolated sandbox
- Sandboxes are destroyed after task completion
- No data persistence between tasks (unless explicitly saved to DB)

### Rate Limiting
- Implement rate limiting per API key
- Use Redis for distributed rate limiting
- Configurable limits per key

## Deployment Strategy

### Render (Recommended)
**Why Render:**
- **Best reliability**: ~145 outages/year vs Railway's 296/year
- **Native Celery support**: Dedicated background worker service type
- **Built for this stack**: FastAPI + Celery + Postgres + Redis
- **Managed Redis**: Key-Value store acts as Celery broker
- **Easy scaling**: Add more worker instances as needed

**Services Setup:**
1. **Web Service** (FastAPI):
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Auto-deploy from Git
   - Free tier available

2. **Background Worker** (Celery):
   - Start command: `celery -A app.celery_app worker --loglevel=info`
   - Multiple workers for scaling
   - Can add disk space for temporary storage

3. **PostgreSQL Database**:
   - Managed Postgres instance
   - Automatic backups
   - Connection pooling

4. **Redis** (Key-Value Store):
   - Managed Redis instance
   - Acts as Celery broker and result backend

**Configuration Files:**
```yaml
# render.yaml (Infrastructure as Code)
services:
  - type: web
    name: cloud-agent-api
    runtime: python
    buildCommand: "uv sync"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: cloud-agent-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: cloud-agent-redis
          type: redis
          property: connectionString

  - type: worker
    name: cloud-agent-worker
    runtime: python
    buildCommand: "uv sync"
    startCommand: "celery -A app.celery_app worker --loglevel=info"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: cloud-agent-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: cloud-agent-redis
          type: redis
          property: connectionString

databases:
  - name: cloud-agent-db
    databaseName: cloudagent
    user: cloudagent

  - name: cloud-agent-redis
    ipAllowList: []
```

### Fly.io (Cost-Effective Alternative)
1. **Pricing**: Free tier + $1.94/month minimum
2. **Setup**: Manual configuration with fly.toml
3. **Best for**: Budget-conscious projects
4. **Tradeoff**: More manual setup vs Render's simplicity

### Railway (Alternative)
1. **Pricing**: ~$12/month for small setup
2. **Limitation**: No dedicated worker type, manual setup needed
3. **Concern**: Higher outage rate (296/year)

### Environment Variables
```
# Phase 1-3 (Local Development)
DATABASE_URL=postgresql://localhost/cloudagent
REDIS_URL=redis://localhost:6379
ADMIN_API_KEY=...             # simple admin key for auth
SYSTEM_ANTHROPIC_API_KEY=...  # fallback
SYSTEM_GITHUB_TOKEN=...       # fallback
NOVITA_API_KEY=...            # sandbox provider

# Phase 4 (Production)
ENCRYPTION_KEY=...            # for encrypting credentials
# API key management replaces ADMIN_API_KEY

# Phase 5 (Provider switching support)
E2B_API_KEY=...               # optional fallback
SANDBOX_PROVIDER=novita       # or 'e2b' for fallback
```

## Project Structure

```
cloud-agent/
├── pyproject.toml           # UV config
├── render.yaml              # Render deployment config
├── README.md
├── .env.example
├── alembic/                 # DB migrations
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app
│   ├── config.py           # Settings
│   ├── database.py         # SQLModel setup
│   ├── models/             # SQLModel models
│   │   ├── api_key.py      # Phase 4
│   │   ├── task.py
│   │   └── task_log.py
│   ├── api/                # API routes
│   │   ├── __init__.py
│   │   ├── tasks.py
│   │   └── admin.py        # Phase 4 (API key management)
│   ├── services/           # Business logic
│   │   ├── auth.py
│   │   ├── encryption.py
│   │   └── task_service.py
│   ├── tasks/              # Celery tasks
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   └── agent_tasks.py  # Single task handler for all prompts
│   └── sandbox/            # Sandbox integrations
│       ├── __init__.py
│       ├── novita_runner.py  # Novita/E2B-compatible runner
│       └── agent_runner.py
├── scripts/
│   └── generate_api_key.py  # Phase 4: CLI for generating keys
└── tests/
    ├── test_api.py
    ├── test_tasks.py
    └── test_sandbox.py
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Initialize UV project with FastAPI
- [ ] Set up local PostgreSQL + SQLModel models
- [ ] Set up local Redis + basic Celery config
- [ ] Simple admin key auth from environment variable
- [ ] Create basic CRUD endpoints for tasks
- [ ] Test everything locally with existing Postgres/Redis

### Phase 2: Sandbox Integration (Week 2)
- [ ] Integrate Novita AI Sandbox (E2B SDK compatible)
- [ ] Create basic sandbox runner (Novita only for now)
- [ ] Test running simple commands in sandbox
- [ ] Implement Claude Code CLI execution
- [ ] Add logging and error handling

### Phase 3: Agent Integration (Week 2-3)
- [ ] Implement single `execute_agent_task` Celery task
  - Load task and decrypt credentials
  - Create sandbox with Claude Code installed
  - Pass natural language prompt directly to Claude Code
  - Capture output and parse results
  - Update task status and store artifacts
- [ ] Add comprehensive error handling and timeout management
- [ ] Implement log streaming from sandbox to database
- [ ] Test with various prompt types:
  - Issue fixing
  - PR reviews
  - Code generation
  - Test writing

### Phase 4: Production Readiness (Week 3-4)
- [ ] Implement full API key management system
  - API keys table in database
  - Key generation, hashing (bcrypt), and storage
  - Admin endpoint for key management
  - Replace simple admin key with proper API key auth
- [ ] Implement credentials encryption
- [ ] Add rate limiting
- [ ] Implement proper logging and monitoring
- [ ] Add task cancellation
- [ ] Write comprehensive tests
- [ ] Documentation and API docs
- [ ] Create render.yaml for deployment
- [ ] Deploy to Render for production

### Phase 5: Enhancements (Future)
- [ ] Add sandbox provider switching support (E2B fallback)
- [ ] Web UI for task management and monitoring
- [ ] Webhooks for task completion notifications
- [ ] Multi-user support with teams and permissions
- [ ] Prompt templates/snippets for common tasks
- [ ] Cost tracking and quotas per API key
- [ ] Task history and analytics
- [ ] Evaluate Agent SDK for more programmatic control
- [ ] BYOC deployment (run Novita in your own VPC)

## Decisions Made

1. **API Design**: ✅ Natural language prompts (no predefined task types)
   - Maximizes flexibility and future-proofs the API
   - Leverages Claude Code's full decision-making capabilities
   - Simpler implementation - no task-specific handlers needed

2. **Development Approach**: ✅ Local-first development
   - Phase 1-3: Build and test everything locally
   - Use simple admin key authentication from environment variable
   - Phase 4: Add production features (full API key management) and deploy to Render
   - Use existing local Postgres and Redis (no Docker Compose)

3. **Sandbox Provider**: ✅ Novita AI (E2B-compatible, 30% cheaper, no base subscription)
   - Focus on Novita only in Phase 1-4
   - Add E2B fallback support in Phase 5

4. **Agent Integration**: ✅ Claude Code CLI with natural language prompts
   - Pass user prompts directly to Claude Code
   - Can migrate to Agent SDK later if more control needed

5. **Deployment Platform**: ✅ Render (best reliability, native Celery workers, built for this stack)
   - Delayed to Phase 4

## Open Questions & Decisions Needed

1. **Credentials storage**: Encrypt in DB vs external secrets manager (AWS/GCP)
2. **Task timeout**: Default 1 hour, configurable per task type?
3. **Concurrent tasks**: Limit per API key to prevent abuse?
4. **BYOC deployment**: Deploy Novita in our own VPC for Phase 5?

## Next Steps

1. ✅ Review and approve this plan
2. Initialize repository with UV and project structure
3. Start Phase 1 implementation (local development first)
4. Connect to existing local Postgres and Redis instances
5. Deploy to Render in Phase 4 once local version is working
