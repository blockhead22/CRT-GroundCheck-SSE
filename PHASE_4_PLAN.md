# Phase 4: Core SSE Improvements (Work Plan)

**Status**: Starting from known-good state (38/38 tests passing)

---

## Overview

Phase 4 fixes two architectural limitations identified in Phase 3, improving Invariant III (Anti-Deduplication) and Invariant VI (Source Traceability) precision.

**No chat layer until Phase 4 core is solid.**

---

## Fix #1: Negation Deduplication (Invariant III)

### The Problem
Claims like "The statement is true" and "The statement is not true" have 0.916 text similarity, passing the 0.8 threshold in `dedupe_claims()`. Result: one claim is incorrectly deduplicated.

### Root Cause
**File**: `sse/extractor.py`, function `dedupe_claims()`, lines 40-62

```python
def dedupe_claims(claim_indices: List[int], claim_texts: List[str], embeddings: np.ndarray, thresh: float = 0.85) -> List[int]:
    """Deduplicate based on embedding + text similarity."""
    keep = []
    for i in claim_indices:
        vec = embeddings[i]
        dup = False
        for j in keep:
            emb_sim = float(np.dot(vec, embeddings[j]))
            if emb_sim > thresh:  # High embedding similarity
                text_sim = string_similarity(claim_texts[i], claim_texts[j])
                if text_sim > 0.8:  # Only deduplicate if text ALSO similar
                    dup = True
                    break
        if not dup:
            keep.append(i)
    return keep
```

**The issue**: Text similarity check (0.8) is too high for detecting negation.
- "is true" vs "is not true" = 0.916 ratio (>0.8, so marked duplicate)
- Should preserve both because they're semantically opposite

### The Solution

Add **negation detection** before the text similarity check:

```python
def has_negation_word(text: str) -> bool:
    """Check if text contains negation keywords."""
    negation_words = {'not', 'no', 'never', 'neither', 'nor', "doesn't", 
                     "don't", "didn't", "isn't", "aren't", "wasn't", 
                     "weren't", "haven't", "hasn't", "won't", "wouldn't",
                     "can't", "couldn't", "shouldn't", "mightn't"}
    words = set(text.lower().split())
    return bool(negation_words & words)

def dedupe_claims(...):
    # ... existing code ...
    if emb_sim > thresh:
        # NEW: Check if one has negation and other doesn't
        has_neg_i = has_negation_word(claim_texts[i])
        has_neg_j = has_negation_word(claim_texts[j])
        
        # If negation differs, they're opposites - preserve both
        if has_neg_i != has_neg_j:
            continue  # Not a duplicate
        
        # Only then check text similarity
        text_sim = string_similarity(claim_texts[i], claim_texts[j])
        if text_sim > 0.8:
            dup = True
            break
    # ... rest of code ...
```

### Test Validation

**Current test** (`test_negation_opposites_preserved`):
- ❌ Fails because "is true" + "is not true" get deduplicated
- Currently documents this as v0.1 limitation

**After fix**:
- ✅ Should pass because both claims preserved
- Run: `pytest tests/test_behavior_invariants.py::TestInvariantIII_AntiDeduplication::test_negation_opposites_preserved -v`

### Expected Impact

- Fixes Invariant III violation
- Should NOT break other tests (only adds false-negative prevention)
- Canonical metrics: Claims should increase (28 → ~30), contradictions increase accordingly

---

## Fix #2: Sentence-Level Offsets (Invariant VI)

### The Problem

**File**: `sse/extractor.py`, function `extract_claims_from_chunks()`, line 79

```python
for cidx, c in enumerate(chunks):
    sents = re.split(r'(?<=[.!?])\s+', c['text'])  # Split into sentences
    for s in sents:
        s = normalize_claim_text(s)
        if is_assertive(s):
            claim_texts.append(s)
            # BUG: Storing chunk offsets, not sentence offsets
            claim_support.append({
                "quote_text": s,
                "chunk_id": c['chunk_id'],
                "start_char": c['start_char'],  # Chunk start, not sentence start
                "end_char": c['end_char']        # Chunk end, not sentence end
            })
```

**Result**: Offsets point to full chunk, not the sentence. 
- Quote: "Water boils at 100°C" (38 chars)
- Offset: [0:56] (full chunk = 56 chars)
- Reconstruction: `text[0:56]` returns full chunk, not just the quote

### The Solution

Track sentence-level offsets inside chunks:

```python
def extract_claims_from_chunks(chunks: List[Dict], embeddings: np.ndarray) -> List[Dict]:
    claims = []
    claim_texts = []
    claim_support = []
    
    for cidx, c in enumerate(chunks):
        chunk_text = c['text']
        chunk_start = c['start_char']  # Document-level offset
        
        sents = re.split(r'(?<=[.!?])\s+', chunk_text)
        
        sent_pos = 0  # Track position within chunk
        for s in sents:
            s = normalize_claim_text(s)
            if not s:
                continue
            
            # Find this sentence in the chunk text
            # (accounting for whitespace after split)
            sent_start_in_chunk = chunk_text.find(s, sent_pos)
            if sent_start_in_chunk == -1:
                continue  # Sentence not found (shouldn't happen)
            
            sent_end_in_chunk = sent_start_in_chunk + len(s)
            sent_pos = sent_end_in_chunk  # Move forward
            
            if is_assertive(s):
                claim_texts.append(s)
                claim_support.append({
                    "quote_text": s,
                    "chunk_id": c['chunk_id'],
                    "start_char": chunk_start + sent_start_in_chunk,  # Document offset
                    "end_char": chunk_start + sent_end_in_chunk        # Document offset
                })
    
    # Rest of function unchanged...
```

