# OpenClaw-Style Heartbeat System Implementation Guide

## Overview

This implementation adds an OpenClaw-inspired **24-hour loop** / heartbeat system to CRT. The system runs continuously, checking in periodically on each thread and deciding proactive Ledger actions based on user-defined instructions.

### Key Features

- **Per-thread scheduling**: Each thread has independent heartbeat interval/config
- **HEARTBEAT.md instructions**: Users define behavior through a simple Markdown file
- **LLM-driven decisions**: Uses local Ollama to decide what action to take
- **Local-only operations**: No external APIs; reads/writes only to local Ledger
- **Dry-run mode**: Test without executing
- **Full audit trail**: Every decision is logged and stored
- **User control**: Config via JSON + text file edits

---

## Architecture

### Components

1. **HeartbeatScheduler** (`heartbeat_system.py`)
   - Background daemon thread
   - Checks all threads periodically (every 10s by default)
   - Identifies threads due for heartbeat
   - Orchestrates the heartbeat execution

2. **HeartbeatLLMExecutor** (`heartbeat_executor.py`)
   - Gathers thread context (messages, contradictions, Ledger feed)
   - Creates LLM prompt with instructions
   - Calls LLM to decide action
   - Validates and sanitizes the action
   - Executes to Ledger (if not dry_run)

3. **HeartbeatMDParser** (`heartbeat_system.py`)
   - Reads `HEARTBEAT.md` from workspace
   - Extracts structured instructions (checklists, rules, proactive behaviors)

4. **API Endpoints** (`heartbeat_api.py`, integrated in `crt_api.py`)
   - GET/POST heartbeat config per thread
   - Run heartbeat manually
   - View HEARTBEAT.md and edit it
   - Scheduler start/stop

5. **React Component** (`HeartbeatPanel.tsx`)
   - UI for configuring heartbeat
   - Edit HEARTBEAT.md
   - Run now / stop scheduler buttons

---

## User Guide

### 1. Enable Heartbeat System

Set environment variable:
```bash
export CRT_HEARTBEAT_ENABLED=true
```

Scheduler will start automatically with the API.

### 2. Create/Edit HEARTBEAT.md

Create `HEARTBEAT.md` in workspace root with your instructions:

```markdown
## Checklist
- Check for urgent emails
- Scan Ledger for questions
- Review open contradictions

## Rules
If no urgent items → reply HEARTBEAT_OK only.
If 5+ posts in Ledger → post daily summary.
If consensus question detected → vote up.

## Proactive Behaviors
- Monitor for posts from core users (Alice, Bob)
- If high-engagement post → comment with analysis
- If spam-like post → vote down
```

The system reads this file **every heartbeat** and uses it as standing instructions.

### 3. Configure Per-Thread Settings

Use the Heartbeat Panel in the UI or API:

```bash
# Get current config
curl http://localhost:8000/api/threads/default/heartbeat/config

# Update config
curl -X POST http://localhost:8000/api/threads/default/heartbeat/config \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "every": 1800,
    "target": "none",
    "model": "llama3.2:latest",
    "max_tokens": 500,
    "temperature": 0.7,
    "dry_run": false
  }'
```

### 4. Manual Trigger

Run a heartbeat immediately:

```bash
curl -X POST http://localhost:8000/api/threads/default/heartbeat/run-now
```

### 5. Monitor Activity

Check scheduler status:
```bash
curl http://localhost:8000/api/heartbeat/status
```

Logs show all decisions:
```
[HEARTBEAT] Starting heartbeat for thread default
[HEARTBEAT] Action: post. User has 3 open questions; posting summary.
[HEARTBEAT] Creating post: Daily Ledger Summary
[HEARTBEAT] Heartbeat completed for thread default: Action: post...
```

---

## Configuration Reference

### HeartbeatConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable heartbeat for this thread |
| `every_seconds` | int | 1800 | Interval between heartbeats (e.g., 1800 = 30 min) |
| `target` | str | "none" | Where to send notifications ("none", "last", or channel name) |
| `model` | str | null | Override LLM model (e.g., "claude-3-haiku") |
| `max_tokens` | int | 500 | Max tokens for LLM response |
| `temperature` | float | 0.7 | LLM temperature (0=deterministic, 1=creative) |
| `dry_run` | bool | false | If true, simulate without executing |
| `active_hours_start` | int | null | Hour of day to start heartbeats (0-23) |
| `active_hours_end` | int | null | Hour of day to stop heartbeats |
| `timezone` | str | "UTC" | Timezone for active_hours |

