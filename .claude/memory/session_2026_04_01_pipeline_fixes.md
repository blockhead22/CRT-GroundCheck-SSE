---
name: Session 2026-04-01 Evening — Pipeline Fixes & Cookie Diagnosis
description: Rule 11, plan→thinking routing, drift/session_state SSE wiring, search_code timeout root cause, context bleed fix, CHANGELOG created
type: project
---

## What shipped

**Cookie orchestrator**
- Rule 11 (SEARCH/LIST EFFICIENCY): Cookie must respond directly from search_code results — no file-read verification pass after a list/find task
- History window reduced: `window=6, 300 chars` → `window=2, 150 chars`
- History label changed to "PRIOR CONTEXT (previous exchange — for continuity only, NOT the current task)" — kills context bleed where Cookie executed a prior task instead of the current one

**Plan → pipeline thinking**
- Cookie's `plan` action now emits `type: "thinking"` SSE instead of streaming as visible tokens
- Plan text + steps appear as italic stub in Agent Loop panel, not in chat bubble
- Fix: initial attempt used `_emit_pipeline_event()` which only works in threaded path; orchestrator is a generator — changed to `yield _sse({...})`

**SSE event chain — drift + session_state**
- Both events were emitted by backend but had no frontend handlers
- Wired full chain: `StreamEventType` → parser cases → `StreamCallbacks` → `App.tsx` handlers → `pipelineSteps`
- `onDrift` renders as `epistemic` step: "N trust shifts · Δ±X.XXX"
- `onSessionState` renders as `status` step: "density X.XXX · N open conflicts"

**PipelineCollapse**
- Summary line now: `N thoughts · N tools · N mem · N shifts · Xs`
- `groupSteps()` collects `sessionNotes` array for density/conflict strings → footer section in expanded view
- `pipelineStepsRef` live capture at `done` time — fixes "1 pipeline step" persistence bug

**Embeddings**
- `EmbeddingEngine._MAX_INPUT_CHARS = 1600` — fixes Token indices > 512 warning for all callers
- `agent_run_log._MAX_ALIGN_CHARS = 400` — truncation in `score_alignment()` and `detect_step_contradictions()`

**CHANGELOG.md created** at `D:\AI_round2\CHANGELOG.md` — full version history from v2.6 through current unreleased

## Fixed (end of session)

**`search_code` timeout + large file guard** — SHIPPED
- rg: `--max-filesize 256K` skips files over 256KB before reading
- rg: excluded `*.min.js`, `*.min.css`, `*.lock`, `*.map`, `_write_copilot_page.py`
- rg: timeout raised 12s→15s
- Python fallback: `os.path.getsize() > 256*1024` check before `open()`
- Root cause: TrustBar searches hit 159s/193s on massive generated files

**`file_pattern` arg support** — SHIPPED
- Cookie was passing `file_pattern: "frontend/**/*.{tsx,ts}"` which search_code silently ignored
- Now parsed: directory prefix → `search_path`, extension set → `file_extensions`
- Prevents full-tree scans when Cookie tries to scope by directory

**Alignment collapse loop** — FIXED (consequence of timeout fix)
- When searches complete fast, alignment stays >0.5, DRIFT_FLAG doesn't fire, Cookie doesn't second-guess

## Still open

- Discord bot: `LoginFailure: Improper token` on every restart — needs valid token from Discord developer portal
- `spawn_agent` — never triggered in a real run
- `ask_user` pause/resume — built but never end-to-end tested
- Layer 2 alignment aggregated stats — per-run scores compute but not verified in SQLite

## Additional fixes (late session)

- **FORCE_RESPOND**: If Cookie ignores "last iteration" hint and returns tool_call, code forces a respond from accumulated reasoning. Backup safety net.
- **Token limit 800→3000**: Last 2 iterations get 3000 tokens for detailed responses (was 800 for all).
- **Rule 12 — RESPONSE DEPTH**: Cookie instructed to include evidence (file names, line numbers, quotes), show don't summarize.
- **Followup suggestions**: `respond` action accepts `followups` + `complete` fields. Backend emits `followup_suggest` SSE. Frontend not yet wired.
- **Token 742>512 silenced**: `logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)` in embeddings.py.
- **spawn_agent LogStep fix**: `result=` → `result_preview=` field name mismatch.
- **spawn_agent context fix**: Removed `context=` kwarg from `child.run()` — not accepted.
- **project_scan/search_code/multi_intent routing**: Added to `_TOOL_REQUIRING_INTENTS`.
- **dir_list src redirect**: Returns "NOTE: third-party reference code" instead of listing Claude Code source dump.
- **dir_list missing dir error**: Returns explicit error + lists real project directories.
- **search_code src/src skip**: Added `--glob !src/src` to rg.
- **PipelineTrace/ToolRow toLowerCase guard**: Prevents crash on undefined values.

**Why:** All search_code slowness + context bleed was traced to: no timeout + window too wide. Both fixable in one pass.
**How to apply:** When Cookie gets stuck in a search loop, first check: (1) is search_code timing out silently? (2) is the history window pulling in prior task context?
