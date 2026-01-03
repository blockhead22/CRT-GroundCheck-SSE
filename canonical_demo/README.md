# Canonical Demo: Frozen Reference Implementation

## Overview

This directory contains the **frozen reference output** of SSE's canonical run.

This is NOT a test. This is a **ground truth artifact**.

Every time SSE is modified, its outputs on this same input should be compared to these artifacts. If outputs change unexpectedly, it signals philosophical drift or unintended regression.

---

## Files

### `input.txt`
The canonical input text: 1,407 characters of deliberately crafted text containing:
- Clear contradictions (round Earth vs flat Earth, exercise benefits vs harms, climate reality vs hoax)
- Hedged claims ("some say", "insist", "claim")
- Ambiguous pronouns and scope
- Repeated claims (for deduplication testing)

**Purpose**: Ground truth input. Do not modify without approval.

---

### `chunks.json`
The text segmented into chunks by `chunk_text()`.

**Structure**:
```json
[
  {
    "chunk_id": "c0",
    "text": "The Earth is round. Scientists have...",
    "start_char": 0,
    "end_char": 250
  },
  ...
]
```

**What it shows**:
- How input is split (max 300 chars, 50 char overlap)
- Exact byte offsets for each chunk
- Validation: `text[start_char:end_char]` must equal `text` field

**Expected count**: 6 chunks

---

### `claims.json`
All claims extracted from text via `extract_claims_from_chunks()`.

**Structure**:
```json
[
  {
    "claim_id": "clm0",
    "claim_text": "The Earth is round.",
    "supporting_quotes": [
      {
        "text": "The Earth is round.",
        "chunk_id": "c0",
        "start_char": 0,
        "end_char": 18
      }
    ],
    "ambiguity": {
      "score": 0.1,
      "type": "none",
      "hedge_detected": false
    }
  },
  ...
]
```

**Validation**:
- **Invariant I (Quoting)**: Every claim has `supporting_quotes`
- **Invariant VI (Traceability)**: For each quote, `input[start_char:end_char]` == `quote.text`
- **Invariant V (Uncertainty)**: Claims with hedge words have `ambiguity` data

**Expected count**: 28 claims

**Key observations**:
- Contradictory claims both present (e.g., "Earth is round" + "Earth is flat")
- Hedged claims marked: "Some flat Earth believers claim..." gets ambiguity flag
- No paraphrasing: Claims are exact substrings or slight variations from source

---

### `contradictions.json`
All detected contradictions between pairs of claims.

**Structure**:
```json
[
  {
    "pair": {
      "claim_id_a": "clm0",
      "claim_id_b": "clm3"
    },
    "label": "contradiction",
    "evidence_quotes": [
      {
        "text": "The Earth is round.",
        "chunk_id": "c0",
        "start_char": 0,
        "end_char": 18
      },
      {
        "text": "However, some flat Earth believers claim the Earth is flat.",
        "chunk_id": "c0",
        "start_char": 260,
        "end_char": 319
      }
    ]
  },
  ...
]
```

**Validation**:
- **Invariant II (Contradiction Preservation)**: Both sides of each contradiction appear in `claims.json`
- **Invariant VI (Traceability)**: Evidence quotes have correct offsets and text

**Expected count**: 34 contradictions

**Analysis**:
- Contradictions properly detected (e.g., clm0 "round" vs clm3 "flat")
- Both claims still in output (not suppressed)
- Grounded with exact quotes and offsets
- Some "false positives" expected (e.g., unrelated claims paired); system prioritizes inclusion over precision

---

### `clusters.json`
Semantic clusters of similar claims via `cluster_embeddings()`.

**Structure**:
```json
[
  {
    "cluster_id": 0,
    "claim_ids": ["clm0", "clm1", "clm2"]
  },
  ...
]
```

**Purpose**:
- Groups semantically similar claims
- Not used for deduplication (opposite claims remain separate)
- Useful for understanding claim relationships

**Expected count**: 12 clusters

---

### `metadata.json`
Summary statistics and configuration.

