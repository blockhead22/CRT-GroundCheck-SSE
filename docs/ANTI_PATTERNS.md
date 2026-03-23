# What NOT to Do

This document catalogs anti-patterns that violate CRT's design principles. These are not theoretical concerns — each one has been encountered (or nearly encountered) during development. If you're extending or modifying CRT, watch for these.

---

## 1. Silent Overwrite of Contradicting Memories

**The anti-pattern:** When new information conflicts with existing memory, silently replace the old value.

```python
# BAD: "last write wins"
existing = memory.get_by_slot("name")
if existing:
    memory.delete(existing.id)
memory.store("name = Alex")
```

**Why it's wrong:** The old value might be correct. The user might have misspoken. The new information might come from a less trustworthy source. By deleting the old memory, you lose the ability to recover from mistakes and destroy the audit trail.

**The CRT way:** Store the new memory alongside the old one. Create a contradiction ledger entry. Let trust scoring and user clarification determine which value wins over time.

---

## 2. Hardcoded Identity ("If User Says X, Answer Y")

**The anti-pattern:** Adding conditional response logic like:

```python
# BAD: hardcoded identity
if "what is your name" in message.lower():
    return "My name is Aether!"
if "who made you" in message.lower():
    return "I was created by Nick Block."
```

**Why it's wrong:** This creates brittle identity that can't evolve, can't be corrected, and doesn't reflect actual system state. If the system's name changes, or if the creator wants to be described differently, every hardcoded string must be found and updated.

**The CRT way:** Identity lives in the memory store (with `kind='identity_constant'` and `authority='locked'`). Self-referential questions are answered via `_answer_self_referential()` which reads the self-model and stored facts, then asks the LLM to formulate a natural response grounded in that data.

---

## 3. Trust Without Evidence

**The anti-pattern:** Assigning high trust to memories without a basis for that trust.

```python
# BAD: arbitrary trust assignment
memory.store("user likes Python", trust=0.95)  # Based on what?
```

**Why it's wrong:** Trust should reflect how validated a piece of information is, not how confident the code author feels. A trust score of 0.95 means "this has been repeatedly confirmed and never contradicted" — not "this seems likely."

**The CRT way:** Initial trust is assigned by source type (user=0.7, system=0.5, fallback=0.3). Trust increases through reinforcement (user re-states the fact, dedup catches it) and decreases through time decay and contradiction. The `0.95` trust level is earned, not assigned.

---

## 4. Resolving Contradictions for Cleanliness

**The anti-pattern:** Auto-resolving contradictions because having open conflicts looks messy.

```python
# BAD: clean up contradictions
for contradiction in ledger.get_open():
    # Just pick the newer one
    winner = contradiction.new_memory
    loser = contradiction.old_memory
    ledger.resolve(contradiction.id, winner_id=winner.id)
    memory.deprecate(loser.id)
```

**Why it's wrong:** Recency is not evidence. The newer statement might be a mistake, a misunderstanding, or a test. Auto-resolution destroys information and prevents the system from asking for clarification.

**The CRT way:** Leave contradictions open. Cap contested memory trust at 10% (`CONTESTED_TRUST_MULTIPLIER = 0.1`). Let the system naturally hedge when presenting contested information. Resolution happens through explicit user correction, not automated cleanup.

---

## 5. Self-Model Smoothing

**The anti-pattern:** Presenting a coherent self-narrative that isn't earned from evidence.

```python
# BAD: smooth self-model
self_model.update("trust_trajectory", "Trust has been consistently growing as I learn more about the user.")
# When actually: trust scores have been flat with two major drops
```

**Why it's wrong:** The self-model exists to give the system honest self-awareness. If the self-model says "I'm doing great" when the evidence shows gate failures and user corrections, the system loses its ability to improve.