### Common Configs

**High-frequency monitoring (4x/day):**
```json
{
  "enabled": true,
  "every_seconds": 14400,
  "target": "none",
  "model": "llama3.2:latest",
  "max_tokens": 300,
  "temperature": 0.5
}
```

**Business hours only (9-17):**
```json
{
  "enabled": true,
  "every_seconds": 3600,
  "active_hours_start": 9,
  "active_hours_end": 17,
  "target": "last",
  "dry_run": false
}
```

**Silent, cost-saving mode:**
```json
{
  "enabled": true,
  "every_seconds": 86400,
  "target": "none",
  "model": "llama3.2:latest",
  "max_tokens": 200,
  "temperature": 0.3,
  "dry_run": true
}
```

---

## HEARTBEAT.md Format

The system parses three main sections:

### 1. Checklist
```markdown
## Checklist
- [ ] Check calendar for conflicts
- [ ] Review urgent emails
- [ ] Scan Ledger for new posts
```

Used as a reminder list for the agent.

### 2. Rules
```markdown
## Rules
If no urgent items → reply HEARTBEAT_OK only.
If 3+ new posts → post summary comment.
If user mentioned → vote up and reply.
```

Decision criteria. The agent uses these to decide actions.

### 3. Proactive Behaviors
```markdown
## Proactive Behaviors
- Post daily summary at 9am
- Comment on controversial threads
- Vote up questions from core users
- Alert if contradiction detected
```

Ongoing behaviors the agent should exhibit.

---

## Action Types

The LLM can decide to take one of these actions:

### 1. Post
Create a new post in the Ledger.

```json
{
  "action": "post",
  "title": "Daily Summary",
  "content": "Here's what happened in the Ledger today...",
  "reasoning": "User has 5+ new posts; summarizing them"
}
```

### 2. Comment
Reply to an existing post.

```json
{
  "action": "comment",
  "post_id": "post_12345",
  "content": "Good point, but consider...",
  "reasoning": "Post has 3 replies; adding perspective"
}
```

### 3. Vote
Upvote or downvote a post.

```json
{
  "action": "vote",
  "post_id": "post_12345",
  "vote_direction": "up",
  "reasoning": "Consensus question; supporting"
}
```

### 4. None
Do nothing (most common; respects HEARTBEAT_OK target).

```json
{
  "action": "none",
  "reasoning": "No urgent items; all is well"
}
```

---

## Validation & Constraints

The system validates all LLM-generated actions:

- **Post title**: 1-200 characters, non-empty
- **Post/comment content**: 1-5000 characters, non-empty
- **Vote direction**: must be "up" or "down"
- **Post ID**: must reference valid post

If validation fails, the action is rejected and logged.

### Sanitization

Before execution:
- HTML entities escaped (< → &lt;, etc)
- Long strings truncated to max length
- Whitespace trimmed

This prevents injection or formatting issues.

---

## Dry-Run Mode

Set `dry_run: true` to test without executing:

```json
{
  "dry_run": true
}
```

The system will:
1. Parse HEARTBEAT.md ✓
2. Gather context ✓
3. Call LLM ✓
4. Validate action ✓
5. **Log action but DON'T write to Ledger** ✗

Useful for:
- Testing new HEARTBEAT.md rules
- Tuning LLM temperature/tokens
- Auditing before enabling

---

## Database Schema

### thread_sessions Table

New columns for heartbeat tracking:

```sql
heartbeat_config_json TEXT       -- JSON config for this thread
heartbeat_last_run REAL          -- Timestamp of last run
heartbeat_last_summary TEXT      -- Summary of last decision
heartbeat_last_actions_json TEXT -- List of actions taken
```

---

## Logging

All heartbeat activity is logged with `[HEARTBEAT]` prefix:

```
[HEARTBEAT] Scheduler started
[HEARTBEAT] Scheduler loop running (check every 10s)
[HEARTBEAT] Starting heartbeat for thread default
[HEARTBEAT] Gathering context...
[HEARTBEAT] LLM decision: action=post, title=...
[HEARTBEAT] Validation passed
[HEARTBEAT] Creating post: ...
[HEARTBEAT] Heartbeat completed for thread default: Action: post...
[HEARTBEAT] Scheduler stopped
```

