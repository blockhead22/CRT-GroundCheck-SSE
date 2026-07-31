# Aether — Project Brief for Incoming Agents

**Repo / active product lane:** `D:\AI_round2` (especially `aether-core` + `workbench`)  
**Do not redirect work to:** `D:\crt-core`, `D:\aether-core` alone, or holder archives as primary.  
**Date context:** mid‑2026; this brief reflects the long exploration + Codex continuity/control-flow repair thread.

---

## 1. What is Aether?

**Aether** is a **local, governed personal AI memory system** with a **Workbench** UI. It is **not** trying to be a better foundation model.

### One-liners

| Layer | Line |
|--------|------|
| **Moral** | Not AI for everyone. AI that remembers *you*, on *your* machine, that you can open and check. |
| **Technical** | If it wasn’t stored and retrieved under release rules, it doesn’t get to speak as fact. |
| **Contract** | **Model = mouth (voice). Governed memory = self. Governance = evidence, release, contradiction state, writes, verification, repair, fallback.** |

### Naming (product / research stack)

| Name | Meaning |
|------|---------|
| **Aether** | Personal dogfood assistant + **Workbench** proof loop |
| **aether-core** | Python package / sidecar runtime (substrate, governance, MCP-ish tools) |
| **Aeteros** | Optional company/research umbrella (“medium through which belief travels”) |
| **CORE** | Architecture idea: Contradiction, Observation, Revision, Epistemics |
| **CRT lineage** | Older Cognitive-Reflective Transformer stack in the same monorepo (`personal_agent`, full frontend, etc.) — parent ideas, not the default Workbench target |

### What problem it attacks

Stateless (or weakly remembered) assistants give **high-confidence, low-consistency** advice to the **same person over months** (health, identity, career, projects) with **no continuity awareness**. Adding raw RAG/memory without governance often **amplifies** drift. Aether’s bet: **epistemic governance** (beliefs with source, trust, disposition, release) beats “bigger context.”

---

## 2. What exists in the monorepo (scope map)

```
D:\AI_round2\
├── aether-core/          # CURRENT product runtime for Workbench
│   └── aether/sidecar/   # FastAPI ~:8765 — chat, memory, traces, continuity…
├── workbench/            # CURRENT UI — Electron + React (docked companion)
├── personal_agent/       # OLDER full CRT “agent OS” brain
├── crt_api.py + routes/  # OLDER full API (~:8000)
├── frontend/ + electron/ # OLDER full desktop app
├── packages/             # groundcheck, belief_classifier (extractable ideas)
├── labs/                 # meaning compression, mirus, routers, evals
├── sse/                  # semantic / evidence-packet lineage
├── docs/                 # Aeteros research site (HTML)
└── models/, tools/, eval/ …
```

**Two productizations of related ideas:**

| Surface | Backend | Character |
|---------|---------|-----------|
| **Workbench** (current lane) | `aether.sidecar` :8765 | Thin, inspectable, review-gated, Continuity job |
| **Full CRT desktop** | `crt_api` :8000 + `personal_agent` | Wide agent OS (jobs, channels, heartbeat, training…) — more features, more sprawl |

**Agent rule:** Active development / Codex repair is **Workbench + aether-core**, not reviving full CRT as default.

---

## 3. How it works (user-visible)

1. User chats in **Workbench** (local Electron; optional always-on-top / Windows AppBar dock).
2. Electron spawns **Python sidecar** (`python -m aether.sidecar`).
3. Each turn roughly:
   - Route / intent signals  
   - Retrieve / plan **evidence packets** (slots, passages, authority)  
   - Decide **release**: answerable | withhold | conflict | no_evidence  
   - Optionally build **governance answer spine**, tension packet, context bridge  
   - **Generate** via Ollama (default local model) or optional **default-off frontier wording** (e.g. Grok as pure renderer)  
   - **Verify** (ownership, atoms, contracts, character critic, etc.)  
   - **One repair** then **fallback** if needed  
   - Stream **only accepted** answer; rejected drafts buffered (not speech-as-truth)  
4. User can open drawers: **Trace**, **Memory** (confirm/correct/quarantine), **Reflect**, **Support**, **Learn/consolidation**, Continuity open-loops.
5. **Exact Continuity commands** (`/where`, `/changed`, `/next`, `/resume`) use fixed claim atoms + verifier — stronger than free chat.
6. **No automatic durable writes** of memory/support/reflection/policy without explicit review/click (product law).

---

## 4. Architecture (how the stack thinks)

### 4.1 Control plane vs model

