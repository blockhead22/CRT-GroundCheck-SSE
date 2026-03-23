# CRT Innovation Pillars

**Version:** 0.9.0-freeze  
**Date:** February 8, 2026  
**Author:** Nick Block  
**Status:** FROZEN — prior art reference document

---

## Purpose

This document establishes what CRT *is*, what it *does that nothing else does*, and the formal mathematical basis that makes its claims rigorous. It serves as:

1. **Prior art documentation** for intellectual property
2. **Technical differentiation** from all existing memory systems
3. **Formal specification** of the theoretical contributions

---

## Pillar 1: Contradictions as First-Class Data

### The Problem

Every memory system in production (2026) treats contradictions as errors to resolve:

| System | Contradiction Handling |
|--------|-----------------------|
| OpenAI Memory | Last-write-wins. Silent overwrite. |
| Mem0 | Deduplication. Older fact removed. |
| Zep | Merge on similarity. No audit. |
| MemGPT/Letta | Context window cycling. Oldest evicted. |
| LangGraph Persistence | Key-value store. Replace by key. |
| RAG (generic) | No contradiction awareness. Nearest neighbor returns latest. |

### CRT's Position

Contradictions are **signals of epistemic change**, not bugs. A system that silently resolves contradictions is a system that lies about its own history.

### Formal Specification

**Contradiction Ledger** — append-only data structure.

```
Entry := {
    ledger_id    : UUID,
    status       : OPEN | REFLECTING | RESOLVED | ACCEPTED,
    type         : REFINEMENT | REVISION | TEMPORAL | CONFLICT | DENIAL,
    claim_a      : (text, memory_id, trust_a, timestamp_a),
    claim_b      : (text, memory_id, trust_b, timestamp_b),
    drift_score  : D_mean ∈ [0, 1],
    resolution   : { method, agent, evidence, timestamp } | ∅
}
```

**Invariant:** `∀ entry ∈ Ledger: ¬∃ operation DELETE(entry)`

No entry is ever removed. Resolution adds metadata; it does not remove or modify the original claims. Both sides are preserved permanently.

**Constitutional enforcement (SSE layer):**
- `SSEClient` exposes only retrieval/query operations
- `pick_winner()`, `synthesize_answer()`, `add_confidence_score()`, `learn_from_feedback()` → `AttributeError`
- Not a runtime check. Not a flag. The methods *do not exist on the class*.

### Why This Matters

A personal assistant that forgot it ever thought you worked at Google — while confidently telling you that you work at Microsoft — has silently gaslit its user. CRT remembers both, shows both, and requires explicit resolution.

---

## Pillar 2: Trust ≠ Confidence

### The Problem

Every LLM system conflates two fundamentally different concepts:

- **Confidence** = "how sure is the model about this output?"
- **Trust** = "how much should this information be relied upon?"

A model can be 99% confident in something that is 0% trustworthy (hallucination). A model can be 30% confident in something that is 95% trustworthy (low recall, high-trust memory).

### CRT's Separation

| Property | Confidence | Trust |
|----------|-----------|-------|
| Source | Model logits / softmax | Earned over time |
| Direction | Per-inference | Per-memory |
| Evolution | Ephemeral | Persistent, asymmetric |
| Failure mode | Overconfident hallucination | Gradual erosion on contradiction |
| Reset | Every inference | Never resets; recovers slowly |

### Formal Specification

**Trust evolution** — asymmetric accumulation:

**Gain (corroboration):**
$$\tau_{\text{new}} = \text{clip}\!\left(\tau + \eta_{\text{pos}} \cdot (1 - D_{\text{mean}}),\ 0,\ 1\right), \quad \eta_{\text{pos}} = 0.10$$

**Loss (contradiction):**
$$\tau_{\text{new}} = \text{clip}\!\left(\tau \cdot (1 - \eta_{\text{neg}} \cdot D_{\text{mean}}),\ 0,\ 1\right), \quad \eta_{\text{neg}} = 0.15$$

The asymmetry is **intentional and load-bearing**: trust takes 50% longer to earn than to lose. This mirrors human epistemic behavior — a single betrayal of trust outweighs many confirmations.

**Trust mass** — stability through corroboration:

$$\mu(m_i) = \mu_{\text{base}} + \log(1 + n_{\text{corr}}) \cdot \sigma_{\text{sessions}}$$

Memories that have been corroborated across multiple sessions develop *inertia*. A single contradiction cannot trivially destroy a deeply validated belief.

**Trust shock** — sharp events can override inertia:

$$\tau_{\text{shocked}} = \tau - \frac{s \cdot A_{\text{shock}}}{\mu(m_i)}$$

But the damage is inversely proportional to trust mass. Well-established beliefs resist shocks.

**Recovery period:**

$$t_{\text{recovery}} = \mu(m_i) \cdot t_{\text{base}}$$

