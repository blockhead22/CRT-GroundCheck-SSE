# Intuition Check

**Version:** v2.7 (March 24, 2026)
**File:** `personal_agent/intuition_check.py`

---

## Overview

A lightweight gpt-4o-mini side-channel that fires at three moments during the conversation lifecycle. It provides situational awareness without blocking the main pipeline — runs in ~150ms, degrades gracefully when cloud is unavailable.

The intuition check is not the main generation model. It's a quick "gut check" that helps Aether be more responsive: clarifying ambiguous input before misrouting, suggesting next steps after completing a task, and welcoming users back with context after idle periods.

---

## Three Triggers

### 1. Clarify (Ambiguous Input)

**When:** Intent classifier returns conversational with confidence < 0.75
**What:** Asks gpt-4o-mini if the message needs clarification before routing
**SSE Event:** `intuition_check` with the clarification question

**Example:**
- User: "check it" (ambiguous — check what?)
- Intuition check: "Could you clarify what you'd like me to check? Your system status, a specific file, or something else?"

**Response format:**
```json
{
  "needs_clarification": true,
  "clarification_question": "...",
  "likely_intent": "system_info",
  "confidence": 0.4
}
```

### 2. Suggest Next (Post-Task)

**When:** After every `task_done` event
**What:** Passes completed task metadata + open tasks to suggest a natural follow-up
**Delivery:** Embedded in the `done` event metadata as `intuition_check.message`

**Example:**
- Completed: file read of `config.json`
- Suggestion: "Want me to apply those settings, or should I check if the format is valid?"

**Response format:**
```json
{
  "has_suggestion": true,
  "suggestion": "...",
  "suggested_action": "file_write",
  "relates_to_open_task": false
}
```

### 3. Reconnect (After Idle)

**When:** User returns after > 5 minutes (300 seconds) of silence
**What:** Generates a welcome-back message with open task context

**Example:**
- User was idle for 20 minutes with an open file write task
- Reconnect: "Welcome back! You were working on updating the config file — want to continue?"

**Response format:**
```json
{
  "has_context": true,
  "message": "...",
  "open_task_summary": "..."
}
```

---

## Implementation

### IntuitionCheck Class

Singleton via `get_intuition_check(cloud_service)`.

| Method | Parameters | Returns |
|--------|-----------|---------|
| `clarify(message, open_tasks, recent_history, classifier_confidence)` | Message text, up to 3 open tasks, last 3 messages, confidence score | `IntuitionResult` or `None` |
| `suggest_next(completed_task, open_tasks, recent_history)` | Completed task metadata, open tasks, recent messages | `IntuitionResult` or `None` |
| `reconnect(open_tasks, last_message_age_seconds, recent_history)` | Open tasks, idle duration, recent messages | `IntuitionResult` or `None` |
| `stats` (property) | — | `{calls, total_latency_ms, avg_latency_ms}` |

### IntuitionResult

| Field | Type | Description |
|-------|------|-------------|
| `action` | str | "clarify", "suggest", "reconnect", or "none" |
| `message` | str | The intuition check's response text |
| `confidence` | float | How confident the check is |
| `metadata` | Dict | Full parsed JSON from the model |
| `latency_ms` | int | Round-trip time |

---

## Rate Limits

Three daily limit categories in CloudFeatureService:
- Clarify checks: 20/day
- Suggest checks: 20/day
- Reconnect checks: 10/day

---

## Graceful Degradation

- `_is_available()` checks if OpenAI is reachable via `cloud_service._openai_available()`
- If cloud is down, all methods return `None` — no error, no blocking
- If JSON parsing fails, returns `None`
- Main pipeline never waits on the intuition check

---

## Model Choice

Uses **gpt-4o-mini** specifically for:
- Low latency (~150ms)
- Low cost (minimal tokens per call: max_tokens=200)
- Good enough for disambiguation and suggestions (doesn't need full reasoning)

Not Claude — this is a quick utility call, not a governance-level decision.
