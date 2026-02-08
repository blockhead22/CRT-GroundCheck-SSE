# CRT Implementation Plan — DNNT Integration Roadmap

**Author:** Nick Block  
**Project:** CRT-GroundCheck-SSE  
**Date:** February 2026  
**Status:** Phase 1.1 in progress (started February 8, 2026; Phase 0 complete)

---

## Vision

CRT is a **personal cognitive architecture** — not a chatbot, not a RAG wrapper, not AGI.

It is a system that gets increasingly good at being one person's thinking partner. An external LLM provides general intelligence. CRT provides *personal* intelligence — learned knowledge of who this specific person is, what they care about, how they communicate, what they've contradicted themselves about, and what they mean when they say ambiguous things.

Over time, the personal intelligence handles more and the general intelligence handles less. The LLM never goes away — it's always there for the hard stuff — but it gets called less and less. The self grows. The mouth recedes.

### Core Principles

1. **"The mouth must never outweigh the self."** — The LLM output (speech) must never override the memory store (belief).
2. **Contradictions are signals, not bugs.** — Nothing is silently overwritten. Tension is preserved until reflection.
3. **Trust is earned, not assigned.** — Every memory's trust evolves through mathematical equations. Easier to lose than to gain.
4. **Auditable by design.** — Every gate decision, every trust change, every contradiction, every training step is logged and traceable.
5. **Shrink the compute, not the capability.** — A 2-20M parameter model on CPU, not a data center.

---

## Architecture: The DNNT

**DNNT = Dynamic Neuromorphic Neuro-Transformer**

The overarching architecture where each cognitive subsystem has its own learned component, all governed by trust layers.

### The Original Design (from core/)

```
MirusHoldenTransformer
├── Mirus (input layer)    — observe, resonate, compress
├── Transformer core       — learn reasoning patterns
├── Holden (output layer)  — reconstruct, gate, verify honesty
├── CogniMap               — belief topology, dependency graph
└── Trust layer            — governs what the system learns from
```

The original `model.py` had:
- **Triple loss** (semantic 0.5, syntactic 0.3, logical 0.2) — learning meaning, structure, and logic simultaneously
- **Trust-gated background learning** — only trains on LLM outputs with similarity > threshold
- **Dynamic vocab expansion** — the model grows as the user introduces new concepts
- **Compression-reconstruction round trip** — encode through Mirus, decode through Holden, fidelity is a trust signal

### The Current System (ai_round2/)

Built the body the original brain needed:
- Trust evolution math (nonlinear dynamics, asymmetric gain/loss)
- Contradiction ledger (append-only, full lifecycle)
- Reconstruction gates (Holden constraints — block confident answers when epistemic state is unresolved)
- GroundCheck (sub-2ms hallucination verification)
- SSE mode selection (bio-inspired compression: lossless/hybrid/cogni)
- XGBoost contradiction classifier + LLM drift assessor
- Episodic memory, reflection loops, heartbeat system
- Active learning with correction tracking
- MicroTransformer architecture (reasoning_learner/ — RoPE, SwiGLU, RMSNorm, 2M params)

**Missing:** The neural learning core. The DNNT. The student-teacher loop. The system retrieves and hands everything to an external LLM. There is no learned reasoning happening. Every conversation is equally dumb from the system's perspective — it doesn't get better at responding, only at remembering.

### The Merge

Take the modern MicroTransformer architecture. Wire it in like the original DNNT — embedded, continuous, trust-governed. Connect every subsystem's learning signal.

**Each component learns its own thing:**

| Component | Learns | Signal |
|-----------|--------|--------|
| **Mirus** | What to pay attention to, how to compress | Reconstruction fidelity, user corrections on forgotten details |
| **Holden** | What to let through, how precisely to reconstruct | User corrections on bad answers, gate pass/fail history |
| **Trust dynamics** | Shape of this user's reliability | Contradiction patterns, validation frequency |
| **CogniMap** | Belief topology — which beliefs depend on which | Co-occurrence, co-contradiction, co-confirmation patterns |
| **DNNT core** | Reasoning patterns: (query + facts) → thinking → response | Trust-filtered LLM outputs, user corrections as negative examples |

The transformer is the capstone, not the foundation. Mirus tells it what's relevant. Holden tells it what's reliable. Trust tells it what to weight. CogniMap tells it what's connected. The DNNT synthesizes all of that.

---

## Phase 0: Foundation (Current — Weeks 1-3)

> **Goal:** Clean the codebase so the DNNT can be wired in. You can't integrate a neural core into a 5,500-line monolith.

### Phase 0.1: Kill List + WAL Centralization ✅

