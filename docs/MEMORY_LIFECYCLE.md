# Memory Lifecycle

This document covers the complete lifecycle of a memory in CRT, from user statement through extraction, storage, retrieval, trust evolution, compression, and eventual deprecation.

Reference: `personal_agent/crt_memory.py` (main), `personal_agent/memory_compression.py` (compression)

## Lifecycle Overview

```
User statement
    |
    v
1. Fact extraction (regex + optional LLM)
    |
    v
2. Transcript pollution guard
    |
    v
3. Dedup check (0.9 cosine similarity + text normalization)
    |
    v
4. Vector embedding (sentence-transformers)
    |
    v
5. Significance scoring -> SSE mode selection (L/C/H)
    |
    v
6. Initial trust assignment (by source type)
    |
    v
7. Storage with metadata (authority, kind, provenance)
    |
    v
8. Retrieval (similarity + recency + trust + tier weight)
    |
    v
9. Citation in responses
    |
    v
10. Trust update (context-aware, reinforcement or decay)
    |
    v
11. Compression (tier transitions via volatility)
    |
    v
12. Deprecation (contradiction resolution or staleness)
```

## 1. Fact Extraction

When a user sends a message, CRT extracts factual claims using two methods:

- **Regex extraction** (`personal_agent/fact_slots.py`) — Pattern matching for common fact formats like "my name is X", "I work at Y"
- **LLM extraction** (optional, via cloud) — `CloudFeatureService.classify_slot()` uses gpt-4o-mini to classify statements into memory slots

The extraction method is recorded on the memory: `extraction_method = 'regex'` or `'llm'`.

## 2. Transcript Pollution Guard

Before storing, `_sanitize_transcript_pollution()` strips content that would poison the memory store:

- `[CONTINUITY INSTRUCTION]` blocks
- `[RECENT CONVERSATION CONTEXT]` blocks
- Lines matching `User:` or `Assistant:` transcript patterns
- Aether's own identity assertions that would be re-extracted as user facts

## 3. Dedup Check

`_find_dedup_match()` prevents storing near-identical memories. It checks:

- **Cosine similarity > 0.9** between the new vector and existing memory vectors
- **Normalized text match** (case-insensitive, whitespace-normalized)

If a duplicate is found, instead of inserting a new memory, the existing memory's trust is reinforced by +0.05 (capped at 1.0) and its timestamp is updated. A `dedup_reinforced` event is logged.

## 4. Vector Embedding

`encode_vector()` from `personal_agent/crt_core.py` uses sentence-transformers to produce a 384-dimensional embedding vector. This is stored as `vector_json` in the database.

## 5. Significance & SSE Mode

Significance is computed from four factors:

- **Emotion intensity** — extracted from text via keyword analysis
- **Novelty** — how different this vector is from existing memories
- **User marked** — whether the user explicitly flagged it as important
- **Future relevance** — whether the text references future events

Based on significance, the memory gets an SSE (Significance-Stratified Encoding) mode:

| Mode | Meaning | Storage |
|------|---------|---------|
| L (Low) | Routine observation | Full text, standard vector |
| C (Condensed) | Moderate significance | May be summarized |
| H (High) | Critical fact | Full text, protected from compression |

## 6. Initial Trust Assignment

Trust starts based on the memory's source:

| Source | Initial Trust | Notes |
|--------|-------------|-------|
| `user` | 0.7 | Direct user statements |
| `system` | 0.5 | System-generated observations |
| `fallback` | 0.3 | Fallback/default values |
| `reflection` | 0.5 | Self-model observations |
| `llm_output` | 0.4 | LLM-generated content |
| `external` | 0.5 | External tool results |

Explicit corrections boost confidence to >= 0.95 regardless of source.

## 7. Storage & Metadata

Each memory row includes:

- **memory_id** — UUID
- **vector_json** — 384D embedding
- **text** — original text
- **timestamp** — Unix time
- **confidence** — fixed at creation, "how certain it sounded"
- **trust** — evolves over time, "how validated it has proven"
- **source** — user/system/fallback/reflection/llm_output/external
- **sse_mode** — L/C/H
- **authority** — provisional/confirmed/locked
- **kind** — user_fact/ops/preference/identity_constant/observation/hypothesis/etc.
- **source_kind** — principal/tool_receipt/model_output/social/external/system
- **user_id** — scoped to authenticated user
- **thread_id** — conversation thread
- **compression_tier** — 0 (cold 10D) / 1 (warm 64D) / 2 (full 384D)
- **review_after** — soft staleness timestamp (kind-dependent defaults)

### Authority Levels

- **provisional** — LLM-generated content, not yet confirmed by a principal (user)
- **confirmed** — Direct user statement or confirmed by user action
- **locked** — Manually locked, never overwritten or compressed

### User Scoping

Since the recent change, memory retrieval is user-scoped: `retrieve_memories()` filters by `user_id` when available. The user ID comes from the `Authorization` header, propagated via a context variable (`_request_user_id`). Thread ID is kept for audit trail purposes.

## 8. Retrieval

`CRTMemorySystem.retrieve_memories()` at line 1508:

```
Score = similarity * recency * belief_weight * tier_weight
```

Where:
- **similarity** = cosine similarity between query vector and memory vector (with query expansion for slot-style questions like "what is my favorite color")
- **recency** = exp(-age / 604800) — 7-day lambda (a 7-day-old memory scores ~0.37)
- **belief_weight** = 0.7 * trust + 0.3 * confidence
- **tier_weight** = {0: 0.85, 1: 0.95, 2: 1.0} — compression tier penalty

Retrieval excludes:
- Deprecated memories
- Memories from resolved contradictions (the "loser" side)
- Memories below the trust threshold
- Memories outside the user scope

Returned memories have their `access_count` incremented for compression volatility tracking.

## 9. Citation

Retrieved memories are formatted into the prompt with trust scores visible:

```
1. FACT: name = Nick [trust: 0.92] [similarity: 0.87]
2. PREF: communication_style = concise [trust: 0.78] [similarity: 0.65]
```

When sending to cloud providers, these metadata annotations are stripped by the cloud prompt scrubber.

## 10. Trust Update

Trust evolves through several mechanisms:

- **Reinforcement** — When a memory is cited in a response and the user doesn't correct it, trust gets a small boost
- **Correction penalty** — When a user explicitly corrects information, the old memory's trust drops
- **Dedup reinforcement** — When the user re-states something already stored, trust increases by 0.05
- **Trust decay** — Periodic decay in the heartbeat cycle reduces trust of unused memories over time
- **Contested cap** — If a memory is involved in an open contradiction, its trust is capped at 10% of its normal value (`CONTESTED_TRUST_MULTIPLIER = 0.1`)

## 11. Compression

After trust decay in the heartbeat cycle, `run_compression_pass()` evaluates each memory:

- Compute volatility V(t) from drift, contradiction density, and fidelity loss
- Promote high-volatility memories to higher tiers (more fidelity)
- Demote low-volatility, low-trust, stable memories to lower tiers (less storage)
- Track stability cycles for memories in the calm zone

See the [Compression doc](COMPRESSION.md) for full details on the V(t) formula and tier transitions.

## 12. Deprecation

Memories are deprecated (soft-deleted) through:

- **Contradiction resolution** — When a contradiction is resolved (e.g., user says "actually, my name is Alex" correcting "name = Nick"), the old memory is deprecated with a reason
- **Staleness** — Memories with `review_after` timestamps that have passed are marked stale (still retrievable but flagged)
- **Self-model updates** — When a self-model slot is updated, old slot memories are deprecated

Deprecated memories are excluded from retrieval by default but remain in the database for audit purposes. They are never physically deleted.

### Review After Defaults

| Kind | Review Period |
|------|-------------|
| identity_constant | Never |
| user_fact | Never |
| preference | 90 days |
| permission | 14 days |
| ops | 30 days |
| hypothesis | 30 days |
| observation | 60 days |
| narrative_note | Never |
