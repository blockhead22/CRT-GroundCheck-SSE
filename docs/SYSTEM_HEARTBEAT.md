# System Info & Heartbeat

**Version:** v1.8+ (March 24, 2026)
**Sprints:** 1-2 (system info), ongoing (heartbeat)
**Files:** `personal_agent/system_info.py`, `personal_agent/heartbeat_system.py`, `personal_agent/heartbeat_executor.py`

---

## System Info (`system_info.py`)

**Layer:** 1 — no checkpoint gate (read-only, passive)

### Overview

Aether can see the host system's state: CPU, RAM, GPU, disk, running processes, and active window. This powers both user-facing queries ("how's my system?") and heartbeat behavioral triggers (gaming detection, idle detection).

### get_system_snapshot()

Returns a comprehensive system snapshot:

| Section | Fields |
|---------|--------|
| **CPU** | percent, per_core (list), logical_cores |
| **RAM** | total_gb, available_gb, used_gb, percent |
| **Disk** | total_gb, free_gb, percent |
| **GPU** | name, gpu_percent, memory_used_mb, memory_total_mb, memory_percent (via pynvml, optional) |
| **Processes** | Top 5 by CPU+memory*2: pid, name, cpu_percent, memory_percent, is_game |
| **Active window** | Current window title (via pygetwindow, Windows only) |
| **Flags** | gaming (GPU>85% + game process), idle (CPU<10% + GPU<15%) |
| **Timing** | snapshot_ms (capture duration) |

### Game Detection

35+ game/launcher executables recognized: steam.exe, cs2.exe, valorant.exe, fortnite.exe, gta5.exe, eldenring.exe, baldursgate3.exe, cyberpunk2077.exe, etc. Matched against running process names.

### Intent Routing

Matches: "system status", "cpu usage", "what am I running", "how's my system" etc. Routes to task agent at 0.95 confidence, Layer 1 (no gate).

### API

`GET /api/system/status` — returns the full snapshot.

---

## Heartbeat System (`heartbeat_system.py`)

### Overview

The heartbeat is a 24/7 background scheduler that runs as a daemon thread. It performs proactive maintenance, self-reflection, and Ledger (Moltbook) engagement. Configurable per-thread with HEARTBEAT.md instructions.

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Master on/off |
| `every_seconds` | 1800 (30 min) | Interval between ticks |
| `target` | "none" | "none", "last", or specific channel |
| `active_hours_start/end` | null | Restrict to time window (0-23, handles wrap-around) |
| `timezone` | "UTC" | For active hours calculation |
| `model` | null | Override LLM model |
| `max_tokens` | 500 | LLM generation limit |
| `temperature` | 0.7 | LLM temperature |
| `dry_run` | false | Log but don't execute |
| `news_monitoring_enabled` | false | Periodic news search |
| `curiosity_enabled` | true | Curiosity pulse system |
| `curiosity_threshold` | 0.42 | Score threshold to trigger |

### HEARTBEAT.md

Each workspace can have a `HEARTBEAT.md` file with structured instructions:

```markdown
## Checklist
- Check for open contradictions
- Review recent feedback

## Rules
- Never post more than once per hour
- Always cite sources

## Proactive Behaviors
- Suggest corrections for low-trust facts
```

The `HeartbeatMDParser` extracts these sections into structured lists for the LLM prompt.

### Self-Reflection Pass

Every heartbeat tick includes a self-reflection pass that:

1. Gathers evidence from last 24 hours: gate failures, negative feedback, trust deltas, open contradictions
2. Calls LLM with structured JSON output prompt
3. Updates 7 self-model slots:
   - `uncertainty_domains` — topics where the system is uncertain
   - `correction_pattern` — common correction types
   - `trust_trajectory` — overall trust trend
   - `known_blindspots` — identified weak areas
   - `growing_confidence` — areas improving
   - `user_relationship` — relationship quality assessment
   - `response_style` — style calibration