### Test Updates

Current tests that will be affected:
- `test_quotes_are_verbatim_substrings` - Will now reconstruct exact quote
- `test_all_claims_have_valid_offsets` - Will have precise offsets

These tests currently check `quote_text in text`. After fix, will check `text[start:end] == quote_text`.

### Expected Impact

- Fixes Invariant VI precision violation
- Offsets now exact at sentence level, not chunk level
- Tests will need updating to verify `text[start:end] == quote_text` (currently just checks `in`)
- Canonical metrics: Should remain same (claims/contradictions unchanged)

---

## Implementation Plan

### Phase 4a: Fix Negation Deduplication

**Step 1**: Implement negation detection
- Add `has_negation_word()` function to `sse/extractor.py`
- Integrate into `dedupe_claims()` logic

**Step 2**: Update test expectations
- Modify `test_negation_opposites_preserved` to expect both claims
- Change from "this is a limitation" to "this is fixed"

**Step 3**: Regression test
```bash
pytest tests/test_behavior_invariants.py -v         # All 18 should pass
pytest tests/ -v                                    # All 38 should pass
python canonical_demo/generate_canonical.py         # Regenerate baseline
# Verify: claims ~28±5%, contradictions ~34±5%
```

### Phase 4b: Fix Sentence-Level Offsets

**Step 1**: Refactor `extract_claims_from_chunks()`
- Change offset calculation logic
- Test with debug script first

**Step 2**: Update tests
- Change `quote_text in text` back to `text[start:end] == quote_text`
- Remove "NOTE: SSE uses chunk offsets" comments
- Update test docstrings

**Step 3**: Regression test
```bash
pytest tests/test_behavior_invariants.py -v
pytest tests/ -v
python canonical_demo/generate_canonical.py
# Verify: metrics unchanged (offsets don't affect counts)
```

### Phase 4c: Expanded Test Coverage

**Add tests for**:
- More negation types (implicit negation, "neither...nor")
- Contradictions with multiple opposites
- Real-world documents (policy, news, science)
- Performance benchmarks

**After both core fixes are validated**: Expand test suite

---

## Regression Testing Protocol

After each fix, follow this checklist:

- [ ] Run invariant suite: `pytest tests/test_behavior_invariants.py -v`
  - All 18 must pass
  - If any fail, the invariant was violated

- [ ] Run full suite: `pytest tests/ -v`
  - All 38 must pass
  - If any original tests fail, we broke backward compat

- [ ] Regenerate canonical: `python canonical_demo/generate_canonical.py`
  - Record metrics in log
  - Claims: expect 28 ± 5% (28 is 26-30)
  - Contradictions: expect 34 ± 5% (34 is 32-36)
  - Clusters: expect 12 ± 5% (12 is 11-13)

- [ ] Compare metadata
  - Embedding model should be "all-MiniLM-L6-v2"
  - Detector should be "heuristic"
  - Ollama should be "false"
  - Times should be within ±20% (performance)

---

## Success Criteria

### Fix #1 Succeeds When:
- ✅ `test_negation_opposites_preserved` passes (both claims present)
- ✅ All 18 invariant tests pass
- ✅ All 38 total tests pass
- ✅ Canonical claims increase to ~29-30 (from 28)
- ✅ Canonical contradictions increase accordingly
- ✅ No other metrics degrade

### Fix #2 Succeeds When:
- ✅ Offsets in claims now reconstruct exact quotes
- ✅ `text[start:end] == quote_text` for all claims
- ✅ All 18 invariant tests pass
- ✅ All 38 total tests pass
- ✅ Canonical metrics unchanged (offsets don't affect counts)
- ✅ Invariant VI now has sentence-level precision

---

## Known Risks

### Fix #1 Risks
- **Risk**: Negation detection might not catch all negation types
- **Mitigation**: Add tests for implicit negation, contractions, etc.
- **Rollback**: Comment out negation check, return to old behavior

### Fix #2 Risks
- **Risk**: Sentence finding logic might fail on complex text
- **Mitigation**: Test with quotes containing special chars, newlines, etc.
- **Rollback**: Revert to chunk offsets

---

## Timeline

Assuming each fix takes ~1-2 hours including testing:

1. **Phase 4a** (2 hours): Negation deduplication
   - Implement + test
   - Verify metrics
   
2. **Phase 4b** (2 hours): Sentence-level offsets
   - Refactor extraction
   - Update tests
   - Verify metrics

3. **Phase 4c** (4 hours): Expanded test coverage
   - Add 10+ new tests
   - Benchmark real-world docs
   - Document performance

**Total Phase 4**: ~8 hours before chat layer

---

## What NOT to Do

❌ Don't touch the chat layer yet  
❌ Don't change invariants  
❌ Don't skip regression testing  
❌ Don't modify canonical baseline (only regenerate)  
❌ Don't merge code until all tests pass  

---

## Next Steps

1. **Confirm this plan** with you
2. **Implement Fix #1** (negation deduplication)
3. **Validate with regression tests**
4. **Implement Fix #2** (sentence offsets)
5. **Validate with regression tests**
6. **Document Phase 4 completion**
7. **Then discuss chat layer architecture**

Ready to start with Fix #1?
