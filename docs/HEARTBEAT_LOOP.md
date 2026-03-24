# Heartbeat Loop

**Version:** v2.5+ (March 24, 2026)
**Sprint:** 10+
**Layer:** Background — runs outside the request path
**Files:** `personal_agent/heartbeat_system.py`, `personal_agent/heartbeat_executor.py`, `personal_agent/continuous_loops.py`

---

## Overview

The heartbeat is a 24/7 background loop that runs periodically per thread. It reads workspace instructions, gathers recent chat context and memory, and can take autonomous proactive actions — posting to the Ledger, monitoring news, exploring curiosity-driven reflections, or running idle desktop tasks.

The heartbeat is **not** triggered by user messages. It fires on a timer (default: every 30 minutes) regardless of chat activity. It is the only system that acts without a user prompt.

---

## Architecture

```
HeartbeatScheduler (background thread)
  └── per-thread loop
       ├── read HeartbeatConfig from thread_sessions.heartbeat_config_json
       ├── check active hours + interval elapsed
       ├── gather context (recent chat, memory slots, system snapshot)
       ├── read HEARTBEAT.md from workspace (if exists)
       ├── call HeartbeatExecutor
       │    ├── LLM decides actions (local model)
       │    ├── execute decided actions (Ledger posts, news fetch, etc.)
       │    └── record results in thread state
       └── emit SSE heartbeat_tick event
```

---

## Configuration

### Per-Thread Config (`heartbeat_config_json`)

Stored on the `thread_sessions` table as a JSON blob. Managed via chat commands or API.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Master toggle |
| `every_seconds` | int | `1800` | Interval between heartbeats (30 min) |
| `target` | string | `"none"` | Where to send results: `"none"`, `"last"` (last channel), or specific channel |
| `active_hours_start` | int? | `null` | Hour of day (0-23) to start. `null` = always |
| `active_hours_end` | int? | `null` | Hour of day (0-23) to stop |
| `timezone` | string | `"UTC"` | Timezone for active hours |
| `model` | string? | `null` | Override model for heartbeat LLM calls |
| `max_tokens` | int | `500` | Max tokens per heartbeat LLM call |
| `temperature` | float | `0.7` | Sampling temperature |
| `dry_run` | bool | `false` | Simulate without writing to Ledger |

### News Monitoring

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `news_monitoring_enabled` | bool | `false` | Fetch news on configured topics |
| `news_topics` | list[str] | `[]` | Topics to search (e.g., `["AI", "climate"]`) |
| `news_query_suffix` | string | `"latest news"` | Appended to each topic query |
| `news_max_results` | int | `5` | Results per topic per cycle |
| `news_cooldown_seconds` | int | `21600` | 6 hours between same-topic fetches |
| `news_post_submolt` | string | `"news"` | Which submolt to post summaries |

### Curiosity Engine

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `curiosity_enabled` | bool | `true` | Generate curiosity-driven reflections |
| `curiosity_threshold` | float | `0.42` | Minimum curiosity score to act (0.1-0.95) |
| `curiosity_cooldown_seconds` | int | `7200` | 2 hours between curiosity posts |
| `curiosity_post_enabled` | bool | `true` | Post reflections to Ledger |
| `curiosity_post_submolt` | string | `"reflections"` | Target submolt |

---

## HEARTBEAT.md

Users can place a `HEARTBEAT.md` file in the workspace root to give the heartbeat custom instructions. The file is read fresh on every heartbeat cycle. Example:

```markdown
# Heartbeat Instructions

- Check if any new GitHub issues were opened on my repos
- If the system has been idle for 2+ hours, organize my downloads folder
- Post a daily summary of conversations to the "daily" submolt
- Don't post anything between 11pm and 7am
```

The LLM interprets these instructions alongside system state and recent context to decide what actions to take.

---

## Heartbeat Executor

The executor (`heartbeat_executor.py`) is the LLM-driven decision engine. On each tick:

1. **Gathers context:** recent messages, active memory slots, system snapshot (CPU/RAM/GPU/processes), pending tasks, last heartbeat results
2. **Reads instructions:** HEARTBEAT.md + per-thread config
3. **LLM decision:** asks the local model what actions (if any) to take
4. **Executes actions:** Ledger posts, Ledger comments, news fetches, desktop tasks
5. **Records results:** stores outcome in thread state DB for audit trail

### Desktop Integration

When `desktop_heartbeat_idle_control` is enabled in user settings, the heartbeat can trigger desktop automation during idle periods. The system snapshot's `idle` flag (CPU < 10%, GPU < 15%) gates this behavior. The `desktop_idle_task` setting specifies what to do.

---

## Settings UI Status

The Settings page (Heartbeat tab) provides controls for:
- Enable/disable heartbeat
- Interval configuration
- Active hours window
- News monitoring with topic list
- Curiosity engine toggle

> **Note:** These UI controls are currently **stubbed**. The values save to `user_settings` but the heartbeat system reads from `heartbeat_config_json` on the `thread_sessions` table. To make UI settings take effect, the heartbeat scheduler needs to be updated to merge `user_settings` values into the per-thread config. See [Settings Page](SETTINGS.md) for details.

---

## Continuous Loops Integration

The heartbeat is started by `continuous_loops.py` alongside other background services:

```python
HeartbeatLoop(session_db=session_db, interval_seconds=heartbeat_interval, enabled=enabled_heartbeat)
```

The `CRT_HEARTBEAT_LOOP_SECONDS` environment variable controls the scheduler's own tick interval (default: 1800). The per-thread `every_seconds` config controls how often each thread's heartbeat actually fires.

---

## Safety

- All heartbeat actions are logged with full audit trail
- Dry-run mode available for testing without side effects
- Active hours prevent unwanted activity during off-hours
- Desktop actions respect the same confirmation policy as user-initiated desktop tasks
- The heartbeat never modifies user memory directly — it can only propose changes via the normal CRT pipeline