```
User message
    → exact command / tool / write gates
    → (target) attach recent ACCEPTED conversation   ← Codex Phase 2
    → select relevant durable evidence + release
    → route / spine / tension / guidance
    → model render (replaceable)
    → verify → repair once → fallback
    → one accepted answer + public trace
```

Model never owns: memory truth, release, routes, tools writes, contradiction disposition as final authority.

### 4.2 Memory model

- **Slots** (typed facts, e.g. `user:favorite_color`) with states, authority, temporal status  
- **Passages / evidence packs** (ranked; lexical + authority priors; optional encoder)  
- **Graph** edges: contradicts, supersedes, supports, related…  
- **Dispositions** on conflict: resolvable | held | evolving | contextual | stale | policy_bound  
- **Belnap-ish** states on nodes (T/F/Both/Neither lineage)  
- **Review-only candidates** (Mirus-style discovery, support patterns, reflections) — not “known” until confirmed  

### 4.3 Prompt / render modes (sidecar)

Not one RAG template. Route-selected builders, including:

| Mode | Role of model |
|------|----------------|
| `build_local_prompt` | Structured allowed/restricted JSON + tools + bridge (includes recent turns when used) |
| `build_voice_with_memory_prompt` | Free chat; personal claims only from owner-labeled pack (**historically often NO recent turns**) |
| `build_hybrid_governed_prompt` | “Holden” pure prose over spine + tension (**historically often NO recent turns**) |
| Continuity atom render | **Wording only** of fixed atoms → JSON/sentences |
| Bounded response contract | Word fixed atoms under tone/length rules |
| Deterministic cards | Sometimes no model |

Ollama client today: **`/api/generate` with a single prompt string** (`aether/sidecar/ollama.py`) — no native `/api/chat` yet.

### 4.4 “Checked / Governed” (important honesty gap)

Currently strong on **authority / safety / ownership / no silent write**.  
Weak on **relevance, conversational correctness, task completion**.  
UI “Checked” can mean “passed narrow gates,” not “good answer.”

### 4.5 CRT full stack (legacy, still in repo)

`personal_agent` + `routes/chat_old.py`: loads `recent_queries` as role dicts and (on main path) can call **`llm.chat(messages)`** multi-turn. That is the **reference** for “ordinary chat had history,” **not** Lumi/CogniForge archives. Orchestrator path is weaker (window=2, 150-char PRIOR CONTEXT dump).

---

## 5. Current roadmap (from Continuity + Codex repair thread)

### 5.1 Product north star (unchanged)

Local assistant that: answers from stored evidence, **holds multi-truth**, doesn’t invent personal lore, is **inspectable**, grows with the user — **not** phrase-route cosplay or SaaS AGI.

### 5.2 Active engineering plan (Codex control-flow repair)

**Not** “add more phrase detectors.” **Control-flow simplification.**

| Priority | Work | Intent |
|----------|------|--------|
| **P0** | Zero-evidence personal inference containment | No health/motive/psych narratives without released personal evidence |
| **Phase 2** | **Conversation context invariant** | Last few **accepted** turns on **every ordinary renderer** (voice + hybrid + local) |
| **Phase 3** | Remove global bare-**“why”** hybrid/synthesis forcing | Ordinary questions stay ordinary; hybrid only with real tension/personal evidence |
| **Phase 4** | Relevance gate before personal memory release | “Allowed” ≠ “belongs in this answer”; kill single-token leaks (e.g. “project” → embedding dim) |
| **Phase 5** | Response contracts end-to-end + honest “Checked” dimensions | Authority / relevance / coverage / conversation ref / presentation / ownership / repair |
| **Phase 6** | Frozen multi-turn suite; cross-model only after packets correct | Failures diagnose packet vs renderer |

**Natural-language Continuity routing:** remains **disabled** (semantic controller shadow-only — failed acceptance bar).

**Frontier (Grok) wording:** default-off, fail-closed, bounded high-composition kinds only; **no** tools/memory/route authority.

### 5.3 Phase 2 design decisions (round 2 reviewer → Codex)

**Invariant:** `ConversationContextPacket` attached to ordinary paths — **not** “must use Ollama `/api/chat`.”

**Acceptance rule (proposed):**

- Same conversation only; exclude current turn  
- Nonempty `user_message` + `local_answer` (strip)  
- `completed_at`  
- **Trace completion receipt** with final `source` (`persist_completion_route` / `update_trace_completion`)  
- **Do not** exclude merely because `needs_stronger_model=True` if receipt exists (flag = quality/escalation, not “unaccepted”)  
- **Do** exclude exception path: `complete_turn` with partial + `needs_stronger_model=True` **without** completion receipt  
- No rejected drafts, repair drafts, CoT, partial error streams  
- Max ~4 pairs; newest-first budget → chronological emit  

