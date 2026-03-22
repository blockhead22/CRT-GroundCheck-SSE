# Phase 1: Adaptive Memory Compression Integration

## Goal
Add tier-based compression to CRT memory storage. Memories with low trust and high stability get folded to 10D. High-trust or volatile memories stay at 384D. The trust_decay heartbeat drives compression passes.

---

## Step 1: Schema Migration — Add compression columns to `memories` table

**File:** `personal_agent/crt_memory.py` (in `_init_db()`)

Add three new columns via idempotent ALTER TABLE (same pattern as existing migrations):

```sql
ALTER TABLE memories ADD COLUMN compression_tier INTEGER DEFAULT 2;
ALTER TABLE memories ADD COLUMN compressed_vector_json TEXT;
ALTER TABLE memories ADD COLUMN cogni_seed_json TEXT;
ALTER TABLE memories ADD COLUMN stable_cycles INTEGER DEFAULT 0;
ALTER TABLE memories ADD COLUMN contradiction_count INTEGER DEFAULT 0;
ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0;
```

- `compression_tier`: 0 (10D), 1 (64D), 2 (384D full). Default 2 = all existing memories stay full.
- `compressed_vector_json`: JSON-serialized compressed vector (null for tier 2).
- `cogni_seed_json`: Serialized CogniSeed for reconstruction (null for tier 2).
- `stable_cycles`: Incremented each trust_decay pass when volatility < 0.1. Reset on promotion/demotion.
- `contradiction_count`: Incremented when contradictions are detected against this memory.
- `access_count`: Incremented on each retrieval hit.

**MemoryItem dataclass** — add corresponding fields with defaults:
- `compression_tier: int = 2`
- `compressed_vector: Optional[np.ndarray] = None`
- `cogni_seed: Optional[Dict] = None`
- `stable_cycles: int = 0`
- `contradiction_count: int = 0`
- `access_count: int = 0`

Update `_row_to_memory()` and `store_memory()` to read/write the new columns.

---

## Step 2: Move compression_lab into personal_agent

**Action:** Copy `compression_lab/adaptive_memory.py` core functions into a new file `personal_agent/memory_compression.py`.

Extract and adapt:
- `fold_vector(vector, target_dim)` → returns `(compressed_vector, cogni_seed_dict)`
- `unfold_vector(compressed, seed)` → returns approximate 384D reconstruction
- `compute_volatility(memory)` → V(t) = α·D(t) + β·C(t) + γ·F(t)
- `compute_throttle(volatility)` → H(t) = H₀·e^(-s·V(t))
- `should_promote(memory)` / `should_demote(memory)` — tier transition logic
- `TIER_DIMS = {0: 10, 1: 64, 2: 384}`

**Key adaptation:** The functions need to work with `MemoryItem` objects (not `CompressedMemory`), reading from the new dataclass fields.

---

## Step 3: Compression pass in trust_decay heartbeat

**File:** `personal_agent/trust_decay.py` — `run_trust_decay_pass()`

After the existing decay logic, add a compression pass:

```python
# --- Compression pass ---
from personal_agent.memory_compression import (
    compute_volatility, should_promote, should_demote,
    fold_vector, unfold_vector, TIER_DIMS
)

for memory in stale_memories:
    volatility = compute_volatility(memory)

    if should_demote(memory, volatility):
        # Fold to lower tier
        target_dim = TIER_DIMS[memory.compression_tier - 1]
        compressed, seed = fold_vector(memory.vector, target_dim)
        update_memory_tier(memory.memory_id,
            new_tier=memory.compression_tier - 1,
            compressed_vector=compressed,
            cogni_seed=seed)

    elif should_promote(memory, volatility):
        # Unfold to higher tier
        if memory.compression_tier < 2:
            reconstructed = unfold_vector(memory.compressed_vector, memory.cogni_seed)
            new_tier = memory.compression_tier + 1
            if new_tier == 2:
                # Back to full — use original vector if available
                ...
            else:
                target_dim = TIER_DIMS[new_tier]
                compressed, seed = fold_vector(memory.vector, target_dim)
                update_memory_tier(...)

    # Track stability
    if volatility < 0.1:
        increment_stable_cycles(memory.memory_id)
    else:
        reset_stable_cycles(memory.memory_id)
```

