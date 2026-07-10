# Architectural assessment: `D:\AI_round2`

**Date:** 2026-07-10  
**Method:** Code, tests, import graphs, and live call paths first. Markdown plans consulted only after the code picture; anything from docs is labeled.  
**No edits.** No secure-packet / funding-narrative product pitch as a conclusion unless the code forces it.

---

## 0. Two generations, and what is live

### Live Workbench path (current product surface)

| Layer | Evidence |
|--------|----------|
| UI | `workbench/` → `VITE_AETHER_API_BASE` default `http://127.0.0.1:8765` (`workbench/src/api.ts` L16–17, L144–154) |
| Chat | `POST /v1/chat/stream` (`workbench/src/api.ts` L148; `aether/sidecar/app.py` L828–829) |
| Process | `python -m aether.sidecar` → uvicorn loopback only (`aether/sidecar/__main__.py` L10–15) |
| Memory UI | `/v1/slots`, confirm/correct/quarantine (`app.py` L2147+, L2263–2338; `api.ts` L49–68) |
| Trace UI | `/v1/traces/{turn_id}` (`api.ts` L54) |
| Review UI | reflections, support-patterns, consolidation (`api.ts` L80–116; drawers in `App.tsx` L6–13) |

**Workbench does not import `personal_agent`, MCP, or `frontend/`.**

### Current chat pipeline (executable order)

From `chat_stream` (`app.py` L828+):

1. Begin turn, load recent turns (L831–842)
2. Ingest explicit facts → substrate write (L858–864, L885)
3. Mirus **review-only** candidates (L865–879)
4. `GovernedQueryService.query_context` over substrate (L893)
5. `run_semantic_tools` (L898–904)
6. Passage hydrate + evidence pack (L919–921 region)
7. Context bridge (L937+)
8. **Answer cascade:** meta → direct → tool answer → character → memory write/candidate → self_description → **RAG** (only if no earlier claimant) (L993–1106)
9. `decide_route` + **keyword force hybrid** (L1137, L1162–1183)
10. Hybrid prompt / voice_with_memory / local prompt (L1325–1368 region)
11. Stream Ollama; character/hybrid repair loops

That cascade is the product’s real “architecture.”

### Implemented but **not** on Workbench chat path

| Module | Used by | Role |
|--------|---------|------|
| `aether.governance.*` | MCP + CLI + unit tests, **not** `sidecar/app.py` | Auditors/detectors |
| `aether.epistemics` | tests / public surface | “backprop” package |
| `aether.predictive` / `aether.topology` | MCP tools + tests | splats / homology |
| `aether.crt` | tests, `integrations/crt.py` defaulting to old `personal_agent/crt_facts.db` | CRT port, not chat router |
| `aether.mcp` | separate MCP server entry (`pyproject` scripts) | not Workbench |

**Docs-only for this assessment:** Continuity Desk, secure packets, LLC/grant framing — not present as executable Workbench features (as of this assessment).

### Old architecture (`personal_agent` + `crt_api` + `frontend`)

Still a large, separate stack:

- `crt_api.py` imports CRT RAG, jobs, DNNT, model_router, etc. (L25–99 region)
- Intent stack: `semantic_intent_router.py`, `llm_intent_router.py`, wired from `task_agent.py` (`classify_intent_hybrid` L1374–1385; semantic lazy-load L1353–1371)
- `agent_tool_loop.py` (~1300 lines), `thinking_loop.py`, `scaffold_generation.py`, `response_synthesis.py`, `orchestrator.py`
- UI: `frontend/` (`crt-frontend`), including belief map — **not** `workbench/`

**No import path from `aether-core` sidecar → `personal_agent` for chat.** Cross-links are comments, CRT port heritage, and optional DB path in `integrations/crt.py`.

---

## 1. North star (from architecture only)

From **package description + live graph**, not from plan MD:

> **Persistent, authority-aware belief state (substrate) outlives any model; the model is a mouth; writes are gated; answers and review are traceable.**

Evidence:

- `pyproject.toml` description: substrate is the self, model is the mouth.
- Live: `SubstrateGraph` + confirm/correct/quarantine APIs.
- Live: review-only Mirus candidates (`ingest` / `mirus_governed_discovery` — no silent confirm).
- Live: SSE `trace` + governance_step events (`api.ts` L136–138).
- Live: Ollama as renderer (`ollama` client; generative branches).

**What the architecture is *not* proving as north star:** a daily work app, a full agent OS, or “CRT geometry product.” Those are either the old stack or labels on heuristics.