- [x] Delete belief_revision/, models/reasoning_learner/ artifacts, 19 debug scripts, 12 root test files (44 files total)
- [x] Remove CodeLLMExecutor + code executor endpoints from crt_api.py (~260 lines)
- [x] Remove MySQL auth conditional (SQLite-only)
- [x] Fix 39 raw `sqlite3.connect()` calls across 8 files → `get_db_connection()` context manager
- [x] Fix dead path in ml_contradiction_detector.py
- [x] **Committed:** `[main 8aa5cc3]` — 8 files changed, 399 ins(+), 429 del(-)

### Phase 0.2: Exception Handling + Test Infrastructure ✅

- [x] Create `personal_agent/exceptions.py` — CRT exception hierarchy + `log_swallowed_exception()`
- [x] Fix 20+ silent `except Exception: pass` patterns in crt_rag.py
- [x] Upgrade conftest.py with proper fixtures (tmp_db_dir, isolated_engine, sample_memories)
- [x] **Committed:** `[main ce52bc5]` — 3 files changed, 154 ins(+), 30 del(-)

### Phase 0.3: Route Modularization Bootstrap (Completed)

- [x] Create `routes/` package with APIRouter-based entrypoint (`routes/register.py`)
- [x] Add `routes/models.py` and `routes/deps.py` as shared extraction targets
- [x] Refactor `crt_api.py` to call `register_routes(app)` (strangler pattern)
- [x] Move first endpoint to modular router (`/health` in `routes/misc.py`)
- [x] Leave remaining route groups in-place for incremental extraction without downtime
- [x] Phase 0.3 completed as bootstrap milestone (full themed extraction continues in Phase 1 hardening)

### Phase 0.4: Split crt_rag.py into Engine Modules (Completed)

- [x] Create `personal_agent/engine/` package
- [x] Extract core integration modules: anchors, resonance scoring, reconstruction fidelity, degradation detection, collapse trail logging
- [x] Wire `CRTEnhancedRAG.retrieve()` to use engine resonance hooks
- [x] Wire query pipeline to use degradation detection hook
- [x] Wire API query paths to emit collapse trails as training lineage
- [x] This creates the DNNT-facing interfaces while preserving current behavior

### Phase 0.5: Wire Core Concepts as DNNT Integration Points (Completed)

> **Critical shift:** These are NOT standalone utility functions. They are the interface layer where the neural core connects.

- [x] **Resonance scoring** hook wired in retrieval (`personal_agent/engine/resonance.py`)
- [x] **Reconstruction fidelity** hook wired in memory writes (`personal_agent/engine/reconstruction.py`)
- [x] **Anchor system** hook wired in memory/retrieval context (`personal_agent/engine/anchors.py`)
- [x] **Collapse trail logging** wired in API query paths (`personal_agent/engine/collapse_trails.py`)
- [x] **Degradation detection** wired in response gating (`personal_agent/engine/degradation.py`)
- [x] Phase 0.5 completed with live, hookable interfaces for DNNT replacement

---

## Phase 1: The DNNT Core (Weeks 4-6)

> **Goal:** Rebuild the MirusHoldenTransformer with modern architecture and wire it into the live pipeline.

### Phase 1.1: Rename + Restructure reasoning_learner → dnnt/

- [x] Rename `personal_agent/reasoning_learner/` → `personal_agent/dnnt/` (with compatibility shims left in `reasoning_learner/`)
- [x] Keep the modern architecture (RoPE, SwiGLU, RMSNorm) from the MicroTransformer
- [x] Add triple loss heads from original design:
  - **Semantic loss** (0.5 weight) — does the output mean the right thing?
  - **Syntactic loss** (0.3 weight) — is it structured correctly?
  - **Logical loss** (0.2 weight) — is it logically sound given the premises?
- [x] Each loss head has distinct computation/evaluation (content-token CE, structural-token CE, facts↔response logical coherence loss)
- [x] Add dynamic vocab expansion from original `expand_model_vocab()`
- [x] Add learnable redundancy penalty (`red_penalty`) from original MirusHoldenTransformer
- [ ] Target: 2-20M parameters, <200ms CPU inference, <50ms GPU

### Phase 1.2: Replace SimpleTokenizer with BPE

- [ ] Integrate sentencepiece or tiktoken for proper subword tokenization
- [ ] ~8000 vocab with the ability to expand dynamically
- [ ] Retrain tokenizer on accumulated conversation data
- [ ] Character-level fallback for OOV tokens

### Phase 1.3: Trust-Gated Training Pipeline

- [ ] Rebuild `background_learning()` loop from original model.py
- [ ] Training data sources:
  - **Collapse trails** — every (query, facts, thinking, response) tuple that passed all gates
  - **User corrections** — from active_learning.py, as negative examples with corrected labels
  - **LLM outputs** — only those that passed GroundCheck + reconstruction gates
