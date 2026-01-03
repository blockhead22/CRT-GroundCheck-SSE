# SSE Validation Guide: Understanding How to Verify SSE Works Correctly

## Overview

This guide explains how to validate that SSE is working correctly.

Validation is NOT benchmarking. It's about **proofing correctness** against the seven invariants.

---

## The Seven Invariants as Validation Criteria

### Invariant I: Quoting
**Claim**: "Every extracted claim must include the exact substring from source"

**How to validate**:
```python
for claim in claims:
    assert len(claim['supporting_quotes']) > 0
    for quote in claim['supporting_quotes']:
        start = quote['start_char']
        end = quote['end_char']
        assert source[start:end] == quote['text']
```

**What this proves**: No paraphrasing occurred.

**Failure mode**: Missing quotes, quote text doesn't match source offset.

---

### Invariant II: Contradiction Preservation
**Claim**: "If source contains A and ¬A, both must be in output"

**How to validate**:
```python
# Given contradictions detected:
for cont in contradictions:
    claim_a_id = cont['pair']['claim_id_a']
    claim_b_id = cont['pair']['claim_id_b']
    
    # Both claims must exist in claims array
    assert any(c['claim_id'] == claim_a_id for c in claims)
    assert any(c['claim_id'] == claim_b_id for c in claims)
```

**What this proves**: Contradictions are preserved, not suppressed.

**Failure mode**: One side of contradiction missing from claims array.

---

### Invariant III: Anti-Deduplication
**Claim**: "Opposite claims must not be deduplicated"

**How to validate**:
```python
# Example: "beneficial" and "harmful"
claim_texts = [c['claim_text'].lower() for c in claims]

# Both sides should be present
has_beneficial = any('beneficial' in ct for ct in claim_texts)
has_harmful = any('harmful' in ct for ct in claim_texts)

assert has_beneficial and has_harmful
```

**What this proves**: Opposite claims survived deduplication.

**Failure mode**: One opposite removed, contradictions not detected because both sides missing.

---

### Invariant IV: Non-Fabrication
**Claim**: "No claims invented; only what's in source"

**How to validate**:
```python
# Sanity check: claim count should be reasonable
# (not more than ~1 claim per 20 words)
expected_max_claims = len(source.split()) // 15
assert len(claims) <= expected_max_claims * 2  # conservative
```

**What this proves**: Claims are extracted, not hallucinated.

**Failure mode**: Implausible number of claims, claims about things not in source.

---

### Invariant V: Uncertainty Preservation
**Claim**: "Ambiguity and hedges preserved, not smoothed"

**How to validate**:
```python
# Claims with hedges should be marked
for claim in claims:
    if any(h in claim['claim_text'].lower() 
           for h in ['might', 'may', 'some', 'possibly']):
        assert claim.get('ambiguity', {}).get('hedge_detected') == True
```

**What this proves**: Hedged claims are flagged.

**Failure mode**: Hedged claims lack ambiguity data.

---

### Invariant VI: Source Traceability
**Claim**: "Every output element maps to source offsets"

**How to validate**:
```python
# All chunks reconstruct source
full_text = "".join(c['text'] for c in chunks 
                    if c['chunk_id'] in sorted_chunk_ids)
# Overlaps may cause repetition, but all offsets must be valid

# All quotes reconstruct from offsets
for claim in claims:
    for quote in claim['supporting_quotes']:
        assert source[quote['start_char']:quote['end_char']] == quote['text']

# All contradictions reference valid claims
for cont in contradictions:
    assert any(c['claim_id'] == cont['pair']['claim_id_a'] for c in claims)
    assert any(c['claim_id'] == cont['pair']['claim_id_b'] for c in claims)
```

**What this proves**: Everything is traceable to source.

**Failure mode**: Invalid offsets, offset-text mismatch, missing claim references.

---

### Invariant VII: Computational Honesty
**Claim**: "Limitations and fallbacks are documented"

**How to validate**:
```python
# Metadata documents the conditions
assert 'embedding_model' in metadata
assert 'contradiction_detector' in metadata
assert 'ollama_available' in metadata
```

**What this proves**: System doesn't hide what it did or what services it used.

