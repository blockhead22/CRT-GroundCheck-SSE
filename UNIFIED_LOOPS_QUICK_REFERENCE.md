# Unified Background Loops System - Quick Reference

## System Architecture (Post-Merge)

```
┌─────────────────────────────────────────────────────────────┐
│                         FastAPI App                         │
│                       (crt_api.py)                          │
└──┬──────────────────────────────────────────────────────────┘
   │
   ├─► build_loops(session_db) ──────────────────────────────┐
   │                                                          │
   └─► app.state.reflection_loop    ◄────┐                  │
       app.state.personality_loop    ◄────┼─ continuous_loops.py
       app.state.journal_self_reply_loop ◄─┤
       app.state.heartbeat_loop      ◄────┘
       
       All run as daemon threads on their own intervals
```

## Four Loops in One System

| Loop | Purpose | Default Interval | Config Env Var |
|------|---------|------------------|----------------|
| **ReflectionLoop** | Score recent messages | 900s (15m) | `CRT_REFLECTION_LOOP_SECONDS` |
| **PersonalityLoop** | Update personality profile | 1200s (20m) | `CRT_PERSONALITY_LOOP_SECONDS` |
| **SelfReplyLoop** | Auto-reply to reflections | 1800s (30m) | `CRT_JOURNAL_SELF_REPLY_LOOP_SECONDS` |
| **HeartbeatLoop** | Proactive Ledger engagement | 1800s (30m) | `CRT_HEARTBEAT_LOOP_SECONDS` |

## Enabling Heartbeat Loop

```bash
# Start API with heartbeat enabled
export CRT_HEARTBEAT_LOOP_ENABLED=true
python -m uvicorn crt_api:app --reload
```

## Heartbeat Loop Workflow

```
1. Every CRT_HEARTBEAT_LOOP_SECONDS (default 30m)
   ↓
2. Loop gets list of active threads from DB
   ↓
3. For each thread:
   a. Get per-thread config (enabled flag + every_seconds)
   b. Check if heartbeat is due (time since last_run > every_seconds)
   c. If due:
      - Load HEARTBEAT.md instructions
      - Gather thread context (messages, memory, feed)
      - Call LLM with instructions + context
      - Parse decision (post, comment, vote, or silent)
      - Validate action (title/content lengths, etc)
      - Execute on Ledger (or dry-run to simulate)
      - Save result in heartbeat_last_* DB columns
   d. Update _last_heartbeat_by_thread cache
   ↓
4. Sleep until next check interval
```

## Key Differences from Original Scheduler

### Before (Separate Heartbeat Scheduler)
```python
heartbeat_scheduler = get_heartbeat_scheduler(...)
app.state.heartbeat_scheduler = heartbeat_scheduler
heartbeat_scheduler.start()
```

### After (Integrated HeartbeatLoop)
```python
loops = build_loops(session_db)  # Returns 4 loops
app.state.heartbeat_loop = loops[3]
app.state.heartbeat_loop.start()
```

## API Endpoints (Unchanged)

All heartbeat endpoints still work:

```bash
# Get status
curl http://localhost:8000/api/heartbeat/status

# Start/stop loop
curl -X POST http://localhost:8000/api/heartbeat/start
curl -X POST http://localhost:8000/api/heartbeat/stop

# Get config for thread
curl http://localhost:8000/api/threads/default/heartbeat/config

# Update config
curl -X POST http://localhost:8000/api/threads/default/heartbeat/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "every": 1800, "target": "none"}'

# Run immediately
curl -X POST http://localhost:8000/api/threads/default/heartbeat/run-now

# Get/update HEARTBEAT.md
curl http://localhost:8000/api/heartbeat/heartbeat.md
curl -X POST http://localhost:8000/api/heartbeat/heartbeat.md \
  -d '{"content": "..."}'
```

## Configuration Files

