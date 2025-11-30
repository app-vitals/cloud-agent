# Agent SDK Migration Plan

## Overview

Migrate from `claude` CLI wrapper to `claude-agent-sdk` Python library for cleaner code, better error handling, and session management.

## Why Migrate?

### Current Issues with CLI Wrapper
- ❌ Complex prompt escaping (bash -c with heredoc, escaping $, ", `, \)
- ❌ Parsing JSON streams manually
- ❌ No structured error handling
- ❌ Session management unclear/undocumented
- ❌ Hard to test and debug

### Benefits of Agent SDK
- ✅ No prompt escaping - just pass strings
- ✅ Structured message objects (`SystemMessage`, `AssistantMessage`, `ResultMessage`)
- ✅ Clean async iterator pattern
- ✅ Session IDs captured automatically
- ✅ Built-in cost/usage metrics
- ✅ Proper error handling
- ✅ Well-documented API

## Architecture Changes

### Before (CLI Wrapper)
```python
# Complex escaping in SandboxService.run_claude_code()
escaped_prompt = (
    prompt.replace("\\", "\\\\")
    .replace('"', '\\"')
    .replace("$", "\\$")
    .replace("`", "\\`")
)
claude_command = (
    f"cd /home/user/repo && "
    f'timeout {timeout} bash -c "echo \\"{escaped_prompt}\\" | '
    f'claude -p --dangerously-skip-permissions --verbose --output-format stream-json"'
)
result = sandbox.commands.run(claude_command)
# Parse JSON stream manually
```

### After (Agent SDK via UV Script)
```python
# In SandboxService.run_agent() - write files, run script in sandbox
task_input = {"prompt": prompt, "resume_session_id": resume_session_id}
sandbox.filesystem.write("/tmp/task_input.json", json.dumps(task_input))
sandbox.filesystem.write("/tmp/sandbox_agent.py", agent_script_content)

result = sandbox.commands.run("cd /home/user/repo && uv run /tmp/sandbox_agent.py")

# Read structured output from files
output = json.loads(sandbox.filesystem.read("/tmp/task_output.json"))
logs = json.loads(sandbox.filesystem.read("/tmp/task_logs.json"))
```

**In sandbox (`scripts/sandbox_agent.py`):**
```python
# UV script with SDK dependency
async for message in query(prompt=prompt, options=options):
    if isinstance(message, SystemMessage):
        session_id = message.data.get("session_id")
    elif isinstance(message, ResultMessage):
        results["result"] = message.result
        results["session_id"] = message.session_id
```

## Implementation Plan

### Phase 1: Add SDK Support ✅ COMPLETED

**Goal**: Add SDK via UV script without breaking existing functionality

**Tasks**:
1. ✅ Create `scripts/sandbox_agent.py` - UV script that runs SDK in sandbox
2. ✅ Script reads `/tmp/task_input.json` (prompt + optional resume_session_id)
3. ✅ Script writes `/tmp/task_output.json` (result, session_id, cost, etc.)
4. ✅ Script writes `/tmp/task_logs.json` (full message history)
5. ✅ Create new `SandboxService.run_agent()` method:
   - Writes task_input.json to sandbox filesystem
   - Uploads sandbox_agent.py to sandbox
   - Runs `uv run /tmp/sandbox_agent.py` in sandbox (no streaming)
   - Reads output and logs from sandbox filesystem
   - Writes logs to local filesystem `logs/tasks/{task_id}/logs.json`
   - Writes session to local filesystem `logs/tasks/{task_id}/session.jsonl`
6. ✅ Removed `run_claude_code()` - fully migrated to SDK
7. ✅ Update `AgentExecutionService` to use `run_agent()`
8. ✅ Add session_id and branch_name fields to Task model
9. ✅ Update tests to mock filesystem operations (98% coverage)
10. ✅ Remove TaskLog model/table (logs now in filesystem)
11. ✅ Add branch creation (`ca/task/{task_id}`) - fails task if branch creation fails
12. ✅ Add optional session_id and branch_name to API for task resumption

**Files modified**:
- ✅ `scripts/sandbox_agent.py` - UV script for SDK
- ✅ `app/services/sandbox.py` - Added run_agent() method
- ✅ `app/services/agent_execution.py` - Uses run_agent(), creates branches
- ✅ `app/services/task.py` - Filesystem-based logs, added session_id/branch_name params
- ✅ `app/models/task.py` - Added session_id and branch_name fields
- ✅ `app/models/task_log.py` - Deleted
- ✅ `app/api/tasks.py` - Updated responses, added session_id/branch_name to TaskCreate
- ✅ `app/cli.py` - New log display format
- ✅ `tests/` - Updated all tests (32 tests, 98% coverage)
- ✅ `alembic/versions/` - Migration for session_id/branch_name + drop task_logs
- ✅ `.gitignore` - Added `logs/` directory
- ✅ `pyproject.toml` - Added CLI to coverage omit

**Database migrations**:
```sql
-- Add session_id
ALTER TABLE tasks ADD COLUMN session_id VARCHAR;

-- Drop task_logs table (logs now in filesystem)
DROP TABLE task_logs;
```

**Filesystem structure** (in project directory):
```
logs/tasks/
  {task_id}/
    logs.json       # Full SDK message history
    session.jsonl   # Claude session file for resumption
```

**Key architectural decisions**:
- ✅ Use UV script (not direct SDK calls) for clean input/output via files
- ✅ No prompt escaping needed - pass via JSON file
- ✅ Structured output via JSON files (not parsing streams)
- ✅ Session resumption supported via `resume_session_id` in input JSON
- ⚠️ Session resumption across sandboxes needs testing (likely server-side storage)

### Phase 2: Git Commit and Push ✅ COMPLETED

**Goal**: Push task outputs to git branches for persistence

**Completed tasks**:
1. ✅ Added git commit logic after successful task completion
2. ✅ Stage all changes with `git add -A`
3. ✅ Check for changes before committing
4. ✅ Commit with descriptive message: `Task {task_id}: {prompt[:50]}`
5. ✅ Push branch to remote with `git push -u origin {branch_name}`
6. ✅ Updated CLI to display branch info in `task get` and `task create`

**Implementation**:
- Commit and push logic added inline in `AgentExecutionService.execute_task()`
- Only commits/pushes if task status is "completed"
- Gracefully handles empty commits (no changes)
- Logs warnings if commit or push fail (non-critical)

### Phase 3: Session Resumption Testing

**Goal**: Verify session resumption works across different sandboxes

**Status**: ✅ ALL TESTS PASSED - Ready for implementation!

## Test Results Summary

| Test | Feature | Status | Key Findings |
|------|---------|--------|--------------|
| **Test 1** | Basic SDK in sandbox | ✅ PASS | No escaping, clean JSON I/O |
| **Test 2** | Session resumption | ✅ PASS | Works by copying .jsonl file |
| **Test 3** | Bash timeout wrapper | ✅ PASS | Exit 124, captures 8 messages |
| **Test 4** | Simple E2B timeout | ✅ PASS | Exception-based, captures 9 messages |
| **Test 5** | Real-time streaming | ✅ PASS | on_stdout/on_stderr callbacks work |
| **Test 6** | Permission bypass | ✅ PASS | No permission prompts with bypassPermissions |

### Test 1: Basic SDK Functionality ✅
- **File**: `scripts/test_sandbox_basic.py`
- **Result**: SDK works perfectly in Novita sandbox
- **Output**: Clean JSON files with session_id, result, cost, duration, logs
- **Key**: No prompt escaping needed - just write JSON to `/tmp/task_input.json`

### Test 2: Session Resumption ✅
- **File**: `scripts/test_sandbox_resume.py`
- **Result**: Sessions CAN be resumed across different sandboxes!
- **Method**: Copy `/home/user/.claude/projects/-home-user-repo/{session_id}.jsonl` file
- **Proof**: Sandbox B remembered "XYZZY-42" from Sandbox A after file transfer
- **Implication**: Store session file (jsonl) in database, restore to new sandboxes for resumption

### Test 3 & 4: Timeout Handling ✅
- **Files**: `scripts/test_sandbox_timeout.py`, `scripts/test_sandbox_timeout_simple.py`
- **Bash wrapper**: `timeout 30 uv run script` → exit code 124, captures partial logs
- **E2B timeout**: `sandbox.commands.run(timeout=30)` → TimeoutException, captures partial logs
- **Winner**: E2B timeout (simpler, no bash wrapper needed)
- **Key**: Progressive flushing writes logs after each message, so timeout still captures them!

### Test 5: Real-time Streaming ✅
- **File**: `scripts/test_sandbox_streaming.py`
- **Result**: E2B streaming callbacks work perfectly
- **Usage**: `sandbox.commands.run(cmd, on_stdout=callback, on_stderr=callback)`
- **Output**: Real-time progress updates with timestamps
- **Benefit**: Can stream logs to database/UI as task runs

### Test 6: Permission Bypass ✅
- **Config**: `ClaudeAgentOptions(permission_mode="bypassPermissions")`
- **Result**: No permission prompts, Write/Read tools work without approval
- **Equivalent**: `--dangerously-skip-permissions` flag in CLI

## What We Confirmed Works

✅ **No prompt escaping** - Use JSON file for input
✅ **Session resumption** - Copy .jsonl file between sandboxes
✅ **Complete logs** - All tool calls (ToolUseBlock, ToolResultBlock, TextBlock)
✅ **Timeout handling** - Simple E2B timeout with progressive flushing
✅ **Real-time streaming** - on_stdout/on_stderr callbacks
✅ **Permission bypass** - bypassPermissions mode
✅ **Cost tracking** - total_cost_usd in ResultMessage
✅ **Progress indicators** - Custom print statements stream in real-time

## Implementation Approach (Validated)

```python
# 1. Write input
task_input = {"prompt": prompt, "resume_session_id": session_id}
sandbox.files.write("/tmp/task_input.json", json.dumps(task_input))

# 2. Upload agent script
sandbox.files.write("/tmp/sandbox_agent.py", script_content)

# 3. Run with timeout (no streaming - we'll check logs after)
try:
    result = sandbox.commands.run(
        "cd /home/user/repo && uv run /tmp/sandbox_agent.py",
        timeout=600
    )
except TimeoutException:
    # Still read partial logs from files (progressive flushing captured them)
    pass

# 4. Read outputs
output = json.loads(sandbox.files.read("/tmp/task_output.json"))

# 5. Store session file for resumption (serves as logs - no separate log file!)
task_dir = f"logs/tasks/{task_id}"
Path(task_dir).mkdir(parents=True, exist_ok=True)
session_jsonl = sandbox.files.read(f"/home/user/.claude/projects/-home-user-repo/{session_id}.jsonl")
Path(f"{task_dir}/session.jsonl").write_text(session_jsonl)
```

**Key Decisions:**
- ❌ **No streaming** - Not needed, we'll check logs after task completes
- ❌ **No separate log collection** - Session file contains everything (messages, tools, results)
- ✅ **Session file = logs** - Single source of truth stored in filesystem
- ✅ **Stream logs line-by-line** - TaskService reads JSONL with offset/limit to avoid memory issues
- 🔮 **Future**: Migrate to S3 or similar for log persistence

**✅ SESSION FILE PROGRESSIVE WRITING CONFIRMED:**
- The Claude Agent SDK **does** write session.jsonl progressively (after each message)
- **Verified**: Timeout test with 30s limit found 2 messages in session file despite timeout
- Session file survives at `/home/user/.claude/projects/-home-user-repo/{session_id}.jsonl`
- This means we get partial logs even when tasks timeout - no separate log collection needed!

### Phase 3: Cleanup ✅ COMPLETED

**Goal**: Remove old CLI wrapper code

**Completed tasks**:
1. ✅ Removed `run_claude_code()` method from `app/services/sandbox.py`
2. ✅ Removed all prompt escaping logic (66 lines of code removed)
3. ✅ All tests still pass (32 tests, 97% coverage)
4. ✅ No more `--output-format stream-json` handling in codebase

## Migration Risks & Mitigation

### Risk 1: SDK doesn't work in sandbox
**Mitigation**: Test in sandbox first with simple script
**Rollback**: Keep CLI wrapper as fallback

### Risk 2: Permissions handling different in SDK
**Mitigation**: Test with `--dangerously-skip-permissions` equivalent
**Note**: SDK uses `permissionMode` in options

### Risk 3: Session resumption doesn't work as expected
**Mitigation**: Start with branch-based outputs, add resumption later
**Fallback**: Use branch + logs as context for new sessions

### Risk 4: Breaking existing tasks
**Mitigation**: Add session_id and branch_name as nullable fields
**Strategy**: Gradual migration, old tasks still work

## Testing Strategy

### Unit Tests
- Mock `claude_agent_sdk.query()` instead of subprocess calls
- Test message handling for each type (SystemMessage, AssistantMessage, ResultMessage)
- Test session_id extraction and storage

### Integration Tests
1. Test SDK in Novita sandbox with simple prompt
2. Test branch creation and push
3. Test full PR review workflow
4. Test error handling and recovery

### Manual Tests
1. Run `scripts/test_agent_sdk.py` in sandbox
2. Trigger PR review with new SDK approach
3. Verify branch is created and pushed
4. Check session_id is stored in database

## Timeline

### Week 1: SDK Integration
- Day 1-2: Add SDK, create run_agent() method
- Day 3: Update AgentExecutionService
- Day 4: Update tests
- Day 5: Test in sandbox

### Week 2: Branch Creation
- Day 1-2: Add branch creation logic
- Day 3: Test branch push workflow
- Day 4-5: Test with real PR reviews

### Week 3: Polish & Documentation
- Day 1-2: Update documentation
- Day 3: Remove old CLI code
- Day 4-5: Buffer for issues

## Success Criteria - ALL MET! ✅

✅ All existing tests pass with SDK (32 tests, 98% coverage)
✅ Session ID captured and stored in database + filesystem
✅ Branch created for each task (`ca/task/{task_id}`)
✅ No more prompt escaping code - uses JSON file
✅ Code is simpler and more maintainable
✅ Filesystem-based logs for better scalability
✅ Session resumption supported via API (optional session_id + branch_name)

## Phase 1 Complete - What We Built

### Core Infrastructure
- **Agent SDK Integration**: UV script (`sandbox_agent.py`) with inline dependencies
- **Clean I/O**: JSON files for input/output (no bash escaping)
- **Progressive Logging**: Logs written after each message (survives timeouts)
- **Session Management**: Session files stored in `logs/tasks/{task_id}/session.jsonl`
- **Permission Bypass**: `bypassPermissions` mode enabled by default

### Database Changes
- Added `session_id` field to Task model
- Added `branch_name` field to Task model
- Removed TaskLog model entirely (logs now in filesystem)
- Migration applied successfully

### API Changes
- Optional `session_id` and `branch_name` in POST /v1/tasks (for resumption)
- Updated responses to include session_id and branch_name
- Logs endpoint with pagination (limit/offset)
- New SDK message format (type + data objects)

### Branch Management
- Auto-creates `ca/task/{task_id}` branch on new tasks
- Checks out existing branch when resuming (if branch_name provided)
- **Critical**: Task fails if branch creation/checkout fails

### Testing
- 32 tests passing (up from 26)
- 98% code coverage (up from 95%)
- All error paths covered (timeouts, branch failures, log errors)

## Migration Complete! 🎉

All phases completed successfully:
- ✅ **Phase 1**: SDK integration, filesystem logs, session management, branch creation
- ✅ **Phase 2**: Git commit and push after task completion
- ✅ **Phase 3**: Removed old CLI wrapper code (66 lines)

**Final Stats**:
- 34 tests passing with 97% coverage
- 0 prompt escaping needed (down from complex bash escaping)
- All tasks automatically create `ca/task/{task_id}` branches
- Session resumption fully supported via API
- **Logs stored as session.jsonl** - No separate log collection, streams line-by-line
- Git commits and pushes happen automatically on successful completion
- **Memory optimized** - No in-memory log storage, uses Claude's session file directly
- **OAuth token support** - Uses Claude Pro/Max subscription instead of pay-per-request
- branch_name and session_id only persisted on successful completion

**Key Optimizations**:
- Removed in-memory log collection from `sandbox_agent.py`
- Session file serves as logs - single source of truth
- TaskService streams logs line-by-line (JSONL format)
- Simplified environment variables (removed SYSTEM_ prefix)

## Answers to Original Questions

1. ✅ **session_id and branch_name in one migration**: Yes, done together
2. ✅ **Support resumption in v1**: Yes, fully implemented via API
3. ✅ **Keep CLI wrapper as fallback**: No, fully migrated to SDK (no fallback needed)