4. Optionally validates via cloud service
5. Trust scores range 0.35-0.80, weighted by severity

---

## Heartbeat Executor (`heartbeat_executor.py`)

### Overview

The executor is the decision-making brain of the heartbeat. It gathers context, runs 12 maintenance tasks per tick, and can execute Ledger (Moltbook) actions.

### Per-Tick Task Sequence

| # | Task | Description |
|---|------|-------------|
| 1 | **GroundCheck sync** | Sync verified facts from GroundCheck bridge (min_trust=0.2) |
| 2 | **Trust decay** | Apply time-based trust degradation |
| 3 | **Contradiction inventory** | Flag stale contradictions (>24h unresolved) |
| 4 | **System snapshot** | CPU/RAM/GPU/processes + behavioral triggers |
| 5 | **Commitment scanner** | 60s lookahead, fire due, log missed, flag stale |
| 6 | **Memory audit** | Count total facts + low-trust facts (<0.4) |
| 7 | **Curiosity pulse** | Score-based curiosity trigger (see below) |
| 8 | **News monitoring** | Periodic web search on configured topics |
| 9 | **Mention response** | Check for Moltbook mentions |
| 10 | **Slot discovery** | Run discovery pass to reclassify slots |
| 11 | **Self-reflection** | Update self-model from evidence |
| 12 | **Intent router improvement** | Review corrections, auto-add prototypes |

### Behavioral Triggers

| Trigger | Condition | Action |
|---------|-----------|--------|
| **Gaming** | GPU > 90% + game process detected | Kill ollama.exe (free VRAM) |
| **High Load** | CPU > 90% or RAM > 90% | Log warning |
| **Idle** | CPU < 10% + GPU < 15% | Restart `ollama serve` (DETACHED_PROCESS) |

The `_resources_reduced` flag tracks whether ollama was killed. On idle detection, it restarts automatically.

### Curiosity Pulse

Computes a curiosity score (0-1) from personality traits and memory state:

| Factor | Max Contribution |
|--------|-----------------|
| Curiosity personality trait | 0.50 |
| Learning drive | 0.20 |
| Open questions in memory | 0.15 |
| Low-confidence fact slots | 0.10 |
| Unanswered ratio | 0.05 |
| Question ratio in recent messages | 0.05 |
| Mood bonus ("curious") | +0.08 |
| State bonus ("reflective_partner") | +0.05 |

If score > threshold (default 0.42), posts a curiosity reflection to the "reflections" submolt. SHA1 fingerprint deduplication prevents repeated posts. Minimum cooldown: 900 seconds.

### News Monitoring

When enabled, periodically searches configured topics via web search, hashes results with SHA1 to detect changes, and posts to the "news" submolt. Cooldown: 6 hours (minimum 900s).

### Ledger Actions

The executor can create Moltbook posts, comments, and votes based on LLM decisions:

| Action | Description | Validation |
|--------|-------------|------------|
| `post` | Create new post | Title <= 200 chars, content <= 5000 chars |
| `comment` | Comment on post | Content <= 5000 chars |
| `vote` | Upvote/downvote | Direction: "up" or "down" |
| `none` | Do nothing | — |

Max 3 actions per heartbeat tick. All content HTML-escaped.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system/status` | System snapshot |
| GET | `/api/heartbeat/status` | Heartbeat loop status |
| POST | `/api/heartbeat/start` | Start heartbeat |
| POST | `/api/heartbeat/stop` | Stop heartbeat |
| GET | `/api/threads/{id}/heartbeat/config` | Get thread heartbeat config |
| POST | `/api/threads/{id}/heartbeat/config` | Update thread heartbeat config |
| POST | `/api/threads/{id}/heartbeat/run-now` | Manual trigger |
| GET | `/api/threads/{id}/heartbeat/history` | Run history |
| GET/POST | `/api/heartbeat/heartbeat.md` | Get/update HEARTBEAT.md |