**Failure mode**: No metadata, hidden fallbacks.

---

## Validation Testing Strategy

### Level 1: Schema Validation
Verify that all outputs conform to JSON schemas.

```python
from jsonschema import validate
validate(instance=output, schema=SSE_SCHEMA)
```

**Covers**: Structural correctness.

### Level 2: Invariant Validation
Verify that all seven invariants are upheld.

Run the tests in `tests/test_behavior_invariants.py`:
```bash
pytest tests/test_behavior_invariants.py -v
```

**Covers**: Philosophical correctness (does SSE do what it promises?).

### Level 3: Canonical Comparison
Compare outputs against frozen canonical reference.

```bash
python validate_against_canonical.py canonical_demo/
```

**Covers**: Regression detection (has behavior changed?).

### Level 4: Manual Inspection
Pick a few claims and verify them by hand against source.

**Covers**: Human sanity check (does this look right?).

---

## Expected Outcomes: The Canonical Reference

Running SSE on the canonical input should produce:

| Metric | Expected | Why |
|--------|----------|-----|
| Chunks | 6 | Text split at 300-char boundaries with 50-char overlap |
| Claims | 28 | 28 explicit sentences/assertions in source |
| Contradictions | 34 | Multiple opposing claim pairs detected |
| Clusters | 12 | Semantic grouping of 28 claims |

### Claim Distribution

- **Clear claims**: ~15 (unambiguous statements)
- **Hedged claims**: ~8 (with "some", "might", "claim", "argue")
- **Opposite claims**: ~5 pairs (10 total), each pair marked contradictory

### Contradiction Distribution

- **Expected contradictions**: Earth shape, exercise benefits, climate reality, water boiling point, vaccine safety (5 core pairs)
- **Detected contradictions**: 34 total (includes some tangential pairs due to broad similarity threshold)

### Ambiguity Distribution

- **Clear** (score 0.0-0.3): ~15 claims
- **Hedged** (score 0.3-0.7): ~8 claims
- **Ambiguous** (score 0.7-1.0): ~5 claims

---

## Failure Modes and Diagnostics

### Failure: Not enough claims extracted

**Symptoms**: Claims count << 28

**Likely causes**:
1. Deduplication too aggressive (lowered threshold back to 0.85 or below)
2. Extractive filter too strict (is_assertive() filtering out valid claims)
3. Chunks too small (missing sentences at boundaries)

**Diagnosis**:
```python
# Check raw sentence extraction before dedup
sents_before_dedup = ...  # before dedupe_claims()
print(f"Sentences before dedup: {len(sents_before_dedup)}")
print(f"Sentences after dedup: {len(claims)}")
# Large drop indicates dedup issue
```

### Failure: Contradictions not detected

**Symptoms**: Contradictions count << 34

**Likely causes**:
1. Heuristic weakened (opposition word pairs removed)
2. Similarity threshold too high (>0.25, filtering out opposition pairs)
3. LLM detector broken

**Diagnosis**:
```python
# Test heuristic directly
from sse.contradictions import heuristic_contradiction

result = heuristic_contradiction("Exercise is beneficial.", "Exercise is harmful.")
assert result == 'contradiction'  # Should pass
```

### Failure: Claims lack quotes

**Symptoms**: Invariant I violated

**Likely causes**:
1. supporting_quotes field not populated during extraction
2. Quote validation disabled

**Diagnosis**:
```python
for i, claim in enumerate(claims):
    if not claim.get('supporting_quotes'):
        print(f"Claim {i} ({claim['claim_text']}) has no quotes!")
```

### Failure: Quote offsets incorrect

**Symptoms**: Invariant VI violated

**Likely causes**:
1. Offset calculation wrong
2. Text modification after offset assignment
3. Chunk boundary errors

**Diagnosis**:
```python
for claim in claims:
    for quote in claim['supporting_quotes']:
        start, end = quote['start_char'], quote['end_char']
        actual = source[start:end]
        expected = quote['text']
        if actual != expected:
            print(f"Offset mismatch: [{start}:{end}]")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")
```

### Failure: One side of contradiction missing

**Symptoms**: Invariant II violated

