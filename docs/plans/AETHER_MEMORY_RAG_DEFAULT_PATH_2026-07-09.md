# Plan: Memory-as-RAG Default Answer Path

**Date:** 2026-07-09  
**Status:** Plan — implement after approval  
**Principle:** Answers come from retrieved memory. No new phrase routing. Tools/governance only at the edges.

---

## Problem (plain)

The system does not answer from what it knows. It classifies the prompt into behavior classes (routes, phrase maps, character guides) and often narrates its own machinery. That will never feel learned.

**Fix:** One default path — retrieve relevant stored text → answer only from that. Same path for hello, how-you-work, favorite drink, meaning questions.

---

## Target shape

```text
user message
    → retrieve top-k from memory store (clear text + claims)
    → optional: tension among retrieved set only
    → generate answer grounded in that pack only
    → if empty: short “I don’t have that yet” / one clarifying ask
    → tools/governance only for write, confirm, conflict, quarantine
```

**Not in the default path:** self-tension monologue, mirus cockpit, model-name essays, keyword “behavior classes.”

---

## What already exists (use, don’t rebuild)

| Piece | Role in this plan |
| --- | --- |
| Substrate slots / claims | Structured memory units |
| `open_claims` + multi-value | Intake that can become passages |
| GPT archive fixture seed | Bulk provisional passages (`user:` / `gpt_inherited:`) |
| `docs/` HTML + MD | Architecture corpus for “how do you work” |
| GapAuditor / held disposition | Governance on *retrieved* set |
| Holden hybrid | Final prose — **only over evidence pack** |
| Archive import review | Production confirm gate |

---

## Non-goals (explicit)

- No new `if "hello"` / `if "how do you work"` routes  
- No growing `DIRECT_PROFILE_QUESTIONS` / character answer catalogs  
- No default injection of full self_tension / drives into every chat turn  
- No silent write of archive into live `~/.aether` without confirm  
- No “personality hardcode” (Nick/orange/leukemia scripts)

---

## Phases

### Phase 0 — Freeze the contract (half day)

**Deliverable:** Canonical freeze doc (not buried only in this plan).

**Landed:** `docs/plans/AETHER_NORTH_STAR_FREEZE_2026-07-09.md` + pointer `aether-core/NORTH_STAR.md`

**Acceptance:**

- [x] Default answer path described as retrieve → generate only  
- [x] Must-not-speak-unless-retrieved (model names, mirus, drives, governance jargon unless in pack)  
- [x] Dogfood probes fixed as regression list  
- [x] Live vs lab isolation + business rhythm + LLC/grant milestones  

**Probes (regression forever):**

1. Hello?  
2. How do you work?  
3. What is my favorite drink?  
4. How many favorite drinks do I have?  
5. What do I think about my favorite drinks?  
6. Why does my favorite color matter? (only if memory holds a reason)  
7. I’m tired today  
8. What do you know about me?

---

### Phase 1 — Passage memory store (1–2 days)

**Goal:** Everything answer-relevant is **clear text you can retrieve**, not only short slot scalars.

**Work:**

1. Define `MemoryPassage` (minimum fields):
   - `passage_id`, `text`, `namespace` (`user` | `gpt_inherited` | `system` | `docs`)
   - `source` (`chat` | `archive_seed` | `doc` | `confirm`)
   - `trust`, `authority`, `slot_id` optional, `created_at`
   - `evidence_ref` (conversation/title/path) optional  
2. Write API: `upsert_passage(...)` into substrate-adjacent store  
   - Prefer extend substrate or a sibling `passages.json` / table under workbench — **one clear store**  
3. Dual-write path:
   - On successful explicit fact confirm → also store a short natural sentence passage  
   - On archive fixture seed → emit passages from claims (user + gpt_inherited)  
   - On docs index → chunk key HTML/MD into `docs` namespace passages  

**Acceptance:**

- [x] Can list N passages without chat (`GET /v1/passages`, `PassageStore.list`)  
- [x] Confirming / persisting a favorite creates a retrievable sentence (dual-write)  
- [x] Fixture seed can re-export as passages (`seed_gpt_archive_fixture.py`)  
- [x] Live `~/.aether` unchanged unless operator points at it  

**Landed:** `aether/memory/passages.py`, dual-write in ingest + confirm/correct, `labs/MEMORY_PASSAGES_PHASE1.md`, `tests/test_passages.py`

