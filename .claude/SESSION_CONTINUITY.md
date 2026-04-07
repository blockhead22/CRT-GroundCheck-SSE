# Session Continuity — April 1, 2026

## Current State

This is the latest continuity file. Previous continuity covered March 25, 2026. A LOT has shipped since then.

---

## What's Happened Since Last Continuity (March 25 → April 1)

### Architecture — Major Shifts
- **Cookie-Opus Orchestrator** built and wired — brain/hands architecture where Claude Opus directs local tool execution. 15 tools. Multi-turn continuity. Plan action. Suspend/resume. Loop currently DISABLED (`and False` gate in chat.py ~line 6165) pending routing gate fix.
- **6-layer governance framework** shipped: L1 measurement (run log + SQLite), L2 alignment check, L3 contradiction detection, L4 epistemic routing (12 structural extractors, belief-weighted scoring, replaces keyword hack), L5 execution beliefs (5 pattern detectors injected into Cookie), L6 interpretation beliefs (earned epistemic posture, The Mirror structural gate).
- **All 10 CRT transformations from Claude Code leak** shipped: belief-aware compaction, density-weighted extraction, prompt cache boundary (6 axioms), inspectable memory index, context decay, restricted authority, execution belief verification, away/resume diff, consolidation pass, intent-gated tools.
- **Session state system** — running belief state per conversation, density-weighted extraction, away/resume diff, session-aware compaction.
- **User belief system** (Phase 0 of reversed CRT) — belief classifier, storage routing, /api/beliefs endpoint.
- **Prompt cache boundary** — static epistemology prefix (6 axioms) with Anthropic cache_control, dynamic evidence below boundary.

### Research & Theory
- **Cascade complexity paper** — full draft written, all 6 theorems patched with real BDG validation (599 nodes from production).
- **All 10 CRT theory modules** implemented and tested (memory splats, contradiction-as-importance, belief geometry, Fisher metric, predictive contradiction, etc.)
- **Research landscape mapped** — 6 agents, 30+ papers surveyed. CRT genuinely novel in 5 areas. Window is months, not years.
- **Vocal cords experiment** — same persistence layer, different model = different philosophical stance. GPT-4o shifted from resolving to holding through earned system pressure (not prompt engineering).

### Frontend
- **PipelineCollapse v2** — Lucide icons, stagger animations, sections, trust shift deltas.
- **Epistemic events** wired end-to-end: drift/contradiction/alignment from orchestrator → SSE+WS → frontend pipeline panel.
- **Pipeline panel** shows live agent steps, memory retrieval, verification badges, tool calls with timing.

### Infrastructure
- **Telegram** — live through full CRT pipeline.
- **Discord bot** — built, needs correct token.
- **Electron shell** — stable, frameless, tray, hotkey, auto-detect backend.
- **Image upload pipeline** — frontend paste/drop/select → backend → Cookie vision.
- **Intent router killed** — settings UI removed, env var removed, replaced by L4 epistemic routing.

### Business Strategy
- **Governance-as-a-service** decided (not the assistant). 4-phase plan: open source → hosted API → enterprise dashboard → consumer epistemic mirror.
- **Open/closed split finalized** — framework (immune agents, belief engine, splats, contradiction lifecycle, trust math) goes open. Product (prompts, providers, models, data, UI, integrations) stays closed.
- **Reversed CRT concept** — same epistemic system applied to user's beliefs.