---

## 2. What the old architecture did better

| Capability | Old evidence | Current gap |
|------------|--------------|-------------|
| **Intent for *actions/tools*** | Hybrid: regex + LLM router + embedding fallback (`task_agent.py` L1374–1385; `semantic_intent_router.py` L1–8, prototypes L25+) | Workbench tools are mostly **phrase/scaffold** (`tools.py` header L1; map aliases L717+) |
| **Multi-step tool execution** | `AgentToolLoop` (`agent_tool_loop.py` ~527+) | Sidecar tools run once per turn, no comparable loop |
| **Task decomposition** | `TaskOrchestrator` (`orchestrator.py` L35–83) | No equivalent in sidecar |
| **Synthesis under memory pressure** | `scaffold_generation` / `response_synthesis` (opt-in flags in old CRT path) | Current “synthesis” often = hybrid prose + tension packet keywords |
| **Breadth of “agent product”** | Desktop, shell, jobs, training loops via `crt_api` | Workbench is chat + review drawers |

Old stack traded **safety and clarity** for **capability surface**. It was a real agent/orchestrator attempt.

---

## 3. What current architecture made safer / cleaner / newly viable

| Gain | Evidence |
|------|----------|
| **Slot-first memory with history** | `substrate/__init__.py` L1–45; `slots` API |
| **Authority / answerability** | `runtime/query.py` `CONFIRMED_SOURCES` / `answerable_sources` L13–40 |
| **Review gates (not silent write)** | Mirus candidates `review_required=True` (`ingest.py` L54–68); reflections create path |
| **UI for memory + trace + support** | Workbench drawers, not buried in CRT inspector only |
| **Bounded local sidecar** | Loopback-only bind (`__main__.py` L11–13) |
| **Memory-as-RAG skeleton** | `passages` + `retrieve.EvidencePack` (`retrieve.py` L1–7, L76–79); wired in chat (L919+) |
| **Separation from mega-`crt_api`** | Smaller product boundary (still swollen *inside* sidecar) |

**Newly viable because of substrate+review+trace:** personal multi-value coexistence, correction without rewrite-as-truth, “won’t invent personal fact,” review candidates with receipts — *when routes hit those paths*.

---

## 4. Single biggest architectural bottleneck today

**Answer-path selection is a brittle, ordered phrase/heuristic cascade inside one ~2.3k-line handler, with a ~3k-line character monologue catalog as the main “understanding” layer.**

Evidence:

- Cascade order `app.py` L993–1106
- Character built *before* RAG when character matches (`L1074–1106`) — phrase routes can **steal** before memory pack
- Hybrid force on bare keywords including `"governance"`, `"held tension"`, etc. (`L1174–1183`)
- `decide_route` is rule/signal text matching (`route_policy.py` L68–79, L82–99)
- `character_answer.py` ~3150 lines of `_asks_*` phrase gates
- `direct_answer.py` favorite/phrase maps (e.g. L18–20)
- `meta_answer.py` phrase intents for governance layers

This bottleneck **produces** the dogfood pathology: meta self-tests hit deterministic/hybrid theater; real work has no first-class path.

Secondary bottleneck: **two product generations co-exist** (`personal_agent`+`crt_api`+`frontend` vs `aether-core`+`workbench`) with no shared live runtime — maintenance and identity confusion.

---

## 5. Over-dependent on phrase matching / deterministic routes / handcrafted guidance?

**Yes — heavily.**

| Mechanism | Live? | Nature |
|-----------|-------|--------|
| meta_answer phrase intents | Yes | Deterministic |
| direct_answer slot phrases | Yes | Deterministic |
| character_answer `_asks_*` + guidance spines | Yes | Phrase + handcrafted spine text |
| hybrid keyword force | Yes | Phrase |
| route_policy synthesis markers | Yes | Phrase/signals |
| tools Wisconsin/map aliases | Yes | Phrase |
| RAG / voice_with_memory | Yes | Retrieval + model (better, but often **shadowed**) |
| Semantic embedding intent (old) | **No** on Workbench | Was better for tools |

Model generation exists, but **which generator and with what spine** is mostly phrase-decided.

---

## 6. Old mechanisms that become useful *only after* substrate / authority / review / trace?