- [ ] Trust gate filter: only train on examples where:
  - Retrieved memories had trust ≥ threshold
  - Response passed GroundCheck
  - No unresolved contradictions in the query's domain
  - User did not correct the response within N turns
- [ ] Hot-reload: new weights loaded without restart after background training completes

### Phase 1.4: Wire DNNT into Query Pipeline

```
User query
   │
   ▼
CRT Memory Retrieval (trust-weighted)
   │
   ▼
Mirus: resonance scoring + compression
   │
   ▼
┌──────────────────────────────────┐
│  DNNT (MirusHoldenTransformer)   │
│  (query + facts → thinking       │
│   → response)                    │
│  confidence check (perplexity)   │
└──────────┬───────────────────────┘
           │
    confident? ── yes ──→ Holden: reconstruct + gate check
           │                        │
           no                       ▼
           │              GroundCheck verification
           ▼                        │
    External LLM (Ollama)           ▼
           │              Trust evolution + log collapse trail
           ▼
    Log as training data (trust-gated)
           │
           ▼
    Holden: reconstruct + gate check
           │
           ▼
    GroundCheck verification
           │
           ▼
    Trust evolution + log collapse trail
```

- [ ] `ReasoningInference` from inference.py becomes the primary response generator
  - Started: `personal_agent/reasoning.py` quick mode now runs DNNT-first with confidence-gated fallback
- [ ] Confidence threshold determines DNNT vs LLM fallback
- [ ] Both paths go through the same Holden gates and GroundCheck
- [ ] LLM responses are logged as training data (filtered by trust gate)
- [ ] DNNT responses are logged for self-evaluation

---

## Phase 2: Mirus Learning Layer (Weeks 6-7)

> **Goal:** Mirus learns what to pay attention to and how to compress for this specific user.

- [ ] SSE mode selection becomes learned, not rule-based
  - Train on: which memories the user references back, which get corrected, which get forgotten
  - High-reference memories should have been stored lossless. Low-reference could have been cogni.
  - The error signal: "I compressed this too aggressively and lost detail the user later needed"
- [ ] Compression weights per domain
  - User talks about work a lot → high fidelity for work topics
  - User mentions food casually → aggressive compression for food topics
  - Learned from frequency + correction patterns
- [ ] Resonance scoring becomes a learned embedding comparison, not just cosine similarity
  - "This new input resonates with these 5 memories but not those 10" — that pattern is learnable

---

## Phase 3: Holden Learning Layer (Weeks 7-8)

> **Goal:** Holden learns what needs tight gates and what can be loose, per domain.

- [ ] Per-domain gate strictness
  - "When I reconstruct memories about family, the user corrects me often → tighten gates"
  - "When I reconstruct memories about music taste, approximate is fine → loosen gates"
  - Learned from correction frequency per topic cluster
- [ ] Reconstruction quality as a training signal
  - Every user correction = Holden let something through that it shouldn't have
  - Every user confirmation = Holden's reconstruction was good enough
  - Feed these as +/- examples to the gate threshold model
- [ ] Consequence-aware strictness
  - High-stakes domains (health, finance, legal) → strict regardless of history
  - Casual domains → adaptive based on learned patterns

---

## Phase 4: CogniMap Topology (Weeks 8-10)

> **Goal:** Build the belief dependency graph that the original Cogni was always meant to be.

- [ ] Replace write-only Cogni logging with a live graph structure
- [ ] Nodes = memories/beliefs, edges = relationships (supports, contradicts, depends-on, temporal)
- [ ] Edge discovery from:
  - Co-occurrence: "user mentions A and B together frequently"
  - Co-contradiction: "when A gets contradicted, B often does too"
  - Co-confirmation: "validating A tends to validate B"
  - Causal language: "because of A, I do B"
- [ ] Propagation: when a belief changes trust, connected beliefs' trust adjusts proportionally
- [ ] Visualization endpoint for the frontend (graph render of belief topology)
- [ ] DNNT context augmentation: when retrieving memories for a query, also retrieve topologically connected beliefs

---

## Phase 5: End-to-End Integration + Demo (Weeks 10-12)

> **Goal:** A working system where you can demonstrate the full cognitive architecture.

### The Demo (5 minutes, shows everything)

1. **Tell it facts.** "My name is Nick. I work at Google. I live in Austin."
   - Watch memories created, trust scores initialized, CogniMap nodes appear

2. **Contradict yourself.** "Actually, I work at Microsoft now."
   - Contradiction ledger entry created. Both memories survive. Trust adjusts.
   - CogniMap shows tension between "Google" and related beliefs (commute, office, etc.)

