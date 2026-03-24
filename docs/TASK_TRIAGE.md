# Task Triage & Acknowledgment

**Version:** v2.4 (March 24, 2026)
**Sprint:** 12
**File:** `personal_agent/task_agent.py` (triage_message function)

---

## Overview

Task triage adds a "pause to think" step before routing. When a message arrives, Aether immediately acknowledges it with a contextual message while the full classification and execution pipeline runs. This prevents the dead silence between user input and first response.

---

## How It Works

### Flow

```
User message arrives
        │
        ▼
┌─────────────────┐
│  triage_message()│ ← instant, deterministic
│  (classify fast) │
└───────┬─────────┘
        │
        ├─→ Emit task_acknowledged SSE event (immediate feedback)
        │
        ▼
┌─────────────────┐
│  Full pipeline   │ ← intent classification, memory retrieval, etc.
│  (may take 1-5s) │
└─────────────────┘
```

### TriageResult

The triage step produces a `TriageResult` that includes:
- Detected intent type (fast classification)
- Acknowledgment message (shown to user immediately)
- Whether the request needs orchestration (multi-intent)
- Extracted slots and parameters

### Acknowledgment Templates (13 intent types)

Each intent type has a contextual acknowledgment:

| Intent | Acknowledgment Example |
|--------|----------------------|
| `system_info` | "Checking your system..." |
| `file_read` | "Reading that file..." |
| `file_write` | "I'll prepare that file..." |
| `shell_exec` | "Running that command..." |
| `git_action` | "Checking git..." |
| `desktop_action` | "Looking at your screen..." |
| `create_commitment` | "Setting that up..." |
| `broad_recall` | "Let me think about that..." |
| `self_referential` | "Let me reflect on that..." |
| `service_action` | "Checking that service..." |
| `project_scan` | "Scanning the project..." |
| `dir_list` | "Looking at that directory..." |
| `conversational` | *(no acknowledgment — responds directly)* |

### SSE Event

```json
{
  "event": "task_acknowledged",
  "data": {
    "message": "Checking your system...",
    "intent_type": "system_info",
    "triage_confidence": 0.92
  }
}
```

---

## Capability-Aware Re-routing

If classification produces an intent that the system can't handle (e.g. a tool is unavailable), `chat.py` re-routes to the closest available capability instead of failing silently.

---

## Post-Task Memory Writer

After a task completes successfully, the system writes a brief memory fact about what was done. This enables Aether to answer follow-up questions like "what did you just do?" from memory rather than hallucinating.

---

## Self-Knowledge Seeds

8 capability self-knowledge facts are seeded into memory so Aether can accurately describe what it can do:
- File read/write capabilities
- Shell execution
- Git operations
- Desktop control
- System monitoring
- Commitment scheduling
- Skill management
- Belief synthesis

---

## Frontend Integration

### Composer Pulse Animation

When a `task_acknowledged` event arrives, the composer input briefly pulses to give visual feedback that the message was received and is being processed.

### Idle Task Debounce

Prevents duplicate triage when rapid messages arrive — debounces to avoid multiple acknowledgment events for quick corrections.

---

## Fixes in v2.4

- **Silent routing failure** — embedding errors in `classify_intent_hybrid()` no longer cause silent fallback to conversational. Errors are caught and regex fallback is used explicitly.
- **Multi-intent detection safety** — edge cases where the embedding model returned NaN scores are handled gracefully.