**Structure**:
```json
{
  "timestamp": "2025-12-31T21:43:03.210373",
  "canonical_version": "1.0",
  "input_length_chars": 1407,
  "input_word_count": 213,
  "chunks_count": 6,
  "claims_count": 28,
  "contradictions_count": 34,
  "clusters_count": 12,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dimensions": 384,
  "contradiction_detector": "heuristic",
  "ollama_available": false
}
```

**Why it exists**:
- Documents the conditions of this run
- Allows future runs to note deviations
- Shows which embedding model + detector was used
- Explains why results should be identical given same inputs and code

---

## How to Use This Reference

### After Code Changes

Run the validation script (TBD):
```bash
python validate_against_canonical.py canonical_demo/
```

This will:
1. Re-run SSE on the same input
2. Compare outputs to canonical artifacts
3. Report any deviations
4. Fail if invariants are violated

### If Outputs Change

**Small changes** (same counts, different ordering):
- Acceptable if behavior is preserved
- Document the reason in CHANGELOG

**Medium changes** (different claim counts, new contradictions):
- Investigate root cause
- Verify it's intentional improvement, not regression
- Update canonical demo if justified

**Large changes** (vastly different outputs):
- Revert or fix the code change
- This likely indicates philosophical drift

---

## Key Properties of This Canonical Run

### What SSE Did Correctly

1. **Preserved contradictions**
   - Both "round Earth" and "flat Earth" claims extracted
   - Contradiction detected between them
   - Both remain in output (not suppressed)

2. **Preserved opposite claims**
   - "Exercise is beneficial" vs "exercise is harmful" both present
   - Not deduplicated despite semantic similarity
   - Contradiction properly marked

3. **Grounded all claims**
   - Every claim mapped to source with exact offsets
   - All quotes verified against source text
   - No paraphrasing or inference

4. **Marked ambiguity**
   - Hedged claims ("some say", "insist") noted
   - Ambiguity scores computed
   - Uncertainty preserved, not smoothed away

### What SSE Did Not Do

1. ❌ Auto-resolve contradictions
2. ❌ Pick "correct" side of disputes
3. ❌ Merge opposite claims for coherence
4. ❌ Paraphrase claims
5. ❌ Create implied claims
6. ❌ Hide limitations (documented heuristic fallback)

---

## Testing Against Canonical

### Invariant-Based Validation

The canonical demo validates these invariants:

| Invariant | Validation |
|-----------|-----------|
| I. Quoting | All 28 claims have supporting quotes |
| II. Contradiction | 34 contradictions detected; both sides in claims |
| III. Anti-Dedup | Opposite claims not removed (beneficial ≠ harmful) |
| IV. Non-Fabrication | No claims beyond 28 explicit statements |
| V. Uncertainty | Hedged claims marked with ambiguity scores |
| VI. Traceability | All offsets valid; `input[start:end]` == quote text |
| VII. Honesty | Metadata documents heuristic fallback |

Each invariant is tested in `tests/test_behavior_invariants.py`.

---

## Regenerating Canonical

**Only do this if SSE's behavior fundamentally improves AND you've approved the change.**

```bash
cd canonical_demo
python generate_canonical.py
```

This overwrites all `.json` files. The `input.txt` should rarely change.

**Before regenerating**, ensure:
1. All tests pass
2. Invariants are still respected
3. Changes are intentional improvements, not drift
4. Document in CHANGELOG why canonical changed

---

## References

- **SSE_INVARIANTS.md**: The seven architectural laws
- **tests/test_behavior_invariants.py**: Automated validation of invariants
- **POSITIONING.md**: What SSE is and is not
- **ARTIFACT_SCHEMAS.md**: Detailed JSON schema documentation

---

## Summary

This canonical demo is **proof that SSE works as intended**.

It shows:
- ✅ Contradictions preserved
- ✅ Claims grounded with source quotes
- ✅ No auto-resolution of disputes
- ✅ Uncertainty marked and preserved
- ✅ All outputs traceable to source

Use these artifacts as your reference. When in doubt about SSE behavior, check if the canonical demo behaves the same way.

If canonical behavior doesn't match your intuition, **your intuition is wrong**. SSE is designed to preserve contradictions and ambiguity, not resolve them.