**Demotion criteria (from compression_lab):**
- trust < 0.3 AND stable_cycles >= 10 AND volatility < 0.1
- Kind not in ("identity_constant", "locked")
- Authority not "locked"

**Promotion criteria:**
- volatility >= 0.6, OR
- trust >= 0.9 AND volatility >= 0.3

---

## Step 4: Tier-aware retrieval in crt_memory.py

**File:** `personal_agent/crt_memory.py` — `retrieve_memories()`

Current flow: encode query → load all memories → compute cosine similarity at 384D.

New flow:
```python
query_vector = encode_vector(query)

for memory in all_memories:
    if memory.compression_tier == 2:
        # Full vector — compare directly
        sim = cosine_similarity(query_vector, memory.vector)
    else:
        # Compressed — fold query to memory's tier
        target_dim = TIER_DIMS[memory.compression_tier]
        query_folded, _ = fold_vector(query_vector, target_dim)
        sim = cosine_similarity(query_folded, memory.compressed_vector)

    # Rest of scoring unchanged (trust-weighted, recency, etc.)
```

Also: increment `access_count` for returned memories.

---

## Step 5: Protect critical memories from compression

**Rules (hardcoded, not configurable):**
- `authority == "locked"` → never compress (tier 2 always)
- `kind == "identity_constant"` → never compress
- `source == MemorySource.USER` AND `trust >= 0.8` → minimum tier 1 (64D)
- Everything else follows volatility/trust demotion rules

---

## Step 6: store_memory() — new memories start at full fidelity

No change to initial storage — all new memories enter at tier 2 (384D full). Compression only happens during heartbeat passes after the memory has aged past the grace period (7 days) and stabilized.

The only addition: initialize `stable_cycles=0`, `contradiction_count=0`, `access_count=0` in the INSERT.

---

## Step 7: Increment contradiction_count on contradiction detection

**File:** `personal_agent/crt_memory.py` — wherever contradictions are logged (the existing contradiction decay logic around line 1293).

When a contradiction is detected against memory X:
```python
cursor.execute(
    "UPDATE memories SET contradiction_count = contradiction_count + 1 WHERE memory_id = ?",
    (contradicted_memory_id,)
)
```

This feeds into V(t)'s C(t) = contradiction_count / access_count.

---

## Step 8: Tests

**New file:** `tests/test_memory_compression_integration.py`

Test cases:
1. Schema migration adds columns without breaking existing data
2. New memories start at tier 2 with null compressed fields
3. Low-trust stable memory gets demoted to tier 0 after enough cycles
4. High-volatility memory gets promoted back to tier 2
5. Locked/identity memories never get compressed
6. Tier-aware retrieval returns correct results across mixed tiers
7. access_count increments on retrieval
8. contradiction_count increments on contradiction detection
9. Round-trip: store → age → compress → retrieve → promote → retrieve

---

## Files Modified
1. `personal_agent/crt_memory.py` — schema, MemoryItem, store, retrieve, row mapping
2. `personal_agent/trust_decay.py` — compression pass in heartbeat
3. **NEW** `personal_agent/memory_compression.py` — adapted from compression_lab
4. **NEW** `tests/test_memory_compression_integration.py`

## Files NOT Modified
- `compression_lab/` — stays as-is (proof of concept / reference)
- `personal_agent/crt_core.py` — no changes to CRT math
- `personal_agent/crt_rag.py` — retrieval changes go in crt_memory.py
- Frontend — no UI changes in Phase 1

## Risk Assessment
- **Low risk:** Schema migration is additive (ALTER TABLE ADD COLUMN with defaults). Existing memories unaffected.
- **Low risk:** Compression pass is append-only in the heartbeat. If it errors, trust decay still runs.
- **Medium risk:** Tier-aware retrieval changes the similarity computation path. Need to validate that folded query comparisons produce equivalent rankings to full-dim comparisons. The compression_lab tests already prove rank preservation, but integration testing with real CRT memories is essential.
- **Rollback:** Set all `compression_tier = 2` and `compressed_vector_json = NULL` to revert. No data loss since original `vector_json` is never modified.
