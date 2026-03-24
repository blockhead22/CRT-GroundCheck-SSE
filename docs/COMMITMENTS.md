# Commitment & Scheduling System

**Version:** v2.0 (March 24-25, 2026)
**Sprint:** 4
**Files:** `personal_agent/commitments.py`, `personal_agent/time_parser.py`, `personal_agent/proactive_triggers.py`, `routes/commitments.py`

---

## Overview

The commitment system makes Aether proactive. Users can set reminders, schedule recurring tasks, and receive browser notifications when commitments are due. The system includes natural language time parsing, a heartbeat-integrated scanner, and proactive conversation triggers.

Commitments are distinct from memory facts — they represent scheduled actions and obligations, not knowledge.

---

## Commitments

### Data Model

| Field | Type | Description |
|-------|------|-------------|
| `commitment_id` | UUID | Primary key |
| `thread_id` | string | Conversation that created it |
| `intent` | string | What to do (e.g. "take medication") |
| `description` | string | Full human-readable description |
| `status` | enum | pending, fired, done, missed, cancelled |
| `origin` | enum | user_requested, system_suggested, proactive |
| `priority` | enum | low, medium, high, critical |
| `consequence` | string | health, work, social, or null |
| `deadline` | epoch float | When it should fire |
| `recurrence` | string | daily, weekly, weekdays, cron expr, every N hours, or null |
| `next_fire_at` | epoch float | Computed next fire time |
| `fire_count` | int | Times fired without acknowledgement |

### Lifecycle

```
Created (pending) → Due → Fired (notification sent)
                         ├─ Recurring: recompute next_fire_at, stay pending
                         └─ One-shot: status = done

Missed: pending where next_fire_at < now - 5 minutes
Stale: fired 3+ times without acknowledgement
Cancelled: user explicitly cancels
```

### Recurrence Types

| Pattern | Example | Behavior |
|---------|---------|----------|
| `daily` | — | Every 24 hours from deadline |
| `weekly` | — | Every 7 days from deadline |
| `weekdays` | — | Mon-Fri, same time |
| `every N hours` | "every 2 hours" | Fixed interval |
| `every N minutes` | "every 30 minutes" | Fixed interval |
| 5-field cron | `0 9 * * 1-5` | Standard cron (searches up to 366 days) |

### Key Functions

| Function | Description |
|----------|-------------|
| `create_commitment(...)` | Create with auto-computed next_fire_at |
| `get_pending_commitments(before)` | Due before timestamp, ordered by next_fire_at |
| `fire_commitment(id)` | Increment fire_count, recompute for recurring |
| `cancel_commitment(id)` | Set status = cancelled |
| `get_missed_commitments()` | Pending where overdue by > 5 minutes |
| `get_stale_commitments(threshold=3)` | Fired N+ times without ack |
| `search_commitments(term)` | LIKE search on intent and description |

---

## Natural Language Time Parsing

`time_parser.py` handles time expressions with zero external dependencies.

### Supported Patterns

| Pattern | Example | Result |
|---------|---------|--------|
| **Relative delta** | "in 5 minutes", "in 2 hours" | deadline = now + delta |
| **Absolute time** | "at 10:30pm", "at 3pm", "at 15:00" | deadline = today/tomorrow at time |
| **Tomorrow** | "tomorrow" | deadline = tomorrow 9:00 |
| **Named time** | "morning" / "afternoon" / "evening" / "tonight" | 9:00 / 14:00 / 18:00 / 21:00 |
| **Daily recurring** | "every day at 10:30pm" | deadline + recurrence = "daily" |
| **Weekday recurring** | "every weekday at 9am" | deadline + recurrence = "weekdays" |
| **Interval recurring** | "every hour", "every 30 minutes" | deadline + recurrence = "every N unit" |

Times in the past automatically roll to the next day.

### Intent Extraction

`extract_reminder_intent(text)` strips common prefixes and time expressions to isolate the pure intent:

```
"remind me to take medication at 10:30pm"
→ intent: "take medication"
→ deadline: today 22:30 (or tomorrow if past)
→ recurrence: null
```

Recognized prefixes: "remind me to", "set a reminder to", "don't let me forget to", "alert me to", "notify me to", "schedule"

---

## Heartbeat Integration

The heartbeat executor runs a commitment scanner on every tick:

1. **60-second lookahead** — checks for commitments due within the next minute
2. **Fire due commitments** — sends browser notification via SSE
3. **Log missed commitments** — flags commitments overdue by > 5 minutes
4. **Flag stale commitments** — commitments fired 3+ times without user acknowledgement

### Browser Notifications

When a commitment fires, a `commitment_notification` SSE event is emitted. The frontend:
- Shows a browser `Notification` API popup
- Injects a system message in the active chat thread

---

## Proactive Triggers

`proactive_triggers.py` provides two systems:

### 1. Response Quality Triggers

Analyzes response metadata to detect when the agent should activate autonomously:

| Trigger | Condition | Auto-Execute? |
|---------|-----------|--------------|
| LOW_CONFIDENCE | Response confidence < threshold | Yes if < 0.4 |
| CONTRADICTION | Contradiction detected in response | Yes |
| INSUFFICIENT_CONTEXT | Response is a fallback type | Yes |
| MEMORY_GAP | < 2 memories retrieved | No |
| COMPLEX_QUERY | > 15 words or multiple "?" | No |

### 2. User-Facing Pattern Detection

Scans user messages for patterns that suggest proactive actions:

| Pattern | Keywords | Suggestion |
|---------|----------|------------|
| `trip_planning` | "planning a trip", "going to" | "Want me to look up routes?" |
| `health_concern` | "feeling sick", "headache" | "Want me to set a reminder?" |
| `deadline_mention` | "due by", "deadline" | "Want me to set a reminder?" |
| `project_mention` | "working on", "my project" | "Want me to check status?" |

Suggestions are appended to response metadata and skipped if the response already addresses the topic.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/commitments` | Create a commitment |
| GET | `/api/commitments` | List commitments (filterable by thread_id, status) |
| GET | `/api/commitments/due` | Get due commitments |
| PUT | `/api/commitments/{id}/status` | Update status |
| DELETE | `/api/commitments/{id}` | Cancel a commitment |

### Deterministic Responses

Commitment operations return deterministic text (no LLM involvement):

```
"Reminder set: take medication. Next fire: today at 10:30 PM. Recurrence: daily."
```

---

## Agent Intents

| Intent | Gate | Description |
|--------|------|-------------|
| `create_commitment` | Medium checkpoint | Create a new commitment |
| `list_commitments` | No gate | Show existing commitments |
| `cancel_commitment` | Medium checkpoint | Cancel a commitment |