**Transport recommendation:**

1. Build packet + filter (flag off = empty).  
2. **Default: serialize** into voice/hybrid prompts as clearly delimited **“Recent accepted turns (referent only; not personal evidence)”** block (`/api/generate`).  
3. Optional later: native `/api/chat` behind second flag.  
4. **Do not** orchestrator-style dump history into the task/spine.

**Old CRT wording correction:** `recent_queries` = **nonempty stored responses**, not full “accepted” algebra. Workbench should be **stricter**.

### 5.4 Explicit non-goals right now

- Reviving full CRT frontend as primary  
- Enabling NL Continuity routing  
- Broadening Grok eligibility without frozen cases  
- Silent memory/support/reflection writes  
- Phrase catalogs as primary continuity fix  
- Porting Lumi auto-memory-write or autonomous Holden fantasy  

### 5.5 Stale vs live roadmaps

| Doc | Status |
|-----|--------|
| `aether-core/ROADMAP.md` (May 2026 library tracks 0–6) | **Stale relative to product lane** |
| Continuity handoffs (July 2026) + Codex plan | **Live product roadmap** |
| North star freeze (July 2026) | **Live philosophy** |

---

## 6. What has been proved vs aims to prove

### Proved / demonstrated (with caveats)

| Claim | Status |
|-------|--------|
| Durable slot/substrate memory + confirm/correct/quarantine | Working |
| Exact Continuity commands + atoms + verifier + repair/fallback | Product-shaped |
| Ownership boundaries (user facts not Aether “I”) in dogfood | Strong progress |
| Rejected drafts not streamed as final speech | Implemented on governed paths |
| Review-gated support/reflection candidates | Working pattern |
| Structural/slot tension without LLM on every pair | Implemented + claimed eval advantage (reproducibility discipline varies) |
| Continuity-blind / contradiction density story on personal ChatGPT corpus | Research program + HTML docs; use claim rubric |
| Frontier can beat local on **composition** while governance retains authority | Shadow/dogfood evidence (e.g. Grok 3/3 vs local 2/3 on frozen composition set) |
| Speech-cannot-upgrade-belief / premature resolution as **laws in code** | Present as immune/governance agents |

### Not proved / known weak

| Claim | Status |
|-------|--------|
| Ordinary multi-turn conversation is reliable | **Phase 1–3 control-flow landed in code (2026-07):** `conversation_context.py` packet (accepted turns + completion receipts) is injected into local/voice/hybrid prompts; bare `why` no longer forces hybrid; regression suite `tests/test_conversation_context.py` + `tests/test_phase1_conversation_control_flow.py` (21 passed as of verification). Live dogfood still recommended. Lexical relevance and honest “Checked” remain partial. |
| NL Continuity routing | Explicitly **not** enabled |
| Full SSE multimodal “meaning compression family” as product | Largely aspirational / lab |
| DNNT as primary mind | Lab; Workbench uses Ollama |
| “New intelligence that understands/feels intent” | **Not** a code claim — still LLM + structure |
| External peer-reviewed benchmark win | Incomplete |
| Market/product PMF | Not established |

### Aims to prove (program thesis)

1. **Failure is real and measurable** (stateless high-confidence inconsistency over time).  
2. **Scale alone doesn’t fix it.**  
3. **Governance can** — contradiction state, trust, release, verification, human review — on top of any replaceable model.

---

## 7. What is actually impressive (no hype)

1. **Contradiction as first-class product state** (hold vs resolve), not silent overwrite.  
2. **Release-before-render + ownership + buffered rejection** — integrity constraints most agent memory skips.  
3. **Workbench as memory debugger** (traces/receipts), not chat cosplay only.  
4. **Year-scale personal corpus problem framing** (continuity-blind contradiction) with a real research site and claim-scoring guide.  
5. **Long compositional R&D** that partially hardened into runnable law (not only a March 2025 thesis PDF/DOCX).

**Not impressive as:** new foundation model, finished consumer app, clean single architecture, solved ordinary chat (yet).

---

## 8. Pros and cons

### Pros

- Clear, defensible thesis (integrity under continuity)  
- Local-first, inspectable, privacy-aligned  
- Replaceable models (mouth only)  
- Strong exact lanes (Continuity, some profile recall)  
- Review culture for writes  
- Deep eval/lab culture when used  
- Extractable ideas (GroundCheck-like verify, dispositions, receipts)  