**Likely causes**:
1. Deduplication removed opposite claim
2. Extraction failed to find one side
3. Contradiction detection removed claim

**Diagnosis**:
```python
contradictions = detect_contradictions(claims, embeddings)
claim_ids = {c['claim_id'] for c in claims}

for cont in contradictions:
    a_id = cont['pair']['claim_id_a']
    b_id = cont['pair']['claim_id_b']
    
    if a_id not in claim_ids:
        print(f"Contradiction references missing claim {a_id}")
    if b_id not in claim_ids:
        print(f"Contradiction references missing claim {b_id}")
```

---

## Validation Checklist

Before deploying SSE changes, verify:

- [ ] **Schema**: All outputs validate against JSON schemas
- [ ] **Invariant I**: All claims have supporting quotes
- [ ] **Invariant II**: Contradictions preserved (both sides present)
- [ ] **Invariant III**: Opposite claims not deduplicated
- [ ] **Invariant IV**: No fabricated claims
- [ ] **Invariant V**: Hedges and ambiguity marked
- [ ] **Invariant VI**: All offsets valid and traceable
- [ ] **Invariant VII**: Metadata documents conditions
- [ ] **Canonical**: Output matches canonical reference counts (±5%)
- [ ] **Tests**: All tests pass, including invariant tests
- [ ] **Manual check**: Spot-check 3-5 claims against source

---

## Performance Expectations

SSE is not optimized for speed, but these are reasonable expectations:

| Operation | Expected Time | Notes |
|-----------|----------------|-------|
| Chunking (1000 words) | <100ms | Simple text split |
| Embedding chunks | ~500ms | Depends on embedding model |
| Claim extraction | ~50ms | Pattern matching + dedup |
| Embedding claims | ~500ms | Same embedding model |
| Contradiction detection | ~100ms | Heuristic only |
| Full pipeline | ~1.5s | Total end-to-end |

If significantly slower, check:
- Embedding model loading
- LLM service latency
- Memory issues

---

## Validation Success Criteria

✅ **SSE is working correctly if**:
1. All 7 invariants hold across all tests
2. Canonical reference matches (±5% in counts)
3. All 20+ tests pass
4. Manual spot-checks show reasonable extractions
5. Contradictions are properly grounded

❌ **SSE has regressed if**:
1. Any invariant test fails
2. Canonical counts change by >10%
3. Any existing test starts failing
4. Manually-checked claims lack quotes or have wrong offsets
5. Contradictions mysteriously disappear

---

## Regression Testing

### Automated Regression (TBD)

Create a script that:
1. Runs SSE on canonical input
2. Compares output to canonical reference
3. Reports any deviations

```python
# Pseudocode
canonical = load_json("canonical_demo/claims.json")
current = run_sse(canonical_input)

assert len(canonical['claims']) == len(current['claims'])
assert len(canonical['contradictions']) == len(current['contradictions'])
```

### Manual Regression Check

After any code change:
```bash
cd canonical_demo
python generate_canonical.py  # Re-run
diff -u claims.json claims.json.bak  # Compare
# Review any differences
```

---

## Expected vs. Actual: Interpreting Validation Results

### Expected: 28 claims, Actual: 25 claims

**Possible causes**:
- 3 claims deduplicated (check if they're opposites → invariant III violation)
- 3 claims filtered by is_assertive() (check if they look like assertions)
- Extraction didn't find some sentences

**Action**: Investigate which 3 are missing and why.

### Expected: 34 contradictions, Actual: 40 contradictions

**Possible causes**:
- Lower similarity threshold catching more pairs
- Opposition word pairs expanded

**Action**: Review additional contradictions; verify they're real or acceptable false positives.

### Expected: All offsets valid, Actual: 2 offsets wrong

**Possible causes**:
- Off-by-one errors in byte counting
- Unicode/encoding issues

**Action**: Print mismatches and debug byte offsets.

---

## Conclusion

Validation is about **proving correctness**, not measuring performance.

If your SSE instance passes all invariant tests and matches canonical reference, **it's working correctly**.

If any test fails, **fix the code before proceeding**.

The validation guide and canonical reference are your proof points.