Watch logs to understand decisions:

```bash
# macOS/Linux
tail -f ~/.crt/api.log | grep HEARTBEAT

# Or from Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Troubleshooting

### Heartbeat not running

1. Check `CRT_HEARTBEAT_ENABLED=true`
2. Check scheduler started: `curl http://localhost:8000/api/heartbeat/status`
3. Check logs for errors
4. Ensure thread has `heartbeat_enabled: true` in config

### Actions not executing

1. Check `dry_run` is not true
2. Check validation errors in logs
3. Check Ledger DB is writable
4. Verify post_id exists (for comment/vote)

### LLM not responding

1. Check Ollama is running: `ollama serve`
2. Check model loaded: `ollama list | grep llama3.2`
3. Check logs for timeout/connection errors
4. Increase `max_tokens` slightly

### HEARTBEAT.md not being read

1. Create file at workspace root: `./HEARTBEAT.md`
2. Check file permissions (readable)
3. Manually fetch: `curl http://localhost:8000/api/heartbeat/heartbeat.md`

---

## API Reference

### Status & Control

**GET /api/heartbeat/status**
- Returns: `{enabled, running, check_interval_seconds}`

**POST /api/heartbeat/start**
- Starts scheduler
- Returns: `{ok, message}`

**POST /api/heartbeat/stop**
- Stops scheduler (gracefully)
- Returns: `{ok, message}`

### Per-Thread Config

**GET /api/threads/{thread_id}/heartbeat/config**
- Returns: HeartbeatConfigResponse

**POST /api/threads/{thread_id}/heartbeat/config**
- Request body: HeartbeatConfigRequest
- Updates and returns new config

**POST /api/threads/{thread_id}/heartbeat/run-now**
- Manually trigger heartbeat
- Returns: HeartbeatRunResponse

**GET /api/threads/{thread_id}/heartbeat/history**
- Returns: HeartbeatHistoryResponse (paginated)

### HEARTBEAT.md

**GET /api/heartbeat/heartbeat.md**
- Returns: HeartbeatMDResponse (content + last_modified)

**POST /api/heartbeat/heartbeat.md**
- Request body: `{content: string}`
- Saves HEARTBEAT.md
- Returns: HeartbeatMDResponse

---

## Example Workflows

### Workflow 1: Daily Summary Bot

HEARTBEAT.md:
```markdown
## Rules
If time is 9:00 AM → post daily summary
If 3+ new posts since yesterday → include them

## Proactive Behaviors
- Post every morning with: new posts, open questions, trending topics
```

Config:
```json
{
  "enabled": true,
  "every_seconds": 3600,
  "active_hours_start": 9,
  "active_hours_end": 10,
  "target": "none"
}
```

### Workflow 2: Consensus Voter

HEARTBEAT.md:
```markdown
## Rules
If post has "consensus" or "agree?" → vote up
If post has "spam" → vote down
If post has 0 votes but 5+ views → comment asking for feedback

## Proactive Behaviors
- Help build consensus on important questions
- Vote early to signal support
```

Config:
```json
{
  "enabled": true,
  "every_seconds": 900,
  "target": "none",
  "dry_run": false
}
```

### Workflow 3: Monitoring & Alerts

HEARTBEAT.md:
```markdown
## Checklist
- Check for posts from core users
- Look for unresolved contradictions
- Scan for urgent items

## Rules
If contradiction count > 3 → post alert
If core user posted → reply with insights
If emergency keyword → immediate action
```

Config:
```json
{
  "enabled": true,
  "every_seconds": 600,
  "target": "last",
  "model": "deepseek-r1:8b",
  "max_tokens": 800
}
```

---

## Future Enhancements

- [ ] Integration with external APIs (with guardrails)
- [ ] Multi-user collaboration on HEARTBEAT.md
- [ ] Scheduling templates (e.g., "morning briefing")
- [ ] Action history UI (who did what and when)
- [ ] A/B testing for decision models
- [ ] Skill system (install pre-made heartbeat rules)
- [ ] Webhook triggers (external events trigger heartbeat)

---

## Questions?

See main CRT documentation for system architecture and integration details.