3. **Ask about the contradiction.** "Where do I work?"
   - Reconstruction gates detect unresolved conflict → discloses both versions
   - GroundCheck verifies the response doesn't hallucinate a resolution

4. **Resolve it.** "Microsoft is correct, I switched jobs last month."
   - Ledger updated. Trust flows. CogniMap propagates (commute beliefs now uncertain).
   - DNNT logs this resolution pattern as training data

5. **Show the learning.** After 50+ conversations:
   - DNNT handles routine queries without LLM
   - Show inference latency: <200ms (DNNT) vs ~2s (LLM)
   - Show training loss decreasing over sessions
   - Show LLM call rate decreasing over time

6. **Show the audit trail.** Pull up any memory → full trust history, every gate decision, every contradiction, every training example it contributed to.

### Metrics to Track

| Metric | Target |
|--------|--------|
| DNNT inference latency | <200ms CPU |
| GroundCheck latency | <2ms (already achieved) |
| LLM fallback rate (after 100 conversations) | <70% |
| LLM fallback rate (after 500 conversations) | <40% |
| Trust score accuracy (vs user corrections) | >85% |
| Contradiction detection recall | >90% (already achieved) |
| Training data quality (% passing trust gate) | >80% |
| Model size | <80MB |

---

## What This Project Is (For Interviews)

> "I built a personal cognitive architecture called CRT — Cognitive-Reflective Transformer. It has its own small transformer that learns reasoning patterns from external LLMs, filtered through a trust-weighted memory system that guarantees no knowledge is ever silently overwritten. The system gets smarter over time while reducing compute dependency — the small model gradually handles more, the LLM handles less. Every decision is auditable: every trust change, every contradiction, every gate decision is logged with full provenance."

### Key differentiators:

1. **Auditable epistemics** — full trust history on every memory, contradiction ledger with lifecycle tracking, gate decision logging. An auditor can trace any answer back to its evidence chain.
2. **Trust-gated learning** — the small model only trains on outputs verified by GroundCheck, cleared by reconstruction gates, and not contradicted by the user. The training signal is epistemically clean.
3. **Shrinking compute** — as the personal model learns, LLM dependency decreases. Designed for edge/on-device deployment at 2-20M parameters.
4. **Contradiction preservation** — architecturally impossible to silently overwrite. This is enforced at the code level, not by policy.
5. **Sub-2ms hallucination verification** — GroundCheck verifies every LLM claim against memory, 2,634× faster than SelfCheckGPT.

### Target employers:

- AI agent companies (need trust + memory for production agents)
- Enterprise AI (need audit trails for compliance)
- On-device / edge AI (need small models that learn)
- AI safety / alignment (need verifiable epistemics)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DNNT too small for useful reasoning | Medium | High | Start at 2M, scale to 20M. Confidence-based fallback means bad DNNT = more LLM calls, not bad answers |
| Triple loss doesn't improve over single loss | Medium | Medium | A/B test early. Worst case, single loss still works |
| Cold start problem (system is dumb for first 50 conversations) | Certain | Medium | LLM handles 100% early. Visible "learning progress" UI shows the system is improving |
| BPE tokenizer swap breaks existing training data | Low | Medium | Retrain tokenizer on accumulated data before DNNT goes live |
| Trust gate too strict → not enough training data | Medium | Medium | Configurable threshold. Start permissive, tighten as data accumulates |
| CogniMap topology gets too complex | Medium | Low | Cap edge count per node. Prune low-confidence edges periodically |
| Phase 0 split introduces regressions | Low | High | Existing 577 tests as safety net. Run full suite after each split commit |

---

## Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **0.1** Kill list + WAL | ✅ Done | Clean codebase, centralized DB access |
| **0.2** Exceptions + tests | ✅ Done | Error handling, test fixtures |
| **0.3** Route modularization bootstrap | ✅ Done | `routes/` package, router entrypoint, first extracted route |
| **0.4** Engine modularization | ✅ Done | `personal_agent/engine/` integration modules + live wiring |
| **0.5** Core concepts as DNNT hooks | ✅ Done | Resonance, fidelity, anchors, collapse trails, degradation |
| **1** DNNT core | 2 weeks | MirusHoldenTransformer v2, trust-gated training, wired into pipeline |
| **2** Mirus learning | 1 week | Learned compression, resonance scoring |
| **3** Holden learning | 1 week | Learned gate strictness, per-domain thresholds |
| **4** CogniMap topology | 2 weeks | Belief dependency graph, propagation |
| **5** Integration + demo | 2 weeks | End-to-end working system, demo script, docs |

**Total remaining from February 8, 2026: ~8-9 weeks**

Phase 0 completion: achieved on February 8, 2026  
DNNT core wired and learning: target by early March 2026  
Full architecture: target by mid to late April 2026
