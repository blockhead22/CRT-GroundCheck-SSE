# Auto-Continuation Plan

## Context

The Agent Loop can emit `complete: false` + `followups` on respond, but nothing acts on it. The user has to manually click a followup chip or type a new message. For long code sessions and multi-phase research, the system should automatically continue when it knows it's not done.

## Design

**Backend-only change.** After the orchestrator completes and emits the response, if `complete: false`, the system auto-fires the first followup as a new orchestrator run within the same HTTP request — no frontend round-trip needed.

### Where to hook it

In `routes/chat.py`, after the orchestrator event loop finishes (around line 6876 where `[ORCHESTRATOR] Complete` is printed), before the final `done` SSE event:

```
Orchestrator run #1 completes
  -> response emitted as tokens
  -> followup_suggest emitted
  -> check: was complete == false?
    YES -> pick first followup
        -> start new Orchestrator run with that followup as objective
        -> stream its events through the same SSE connection
        -> repeat check
    NO -> emit done, return
```

### Implementation

**File: `routes/chat.py`** — wrap the orchestrator section in a continuation loop:

1. Before the orchestrator event loop, add: `_continuation_count = 0`, `_max_continuations = 3`
2. Wrap the orchestrator init + event loop in `while _continuation_count <= _max_continuations:`
3. Track `_pending_followup` from `followup_suggest` events (set when `complete == false`)
4. After orchestrator generator exhausts, check `_pending_followup`:
   - If set: emit a `status` SSE ("Continuing..."), create new Orchestrator, set `_orch_msg = _pending_followup`, increment `_continuation_count`, `continue`
   - If not: `break` out of continuation loop, emit `done` as normal
5. Each continuation run gets conversation history that includes the prior run's answer (already stored via `record_query`)

**File: `personal_agent/cookie_orchestrator.py`** — no changes needed. The orchestrator already supports `followups` + `complete` in the respond action. The system prompt already has the schema.

**File: `frontend/src/App.tsx`** — minimal change:
- In `onFollowupSuggest`, if `complete === false`, don't show chips (system will auto-continue)
- Only show chips when `complete === true` (optional suggestions, not continuations)

### Safeguards

- **Max 3 continuations** per user message — prevents infinite loops
- **Each continuation is a fresh Orchestrator** with its own iteration budget
- **Conversation history carries forward** — each run sees prior answers
- **User can still click chips** for `complete: true` suggestions
- **SSE status event** between runs so user sees "Continuing..." in the pipeline

### Key code locations

1. **`D:\AI_round2\routes\chat.py`** (~lines 6460-6890) — orchestrator event loop, continuation wrapper goes here
2. **`D:\AI_round2\personal_agent\cookie_orchestrator.py`** (~line 1877) — where followup_suggest is yielded from respond action
3. **`D:\AI_round2\frontend\src\App.tsx`** (~line 993) — onFollowupSuggest handler, suppress chips when complete===false
4. **`D:\AI_round2\frontend\src\lib\api.ts`** (~line 748) — followup_suggest parser case
5. **`D:\AI_round2\frontend\src\lib\ws.ts`** (~line 327) — followup_suggest WS dispatcher

### Data flow

```
User sends message
  -> routes/chat.py: intent classify, routing gate
  -> Orchestrator.run() generates events
  -> response event: tokens streamed to user
  -> followup_suggest event: {followups: [...], complete: false}
  -> chat.py detects complete==false
  -> stores answer in conversation history via record_query()
  -> emits status SSE: "Continuing with: <followup text>"
  -> creates new Orchestrator instance
  -> new run starts with followup as objective
  -> conversation_history includes prior run's Q+A
  -> repeat up to _max_continuations=3
  -> final run responds with complete: true
  -> done SSE emitted, request ends
```

### Verification

1. Send a complex task like "refactor the tool executor — extract it into its own file, update imports, and test"
2. Agent Loop should: analyze -> respond with plan + `complete: false` -> auto-continue -> execute extraction -> respond with `complete: true`
3. Check logs for `[ORCHESTRATOR] Auto-continuing` messages
4. Verify max 3 continuations enforced (no infinite loops)
5. Verify followup chips only appear for `complete: true` responses
6. Verify each continuation run has access to prior run's answer in conversation history
7. Test edge case: what if all 3 continuations respond with `complete: false`? Should emit final done + show chips for remaining followups

### Open questions

1. Should the continuation count be visible to the user? (e.g., "Phase 2 of 3...")
2. Should the user be able to interrupt auto-continuation? (stop button)
3. Should each continuation phase show a separate pipeline trace, or append to the same one?
4. Cost consideration: each continuation is a full orchestrator run with multiple brain calls. 3 continuations = 3x the API cost.