Trust does not snap back. Recovery is proportional to the depth of the belief. This prevents oscillation.

### Retrieval Integration

Trust enters the retrieval equation directly:

$$R_i = \text{sim}(z_q, z_i) \cdot \rho_i \cdot \left(\alpha \cdot \tau_i + (1 - \alpha) \cdot c_i\right), \quad \alpha = 0.7$$

Trust accounts for 70% of the belief weight. A highly relevant, recent memory with low trust will be outranked by a less relevant memory with high trust. This is the correct behavior — you should not trust recent lies over established truths.

### Source-Based Trust Capping

| Source | Max Trust |
|--------|-----------|
| USER | 1.0 |
| SYSTEM | 1.0 |
| REFLECTION | 0.8 |
| EXTERNAL | 0.7 |
| LLM_OUTPUT | 0.5 |
| FALLBACK | 0.3 |

Fallback speech (when the system has no memory and fabricates) can never exceed 0.3 trust. This is non-negotiable. The system's own fabrications are never treated as beliefs.

---

## Pillar 3: Reconstruction Gates

### The Problem

LLMs generate text regardless of whether they have sufficient knowledge. There is no mechanism to say "I don't have enough information to answer this safely."

### CRT's Gates

Two gates must pass before any response reaches the user:

**Intent alignment gate:**
$$\text{sim}(z_{\text{response}}, z_{\text{query}}) \geq \theta_{\text{intent}} = 0.5$$

The response must be semantically relevant to what was asked.

**Memory alignment gate:**
$$\text{sim}(z_{\text{response}}, z_{\text{memory}}) \geq \theta_{\text{mem}} = 0.38$$

The response must be grounded in retrieved memory.

If either gate fails, the system:
1. Logs the gate failure with full context
2. Falls back to a lower-confidence response mode
3. Marks the output as fallback (trust capped at 0.3)
4. Can refuse to answer entirely if both gates fail

### GroundCheck Integration

After gates pass, GroundCheck runs inline (sub-2ms) to verify specific claims:

1. **Extract facts** from generated response (heuristic + neural NER)
2. **Match** against retrieved memories (5-stage: exact → normalized → fuzzy → synonym → embedding)
3. **Score** grounding level per claim
4. **Flag** hallucinated claims with specific memory contradictions

**Mutually exclusive slots** (employer, location, name, etc.) — the system knows that a person cannot work at two companies simultaneously. If the response says "Google" but memory says "Microsoft", this is a hard contradiction, not an additive fact.

---

## Pillar 4: CogniMap — Belief Topology

### The Concept

Beliefs do not exist in isolation. They form a directed graph where:

- Some beliefs **depend on** others ("I like my job" depends on "I work at X")
- Some beliefs **contradict** others
- Some beliefs **corroborate** others
- Some beliefs **supersede** others (temporal evolution)
- Some beliefs are **foundational** (high centrality, many dependents)

### Edge Types

| Type | Meaning | Example |
|------|---------|---------|
| `CONTRADICTS` | Mutually incompatible | "Works at Google" ↔ "Works at Microsoft" |
| `CORROBORATES` | Reinforces truth | "Lives in NYC" ← "Commutes via subway" |
| `DEPENDS_ON` | Truth requires parent | "Likes job" → "Has a job" |
| `SUPERSEDES` | Replaces with evidence | "Works at Microsoft" → "Works at Google" (with user confirmation) |
| `EVOLVED_FROM` | Gradual change | "Prefers tea" → "Prefers coffee" |
| `CONTEXT_OF` | Provides frame | "Has allergies" → "Avoids peanuts" |

### Dependency Propagation

$$\Delta\tau_{\text{child}} = \Delta\tau_{\text{parent}} \cdot w_{\text{edge}} \cdot \lambda^{d}$$

When a parent belief's trust changes, all dependent beliefs feel the effect, attenuated by edge weight and depth. If "I work at Google" is contradicted, "I like my commute to the Google campus" also takes a trust hit — automatically, through the graph.

### Foundational Belief Detection

Beliefs with high graph centrality (many edges, many dependents) are **foundational**. The system automatically identifies which beliefs, if changed, would have the greatest cascading impact. These are protected with higher trust mass and require stronger evidence to override.

---

## Pillar 5: Compression Without Destruction

### SSE Modes

| Mode | When | What |
|------|------|------|
| **Lossless** ($S \geq 0.7$) | Identity-critical, contradiction-heavy | Full text preserved |
| **Hybrid** ($0.3 \leq S < 0.7$) | Moderate significance | Adaptive mix |
| **Cogni** ($S < 0.3$) | Low significance, routine | Fast sketch — "what it felt like" |

### Significance Score

$$S = 0.20 \cdot E + 0.25 \cdot N + 0.30 \cdot U + 0.15 \cdot C + 0.10 \cdot F$$

