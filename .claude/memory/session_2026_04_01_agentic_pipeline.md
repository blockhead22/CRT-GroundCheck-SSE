# Session 2026-04-01 — Agentic Pipeline Design + Frontend Fixes

## Status at session end
- Cookie orchestrator loop: **RE-ENABLED** (gate removed; confirmed live 2026-04-05 — `[ORCHESTRATOR] >>> ENTERING agent loop path` in logs)
- Frontend pipeline panel: **REWRITTEN** (PipelineCollapse v2, ToolRow with Lucide icons)
- Backend stream: **FIXED** (generator bug resolved, live belief events working)

---

## Bugs Fixed This Session

### 1. Stream error: 'generator' object has no attribute 'metadata'
- **Root cause**: `yield _sse(...)` calls added inside `chat_send()` (sync function) turned it into a generator. `_run_shared_chat_pipeline()` returned generator object instead of `ChatSendResponse`. `.metadata` access failed.
- **Fix**: New `_pipeline_event_queue` context var + `_emit_pipeline_event()` function (same pattern as `_pipeline_status_queue`). All `yield _sse(...)` in `chat_send()` replaced with `_emit_pipeline_event(...)`. Queue drained inside `generate_stream()` alongside status_q.
- **Files**: `routes/chat.py` lines ~88-102, ~6719-6780

### 2. OAI dump when model set to Opus/cloud_claude
- **Root cause**: Agent loop's `cloud_to_local` fallback ignored `generation_mode`
- **Fix**: `_agent_loop_model_ok` check redirects to orchestrator when `generation_mode=cloud_claude`
- **Status**: Fixed and working

### 3. False contradiction disclosures
- **Root cause**: GroundCheck regex pulled garbage "facts" from conversational text → low confidence hallucinations → hard_fail
- **Fix**: Early PASS when no verifiable claims, filter confidence=0.0 from `_has_real_contradictions`, fallback always uses `draft_answer`
- **File**: `personal_agent/crt_critic.py`

### 4. Duplicate memories in pipeline panel
- **Root cause**: `onRetrieval` pushed to `pipelineSteps` AND `RetrievalPanel` also rendered from same data
- **Fix**: `ChatThreadView.tsx` — `RetrievalPanel` only renders when `!hasPipelineSteps`

### 5. Green bar remaining after stream done
- **Fix**: `PipelineTrace.tsx` — bar fades to `opacity: 0` when `!streaming` instead of turning green

---

## Frontend: Pipeline Panel Redesign (PipelineCollapse v2)

### New files
- `frontend/src/components/chat/PipelineCollapse.tsx` — full rewrite
- `frontend/src/components/chat/ToolRow.tsx` — NEW, Lucide icon tool rows

### Design: VERSION B (Lucide icons)
```
◆ RETRIEVING N MEMORIES          ← section header
  T:0.85 ████████░  I am sleepy  ← staggered in, 80ms per bar
  T:1.00 ████████░  Yes I am Nick
  ...

◆ verifying ✓                    ← verification badge

◆ AGENT LOOP                     ← section header
  ┊ Step 1: planning...          ← thinking stub, italic, 80 char truncate
  [FileText]  read   chat.py     ✓ 43ms
  [PenLine]   edit   chat.py     ✓ 31ms
  ┊ Now checking...
  [Terminal]  bash   grep...     ✓ 0.1s

● generating...                  ← pulse dot while streaming

▸ 5 mem · ✓ · 3 tools · 1.2s   ← collapsed after 700ms
```

### Icon map (lucide-react)
```
FileText  → read_file, file_read
PenLine   → edit, write, patch
Terminal  → bash, shell, exec
Search    → search, grep, find
Globe     → web, fetch, http
Brain     → memory, recall
FolderOpen → dir, list, folder
Save      → save, output
Zap       → default
```

### Trust shift deltas
- On expand after done: bars show `from → to` with ↑↓ indicators
- `shiftById` merges trust_shift events into retrieval bars by memory id