**The CRT way:** Self-model updates are driven by the `_SELF_REFLECTION_PROMPT` which is given actual evidence: gate failure counts, negative feedback events, trust delta batches, open contradiction counts. The LLM assesses based on this evidence. Trust for the self-assessment is weighted by evidence density:
```python
trust = max(0.35, min(0.80, 0.55 + len(negative_feedback_lines) * 0.03))
```
More evidence = higher trust in the self-assessment. No evidence = low trust.

---

## 6. Cloud Dependency Drift

**The anti-pattern:** Gradually routing everything to cloud because it produces better output.

```python
# BAD: "cloud is better, use it for everything"
if cloud_available:
    response = cloud.generate(prompt)
else:
    response = local.generate(prompt)
```

**Why it's wrong:** CRT's architecture depends on the control layer staying local. Memory, trust, verification, and governance must not depend on cloud availability. If cloud goes down (or becomes too expensive, or changes terms), the system should still function with local generation only.

**The CRT way:** Cloud is explicitly opt-in for specific features with daily limits:
- Slot classification: 10 calls/day
- NLI contradiction: 10 calls/day
- Reflection validation: 3 calls/day

The `product_mode` setting enforces this: `local_only` means no cloud at all. `hybrid_verified` means cloud generation is available but verification stays local. There is no mode where cloud owns the control layer.

---

## 7. Prompt Stuffing Without Trust Filtering

**The anti-pattern:** Retrieving all similar memories and dumping them into the prompt.

```python
# BAD: stuff everything in
memories = memory.retrieve(query, k=50, min_trust=0.0)
prompt = f"Context:\n{format_memories(memories)}\n\nQuestion: {query}"
```

**Why it's wrong:** Low-trust memories, deprecated memories, and contested memories can mislead the LLM. The more noise in the prompt, the more likely the LLM is to pick up wrong information.

**The CRT way:** Retrieval uses trust-weighted scoring (`similarity * recency * belief_weight * tier_weight`) and excludes deprecated memories, resolved contradiction losers, and memories below the trust threshold. The prompt is assembled with trust annotations visible so the LLM can weigh the evidence.

---

## 8. Skipping the Dedup Check

**The anti-pattern:** Storing every extracted fact without checking if it already exists.

```python
# BAD: store unconditionally
for fact in extracted_facts:
    memory.store(fact.text, confidence=0.8, source=MemorySource.USER)
```

**Why it's wrong:** The user will re-state facts naturally ("my name is Nick" mentioned across multiple conversations). Without dedup, you get dozens of near-identical memories cluttering retrieval and wasting storage.

**The CRT way:** `store_memory()` calls `_find_dedup_match()` which checks for cosine similarity > 0.9 combined with normalized text matching. If a match is found, the existing memory is reinforced (trust +0.05) rather than duplicated.

---

## 9. Treating All Memory Kinds Equally

**The anti-pattern:** Applying the same trust decay, compression, and retrieval rules to all memory types.

**Why it's wrong:** An `identity_constant` (e.g., the user's name) should never be compressed to 10D or have its trust decay to zero. An `ops` memory (e.g., "user prefers dark mode") should eventually expire. A `hypothesis` should be reviewable.

**The CRT way:** Different kinds have different rules:
- `identity_constant`: never compressed below tier 2, no scheduled review
- `preference`: 90-day review period
- `permission`: 14-day review period
- `ops`: 30-day review period, eligible for quiet model_output -> confirmed promotion
- `hypothesis`: 30-day review period
- Protected kinds/authorities skip compression entirely

---

## 10. Ignoring the Source Kind

**The anti-pattern:** Treating model-generated content as equivalent to user-stated facts.

**Why it's wrong:** If the LLM extracts "the user works in finance" from context, that's an inference — not a user statement. Storing it with the same authority as "I work in finance" (said by the user) leads to the system asserting things the user never said.

**The CRT way:** The `source_kind` field distinguishes between:
- `principal` — direct user statement
- `model_output` — LLM-generated (automatically gets `authority='provisional'`)
- `tool_receipt` — result from a tool call
- `social` — from social channels
- `external` — from external sources

Model output can never promote itself to confirmed authority without user action.