---

### Phase 2 — Retrieve (1–2 days)

**Goal:** Every user message gets a **ranked evidence pack**, not a behavior class.

**Work:**

1. Index passages (start simple):
   - **v1:** BM25 or simple embedding over passage text (local encoder already in tree if usable)  
   - **v1 fallback:** token overlap if encoder cold  
2. `retrieve(query, k=8) → EvidencePack`
   - Prefer higher authority: confirmed `user` > provisional `user` > `docs` > `gpt_inherited`  
   - Never let `gpt_inherited` overwrite user facts in the pack ranking  
3. Empty pack is valid  
4. **Remove from default pack:** full self_tension, mirus candidate lists, model inventory — unless a passage in `system`/`docs` ranks in  

**Acceptance:**

- [x] “How do you work?” retrieves docs passages when seeded (unit test)  
- [x] “Favorite drink?” retrieves drink-related passages when present  
- [x] “Hello?” empty/weak pack OK  
- [x] Unit tests with fixed passage store (no live model required)

**Landed:** `aether/memory/retrieve.py`, `GET /v1/passages/retrieve`, `labs/MEMORY_RETRIEVE_PHASE2.md`, `tests/test_retrieve.py`

---

### Phase 3 — Generate from pack only (1–2 days)

**Goal:** One synthesis path. Model sees pack + short system rules. No parallel “character essay” unless pack is empty and we allow a minimal fallback.

**Work:**

1. Default chat path:
   ```text
   evidence_pack = retrieve(message)
   answer = generate(message, evidence_pack)  # local model
   ```
2. Prompt contract (short):
   - Answer using only the evidence  
   - If evidence empty: say you don’t have it / ask one question  
   - Do not invent personal facts  
   - Do not narrate internal pipeline names unless they appear in evidence  
3. **Demote** `decide_route` from answer-content chooser to **optional** tool/escalation hint (or ignore for content)  
4. Keep direct deterministic answers **only** as an optimization when pack is a single high-trust scalar and question is pure lookup — **same evidence source**, not a separate phrase table growth  
5. Held multi-value: if pack has multiple coexisting values for one preference, list them (existing multi-value logic, driven by pack)  

**Acceptance (dogfood probes):**

- [x] Hello → short; no governance speech unless evidence says so  
- [x] How do you work → docs-grounded when docs passages exist  
- [x] Drink probes → from memory; multi-value when stored  
- [x] Tired → support tone without inventing history  
- [x] About me → from governed memory / pack  
- [x] Abstract world-knowledge Qs → refuse invent (empty pack)

**Landed:** `aether/sidecar/rag_answer.py`, app wiring, `labs/dogfood_rag_phase3.py`, `labs/MEMORY_RAG_PHASE3.md`, `tests/test_rag_answer.py`  
**Toggle:** `AETHER_RAG_DEFAULT=1` (default on)

---

### Phase 4 — Governance & tools at the edge (1 day + ongoing)

**Goal:** Governance steps in when needed, not as the main OS.

| Situation | Action |
| --- | --- |
| User states a new fact | Tool/write → passage + claim; confirm policy as today |
| Pack has conflicting user claims | Surface held tension; don’t collapse |
| Pack empty + high-stakes (health) | Refuse invent; ask / review |
| Low trust / archive provisional | Label as unconfirmed in answer |
| User asks to correct | correct_slot + passage update |

**Acceptance:**

- [ ] No mandatory “tension monologue” on meta questions  
- [ ] Writes still audited  
- [ ] Archive seed stays provisional until confirm  

---

### Phase 5 — Wire archive fixture + docs (parallel, ~1 day)

**Goal:** Dense enough memory to dogfood RAG without months of live chat.

1. Re-run `seed_gpt_archive_fixture.py` → passages export  
2. Chunk `docs/architecture.html`, `start-here.html`, `THREE_LAWS.md`, `MEMORY_LIFECYCLE.md`, etc. into `docs` passages  
3. Dogfood sidecar with:
   - `AETHER_PASSAGE_STORE=.../fixture`  
   - `AETHER_ARCHIVE_SEED_ANSWERABLE=1` for fixture only  
4. **Do not** merge fixture into live `~/.aether` until review  

**Acceptance:**

- [ ] How-you-work works offline from docs passages  
- [ ] At least some personal probes hit archive-seeded user passages  
- [ ] Document known sparsity (open extract still thin without LLM extract)  

