# CRT Whitepaper
## Cognitive Reflective Transformer: Memory Governance for Conversational AI

**Date:** January 10, 2026  
**Status:** Draft (engineering-oriented)  

---

## Abstract

Most “LLM memory” systems today are storage + retrieval wrapped around a chatbot. In practice, they fail in predictable ways: identity drift, false contradiction flags, stale facts, and confident hallucinations.

CRT (Cognitive Reflective Transformer) is an architecture for **memory governance** in conversational AI. It treats user statements as evolving claims, maintains a contradiction ledger, updates trust over time, and uses explicit gates to decide when the system can answer with commitment versus when it must ask for clarification.

CRT is not a foundation model. It is a **policy + data layer** that makes an underlying LLM behave more consistently over long horizons.

CRT also inherits a boundary principle common to contradiction-preserving evidence systems: conflicts are not silently “resolved” by generation; they are recorded, exposed, and used to drive clarification. CRT extends this boundary across **time**, not just across documents.

---

## What CRT is not

- Not truth verification.
- Not a new model.
- Not a replacement for retrieval.

---

## 1. Problem Statement

A memoryful assistant must reliably answer questions like:

- “What did I say my name was?”
- “Do I prefer remote work or office work?”
- “What did we decide last week?”

Naive RAG memory stacks often fail in four ways:

- **Drift:** the assistant invents facts or imports unrelated details from elsewhere.
- **False contradictions:** two different questions are treated as conflicting evidence.
- **Refusal loops:** the system becomes over-cautious even when evidence agrees.
- **Untraceability:** you can’t inspect which memories drove the output.

CRT’s goal is to make long-horizon chat **inspectable, testable, and safer** by design.

---

## 2. Key Ideas

### 2.1 Memory items

A memory item is text plus metadata (source, timestamp, tags, etc.).

Two scalar values are tracked distinctly:

- **Confidence:** confidence in the capture event (explicit user claim vs inferred).
- **Trust:** current belief-weight assigned to that memory over time.

### 2.2 Belief vs speech

CRT separates:

- **Belief:** what the system is willing to store as high-trust, stable memory.
- **Speech:** low-trust outputs used when coherence is uncertain (safe fallback voice).

This prevents the system’s voice from automatically becoming its belief.

### 2.3 Contradictions are first-class objects

Contradictions are not silently overwritten. CRT maintains a **contradiction ledger** that records:

- prior memory id
- new memory id
- similarity / drift score
- status (open/resolved)
- audit trail (what changed, when, and why)

### 2.4 Gates: confidence is earned, not default

Before CRT emits or stores belief-grade content, it runs gates such as:

- **Intent alignment:** did the system answer the asked question?
- **Memory alignment:** does the candidate answer align with retrieved memories?
- **Contradiction checks:** are there open conflicts relevant to this answer?

If gates fail, CRT returns either:

- **speech** (non-committal output), or
- **uncertainty** (explicit clarification request)

---

## 3. Architecture Overview

CRT is a pipeline around a replaceable LLM.

```
User message
  │
  ├─► (0) Store user message as USER memory
  │
  ├─► (1) Retrieve memories (trust-weighted)
  │
  ├─► (2) Generate candidate answer (LLM “vocal cords”)
  │
  ├─► (3) Evaluate gates
  │      ├─ intent alignment
  │      ├─ memory alignment
  │      └─ unresolved contradictions
  │
  ├─► (4) Decide response type
  │      ├─ belief (high-trust)
  │      ├─ speech (low-trust)
  │      └─ uncertainty (ask a clarifying question)
  │
  ├─► (5) Detect contradictions (ledger entries)
  │
  └─► (6) Update trust scores
         └─ optionally queue reflection/audit
```

The core design choice is that the LLM is treated as voice, not authority. Stability comes from governance, not prompt cleverness.

---

## 4. Trust-Weighted Retrieval

Standard RAG ranks memories primarily by similarity. CRT ranks by a composite retrieval score:

$$
R_i = s_i \cdot \rho_i \cdot w_i
$$

Where:

- $s_i$: similarity(query, memory)
- $\rho_i$: recency weight
- $w_i$: trust weight (a blend of trust and confidence)

