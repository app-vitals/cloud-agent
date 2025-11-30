# SIGKILL (-9) Issue in Novita Sandboxes

## Problem

Claude Code processes are intermittently killed with SIGKILL (-9) inside Novita sandboxes.

## Evidence

### Celery Worker Logs (2025-11-30)
```
Fatal error in message reader: Command failed with exit code -9 (exit code: -9)
```

### What Works Before Kill
1. ✅ SDK downloads: "Installed 30 packages in 33ms"
2. ✅ Agent starts: "🤖 Agent starting..."
3. ✅ Session created: "🆔 Session: 16dd8802..."
4. ✅ Got 2 assistant messages (Claude responding)
5. ❌ Then SIGKILL (-9)

### Intermittent Nature
- ✅ Direct test succeeded: `/tmp/test_like_celery.py` returned "4"
- ✅ Timeout test with repo clone found 2 messages in session.jsonl
- ❌ Integration test failed with SIGKILL
- ❌ Progressive test: 1 success, 1 failure with exit 1, both showing Claude API errors

## Root Cause

SIGKILL (-9) indicates **external termination**, not a crash:
- Likely **sandbox OOM killer** (out of memory)
- Or **sandbox CPU/time limits**
- Or **Novita resource restrictions**

## Current Configuration

### Sandbox Template
- Template: `cloud-agent-v1`
- Timeout: 600s (10 minutes) - set in `SANDBOX_TIMEOUT`
- Command timeout: 300s (5 minutes) - set in `CLAUDE_CODE_TIMEOUT`

### Memory/CPU
- Not explicitly configured
- Using Novita defaults

## Mitigation Attempts

1. **Removed in-memory log collection** ✅
   - Changed from collecting logs in Python list to using SDK's session.jsonl
   - Reduced memory footprint of `sandbox_agent.py`

2. **Simplified environment variables** ✅  
   - Removed SYSTEM_ prefix
   - Using OAuth token (not API key)

## Recommendations

### Short-term
1. **Document as known issue** - Intermittent sandbox resource limits
2. **Rely on Celery retries** - Currently configured for 3 attempts
3. **Monitor success rate** - Track how often retries succeed

### Medium-term
1. **Contact Novita support** - Ask about:
   - Default memory/CPU limits for sandboxes
   - Whether `cloud-agent-v1` template can have higher limits
   - Logs/metrics for why processes are killed
   
2. **Test with E2B directly** - Compare if E2B native has same issues

3. **Optimize SDK usage** - Investigate if there are SDK options to:
   - Reduce memory usage
   - Stream more efficiently
   - Limit concurrent operations

### Long-term
1. **Switch providers** if Novita limits can't be increased
2. **Use pre-warmed sandboxes** to reduce cold start overhead
3. **Implement circuit breaker** pattern for failing sandboxes

## Success Metrics

Track in production:
- **Task success rate**: % of tasks that complete without SIGKILL
- **Retry success rate**: % of tasks that succeed on retry
- **Time to SIGKILL**: How long before process is killed
- **Messages before kill**: How many Claude messages before SIGKILL

## Related Files

- `app/services/sandbox.py:112-213` - `run_agent()` method
- `scripts/sandbox_agent.py` - UV script running in sandbox
- `SDK_MIGRATION_PLAN.md:249-253` - Session file progressive writing verification
- `app/tasks/agent_execution.py:12-18` - Celery retry configuration

## Retry Behavior - CONFIRMED WORKING ✅

**Test Results (2025-11-30):**
- Attempt 1: SIGKILL after 2 assistant messages (~36s)
- Attempt 2: SUCCESS - Completed with result ✅
- Total time: ~2.5 minutes (including retry delay)

**Conclusion:** Celery auto-retry successfully handles the intermittent SIGKILL issue. The retry mechanism provides resilience against sandbox resource limits.

## Integration Test Implications

The integration test needs longer timeout to account for retries:
- Current: 300s (5 minutes)
- Recommended: 600s (10 minutes) to allow for 3 retry attempts
- Each retry has ~6s delay + task execution time

## Next Steps

1. ✅ Celery retries confirmed working
2. 📝 Update integration test timeout from 300s to 600s
3. 📊 Monitor production success rates
4. 📧 Contact Novita support about resource limits (optional - retries work)
