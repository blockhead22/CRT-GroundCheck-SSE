# Session Prompt: Phase 1 — Replace fold_vector with Rotation + Lloyd-Max Quantization

## What This Is

Replace the internals of `personal_agent/memory_compression.py` so that compression uses **rotation + Lloyd-Max scalar quantization** instead of **chunked averaging (fold_vector)**. The volatility governance logic (WHEN to compress, promote/demote decisions) stays exactly as-is. Only the HOW changes.

This is a **production change** to `D:\AI_round2\personal_agent\memory_compression.py`. The proven implementation lives at `D:\CRT\compression_lab\turboquant_memory.py` and `D:\CRT\compression_lab\residual_vq.py`.

## Why

Benchmarks on 556 real memory vectors proved fold_vector is catastrophically lossy:
- fold to 64D: 0.408 cosine similarity, 65% top-10 recall at 256 bytes
- fold to 10D: 0.153 cosine similarity, 29% top-10 recall at 40 bytes

Rotation + Lloyd-Max at 3-bit: **0.983 cosine similarity, 93.9% top-10 recall at 148 bytes.**

GroundCheck cannot reliably detect contradictions on folded vectors. The new method preserves all 384 dimensions at reduced bit precision, maintaining the semantic topology.

## Important Naming

Do NOT use the name "TurboQuant" — that's now a Google ICLR 2026 paper. The internal name for this method should be **MemQuant** (or suggest something better). The variable names, class names, docstrings should all use the new name.

## Reference Files (READ ONLY)

- `D:\CRT\compression_lab\turboquant_memory.py` — MemoryQuantizer class (the math). Rename to MemQuant.
- `D:\CRT\compression_lab\residual_vq.py` — ResidualVQ class (variable depth, Phase 2). Don't implement yet, just don't break compatibility.
- `D:\AI_round2\compression_lab\IMPLEMENTATION_BRIEF.md` — Full context on what was proven.

## File to Modify

`D:\AI_round2\personal_agent\memory_compression.py` (~516 lines)

## What STAYS Unchanged

All of this governance logic is correct and stays as-is:
- `VOLATILITY_ALPHA`, `VOLATILITY_BETA`, `VOLATILITY_GAMMA` constants
- `PROMOTION_THRESHOLD`, `DEMOTION_THRESHOLD`, `DEMOTION_STABLE_CYCLES`, `DEMOTION_MAX_TRUST`
- `PROTECTED_KINDS`, `PROTECTED_AUTHORITIES`
- `compute_volatility()` — the V(t) formula
- `compute_volatility_from_item()` — convenience wrapper
- `should_promote()` — decides when to promote
- `should_demote()` — decides when to demote
- `minimum_tier()` — protection logic
- All `_log_*` functions — logging stays the same
- `run_compression_pass()` — the outer loop that scans all memories. This calls fold_vector/unfold_vector internally, those calls change.

## What Changes

### Step 1: Add MemQuant quantizer class — PAUSE after

Copy the core math from `turboquant_memory.py` into `memory_compression.py`, renamed:

