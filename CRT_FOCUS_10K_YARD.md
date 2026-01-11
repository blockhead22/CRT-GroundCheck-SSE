# CRT focus (10,000‑yard stare)

Focus on the few things that make CRT meaningfully different, and make them measurable + hard to regress.

## 1) Define the “CRT Contracts” (non‑negotiables)
- Questions don’t create contradictions.
- Conflicts create a clarification loop, not silent overwrite.
- When claiming memory, stay grounded to memory text (no new entities).
- Deterministic gates fire reliably (`assistant_profile`, `user_named_reference`, `memory_citation`, `contradiction_status`).
- Belief updates happen only on explicit/user-approved signals (per policy).
- Everything else is optional.

## 2) Build metrics, not just pass/fail
Track rates over batches:
- contradiction-on-question rate
- hallucination-under-memory-claim rate
- gate-trigger accuracy
- “uncertainty when warranted” rate

Over time you want trends like: “memory-claim hallucination down 10×”.

## 3) Harden the oracles (what decides good/bad)
- Prefer checks based on metadata + retrieved context over brittle phrase matching.
- Internal signals (`gate_reason`, `retrieved_memories`, ledger counts) are an advantage—use them as test oracles.

## 4) Decide what the product guarantees
- Are we promising *truth*, or *coherence + grounded recall + safe uncertainty*?
- CRT’s edge is coherence over time + explicit conflict handling; don’t oversell “accuracy”.

## 5) Put effort where failures are expensive
Worst failures to prevent first:
- “I remember…” + hallucinated proper nouns (trust-destroying).
- Wrong gate: assistant-profile questions answered like a human with a fake history.
- Contradiction ledger behaves inconsistently (creates user confusion).

Optimize for these first; everything else is second-order.