---

### Phase 6 — Optional density (later, not blocker for path)

- Small local LLM open-claim extract on archive **user** turns → more passages  
- Full 1,275 conv seed  
- Cross-namespace `tensions_with` / `interprets` edges in pack  
- Retire large parts of `character_answer` phrase catalogs once probes pass  

---

## File / module sketch (implementation)

| Module | Responsibility |
| --- | --- |
| `aether/memory/passages.py` | Passage model + store load/save |
| `aether/memory/retrieve.py` | `retrieve(query, store) → EvidencePack` |
| `aether/sidecar/rag_answer.py` | Build prompt from pack; call model; empty-pack policy |
| `aether/sidecar/app.py` | Default chat path → rag_answer; demote route-as-content |
| `scripts/index_docs_passages.py` | Chunk docs → passages |
| `scripts/seed_gpt_archive_fixture.py` | Emit passages as well as slots |
| `labs/MEMORY_RAG_LAB.md` + probes | Regression |

---

## Success metrics

| Metric | Pass |
| --- | --- |
| Probe suite (8 questions) | No invent; grounded when memory exists |
| New phrase routes added | **0** for this workstream |
| “How do you work?” cites docs content | Yes (paraphrase of retrieved docs OK) |
| Self-tension / model list in hello | No unless retrieved |
| Live substrate mutation from archive seed | No without explicit confirm path |

---

## Risk register

| Risk | Mitigation |
| --- | --- |
| Sparse archive extract | Docs passages for meta; LLM extract later for personal density |
| Encoder cold / slow | BM25 fallback |
| Team habit of adding routes | Lab fails if new phrase table used for probes |
| Empty pack feels dumb | Honest empty response > fake warmth |

---

## Order of execution (when “go”)

1. Phase 0 checklist freeze  
2. Phase 1 passage store + dual-write from confirm  
3. Phase 2 retrieve + tests  
4. Phase 3 default path swap + demote always-on meta dump  
5. Phase 5 docs + fixture passages + dogfood  
6. Phase 4 tighten governance edges  
7. Phase 6 density when path is trusted  

---

## One-line north star

**One path: memory in, relevant memory out, answer from that — learn by storing, not by routing.**

---

## After this work — direction, LLC, grants (when “it’s time”)

This section is intentional. The RAG path is not the end; it is the **proof floor** that makes structure and funding conversations honest instead of theatrical.

### Trajectory (clear order)

```text
1. Memory-as-RAG default works (this plan, Phases 0–5)
2. Dogfood proves it on your life + archive fixture (not demos)
3. LLC shell (structure for money/IP — can be earlier if paperwork only)
4. Grant packaging with honest scope
5. Optional team / larger raise only if product users exist beyond you
```

**Rule:** Do not sell “finished personal AI.” Sell **governed local memory that answers from what was stored**, with held tension — once that is demonstrably true.

---

### Milestone A — “RAG path is real” (end of Phases 3–5)

**You’re here when:**

| Check | Pass looks like |
| --- | --- |
| Same path for all probes | Hello / how-you-work / drinks / tired / about-me — no special phrase routes added |
| Grounded answers | “How do you work?” comes from docs memory; personal Qs from stored passages |
| Empty is honest | Missing memory → “I don’t have that,” not invent or cockpit monologue |
| Multi-value | Two drinks (or similar) list/count without collapse |
| No makeup lore | Demo hardcode off; no Nick/orange scripts in default path |
| Artifact | Probe log + short video or trace screenshots + this plan checked off |

**Not yet funding pitch.** This is **builder proof** you stopped the routing circle.

**Nick note to self:** *When A is green, stop adding routes. Celebrate the path. Then decide LLC vs more density — not more architecture renames.*

---

### Milestone B — “It’s time to form the LLC” (structure, not success theater)

LLC is **legal plumbing**, not a product award. Form it when **any** of these is true:

| Trigger | Why |
| --- | --- |
| You will apply for a grant that wants an entity | Eligibility / bank / tax |
| You will take even small paid work / contractor IP | Clean assignment |
| You want IP / repo ownership off personal-only | Continuity |
| You’re about to put real money into infra/tools under a brand | Accounting |

**You can form LLC in parallel with Milestone A** if paperwork is the only goal.  
**You should not wait for “perfect AI”** to form an LLC — and **you should not claim product-market fit** just because an LLC exists.

