# The Three Laws of CRT

These three design laws govern every subsystem in CRT/Aether. They are not enforced by a single module — they are structural properties that emerge from how the systems interact.

---

## Law 1: The Mouth Should Never Outweigh the Self

*Belief/speech separation: what the system says is provisional output, not truth.*

### What It Means

CRT distinguishes between what it *believes* (high-trust memories backed by evidence) and what it *says* (generated text that may be speculative, hedged, or wrong). The system's speech — its generated responses — should never be treated as authoritative over its actual memory state.

Concretely: if Aether generates a response that contradicts a stored memory, the response does not overwrite the memory. The contradiction is logged, and the system asks the user for clarification rather than silently resolving it.

### How It's Implemented

**Belief/speech tracking table** (`crt_memory.py:389`):
```sql
CREATE TABLE belief_speech (
    entry_id INTEGER PRIMARY KEY,
    timestamp REAL,
    query TEXT,
    response TEXT,
    is_belief INTEGER,     -- 1 if backed by high-trust memory, 0 if speech
    memory_ids_json TEXT,  -- which memories supported this
    trust_avg REAL,        -- average trust of supporting memories
    source TEXT
)
```

**Authority levels on memories** (`crt_memory.py:68-73`):
- `provisional` — LLM-generated content that has not been confirmed by a user (the "speech" that hasn't earned trust)
- `confirmed` — User-stated or user-confirmed facts
- `locked` — Manually protected, never overwritten

**Source kind enforcement** (`crt_memory.py:1137-1139`):
```python
# model_output provenance -> always provisional
if resolved_source_kind == "model_output" and authority not in {"locked"}:
    authority = "provisional"
```

This means anything the LLM generates is automatically classified as provisional. It can only be promoted to `confirmed` through user action.

### What Violations Look Like

- A system that overwrites stored facts based on LLM output
- A system that treats its own generated text as ground truth
- Silent resolution of contradictions in favor of the most recent generation

---

## Law 2: Contradictions Are Preserved Unless Resolution Is Earned

*Don't resolve contradictions for cleanliness. Preserve both sides until evidence determines which is correct.*

### What It Means

When CRT detects that a new piece of information contradicts an existing memory, it does not silently overwrite the old one. Instead, it creates a contradiction entry in the ledger and preserves both memories. Resolution happens only through:

- **User clarification** — The user explicitly says which is correct
- **Evidence accumulation** — One side accumulates significantly more trust through repeated reinforcement
- **Explicit correction** — The user uses correction language ("actually", "not", "I meant")

### How It's Implemented

**Contradiction ledger** (maintained in a separate database, `crt_ledger*.db`):
- Status tracking: `OPEN`, `REFLECTING`, `RESOLVED`
- Both memory IDs preserved (old and new)
- Resolution method recorded for audit

**Contested memory trust cap** (`crt_memory.py:301`):
```python
CONTESTED_TRUST_MULTIPLIER = 0.1
```
Memories involved in open contradictions have their effective trust capped at 10% of normal. This prevents contested facts from being presented with false confidence.

**No silent overwrites** — The `store_memory()` method never deletes an existing memory. The dedup check (similarity > 0.9) only *reinforces* the existing memory rather than replacing it. If the new memory is different enough to not match the dedup threshold but contradicts existing facts, it creates a ledger entry.

**Contradiction caveat detection** (`routes/chat.py:120-132`):
```python
_CONTRADICTION_CAVEAT_RE = re.compile(
    r"most recent|latest|conflicting|however|updat(e|ed|ing)|"
    r"correct(ed|ing|ion)?|previously|chang(e|ed|ing)|versus|no longer"
)
```
If the LLM's response contains hedging language that indicates it's navigating contradictory data, this is detected and flagged in the response metadata.

### What Violations Look Like

- Silently overwriting a memory when the user says something different
- Picking the "most recent" value without evidence that the old value is wrong
- Cleaning up contradictions for aesthetic consistency

---

## Law 3: Structure Should Emerge, Not Be Hardcoded

*The system should discover patterns, not be programmed with them.*

### What It Means

CRT avoids hardcoding identity, behavior patterns, or response strategies. Instead, structure emerges from:

- **Trust evolution** — Important facts naturally rise to the top through repeated reinforcement
- **Self-reflection** — The self-model is populated by observing actual behavior, not by configuration
- **Compression** — Memory tier assignment is driven by volatility math, not manual curation
- **Style adaptation** — Response style is calibrated from user interaction patterns, not preset templates

### How It's Implemented

**Self-model from evidence** (`heartbeat_system.py:530-555`):
The self-reflection prompt gathers actual evidence (gate failures, feedback, trust deltas, contradictions) and asks the LLM to produce self-observations. The slots are not populated from a config file — they emerge from what actually happened.

**Adaptive compression** (`memory_compression.py:227-260`):
Tier assignment is computed from `V(t) = alpha * D(t) + beta * C(t) + gamma * F(t)` — a formula that combines drift, contradiction density, and fidelity loss. No manual tier assignment.

**Trust-weighted retrieval** (`crt_memory.py:1651-1661`):
```python
score = similarity * recency * belief_weight * tier_weight
```
Which memories surface is determined by a combination of relevance, age, and earned trust — not by manual prioritization.

**Style profile from observation** (session database):
The system tracks the user's communication patterns (message length, vocabulary, question frequency) and adapts its response style accordingly. This happens through `update_style_profile()` on every message.

**Onboarding as initial data, not identity** (`runtime_config.py:353-367`):
The onboarding questions collect initial facts, but these are stored as regular memories with standard trust scores. They don't get special privilege — they can be corrected, contradicted, and deprecated just like any other memory.

### What Violations Look Like

- Hardcoded identity statements ("if user asks my name, say Aether")
- Predetermined response strategies that don't adapt to user behavior
- Manual curation of which memories are important
- Self-model values set in a config file rather than observed from behavior
- Smoothing over the self-model to present a coherent narrative that isn't earned from evidence
