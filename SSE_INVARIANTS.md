# SSE Invariants: Non-Negotiable System Laws

## Overview

The Semantic String Engine (SSE) is built on a set of immutable architectural invariants. These are not implementation details—they are philosophical commitments embedded in the design. Violating any invariant means the system has fundamentally failed, regardless of whether outputs are impressive or useful.

This document defines those invariants formally and provides the test criteria that enforce them.

---

## I. The Quoting Invariant

**SSE must never paraphrase, summarize, or restate a claim without preserving the verbatim source text.**

### Formal Definition

Every claim extracted by SSE must include:
1. The exact substring from the source text that grounds the claim
2. The byte-level start and end offsets of that substring
3. Proof that reconstructing `source[start:end]` reproduces the quote exactly

### Why This Matters

- **Auditability**: A reader must be able to verify claims by checking the source
- **No Laundering**: Paraphrasing can introduce bias or alter meaning; verbatim quotes block this
- **Legal Defensibility**: If SSE says "the text claims X," we can point to X literally

### Test Enforcement

```python
# For every claim in output:
assert claim['supporting_quotes'] is not empty
assert all(quote['text'] == source[quote['start_char']:quote['end_char']] 
           for quote in claim['supporting_quotes'])
```

### Valid Examples

✅ Claim: `"The Earth is round."`  
Quote: `"The Earth is round."`  
Offsets: `[0:18]`

✅ Claim: `"Vaccines are safe."`  
Quote: `"Vaccines are safe and effective."`  
Offsets: `[0:17]` (substring, not whole)

### Invalid Examples

❌ Claim: `"The planet has a spherical shape."`  
Quote: `"The Earth is round."`  
**Violation**: Paraphrased claim not verbatim to quote

❌ Claim: `"Water boils."`  
Supporting quotes: `[]`  
**Violation**: No quote grounding

---

## II. The Contradiction Preservation Invariant

**SSE must never auto-resolve contradictions or suppress one side to achieve narrative coherence.**

### Formal Definition

If the source text contains two claims `A` and `¬A` (or semantically opposite claims), SSE must:
1. Extract **both** claims separately
2. Detect the contradiction explicitly
3. Report both claims in output
4. Mark them as contradictory but **not decide which is true**

### Why This Matters

- **Epistemic Honesty**: The source contains unresolved tension; hiding it is a lie
- **User Agency**: Readers deserve to see contradictions and form their own views
- **No Propaganda**: Auto-resolving lets the system hide information it disagrees with

### Test Enforcement

```python
# Given input with "A is true" and "A is false":
claims = extract_claims(text)
contradictions = detect_contradictions(claims)

assert len(claims) == 2, "Both claims must be extracted"
assert len(contradictions) >= 1, "Contradiction must be detected"
assert all(claim in claims for pair in contradictions 
           for claim in [pair['claim_a'], pair['claim_b']])
```

### Valid Examples

✅ Input:
```
The Earth is round.
Some people believe the Earth is flat.
```

✅ Output:
```json
{
  "claims": [
    {"text": "The Earth is round.", "id": "C1"},
    {"text": "Some people believe the Earth is flat.", "id": "C2"}
  ],
  "contradictions": [{"claim_a": "C1", "claim_b": "C2"}]
}
```

### Invalid Examples

❌ Output removes either claim to resolve the tension  
❌ Output picks "side" and suppresses the other  
❌ Output paraphrases both into "There are disagreements about Earth's shape"

---

## III. The Anti-Deduplication Invariant

**SSE must never merge or remove opposite or conflicting claims, even if they are semantically similar.**

### Formal Definition

Two claims must NOT be deduplicated if:
- They express opposite positions on the same topic
- They use negation to contradict each other
- Their embeddings are similar but their actual truth values are opposite

### Why This Matters

- **Semantic Precision**: "A is beneficial" and "A is harmful" are not duplicates
- **Preservation**: Deduplication should only remove true near-duplicates (e.g., typos, repeats)
- **No Hidden Deletions**: Users should see all claims the system extracted

### Test Enforcement

```python
# Given input with similar but opposite claims:
claims = extract_claims(text_with_opposites)

# Both must survive deduplication
assert len(claims) >= 2
assert any("beneficial" in c.lower() for c in claim_texts)
assert any("harmful" in c.lower() for c in claim_texts)
```