| Old idea | Why newly relevant |
|----------|-------------------|
| **Semantic / hybrid intent** (`semantic_intent_router`, `llm_intent_router`, `classify_intent_hybrid`) | Current stack has **places to route to** (substrate packet, tools, review-only, hybrid, voice) that need a real classifier — not more `_asks_*` |
| **Evidence / citation discipline** (old CRT RAG citation modules) | Substrate authority + evidence pack give citations something true to bind to |
| **Scaffold / constrained generation** (`scaffold_generation`) | Useful *if* bound to a governed pack + verifier — not as free poetic scaffold |
| **Response synthesis** | Useful for multi-source packs (git+turns+slots) once Continuity-like packs exist |
| **Tool loop** | Only if tool results stay in receipts and memory writes stay review-gated |

**Not newly relevant to revive as-is:** full `AgentToolLoop` autonomy, DNNT training loops, desktop control, multi-intent orchestrator for chat identity questions.

---

## 7. Candidate directions (skeptical compare)

| Direction | Code support | Verdict |
|-----------|--------------|---------|
| Revive semantic/LLM intent controller | Strong old code; **zero** Workbench wiring | High leverage **if narrowed** to answer-class, not full agent |
| Strengthen memory-as-RAG | Partial live; often preempted by character/meta | Necessary **substrate work**, not the daily job by itself |
| Continuity Desk | **Not implemented** (docs/prior advice only) | Best **product job**; must not be another phrase monologue |
| Frontier-model routing | Escalation API exists (`api.ts` L70–74; `escalation.py`); not core loop | Premature as main bet; local path already generative |
| More Workbench tools | Partial tools path | Useful after intent + continuity pack |
| More deterministic route hardening | Dominant strategy already | **Wrong primary move** — deepens bottleneck |
| CRT geometry / topology / backprop | Tests/MCP only on chat | Research, not next product eng |

---

## Recommended ONE next engineering move

### Precise boundary

```text
Add a first-class Continuity answer family on the live path:
  evidence pack (deterministic) → optional model voice bound to pack → trace
  selected by a *small* answer-class gate (not 3k lines of character phrases)
```

**Architectural name:** Continuity as a **packetized answer path**, peer to meta/direct/RAG — **not** a new hybrid keyword.

Implement:

1. **`build_continuity_pack(...)`** — pure functions: last N turns from `WorkbenchDB`, optional git status for configured workspace root, confirmed slots from substrate.
2. **`build_continuity_answer` / prompt** — deterministic sections + model only for “next 3” phrasing bound to pack.
3. **Single entry in `chat_stream`** early enough that hybrid cannot steal (same protection pattern as meta preservation).
4. **Workbench:** one button or slash → fixed messages (`/where`, `/changed`, `/next`) or auto-brief on empty composer — UI only, no second brain.

### Old code worth adapting

- **Prototype/embedding intent idea** from `semantic_intent_router.py` L25+ and `task_agent.classify_intent_hybrid` L1374+ — only for **answer classes**:
  `{memory_lookup, continuity, system_meta, general_voice, tool, personal_meaning}`
- Optional: **coherence scoring** spirit of `scaffold_generation._score_coherence` — as verifier, not as identity speech.

### Current code to connect

- `app.py` `chat_stream` cascade (after tools/context, before/around hybrid force)
- `db.py` conversation turns / traces
- `GovernedQueryService` / substrate slots
- `retrieve.EvidencePack` pattern for “continuity pack”
- `build_voice_with_memory_prompt` pattern for model bound to pack
- Workbench `ChatPanel` / `App.tsx` for one control

### Do not revive

- Full `AgentToolLoop` as default chat
- `thinking_loop` as primary UX
- `crt_api` mega-stack merge
- DNNT / desktop_agent
- Expanding `character_answer` phrase catalog for continuity
- Topology/predictive/epistemics on critical path

### Smallest viable implementation

1. Continuity pack builder + unit tests (no model).
2. Sidecar: if message matches **fixed** continuity commands *or* empty-session “where were we”, emit pack-bound answer; set `source=aether_continuity`.
3. Block hybrid for that source.
4. Workbench button “Where were we?” posting that message.
5. One live harness: dirty git file appears in `/changed`; no “interwoven currents.”

### 1–2 week validation experiment

| Day | Action |
|-----|--------|
| 1–3 | Pack + `/where` `/changed` deterministic |
| 4–5 | `/next` model-bound; pin open loop store (SQLite or slot) |
| 6–10 | Nick opens Workbench daily for **work** on aether-core; log opens and whether next-step was followed |

### Pass / fail