### Bug Fixes (notable)
- Generator bug (yield in sync function broke stream)
- JSON parser rewrite (handles 4o's code-fenced multi-line JSON)
- False contradiction disclosures (GroundCheck regex garbage → hard_fail)
- Cookie iteration limit (for→while, plan doesn't consume slot)
- Tool call ID mismatch (caused Gödel hallucination)
- search_code hanging
- User message text alignment

---

## Current Session (April 1 evening)

### Topic: Closed Limited Beta Planning

Nick is preparing for limited friend beta testing (3-5 people). Key decisions being discussed:

**Proposed flow:**
1. Nick picks testers, DMs invite token + repo link
2. They clone repo, run locally
3. Backend hits Cloudflare-fronted API, Nick's key powers cloud LLM calls
4. Hard limits on Cloudflare, per-user daily caps, time windows

**Infrastructure available:**
- Wrangler CLI 3.99.0 installed, authenticated as blocknick5943@yahoo.com
- Full Cloudflare permissions (workers, KV, D1, pages, zone)
- Existing auth system (SQLite, bcrypt, rate limiter)

**Open decisions:**
- Architecture: full local stack vs hosted backend (key safety)
- Cookie exposed to beta users or base chat only?
- Per-user and total daily token caps
- Data privacy policy for tester conversations
- Onboarding tuning for non-Nick users

**What needs building:**
- Invite-only registration gate (email allowlist)
- Pre-shared beta tokens (DMD tokens)
- Cloudflare edge rules (rate limiting, IP/header firewall)
- Usage windows (beta_active_hours)
- Admin purge endpoint

---

## April 4, 2026 Update

### Open Source vs Product Boundary
- **`crt-core` is the public constitution** - laws, governance agents, immune checks, boundary principles, public interfaces, examples, and tests.
- **Aether / AI_round2 is the private product system** - orchestration, memory shaping, eval corpus, learned routing, local-first degradation handling, delegation/council behavior, integrations, and UX.
- **Working rule** - open source explains the epistemic framework; the business/product ships the system that can actually live by it.
- **Moat direction** - not the existence of CRT, but the production operating experience: continuity quality, route learning, memory ingestion, failure replay, local-model control, and real-world orchestration.

### Public Repo Cleanup Completed Today
- Hardened `D:\\crt-core` for public scope honesty: README now reflects what ships today, placeholder namespaces are described as placeholders, and product-specific validation language was softened.
- Scrubbed product/private-lore residue from core governance docstrings so the repo reads like a reusable framework rather than a leak of private project mythology.
- Added lightweight public-surface tests and GitHub Actions CI to keep the open repo credible and maintainable.

### Practical Strategy Snapshot
- **Open repo mission** - publish the CRT framework clearly enough that people can understand and adopt the governance layer.
- **Private product mission** - build a coherent governed AI system that remembers, stays honest under pressure, degrades gracefully, and feels continuous in actual use.
- **Near-term implication** - continue letting `crt-core` become the clean public framework while keeping the strongest orchestration and evaluation advantages in the closed app.

---

## April 7, 2026 Update

### Continuity-Blind Revalidation
- Rechecked the continuity-blind corpus against `data\\chatgpt_corpus.db` and confirmed the published corpus counts: `1,275` conversations and `59,370` messages.
- Audited the original scripts:
  - `tools\\corpus_consistency.py`
  - `tools\\corpus_gaslighting.py`
- Preserved the original study as **v1**: real and useful, but narrower and more heuristic than earlier prose implied.

### Docs + Plan
- Updated:
  - `docs\\continuity-blind.html`
  - `docs\\contradiction-density.html`
- Added `docs\\plans\\continuity-blind-v2-plan.md`.
- Current docs now distinguish:
  - validated v1 baseline
  - future v2 methodology upgrade

### v2 Harness State
- Added `tools\\continuity_blind_v2.py` as the deterministic successor harness.
- Added `tests\\test_continuity_blind_v2.py`.
- v2 currently supports:
  - deterministic embedding cache
  - richer continuity / confidence signals
  - typed pair labels
  - manual audit queue
  - generated HTML report in `docs\\labs`

### Important Research Lesson
- Initial v2 runs showed that broad topic retrieval alone produced weak evidence pairs.
- Main issue: many top contradiction examples were only loosely related by topic, not tightly aligned to the same underlying user question.
- Current fix in progress:
  - assistant responses now carry their preceding user prompt
  - cache now stores both response embeddings and prompt embeddings
  - pair scoring now requires a query-side semantic similarity gate
- Next meaningful rerun should use:
  - `python -m tools.continuity_blind_v2 run --refresh-index`

### HTML Report Surface
- Generated report path:
  - `docs\\labs\\continuity-blind-v2-latest.html`
- Report now includes:
  - summary cards
  - top topics
  - audit queue preview
  - model summary slice
  - heuristic token-level signal overlay for risky vs stabilizing language
- Current judgment: visualization is useful for inspection, but pair-quality validation remains the higher-ROI priority before further doc updates.

### Priority Adjustment
- Highest-ROI next work:
  1. tighten continuity pair matching
  2. manually audit top contradiction pairs
  3. rerun continuity before updating public claims further
- Activation heatmaps remain worthwhile later as an interpretability layer, but not as the core evidence surface yet.

---

## Known Rough Edges
- `unexpected_failure` noise in logs for diff_preview — cosmetic
- Discord bot failing on startup (bad token)
- Cookie hits iteration limit on complex multi-step tasks
- Cookie loop DISABLED pending routing gate fix
- Plan approval gate 80% done (approve path untested)
- Routing too permissive (generic convos hit Cookie when enabled)

## What's Solid
- Core chat + memory + trust scoring + belief graph
- Diff preview + confirmation gate end-to-end
- Telegram live
- Electron shell stable
- SSE + WebSocket streaming
- PipelineCollapse showing live agent steps
- 5 immune agents (31/31 tests)
- 3 variance regimes confirmed (16/16 robust)
- All 10 CRT transformations running

---

## Priority Queue
1. **Beta infrastructure** — invite gate, tokens, Cloudflare rules (THIS SESSION)
2. Routing gate — stop generic convos hitting Cookie, unblocks loop re-enable
3. ask_user pause/resume — core agentic primitive
4. Re-enable Cookie loop
5. Discord token
6. Contradiction-density paper
7. Frontend rebuild for latest changes