### Show/hide logic
- Panel shows when: `memories > 0 OR tools > 0 OR thinking present`
- Panel hidden for pure conversational (no steps)

---

## Anti-sycophancy Changes
- `cookie_orchestrator.py` ORCHESTRATOR_SYSTEM: Rule 8 — intellectual honesty, disagree when evidence doesn't support
- `personal_agent/prompt_prefix.py` STATIC_PREFIX: "Disagree when warranted", "No formulaic structure"

---

## Cookie Orchestrator: Plan Action Added
**Status**: Added and loop is **RE-ENABLED** (confirmed live 2026-04-05).

### Change: `personal_agent/cookie_orchestrator.py`
- Added `plan` action to ORCHESTRATOR_SYSTEM
- Rule 2: FIRST action must always be `plan` — human-readable intent declaration
- `plan` handler in `run()` loop: yields `{"type": "plan", "content": ..., "steps": [...]}`
- Loop continues after plan (doesn't count as iteration)

### Change: `routes/chat.py`
- `plan` event handler: yields as visible `token` before tools fire
- Ack text seeded into `_orch_answer` so final settled message is consistent
- Previous keyword-match ack (`"On it."` / `"Looking at that..."`) still present as fallback

---

## Cookie Orchestrator: RE-ENABLED (2026-04-05)

The `and False` gate was removed. The agent loop now routes via Layer 4 orchestrator routing when confidence thresholds are met. Confirmed live with orchestrator traces in production logs.

---

## Agentic Pipeline — Full Design Map

See `project_agentic_pipeline.md` for full architecture design.

### What's built
- ✓ plan action (orchestrator + chat.py handler)
- ✓ frontend pendingCheckpoint (ask_user partial)
- ✓ EventBus exists
- ✓ WS layer exists
- ✓ action card component exists

### What's missing
- ✗ routing gate (too permissive, generic convos hit Cookie)
- ✗ ask_user actually suspends the loop
- ✗ ask_user reply resumes the loop
- ✗ followup emit from Cookie after respond
- ✗ connection registry (thread_id → WS socket)
- ✗ outbox queue (per-thread, survives disconnect)

### Dependency order
```
1. Routing gate       — stop noise, can do independently
2. ask_user pause     — core behavior gap, uses pendingCheckpoint
3. ask_user resume    — needs WS send-back into suspended loop
4. followup suggest   — Cookie emits suggestions, action card shows them
5. proactive turns    — registry + outbox, biggest lift, last
```

---

## Epistemic Events Wired (also this session)
- `drift_warning` + `contradiction_warning` from orchestrator now reach frontend
- `alignment` score added to `thinking` and `tool_call` yields in orchestrator
- `chat.py`: `drift_warning` → `epistemic_event` SSE, `contradiction_warning` → `epistemic_event` SSE
- `api.ts`: `epistemic_event` type added, `onEpistemicEvent` callback added
- `ws.ts`: `epistemic_event` case added, `agent_thinking_token` fires drift if alignment < 0.3
- `App.tsx`: `onEpistemicEvent` → pushes `epistemic` PipelineStep
- `PipelineCollapse.tsx`: `epistemic` step kind added, `EpistemicRow` component
  - Drift: orange pill with ⚠ icon, alignment score, delta from avg
  - Contradiction: yellow pill with ⚡ icon, step_a ↔ step_b
  - Thinking stubs: color shifts orange when alignment < 0.35, score shown right-aligned

## Adaptive Depth / Mid-Updates / Subagents Design (end of session)
- All three are the same mechanism at different scales
- ask_user pause = suspend/resume primitive
- spawn_agent = same primitive, child loop fills the resume slot instead of human
- See `project_agentic_pipeline.md` for full design

## Next Session Priorities
1. Read `project_agentic_pipeline.md` — full pipeline design + subagent architecture
2. **Routing gate** — Phase 1, unblocks everything, do this first
3. ask_user pause/resume — Phase 2, establishes suspend/resume primitive
4. Re-enable Cookie loop after gate + ask_user
5. Test plan action + epistemic events live with loop re-enabled
