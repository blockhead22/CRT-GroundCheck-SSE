# CRT System Architecture Specification

**Version:** 0.9.0-freeze  
**Date:** February 8, 2026  
**Author:** Nick Block  
**Status:** FROZEN — canonical reference for all development

---

## 1. System Identity

**Name:** CRT — Contradiction-Resilient Trust  
**Package:** `crt-memory`  
**Classification:** Personal Cognitive Architecture  
**License:** MIT

CRT is **not** a chatbot, RAG wrapper, or AGI attempt. It is a personal cognitive layer that sits between a human and an external LLM, providing *personal intelligence* — memory that evolves, trust that is earned, and contradictions that are never silently resolved.

> "The mouth must never outweigh the self."  
> — LLM speech never overrides memory belief.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                         USER                                 │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Gateway                            │
│              crt_api.py → routes/*                            │
│         99 endpoints across 10 modular routers               │
└──────┬───────────┬──────────┬────────────┬───────────────────┘
       │           │          │            │
       ▼           ▼          ▼            ▼
┌───────────┐ ┌─────────┐ ┌──────────┐ ┌────────────────┐
│  CRT RAG  │ │  SSE    │ │ Ground   │ │  Background    │
│  Engine   │ │  Client │ │  Check   │ │  Systems       │
│           │ │         │ │          │ │                │
│ crt_rag.py│ │ client  │ │ verifier │ │ heartbeat      │
│ crt_core  │ │ extrac- │ │ fact_ext │ │ reflection     │
│ crt_memory│ │ tor     │ │ semantic │ │ training_loop  │
│ crt_ledger│ │ coher-  │ │ matcher  │ │ jobs_worker    │
│           │ │ ence    │ │ neural   │ │ scheduled_tasks│
│           │ │         │ │ extrac-  │ │ thinking_loop  │
│           │ │         │ │ tor      │ │ continuous_loop│
└─────┬─────┘ └────┬────┘ └────┬─────┘ └────────────────┘
      │            │           │
      ▼            ▼           ▼
┌──────────────────────────────────────────────────────────────┐
│                    DNNT Neural Core                           │
│          Dynamic Neuromorphic Neuro-Transformer               │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Mirus   │  │  Holden  │  │  Trust   │  │  CogniMap  │  │
│  │ (input/  │  │ (output/ │  │  Gate    │  │  (belief   │  │
│  │  percep- │  │  recon-  │  │  (train  │  │  topology) │  │
│  │  tion)   │  │  struct) │  │  filter) │  │            │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
│                                                              │
│  Model: MicroTransformer (RoPE, SwiGLU, RMSNorm)            │
│  Params: 2-20M | Inference: <200ms CPU | Size: <80MB        │
└──────────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────────────────────┐
│               Persistent Storage Layer                        │
│                                                              │
│  SQLite DBs (per-thread)    FAISS vector indices             │
│  JSON ledgers               Append-only logs                 │
│  Collapse trail archives    Schema-validated artifacts        │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. The Three Interlocking Systems

### 3.1 CRT — Contradiction-Resilient Trust

The mathematical core. Governs how memory is stored, scored, retrieved, trusted, and evolved.

| Component | Responsibility |
|-----------|---------------|
| `CRTMath` | Trust evolution equations, drift measurement, retrieval scoring |
| `CRTConfig` | Hyperparameters — tuned from adversarial stress tests |
| `MemoryItem` | Immutable memory attestation with trust, confidence, source, temporal metadata |
| `ContradictionLedger` | Append-only contradiction history — OPEN → REFLECTING → RESOLVED/ACCEPTED |
| `FactSlots` | Tier A (regex hard slots) + Tier B (LLM open-world tuples) |
| `DisclosurePolicy` | Yellow-zone routing with per-session contradiction budget |

**Non-negotiable invariants:**
1. No memory is silently deleted or merged
2. Every contradiction is logged with both sides preserved
3. Trust is asymmetric: harder to earn ($\eta_{\text{pos}} = 0.10$) than to lose ($\eta_{\text{neg}} = 0.15$)
4. Fallback speech is capped at $\tau = 0.3$ trust
5. Below $\tau_{\text{train\_min}} = 0.6$, memory is excluded from weight updates

### 3.2 GroundCheck — Inline Hallucination Verification

Sub-2ms claim-level verification. Not a post-hoc audit tool — runs inline on every response.

| Component | Responsibility |
|-----------|---------------|
| `GroundCheck` | Orchestrates extraction → matching → scoring → classification |
| `FactExtractor` | Heuristic slot extraction with compound value splitting |
| `HybridFactExtractor` | Regex + neural NER fallback |
| `SemanticMatcher` | 5-stage matching: exact → normalized → fuzzy → synonym → embedding |
| `TupleVerifier` | Subject-predicate-object verification |

**Performance envelope:**
- Mean latency: **1.17ms**
- p95 latency: **2.09ms**
- 2,634× faster than SelfCheckGPT

**Non-negotiable invariants:**
1. Mutually exclusive slots (employer, location, name, etc.) cannot hold multiple values simultaneously
2. Trust difference ≥ 0.3 suppresses low-trust contradicting memories
3. Minimum trust for disclosure: 0.75
4. Semantic similarity threshold: 0.85

### 3.3 SSE — Semantic String Engine

Claim extraction with character-level provenance. Constitutional enforcement makes it architecturally impossible to resolve contradictions.

| Component | Responsibility |
|-----------|---------------|
| `SSEClient` | Constitutional governor — exposes ONLY Phase A-C operations |
| `SSENavigator` | Read-only navigation — `SSEBoundaryViolation` on prohibited ops |
| `CoherenceTracker` | Disagreement graph — tracks, never resolves |
| `Extractor` | Claim extraction with char offsets, negation detection |
| `Contradictions` | Heuristic + NLI-based contradiction detection |

**Constitutional principle:** If a method exists on the client, it is permitted. If it does not exist, `AttributeError` fires at call time. No runtime configuration. No feature flags. No workarounds.

**Non-negotiable invariants:**
1. No `add_confidence_score()` — SSE never weights claims
2. No `pick_winner()` — SSE never resolves contradictions
3. No `synthesize_answer()` — SSE never generates conclusions
4. No `learn_from_feedback()` — SSE never adapts to preferences

---

## 4. Inference Pipeline

```
User query
    │
    ▼
┌─────────────────────────┐
│  Memory Retrieval        │  R_i = sim × recency × (α·τ + (1-α)·c)
│  Trust-weighted scoring  │  α = 0.7 (trust dominates)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Mirus Resonance         │  Compression + embedding
│  Similarity to anchors   │  Confidence routing (CPU vs GPU)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  DNNT Inference          │  <200ms CPU target
│  Confident?              │
└───┬──────────────┬──────┘
    │ YES          │ NO
    ▼              ▼
 [Holden      [External LLM
  Gates]       Fallback]
    │              │
    │              ▼
    │         [Log as training
    │          data, trust-gate
    │          filtered]
    │              │
    └──────┬───────┘
           │
           ▼
┌─────────────────────────┐
│  GroundCheck             │  Claim extraction → memory matching
│  Hallucination gate      │  Sub-2ms inline verification
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Trust Evolution         │  τ_new = clip(τ + η·f(D_mean), 0, 1)
│  Contradiction ledger    │  Append-only, never silent
│  SSE compression         │  Lossless / Cogni / Hybrid
└──────────┬──────────────┘
           │
           ▼
       Response
```

---

## 5. Trust Mathematics

### 5.1 Retrieval Score

$$R_i = \text{sim}(z_q, z_i) \cdot \exp\!\left(\frac{-(t_{\text{now}} - t_i)}{\lambda}\right) \cdot \left(\alpha \cdot \tau_i + (1 - \alpha) \cdot c_i\right)$$

Where $\alpha = 0.7$, $\lambda = 86400\text{s}$.

### 5.2 Trust Gain (Corroboration)

$$\tau_{\text{new}} = \text{clip}\!\left(\tau + \eta_{\text{pos}} \cdot (1 - D_{\text{mean}}),\ 0,\ 1\right)$$

### 5.3 Trust Loss (Contradiction)

$$\tau_{\text{new}} = \text{clip}\!\left(\tau \cdot (1 - \eta_{\text{neg}} \cdot D_{\text{mean}}),\ 0,\ 1\right)$$

### 5.4 Trust Mass (Stability)

$$\mu(m_i) = \mu_{\text{base}} + \log(1 + n_{\text{corr}}) \cdot \sigma_{\text{sessions}}$$

### 5.5 Trust Shock

$$\tau_{\text{shocked}} = \tau - \frac{s \cdot A_{\text{shock}}}{\mu(m_i)}$$

### 5.6 SSE Significance Score

$$S = 0.20 \cdot E + 0.25 \cdot N + 0.30 \cdot U + 0.15 \cdot C + 0.10 \cdot F$$

Where $S \geq T_L \implies$ Lossless, $S < T_C \implies$ Cogni, else Hybrid.

### 5.7 Drift Detection

$$D_{\text{mean}} = 1 - \text{sim}(z_{\text{new}}, z_{\text{prior}})$$

- $D < \theta_{\text{align}} = 0.15$ → aligned
- $D > \theta_{\text{contra}} = 0.28$ → contradiction candidate
- $0.15 \leq D \leq 0.28$ → yellow zone → disclosure policy applies

### 5.8 Asymmetric Trust Rates

| Parameter | Value | Meaning |
|-----------|-------|---------|
| $\eta_{\text{pos}}$ | 0.10 | Trust increase rate |
| $\eta_{\text{neg}}$ | 0.15 | Trust decrease rate — 50% faster than gain |
| $\eta_{\text{reinforce}}$ | 0.05 | Reinforcement rate for validated memories |
| $\tau_{\text{base}}$ | 0.70 | Starting trust for new memories |
| $\tau_{\text{fallback\_cap}}$ | 0.30 | Maximum trust for fallback/generated speech |
| $\tau_{\text{train\_min}}$ | 0.60 | Minimum trust for DNNT weight updates |

---

## 6. Data Contracts

### 6.1 Memory Item

```python
@dataclass
class MemoryItem:
    memory_id: str              # UUID
    vector: np.ndarray          # 768-dim embedding
    text: str                   # Original text
    timestamp: float            # Unix epoch
    confidence: float           # Model confidence [0,1]
    trust: float                # Earned trust [0,1]
    source: MemorySource        # USER | SYSTEM | FALLBACK | EXTERNAL | REFLECTION | LLM_OUTPUT
    sse_mode: SSEMode           # LOSSLESS | COGNI | HYBRID
    temporal_status: str        # past | active | future | potential
    valid_from: Optional[str]
    valid_until: Optional[str]
    domain_tags: List[str]
    fact_tuples: List[Tuple]
    extraction_method: str
```

### 6.2 Contradiction Entry

```python
@dataclass
class ContradictionEntry:
    ledger_id: str              # UUID
    status: ContradictionStatus # OPEN | REFLECTING | RESOLVED | ACCEPTED
    type: ContradictionType     # REFINEMENT | REVISION | TEMPORAL | CONFLICT | DENIAL
    claim_a: str                # First claim text
    claim_b: str                # Second claim text
    memory_id_a: str
    memory_id_b: str
    drift_score: float          # D_mean between claims
    resolution_metadata: Dict   # Who resolved, how, when
    created_at: str             # ISO timestamp
```

### 6.3 Verification Report

```python
@dataclass
class VerificationReport:
    passed: bool
    hallucinations: List[str]
    grounded_facts: List[str]
    trust_scores: Dict[str, float]
    contradiction_pairs: List[Tuple[str, str]]
    processing_time_ms: float
```

---

## 7. Module Dependency Map

```
crt_api.py (Gateway)
  ├── routes/* (10 routers, 99 endpoints)
  ├── personal_agent/
  │   ├── crt_rag.py (RAG engine)
  │   │   ├── crt_core.py (CRTMath, CRTConfig)
  │   │   ├── crt_memory.py (Trust-weighted store)
  │   │   ├── crt_ledger.py (Contradiction ledger)
  │   │   ├── two_tier_facts.py (Fact system)
  │   │   └── intent_router.py (15 intent types)
  │   ├── dnnt/ (Neural core)
  │   │   ├── model.py (MicroTransformer)
  │   │   ├── inference.py (DNNT-first pipeline)
  │   │   ├── trust_gate.py (Training data filter)
  │   │   ├── background_learning.py (Collapse trail consumer)
  │   │   └── tokenizer_bpe.py (SentencePiece + OOV fallback)
  │   ├── engine/ (Integration hooks)
  │   │   ├── anchors.py (Identity protection)
  │   │   ├── resonance.py (Memory matching)
  │   │   ├── reconstruction.py (Fidelity scoring)
  │   │   ├── degradation.py (Quality gating)
  │   │   └── collapse_trails.py (Training tuple logging)
  │   ├── reasoning.py (DNNT-first with LLM fallback)
  │   ├── reflection_system.py (Post-response assessment)
  │   ├── episodic_memory.py (Session summaries)
  │   ├── heartbeat_system.py (Proactive engagement)
  │   ├── thinking_loop.py (Background contemplation)
  │   └── continuous_loops.py (24/7 reflection + personality)
  ├── groundcheck/
  │   ├── verifier.py (GroundCheck orchestrator)
  │   ├── fact_extractor.py (Heuristic slots)
  │   ├── semantic_matcher.py (5-stage matching)
  │   ├── semantic_contradiction.py (NLI detection)
  │   ├── neural_extractor.py (Hybrid regex + NER)
  │   └── tuple_verifier.py (SPO verification)
  ├── sse/
  │   ├── client.py (Constitutional governor)
  │   ├── interaction_layer.py (Read-only navigator)
  │   ├── coherence.py (Disagreement graph)
  │   ├── extractor.py (Claim + provenance)
  │   └── contradictions.py (Detection)
  └── schemas/ (7 JSON Schema files)
```

---

## 8. Non-Negotiable System Invariants

These are absolute. Any code change that violates these is rejected.

| # | Invariant | Enforcement |
|---|-----------|-------------|
| 1 | No memory is silently deleted or merged | Append-only ledger, no DELETE operations |
| 2 | Contradictions are signals, not bugs | Every contradiction logged and preserved |
| 3 | Trust is earned, not assigned | Asymmetric math: $\eta_{\text{neg}} > \eta_{\text{pos}}$ |
| 4 | Refuse rather than lie | Reconstruction gates block epistemically unsafe output |
| 5 | Auditable by design | Every decision logged with reasoning chain |
| 6 | Compression preserves structure | SSE modes maintain semantic fidelity |
| 7 | LLM speech ≠ memory belief | Fallback capped at $\tau = 0.3$ |
| 8 | SSE never resolves contradictions | Constitutional enforcement via missing methods |
| 9 | GroundCheck runs inline, not post-hoc | Sub-2ms on every response |
| 10 | DNNT trains only on trusted data | Trust gate: $\tau \geq 0.6$ required |

---

## 9. Technology Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Index | FAISS |
| Neural Core | PyTorch (MicroTransformer) |
| Classification | XGBoost (GroundCheck) |
| Tokenizer | SentencePiece BPE + dynamic OOV |
| Storage | SQLite (per-thread) + JSON |
| Schema Validation | JSON Schema (7 schemas) |
| Python | ≥ 3.10 (developed on 3.13) |

---

*This document is the canonical architecture reference. All implementation must conform to these specifications.*