- `MemoryQuantizer` → `MemQuantizer`
- `CompressedMemory` → `QuantizedMemory`
- `lloyd_max_codebook()` stays (it's a generic algorithm name)
- Strip QJL (Stage 2) — the implementation brief says it's marginal benefit for production. Keep only Stage 1 (rotation + Lloyd-Max).
- Add `scipy` to imports (needed for `norm.cdf`, `norm.pdf` in lloyd_max_codebook)

The quantizer should be a **module-level singleton** initialized once:
```python
# Initialize quantizers for each bit depth
_QUANTIZERS: Dict[int, MemQuantizer] = {}

def _get_quantizer(bits: int, dim: int = 384) -> MemQuantizer:
    key = (bits, dim)
    if key not in _QUANTIZERS:
        _QUANTIZERS[key] = MemQuantizer(dim=dim, bits=bits, seed=42)
    return _QUANTIZERS[key]
```

### Step 2: Remap tier system — PAUSE after

The old tier system mapped tiers to dimensions:
```python
TIER_DIMS = {0: 10, 1: 64, 2: 384}
```

The new system maps tiers to bit depths (all stay at 384D):
```python
TIER_BITS: Dict[int, int] = {0: 2, 1: 3, 2: 0}  # 0 = uncompressed (full 384D float32)
TIER_NAMES: Dict[int, str] = {0: "cold-2bit", 1: "warm-3bit", 2: "full-384D"}
```

Keep `TIER_DIMS` around temporarily for backward compatibility but mark it deprecated.

### Step 3: Replace fold_vector / unfold_vector — PAUSE after

Replace the internals but keep the same function signatures for now:

```python
def fold_vector(vector: np.ndarray, target_dim: int) -> Tuple[np.ndarray, CogniSeed]:
    """Compress a vector using rotation + Lloyd-Max quantization.

    NOTE: target_dim is now mapped to bit depth internally.
    384 → uncompressed, 64 → 3-bit, 10 → 2-bit.
    The returned 'compressed' array is the quantized indices (uint8), not a lower-dim vector.
    CogniSeed stores the bit depth and norm for reconstruction.
    """
```

Actually — better approach. **Add new functions** and update `run_compression_pass` to call them instead:

```python
def quantize_vector(vector: np.ndarray, bits: int) -> Tuple[np.ndarray, dict]:
    """Compress using MemQuant. Returns (indices_array, metadata_dict)."""
    q = _get_quantizer(bits, dim=len(vector))
    compressed = q.compress(vector)
    metadata = {
        "method": "memquant",
        "bits": bits,
        "norm": compressed.norm,
        "original_dim": len(vector),
    }
    return compressed.indices.astype(np.uint8), metadata

def dequantize_vector(indices: np.ndarray, metadata: dict) -> np.ndarray:
    """Reconstruct from MemQuant compressed form."""
    bits = metadata["bits"]
    norm = metadata["norm"]
    dim = metadata.get("original_dim", 384)
    q = _get_quantizer(bits, dim=dim)
    cm = QuantizedMemory(indices=indices, bits=bits, norm=norm)
    return q.decompress(cm)

def quantized_inner_product(query: np.ndarray, indices: np.ndarray, metadata: dict) -> float:
    """Compute inner product directly from compressed form (faster than decompress + dot)."""
    bits = metadata["bits"]
    norm = metadata["norm"]
    dim = metadata.get("original_dim", 384)
    q = _get_quantizer(bits, dim=dim)
    cm = QuantizedMemory(indices=indices, bits=bits, norm=norm)
    return q.inner_product(query, cm)
```

Keep `fold_vector` and `unfold_vector` as deprecated wrappers that call the new functions internally, so nothing breaks during transition.

### Step 4: Update run_compression_pass — PAUSE after

In `run_compression_pass()`, the promote/demote logic currently calls:
```python
new_vec, new_seed = fold_vector(original_vector, new_dim)
```

Change to:
```python
tier_to_bits = {0: 2, 1: 3, 2: 0}  # 0 means uncompressed
bits = tier_to_bits[new_tier]
if bits > 0:
    indices, metadata = quantize_vector(original_vector, bits)
    # Store indices as JSON array (uint8 values)
    # Store metadata as JSON dict
    conn.execute(
        f"""UPDATE memories SET
                compression_tier = ?,
                compressed_vector_json = ?,
                cogni_seed_json = ?
            WHERE {id_col} = ?""",
        (new_tier, json.dumps(indices.tolist()), json.dumps(metadata), mem_id),
    )
```

The `compressed_vector_json` column now stores uint8 indices (not a lower-dim float vector).
The `cogni_seed_json` column now stores the metadata dict (not a CogniSeed).

**Backward compatibility:** Check the stored data format. If `cogni_seed_json` contains `"method": "memquant"`, use the new path. Otherwise fall back to old CogniSeed parsing for existing compressed memories.

### Step 5: Update compute_volatility drift calculation — PAUSE after

`compute_volatility()` computes drift as cosine similarity between original and reconstructed vectors. Update the reconstruction path:

```python
# D(t): drift — reconstruction vs original
drift = 0.0
if compressed_vector is not None and cogni_seed is not None and original_vector is not None:
    # Check if this is new-format (memquant) or old-format (fold)
    if isinstance(cogni_seed, dict) and cogni_seed.get("method") == "memquant":
        reconstructed = dequantize_vector(
            np.array(compressed_vector, dtype=np.uint8),
            cogni_seed
        )
    else:
        # Legacy fold format
        reconstructed = unfold_vector(compressed_vector, cogni_seed)
    # ... rest of cosine sim calculation stays the same
```

### Step 6: Update retrieval path in crt_memory.py — PAUSE after

`crt_memory.py:1705-1720` handles retrieval with compressed vectors. Currently it folds the query down to match the compressed dimension:

```python
from personal_agent.memory_compression import fold_vector, TIER_DIMS
# ...
target_dim = TIER_DIMS.get(tier, 384)
folded_query, _ = fold_vector(qvec, target_dim)
```

With the new system, compressed memories stay at 384D (just quantized). Retrieval options:
1. **Simple approach:** Decompress the memory vector, do normal cosine similarity. Slightly slower but no changes to retrieval logic.
2. **Fast approach:** Use `quantized_inner_product()` to compute similarity directly from compressed form.

For Phase 1, use the simple approach (decompress then compare). Phase 2 (RVQ) will optimize this.

The retrieval code at `crt_memory.py:1705-1720` should change to:
```python
from personal_agent.memory_compression import dequantize_vector

# For compressed memories:
if tier < 2 and compressed_vector is not None and cogni_seed is not None:
    if isinstance(cogni_seed, dict) and cogni_seed.get("method") == "memquant":
        effective_vector = dequantize_vector(
            np.array(compressed_vector, dtype=np.uint8), cogni_seed
        )
    else:
        # Legacy fold path
        target_dim = TIER_DIMS.get(tier, 384)
        folded_query, _ = fold_vector(qvec, target_dim)
        # ... existing logic
```

### Step 7: Write tests — PAUSE after

Create `tests/test_memquant.py`:

1. **Round-trip test:** Compress a random 384D vector at each bit depth (2, 3, 4, 8), decompress, verify cosine similarity > 0.93
2. **Inner product preservation:** 100 random pairs, verify correlation > 0.99 at 3-bit
3. **Determinism:** Same input + same seed = same output
4. **Zero vector handling:** Compress a zero vector, verify no crash
5. **Integration test:** Run `run_compression_pass` on a test DB with 10 memories, verify it uses memquant format
6. **Backward compat:** Create a memory with old fold format, verify it still loads and reconstructs

### Step 8: Migration script — PAUSE after

Create `scripts/migrate_compression.py`:

For all existing compressed memories (tier 0 or 1):
1. Load the original vector (vector_json, which is always stored at full 384D)
2. Re-compress using `quantize_vector()` at the appropriate bit depth
3. Update `compressed_vector_json` and `cogni_seed_json` with new format
4. Print progress every 100 memories

This should be idempotent — skip memories that already have `"method": "memquant"` in their metadata.

### Step 9: Verify and commit — PAUSE after

1. Run all existing tests: `pytest tests/ -x -q`
2. Run the new tests: `pytest tests/test_memquant.py -v`
3. Start the server: `python crt_api.py` — verify no startup errors
4. Run a compression pass manually and check logs for diamond prefix events
5. Commit with a clear message

## Technical Notes

- `scipy` is already in requirements.txt (used by belief_synthesis.py)
- The rotation matrix and codebooks are deterministic (seed=42) — same compression every time
- The MemQuantizer is lightweight (~1MB for the rotation matrix at 384D) — fine as a singleton
- Don't delete the old fold_vector/unfold_vector/CogniSeed code yet — keep as deprecated. Phase 2 (RVQ) will be the clean break.
- The `vector_json` column (full 384D) is ALWAYS preserved — compression is additional storage, not replacement. This means we can always re-compress without data loss.

## DB Schema Note

No schema changes needed. We reuse existing columns:
- `compressed_vector_json` — was JSON array of floats (64D or 10D), now JSON array of uint8 indices (384 values, 0-7 for 3-bit)
- `cogni_seed_json` — was CogniSeed dict, now metadata dict with `"method": "memquant"`
- `compression_tier` — same meaning (0=cold, 1=warm, 2=full), just different compression behind it

The format detection (`cogni_seed.get("method") == "memquant"`) handles both old and new formats automatically.