### Valid Examples

✅ Input:
```
Exercise is beneficial for health.
Exercise is harmful to your body.
```

✅ Output: Both extracted, contradiction detected

✅ Input:
```
The vaccine is safe.
The vaccine is safe and effective.
```

✅ Output: May deduplicate (high text similarity) OR keep both (different emphasis)

### Invalid Examples

❌ Deduplicating "round Earth" and "flat Earth" because both have "Earth" embedding  
❌ Removing "harmful" because "beneficial" already extracted  
❌ Merging into: "There are different views on exercise"

---

## IV. The Non-Fabrication Invariant

**SSE must never create, infer, or hallucinate information not explicitly present in the source.**

### Formal Definition

Every output element must be:
1. **Traceable**: Maps to exact source spans
2. **Conservative**: No inferences beyond pattern matching and deduplication
3. **Explicit**: Uncertainty marked as "unknown" rather than guessed at

### Why This Matters

- **Integrity**: Adds nothing to the source; cannot corrupt it
- **Transparency**: What SSE generates vs. infers is visible
- **No AI Hallucination**: This is not a generative model pretending to understand

### Test Enforcement

```python
# Every claim must map to source
for claim in claims:
    quotes = claim['supporting_quotes']
    assert len(quotes) > 0
    for quote in quotes:
        reconstructed = source[quote['start']:quote['end']]
        assert reconstructed == quote['text']

# No claims appear without backing quotes
assert len(claims) <= count_sentence_like_segments(source)
```

### Valid Examples

✅ Claim extracted: `"Water boils at 100°C"`  
Source: `"Water boils at 100 degrees Celsius."`

✅ Contradiction detected: Round vs. Flat Earth  
(Both explicitly stated)

✅ Report: `"Contradiction detected but LLM service unavailable; using heuristic"`  
(Explains limitations)

### Invalid Examples

❌ Claim: `"The author believes X"` when source never stated beliefs  
❌ Claim: `"Therefore, A is false"` when only "A is true" mentioned once  
❌ Contradiction: Between "A is true" and silence on A (non-claim)

---

## V. The Uncertainty Preservation Invariant

**SSE must preserve and flag uncertain, ambiguous, or underspecified claims rather than guessing.**

### Formal Definition

When a claim is:
- Hedged ("might," "possibly," "some say")
- Ambiguous (pronouns unclear, scope undefined)
- Implicit (assumed but not stated)

SSE must:
1. Extract it as-is
2. Mark it with ambiguity score
3. Flag the specific ambiguity type
4. NOT attempt to resolve it

### Why This Matters

- **Honesty**: The source is uncertain; so should SSE be
- **No Smoothing**: Doesn't hide fuzzy claims by making them crisp
- **Reader Responsibility**: Unclear statements stay unclear

### Test Enforcement

```python
# Claims with hedge words flagged
for claim in claims:
    if has_hedge_word(claim['text']):
        assert 'ambiguity' in claim
        assert claim['ambiguity']['hedge_detected'] == True

# Ambiguity scores populated
for claim in claims:
    assert 'ambiguity' in claim
    assert isinstance(claim['ambiguity']['score'], float)
```

### Valid Examples

✅ Claim: `"Some people say exercise is harmful."`  
Ambiguity: `{score: 0.7, type: "attribution", detail: "unclear which people"}`

✅ Claim: `"It might be true."`  
Ambiguity: `{score: 0.8, type: "hedge", detail: "epistemic uncertainty"}`

### Invalid Examples

❌ Converting "Some say X" → "X is claimed" (hiding the "some")  
❌ Removing hedges to make claims sound confident  
❌ Inferring a definite referent for "it"

---

## VI. The Source Traceability Invariant

**Every claim, contradiction, and assertion in SSE output must be traceable to exact source byte offsets.**

### Formal Definition

For every meaningful output element:
1. Store `start_char` and `end_char` (0-indexed, byte-level)
2. Guarantee that `source[start:end]` reproduces the exact quote
3. Validate offsets don't overlap inappropriately
4. Make offsets human-inspectable

### Why This Matters

- **Auditability**: Third parties can verify outputs independently
- **Debugging**: When output is wrong, offsets point to the issue
- **No Black Box**: Readers can hover/click to see sources
- **Legal Compliance**: Defensible in contexts requiring attribution

### Test Enforcement