This allows a slightly less-similar but high-trust memory to outrank a fresh low-trust fragment.

---

## 5. Uncertainty as a First-Class Output

CRT treats uncertainty as a valid system state, not a failure. A good uncertainty response:

- states what conflicts (and how)
- cites the memory candidates
- asks a clarifying question that resolves the conflict if answered

This matters in domains where consistency and auditability beat “always produce an answer.”

---

## 6. Observability: Make Decisions Inspectable

CRT emits both user-facing content and machine-readable metadata.

Suggested response envelope:

```json
{
  "answer": "...",
  "mode": "quick|thinking|deep|uncertainty",
  "response_type": "belief|speech|uncertainty",
  "confidence": 0.0,

  "gates_passed": true,
  "gate_reason": "...",
  "intent_alignment": 0.0,
  "memory_alignment": 0.0,

  "contradiction_detected": false,
  "unresolved_contradictions": 0,
  "contradiction_entry": null,

  "retrieved_memories": [
    {
      "text": "...",
      "trust": 0.0,
      "confidence": 0.0,
      "source": "user|system|doc"
    }
  ]
}
```

This enables debugging (“why did it answer that?”), UI inspectors, and regression suites.

---

## 7. Evaluation: Multi-Turn Is the Benchmark

Single-turn benchmarks miss the real failure modes. CRT evaluation must be multi-turn:

- introduce a stable fact (name, role)
- reinforce it
- introduce a controlled contradiction
- verify uncertainty triggers only when appropriate
- resolve contradiction
- verify convergence

### 7.1 Success criteria

A successful CRT system should satisfy:

- no contradiction from questions alone
- contradictions only for conflicting assertions (“my name is Nick” vs “my name is Emily”)
- no refusal loops when evidence is consistent
- no hallucinated identity facts without user evidence

### 7.2 Adaptive probing

Static prompts can hide failures. An adaptive probe (“tester agent”) should:

- read CRT’s last answer + metadata
- detect suspicious behavior
- select the next probe to isolate a defect

---

## 8. Practical Use Cases

CRT is useful anywhere long-horizon coherence matters:

- personal assistants tracking preferences, identity, and long-running projects
- enterprise assistants maintaining policy and company facts over time
- multi-agent systems sharing a common evidence/contradiction ledger
- compliance or clinical-adjacent assistants (with additional safeguards)

---

## 9. Limitations

CRT does not guarantee truth. It enforces **consistency with evidence**, not correctness.

Current constraints:

- if all memories are user-provided, CRT enforces internal coherence only
- contradiction detection is hard; semantic drift is not always logical conflict
- without typed schemas, identity facts remain fragile (“Nick” vs “Nick Block”)

---

## 10. Roadmap

High-leverage next steps:

1) **Typed claims** (identity.name, work.company, location.city)

- enables field-level contradiction detection
- supports deterministic convergence rules

2) **Provenance + evidence packets**

- separate user-said vs tool-output vs docs
- audit-friendly decision making (aligned with contradiction-preserving evidence philosophy)

3) **Stronger eval suite**

- standardized metrics: false-contradiction rate, convergence time, hallucination rate
- automatic artifact output per run

4) **Inspector UI**

- show retrieved memories, trust evolution, and open contradictions

---

## 11. Open-Sourcing Strategy

Safe to open-source early (high value, low risk):

- evaluation harness (adaptive stress tests + scoring + artifact schemas)
- memory-store interface (pluggable backends)
- contradiction ledger model (provider-agnostic)

Hold back until stable (more differentiating):

- full trust policy + gating policy
- production prompts and tuned heuristics
- anything containing real user logs

---

## Appendix A: Implementation Pointers

- CRT engine: `personal_agent/crt_rag.py`
- Reasoning modes: `personal_agent/reasoning.py`
- Ledger + memory store: `personal_agent/crt_ledger.py`, `personal_agent/crt_memory.py`
- Evaluators: `crt_response_eval.py`
- Probe tooling: `crt_adaptive_stress_test.py`, `crt_live_probe.py`

---

## Appendix B: Guiding Principle

Coherence over time beats single-turn cleverness.

A memoryful assistant must be accountable to its own evidence and able to say “I don’t know” when the record is contradictory.
