---
name: Session 2026-03-30 Night — Governance L4-L5, 14 Cookie Tools, Research Landscape
description: Governance layers 4-5 shipped (epistemic routing + execution beliefs), 14 Cookie tools, plan approval gate 80%, Discord bot built, Telegram live, intent router killed, image upload pipeline, research landscape complete (6 agents, 30+ papers). Unfinished: plan approval e2e test, Discord token, frontend rebuild.
type: project
---

## What Shipped

**Governance Layers 4-5:**
- Layer 4: Epistemic routing (`routing_beliefs.py`) — 12 structural feature extractors, belief-weighted scoring, SQLite persistence, learning feedback loop. Replaced keyword hack in chat.py. Fires BEFORE agent loop gate so Cookie gets tasks instead of GPT-4o-mini.
- Layer 5: Execution beliefs (`execution_beliefs.py`) — 5 pattern detectors (verification, calibration, drift, efficiency, tool reliability). Injected into Cookie's system prompt every run.

**14 Cookie Tools (new):** `code_intel`, `fetch_url` (markdown), `memory_store`, `run_python`, `diff_file`, `image_read` (vision), `plan_create` (with approval gate)

**Bug Fixes:** `tool_call_id` mismatch in agent loop (caused Gödel hallucination) — fixed in both `agent_tool_loop.py` and `litellm_client.py`. Cloud-usage polling storm, SQLite thread safety, triple SSE connect. Telegram unblocked from cloud models.

**Infrastructure:** Discord bot built (`channels/discord_bot.py`) — needs correct token. Telegram live through full CRT pipeline. Both bots auto-launch from Electron and `start_services.ps1`. Intent router killed (settings UI removed, env var removed, pre-warming removed). Image upload pipeline (frontend paste/drop/select → backend → Cookie vision). `has_attachment` feature in Layer 4 — images always route to Cookie.

**Plan Approval Gate (80% done):** Cookie proposes plans → checkpoint event → approve/deny buttons show. Plan text surfaces in chat. Pending checkpoint stored in session DB. "Yes, go ahead" confirmation path written but needs testing — handler at ~line 5043 in chat.py checks for `_plan_proposal` flag.

## Research Landscape (Complete — 6 Agents, 30+ Papers)

**Genuinely novel:** Contradiction as importance signal, heuristics ARE beliefs, multi-model epistemic handoff, persistent homology on beliefs, three-regime taxonomy.
**Novel combination:** Held contradictions + BDG cascade + belief/speech auditing — pieces exist, nobody assembled them.
**Closest competitors:** Kumiho (AGM graph memory), SLM-V3 (Fisher retrieval), Governed Memory (enterprise governance), Universe Routing (epistemic dispatch).
**External validation:** UPenn proved belief/speech gap is orthogonal in model activations. Agentic Overconfidence paper documents exact problem execution beliefs solve. ERL validates earned heuristics.
**Window:** Months, not years. March 2026 produced 6 papers in your territory.

**Recommended publication sequence:** 1. Contradiction density as importance signal 2. Multi-model epistemic handoff 3. Cascade complexity paper 4. Heuristics ARE beliefs (position) 5. Three-regime taxonomy (empirical)

## Unfinished

1. Plan approval gate — test "Yes, go ahead" → plan saved flow e2e
2. Discord token — get correct bot token from Discord Developer Portal
3. Frontend rebuild — `cd frontend && npm run build` for image upload + settings removal
4. Stale profile data cleanup — Cookie generated a plan, could execute it
5. Accumulate 50+ runs for Layer 4/5 to mature
6. Start writing contradiction-density paper