### Cons

- Dual stack (Workbench vs full CRT) = confusion and cost  
- Ordinary chat orchestration brittle (the active fire)  
- Heuristic/regex routing still heavy  
- Huge monorepo / dirty worktree / doc lag  
- “Checked” UX can overclaim  
- Substrate pollution / historical junk values  
- Research sprawl vs one daily job  
- Not monetized; hard to demo in 90 seconds without ceremony  

---

## 9. How to run / orient (agent practical)

- **Workbench:** `workbench/` — Vite + Electron; sidecar on **8765**; UI often **5175**.  
- **Sidecar:** `python -m aether.sidecar` with `PYTHONPATH` including `aether-core`.  
- **Key packages:** `aether/sidecar/app.py` (orchestration), `route_policy.py`, `rag_answer.py`, `prompt.py`, `continuity_*.py`, `governance_spine.py`, `db.py`, `ollama.py`.  
- **Tests:** large suite under `aether-core/tests/` (focused character/route suites used in dogfood).  
- **Continuity first-read (when allowed):** `aether-core/CONTINUITY_2026-07-15_FRONTIER_AND_EVIDENCE_HANDOFF.md`, `NEXT_SESSION.md` — product stop state; Codex work may be mid-Phase-2 on top of that.

---

## 10. Interesting / uncommon (relative to typical agent stacks)

Things that stand out vs “LangChain + RAG + memory”:

| Idea | Why uncommon |
|------|----------------|
| **Held contradictions** as intentional product state | Most systems merge/overwrite |
| **Premature resolution guard / speech-leak immune agents** | CRT “laws” as runtime monitors |
| **Evidence packets that forbid fake confidence language** (`sse` lineage) | Epistemic packaging |
| **Governance spine pre-render contract** | Structured “what may be said” before tokens |
| **Query-scoped personal synthesis** + post-render ownership repair | Personal facts as second-person only |
| **Continuity claim atoms** (wording-only model) | Strong separation of fact selection vs prose |
| **Structural tension meter** (non-LLM) for write-path | Cost/structure first |
| **Belief-as-Gaussian-splat / geometric contradiction** (partial) | Research-grade, partial live |
| **VILT** (verification-in-the-loop training with GroundCheck-like signal) | Training-time integrity idea in monorepo |
| **Support patterns** as review-gated behavior candidates | Not free-form memory |
| **Frontier as wording provider only** with disposable empty workspace | Unusual safety framing for “use Grok” |
| **Disposition simplex / multi-truth personal meaning** (e.g. preference + concern held) | Ethical product edge |

---

## 11. Lineage (for archaeology only)

```
Lumi (FAISS/DNT, always-write memory)
  → CogniForge (Holden, self_reflect, mirus, contradiction_manager)
    → CRT / personal_agent + full frontend
      → aether-core + Workbench (governed, review-gated, Continuity-first)
```

**Landing points** `H:\holder\...`, `D:\crt-core`: historical. **Not** multi-turn chat references for Phase 2 (except **ai_round2** `chat_old` + `reasoning._call_llm`).

**Origin thesis:** `workingfinal.docx` (~2025-03-27 create) — philosophy seed; code is stricter and less magical than the prose.

---

## 12. Success criteria (near term)

Call Phase 2–3 **working** when frozen multi-turn dogfood shows:

- No false “I can’t access prior conversation” when history exists  
- No bare-why hybrid poetry on general knowledge  
- No unrelated personal memory injection on general questions  
- Explicit presentation constraints honored  
- Exact Continuity + ownership + no silent writes **unchanged**  
- Fewer special phrase claimants, more ordinary chat works  

**Weekly product test (north star):** store → new session → ask → grounded, no invent.

---

## 13. One paragraph for a rushed agent

**Aether is a local Workbench + aether-core sidecar that treats personal AI as governed belief substrate: the LLM only speaks; slots/passages/dispositions/release rules decide what is true enough to say; users inspect traces and review writes. The monorepo also contains an older, wider CRT agent OS—do not default to it. Exact Continuity and memory gates are strong; ordinary multi-turn chat is the active failure mode. Codex is repairing control flow: accepted conversation context on all ordinary renderers, stop bare-why hybrid hijack, then relevance and honest verification—packet-first, serialized history in generate prompts by default, not a phrase-catalog revival. Thesis: continuity without integrity is the industry failure; Aether aims to prove governance can fix it without claiming a new foundation model.**

---

*Prefer code and Continuity/Codex plan over stale `aether-core/ROADMAP.md` for “what next.”*