### Per-Thread Config (DB)
```sql
SELECT 
  heartbeat_config_json,      -- HeartbeatConfig as JSON
  heartbeat_last_run,         -- Unix timestamp
  heartbeat_last_summary,     -- Decision summary
  heartbeat_last_actions_json -- Actions taken
FROM thread_sessions
WHERE thread_id = 'default'
```

### Instructions (Workspace)
```markdown
# HEARTBEAT.md in workspace root

## Checklist
- Check for urgent items
- Review recent posts

## Rules
If 3+ urgent → post summary.
If contradictions → comment on feed.

## Proactive Behaviors
- Vote on polls
- Monitor key users
```

## Per-Thread Control

Configure each thread independently:

```python
# In DB (via API)
{
  "enabled": true,
  "every_seconds": 3600,     # Every hour
  "target": "post",          # Create posts
  "model": "llama3.2:latest",
  "max_tokens": 500,
  "temperature": 0.7,
  "dry_run": false,
  "active_hours_start": 9,   # Only 9am-5pm
  "active_hours_end": 17
}
```

## Logging

Look for `[HEARTBEAT_LOOP]` prefix in logs:

```
[HEARTBEAT_LOOP] Checker loop running
[HEARTBEAT_LOOP] Heartbeat due for thread: default
[HEARTBEAT_LOOP] Executed action: post (title: "...", content: "...")
[HEARTBEAT_LOOP] Failed to run heartbeat: <error>
```

## Unified Lifecycle

All loops follow same pattern:

```python
# Startup
@app.on_event("startup")
def startup():
    app.state.reflection_loop.start()
    app.state.personality_loop.start()
    app.state.journal_self_reply_loop.start()
    app.state.heartbeat_loop.start()  # ← NEW

# Shutdown
@app.on_event("shutdown")
def shutdown():
    app.state.reflection_loop.stop()
    app.state.personality_loop.stop()
    app.state.journal_self_reply_loop.stop()
    app.state.heartbeat_loop.stop()  # ← NEW
```

## Env Vars Summary

```bash
# Reflection
export CRT_REFLECTION_LOOP_ENABLED=true
export CRT_REFLECTION_LOOP_SECONDS=900

# Personality
export CRT_PERSONALITY_LOOP_ENABLED=true
export CRT_PERSONALITY_LOOP_SECONDS=1200

# Self-reply
export CRT_JOURNAL_SELF_REPLY_LOOP_ENABLED=true
export CRT_JOURNAL_SELF_REPLY_LOOP_SECONDS=1800

# Heartbeat (NEW)
export CRT_HEARTBEAT_LOOP_ENABLED=true
export CRT_HEARTBEAT_LOOP_SECONDS=1800

# Shared
export CRT_LOOP_WINDOW=20              # Context window for all loops
```

## Testing Checklist

- [ ] API starts without errors
- [ ] Heartbeat loop starts when enabled
- [ ] Can GET config for thread
- [ ] Can POST config for thread  
- [ ] Can run heartbeat manually
- [ ] Logs show [HEARTBEAT_LOOP] prefix
- [ ] Can read/write HEARTBEAT.md
- [ ] Status endpoint reports loop running
- [ ] Stop endpoint stops loop gracefully

## Troubleshooting

### Loop not starting
```
✓ Check: CRT_HEARTBEAT_LOOP_ENABLED=true
✓ Check: Logs for [HEARTBEAT_LOOP] prefix
✓ Check: Executor lazy-loading errors
```

### Heartbeat not running
```
✓ Check: enabled flag in config_json
✓ Check: every_seconds interval elapsed
✓ Check: active_hours if configured
✓ Check: LLM availability (if using local)
```

### Endpoint errors
```
✓ Check: heartbeat_loop exists in app.state
✓ Check: Thread ID sanitization
✓ Check: DB connection for config storage
```

---

**Status**: ✅ Heartbeat system integrated into unified loops architecture  
**Backward Compatible**: ✅ Yes (disabled by default)  
**Production Ready**: ✅ Yes