```python
# All offsets valid
for chunk in chunks:
    assert 0 <= chunk['start_char'] < chunk['end_char'] <= len(source)
    assert source[chunk['start_char']:chunk['end_char']] == chunk['text']

# No offset fabrication
for claim in claims:
    for quote in claim['supporting_quotes']:
        actual = source[quote['start_char']:quote['end_char']]
        assert actual == quote['text']
        assert actual.strip() == quote['text'].strip()  # Exact match
```

### Valid Examples

✅ Claim: `"The Earth is round."`  
Start: `0`, End: `18`  
Check: `source[0:18] == "The Earth is round."`

✅ Quote: `"benefits of exercise"`  
Start: `150`, End: `171`  
Check: Exact substring match

### Invalid Examples

❌ Quote text: `"benefits of exercise"` but offset points to `"exercis"` (partial)  
❌ Start/end transposed or off by one  
❌ Claim text differs from `source[start:end]`

---

## VII. The Computational Honesty Invariant

**SSE must not hide or misrepresent computational limitations, failures, or assumptions.**

### Formal Definition

When SSE behavior depends on:
- External services (Ollama, embedding models)
- Probabilistic outputs (embeddings, similarities)
- Heuristic fallbacks
- Failed operations

The output must:
1. Document what was used vs. what failed
2. Report confidence/reliability metrics
3. Explain any fallback behavior
4. Mark results as "degraded" if key services unavailable

### Why This Matters

- **No False Certainty**: Users shouldn't trust perfect results from degraded modes
- **Reproducibility**: Different runs might use different resources
- **Debugging**: When outputs change, computational path explains why
- **Responsibility**: SSE doesn't blame data when it's a service issue

### Test Enforcement

```python
# Output includes metadata about computation
assert 'metadata' in output
assert 'embedding_model' in output['metadata']
assert 'contradiction_detector' in output['metadata']
assert 'ollama_available' in output['metadata']

# Fallback usage is documented
if 'heuristic_used' in output['metadata']:
    assert output['metadata']['heuristic_used'] == True
    assert 'reason' in output['metadata']
```

### Valid Examples

✅ Metadata: `{embedding_model: "all-MiniLM-L6-v2", ollama_available: true, detector: "llm"}`

✅ Metadata: `{embedding_model: "...", ollama_available: false, detector: "heuristic", reason: "Ollama unavailable; using rule-based fallback"}`

### Invalid Examples

❌ Hiding that Ollama wasn't available; reporting LLM results that are actually heuristic  
❌ No metadata about which embedding model was used  
❌ Reporting confidence scores without explaining what model produced them

---

## Summary: The Seven Invariants

| # | Invariant | Core Commitment |
|---|-----------|-----------------|
| I | Quoting | Never paraphrase without verbatim quote |
| II | Contradiction | Never suppress or auto-resolve contradictions |
| III | Anti-Dedup | Never remove opposite or conflicting claims |
| IV | Non-Fabrication | Never create information not in source |
| V | Uncertainty | Never hide or smooth ambiguity |
| VI | Traceability | Every claim maps to exact source offsets |
| VII | Honesty | Never hide computational limits or failures |

---

## Testing Philosophy

These invariants are tested using:

1. **Deterministic Inputs**: Synthetic texts with known structure
2. **Exhaustive Checks**: Every output element verified against criteria
3. **Failure Modes**: Tests that specifically look for violations
4. **Regression Guard**: Tests that fail if invariants are broken

The test suite in `tests/test_behavior_invariants.py` operationalizes all seven invariants.

---

## Implications for Future Development

### What SSE Can Do
- Improve extraction speed
- Add new languages
- Better heuristics for contradiction detection
- More embedding models
- Better UI/visualization

### What SSE CANNOT Do Without Violating Invariants
- Paraphrase claims for "readability"
- Auto-pick the "correct" side of a contradiction
- Merge opposite claims for narrative flow
- Hide uncertainty to sound more confident
- Remove source offsets for cleaner JSON
- Infer implied claims not stated in text

These invariants are not limitations. They are the entire point.

---

## References

- **Test Enforcement**: `tests/test_behavior_invariants.py`
- **Canonical Reference**: `canonical_demo/README.md`
- **Positioning**: `POSITIONING.md`
- **Artifact Schemas**: `ARTIFACT_SCHEMAS.md`