| Weight | Factor | Meaning |
|--------|--------|---------|
| 0.30 | $U$ (user_mark) | User explicitly flagged as important |
| 0.25 | $N$ (novelty) | How different from existing memory |
| 0.20 | $E$ (emotion) | Emotional content detected |
| 0.15 | $C$ (contradiction) | Contains contradictory information |
| 0.10 | $F$ (future) | Forward-looking / planning content |

### Compression Integrity

**Mirus** (input/perception):
- Embeds → compresses → logs vector → updates FAISS index
- Computes **reconstruction fidelity** — round-trip compression quality
- Fidelity < 0.6 → trust capped at 0.4
- Fidelity < 0.75 → trust capped at 0.6
- Fidelity ≥ 0.75 → trust set to 0.9

**Holden** (output/reconstruction):
- Decompresses → reconstructs → gates output
- Detects degraded responses ("not too sure", "(0.00)", "more context?")
- SHA256 fingerprinting for integrity verification
- Thread-safe reconstruction with `ThreadPoolExecutor(max_workers=4)`

The compression pipeline has a **quality guarantee**: if compression degrades the content below fidelity threshold, the trust of the resulting memory is automatically reduced. The system never trusts its own compressed output more than the compression quality warrants.

---

## Pillar 6: Personal Cognitive Architecture (DNNT)

### The Vision

CRT is not a chatbot. It is a **cognitive layer** between a human and an LLM. Over time, the personal model (DNNT) learns the user's patterns, and the LLM is needed less.

```
Session 1:   [LLM handles 100% of reasoning]
Session 100: [DNNT handles 30%, LLM handles 70%]
Session 500: [DNNT handles 60%, LLM handles 40%]
```

### DNNT Architecture

**Dynamic Neuromorphic Neuro-Transformer**

| Component | Learns | Signal |
|-----------|--------|--------|
| **Mirus** | Attention/compression patterns | Reconstruction fidelity, user corrections |
| **Holden** | Gate pass/fail, reconstruction quality | User corrections, gate history |
| **Trust dynamics** | User reliability shape | Contradiction patterns, validation frequency |
| **CogniMap** | Belief topology | Co-occurrence, co-contradiction patterns |
| **DNNT core** | Reasoning patterns | Trust-filtered LLM outputs, user corrections |

### Model Specifications

- **Architecture:** MicroTransformer with RoPE, SwiGLU, RMSNorm
- **Parameters:** 2-20M (target <80MB)
- **Inference:** <200ms on CPU
- **Training signal:** Collapse trails (query, facts, thinking, response) tuples
- **Training gate:** Only data with $\tau \geq 0.6$ enters the training pipeline

### The Key Insight

Every other personal AI system starts with a powerful model and cuts it down to fit the user. CRT starts with nothing and **grows** a model from the user's actual cognitive patterns. The external LLM provides the initial capability; DNNT captures what the user actually needs.

---

## Landscape Comparison

| Feature | CRT | OpenAI Memory | Mem0 | Zep | MemGPT | LangGraph |
|---------|-----|---------------|------|-----|--------|-----------|
| Trust evolution | ✅ Asymmetric math | ❌ | ❌ | ❌ | ❌ | ❌ |
| Contradiction preservation | ✅ Append-only ledger | ❌ Silent overwrite | ❌ Dedup | ❌ Merge | ❌ Eviction | ❌ Replace |
| Reconstruction gates | ✅ Pre-response | ❌ | ❌ | ❌ | ❌ | ❌ |
| Inline hallucination check | ✅ 1.17ms | ❌ | ❌ | ❌ | ❌ | ❌ |
| Belief graph (CogniMap) | ✅ Typed edges | ❌ | ❌ | ❌ | ❌ | ❌ |
| Source-based trust caps | ✅ 6 source types | ❌ | ❌ | ❌ | ❌ | ❌ |
| Constitutional SSE | ✅ Missing-method enforcement | ❌ | ❌ | ❌ | ❌ | ❌ |
| Personal model growth | ✅ DNNT (2-20M params) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Auditable decisions | ✅ Full trace logging | Partial | ❌ | Partial | ❌ | Partial |

**CRT is the only system that addresses all nine dimensions.** No competitor addresses more than two.

---

## What CRT Is Not

To prevent mischaracterization:

1. **Not an AGI attempt.** CRT is a cognitive layer, not a general intelligence.
2. **Not a chatbot.** The external LLM provides conversational ability. CRT provides memory, trust, and contradiction awareness.
3. **Not a RAG wrapper.** RAG retrieves by similarity. CRT retrieves by trust-weighted belief scoring.
4. **Not a prompt engineering framework.** The math is in the code, not in the prompts.
5. **Not a vector database.** FAISS is a tool CRT uses. CRT's value is in what happens before and after retrieval.

---

*This document establishes the theoretical and practical innovations of CRT. It is timestamped and versioned for prior art documentation.*
