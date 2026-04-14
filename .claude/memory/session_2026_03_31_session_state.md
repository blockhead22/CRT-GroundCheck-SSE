---
name: session_2026_03_31_session_state
description: CRT Session State shipped — running belief state per conversation, density-weighted extraction, away/resume diff, session-aware compaction
type: project
---

## Session: 2026-03-31 (night, continued)

### CRT Session State — SHIPPED

Running belief state that tracks turn-by-turn epistemic changes during a conversation. Inspired by Claude Code's `.session.md` but with trust scores, contradiction tracking, and density signals.

**New file: `personal_agent/session_state.py`**
- `SessionState` dataclass — per-session rolling aggregates: total_trust_delta, open_contradiction_count, memories_confirmed/expired, cumulative_density, cumulative_tokens
- `TurnSnapshot` dataclass — per-turn: trust_shifts, contradictions_detected/resolved, slots_classified, memories_cited, tokens, density_score
- `get_or_create_session(thread_id)` — in-memory dict, thread-safe, auto-creates new segment on 30-min gap
- `record_turn()` — aggregates from existing pipeline signals in <50ms (3 indexed SQLite reads)
- `should_extract()` — dual trigger: tokens >= 5000 OR density >= 0.02 OR 30-min fallback
- `render_away_resume_diff()` — belief state diff for system prompt ("since you were last here...")
- `get_hot_memory_ids()` — union of cited, shifted, contradicted memory IDs
- `flush_to_db()` / `load_from_db()` — persistence via session_snapshots table

### Integration Points
- `routes/chat.py` — record_turn() wired into _run_post_response_bookkeeping() background thread
- `personal_agent/context_feed.py` — away/resume diff prepended to both regular and compacted context
- `personal_agent/context_feed.py` — hot memory IDs passed to compact_context() for prioritization
- `personal_agent/belief_compaction.py` — `session_hot_ids` param with PRIORITY_SESSION_HOT=15 boost
- `personal_agent/idle_scheduler.py` — density-triggered extraction enqueues heartbeat_learning jobs
- `personal_agent/background_jobs.py` — heartbeat_learning job handler added

### Four Features from One Module
1. **Compaction source** — hot IDs prioritized for verbatim representation
2. **Away/resume diff** — "Since you were last here: 5 confirmed, 1 expired, 2 open contradictions"
3. **Density-weighted extraction** — replaces 30-min timer, saves API calls on casual chat
4. **Consolidation prioritization** — session-flagged contradictions available for priority checking

### Test Results
- 10-turn session recording: rolling aggregates correct, density=0.025
- should_extract: all 4 trigger conditions verified (token, density, time, none)
- Away/resume diff: renders trust changes, contradictions, slot activity correctly
- Session-aware compaction: hot memories maintained/improved representation
- DB flush/load: JSON serialization round-trips correctly

### Context
This was the #1 finding from the Claude Code research deep dive. Their .session.md accidentally built a belief snapshot without calling it one. Ours is intentional and epistemically aware.