| Pass | Fail |
|------|------|
| ≥5 days open for continuity, not meta quiz | Still default to “what are you?” |
| `/changed` lists real dirty files / recent commits | Invented files or hybrid poetry |
| `/next` items cite turn/file/slot or refuse | Uncited next steps |
| Meta self-probes not required for daily use | Continuity only works if you phrase-match carefully |

### Rollback / stop

- Stop if Continuity becomes another 500 lines of `_asks_*` in `character_answer`.
- Stop if hybrid force is the only way it “works.”
- Rollback: feature-flag `AETHER_CONTINUITY=0`; no substrate schema break.

### Safety / product risks

- **Git noise** overwhelms signal
- **Stale next** suggests finished work
- **Silent memory pollution** if next-steps auto-write identity
- **Scope creep** into full IDE agent
- **False product readiness** if Continuity works only on aether-core monorepo path hardcoding

---

## Terminology audit (skeptical)

| Term | Live meaning on Workbench chat |
|------|--------------------------------|
| **Mirus** | Review-only candidate pipeline + heuristics (`mirus_governed_discovery.py` L1–11; scalar “splat” variance L29–58 — **not** real geometric CRT) |
| **Holden** | Comments + hybrid prose cleanup / degraded detection in `app.py` — **not** a separate runtime module |
| **CRT** | Port package + integration DB path; **chat path uses “crt_migration_signals” as trace fields from Mirus heuristics**, not full CRT engine |
| **Epistemic backprop** | Package + tests — **not** chat loop |
| **Tension geometry** | Keyword disposition + variance scores in Mirus — **not** topology layer on chat |
| **model=voice / memory=self** | Partially implemented (`rag_answer`, voice prompt) but **overridden** by phrase cascade and hybrid |

---

## LLC / funding (from architecture evidence only)

| Question | Assessment |
|----------|------------|
| **Coherent LLC-owned project?** | **Not yet.** Two generations (`personal_agent`/`crt_api`/`frontend` vs `aether-core`/`workbench`), alpha status (`pyproject` Development Status 3), north star clearer than **daily job**. LLC as legal shell is orthogonal; **product coherence is not**. |
| **Non-dilutive funding exploration justified?** | **Exploratory only**, not application-ready. You have real modules (substrate, review, trace UI) but **no single measurable daily job** proven in code. |
| **Missing before serious funding** | (1) One live job used weekly with logs; (2) eval suite that is not meta-self-chat; (3) clear single product boundary (Workbench path only); (4) honest claims (no “geometry” without topology on path); (5) threat model if claiming safety. |
| **Defensible contribution** | **Integration of governed memory + authority + review + trace**, not any one of: raw memory, pure synthesis, or continuity theater. Continuity is the **use case**; substrate/review/trace is the **defensible tech**. Synthesis without pack is weak. |

---

## Finish

### A. One recommended next move

**Ship Continuity as a first-class, pack-bound answer path on the live Workbench/sidecar stack** (deterministic evidence + bound voice), and **stop growing phrase routes** as the primary strategy.

### B. One viable alternative

**Narrow answer-class intent controller** (adapt old semantic/LLM hybrid *only* for 5–6 answer classes) wired at the top of `chat_stream`, demoting `character_answer` phrase catalog over time — without Continuity UI first. Fixes routing; still lacks a daily job until Continuity or tools attach.

### C. One tempting distraction to avoid

**Reviving the full old agent OS** (tool loop + desktop + DNNT + `crt_api` merge) or **more hybrid/governance keyword monologue** and CRT geometry marketing without wiring topology into chat.

### D. Most surprising old mechanism newly relevant now

**Hybrid semantic + LLM intent classification for routing** (`task_agent.classify_intent_hybrid` + `SemanticIntentRouter` prototypes) — it was built for tool chaos; the new substrate/review/trace stack finally gives it **safe, typed destinations**. The current system reinvented intent as **string contains** at larger scale.

---

## Related docs

- Continuity Desk product answer: `docs/plans/AETHER_FIRST_DAILY_JOB_CONTINUITY_DESK_2026-07-10.md`
- Secure-packet pivot (deferred): `docs/plans/AETHER_SECURE_CONTEXT_PACKET_PIVOT_PROMPT_FOR_GROK_2026-07-09.md`
- Product root: `D:\AI_round2\aether-core`
- Old stack root: `D:\AI_round2\personal_agent`
- Live UI: `D:\AI_round2\workbench`

*Markdown plans (Continuity Desk writeup, packet pivot, grokbuild handoffs) align with “need a job” and “routing is brittle,” but the bottleneck and live path claims above stand on code alone.*