**Minimum LLC readiness checklist:**

- [ ] Name + purpose (governed local memory / personal AI infrastructure)  
- [ ] Who owns IP (you / assignment into LLC)  
- [ ] Banking + basic books if any grant/revenue  
- [ ] One-page description matching **what actually works** (RAG memory path), not the roadmap fantasy  

**Nick note:** *LLC = “I’m treating this as a real vessel.” Not “I’m funded.”*

---

### Milestone C — “It’s time to prove grants / non-dilutive funding”

Grants want **credible problem + method + evidence + honest gaps**, not polish.

**You’re grant-ready when Milestone A is true AND most of these:**

| Check | Evidence |
| --- | --- |
| Clear problem | Corporate/chat memory loses personal multi-truth; tools flatten or invent |
| Differentiated method | Local substrate + retrieve-from-memory + held tension (not another chatbot) |
| Working demo | 5–10 minute path: store → new session → retrieve answer; multi-value; no invent |
| Evaluation | Probe suite results; optional archive fixture stats; self-critique documented |
| Scope honesty | “Infrastructure / research tooling,” not “solves personal AI” |
| One-pager + budget sketch | What money buys (time, eval, open artifacts) |
| Entity | LLC or equivalent if the program requires it |

**Target shape (realistic):** small/niche grants — personal AI, local agents, AI governance tooling, open infra — tens to low hundreds of k, not island money.

**Pitch line that matches the work:**

> A local memory system that **answers only from what it stored**, holds conflicting personal truths under tension, and makes governance visible — demonstrated on real archive + live dogfood, not prompt theater.

**Not grant-ready if:**

- Answers still depend on phrase routes or demo hardcode  
- “How do you work?” is still a self-tension monologue with empty docs retrieval  
- You cannot show store → forget session → recall without cheating  

**Nick note:** *When C is true, write the one-pager. Until then, more memory path — not more pitch decks.*

---

### Milestone D — “Maybe commercial / partners” (later)

Only after C-ish proof plus **someone who isn’t you** gets value (even 3–5 serious users or one design partner).

Needs: clearer product shape (library vs workbench vs both), support story, still no overclaim.

VC-style funding stays **optional and later** — this plan does not optimize for it.

---

### Results that count (what to show a funder or future-you)

| Result type | Example artifact |
| --- | --- |
| Behavioral | Probe suite before/after RAG path (routes vs retrieve) |
| Continuity | New thread, same memory answers |
| Multi-truth | Two favorites + concern held, not collapsed |
| Anti-invent | D0-style: no health story without stored claim |
| Corpus | Archive fixture + docs retrieval (how-you-work) |
| Honesty | Written gaps (sparse extract, no multi-user yet) |
| Self-use | You actually use it for a week without turning hardcode back on |

---

### Timeline sketch (indicative, not a promise)

| Window | Focus |
| --- | --- |
| Now → ~2 weeks | Phases 0–5 RAG path + docs/fixture dogfood → **Milestone A** |
| Same window or whenever | LLC if grant/entity need → **Milestone B** (can overlap) |
| After A stable + 1–2 weeks packaging | One-pager, demo tape, eval note → **Milestone C** first applications |
| Later | Density (LLM extract), more users → **Milestone D** |

If A slips, **do not** jump to C with demos and routes. That restarts the circle.

---

### Decision tree (print this)

```text
Does default chat answer from retrieved memory on the probe suite?
  NO  → stay on this RAG plan. No grant story yet.
  YES → Milestone A.
        Need entity for money/IP/grant form?
          YES → Milestone B (LLC).
        Can you demo store→recall, multi-truth, anti-invent, honest scope in 10 min?
          NO  → tighten demo + eval; still not C.
          YES → Milestone C (grant packaging).
        Non-you users getting value?
          YES → consider Milestone D.
```

---

### How this plan “includes the direction after”

| This plan delivers | After that, direction is |
| --- | --- |
| Technical proof floor (memory RAG) | Stop circling routes |
| Dogfood credibility | LLC when structure needs it |
| Artifacts funders understand | Grants when A+demo+honesty exist |
| Explicit “not yet” gates | Protects you from pitching too early |

**North star after the work:**  
*Nick: when memory answers like a notebook, make the vessel (LLC) if needed; when you can show that notebook working without makeup, it’s grant time — not before.*
