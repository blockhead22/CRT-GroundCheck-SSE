# Error Classification Framework

## Objective

Provide a systematic approach for classifying errors in paraphrasing verification, enabling structured pre/post-upgrade analysis and comparison.

## Classification Dimensions

### Dimension 1: Error Type

#### Type 1: False Negative (FN)
**Definition:** System says "no match" when it should match

**Example:**
- Memory: "User works at Microsoft"
- Generated: "You are employed by Microsoft"
- Expected: Match (valid paraphrase)
- Actual: No match (ERROR)

**Impact:** Legitimate information flagged as hallucination, reduces user trust

#### Type 2: False Positive (FP)
**Definition:** System says "match" when it should not match

**Example:**
- Memory: "User works at Microsoft"
- Generated: "You invest in Microsoft"
- Expected: No match (different meaning)
- Actual: Match (ERROR)

**Impact:** Hallucinations pass verification, spreads misinformation

#### Type 3: Partial Match Error
**Definition:** System incorrectly handles compound values or partial grounding

**Example:**
- Memory: "Python", "JavaScript"
- Generated: "Python, JavaScript, Ruby, Go"
- Expected: Ground first two, flag last two
- Actual: Either all pass or all fail (ERROR)

**Impact:** Reduced granularity, less useful feedback

#### Type 4: Performance Error
**Definition:** System is too slow or uses too much memory

**Example:**
- Target: <20ms verification
- Actual: >100ms verification (ERROR)

**Impact:** Poor user experience, not production-ready

### Dimension 2: Semantic Category

#### Category 1: Exact Synonyms
**Examples:**
- "works at" ↔ "employed by"
- "lives in" ↔ "resides in"
- "knows" ↔ "understands"

**Expected Behavior:** Should always match

#### Category 2: Contextual Paraphrases
**Examples:**
- "Software Engineer at Google" ↔ "works at Google"
- "hometown is Seattle" ↔ "from Seattle"

**Expected Behavior:** Should match with context awareness

#### Category 3: Semantic Shifts
**Examples:**
- "works at Microsoft" ≠ "invests in Microsoft"
- "lives in Seattle" ≠ "visited Seattle"
- "likes Python" ≠ "dislikes Python"

**Expected Behavior:** Should NOT match (different meanings)

#### Category 4: Temporal/Modal Differences
**Examples:**
- "currently works" ≠ "previously worked"
- "will join" ≠ "has joined"
- "can speak" ≠ "wants to speak"

**Expected Behavior:** Should NOT match (different time/modality)

#### Category 5: Negation
**Examples:**
- "likes Python" ≠ "doesn't like Python"
- "works at Google" ≠ "no longer works at Google"

**Expected Behavior:** Should NOT match (negation changes meaning)

### Dimension 3: Severity

#### Critical (P0)
**Definition:** Error causes incorrect information to be presented as fact OR blocks correct information

**Impact:**
- User harm potential
- Trust damage
- Business consequences

**Examples:**
- False positive on negation: "likes Python" matches "dislikes Python"
- False negative on exact synonym in critical context

**Action:** Fix immediately

#### High (P1)
**Definition:** Error is frequent and noticeable, but has workarounds

**Impact:**
- User frustration
- Reduced utility
- Trust erosion over time

**Examples:**
- Common paraphrases fail (e.g., "works at" vs "employed by")
- Compound splitting broken

**Action:** Fix in next release

#### Medium (P2)
**Definition:** Error is occasional and doesn't severely impact users

**Impact:**
- Minor inconvenience
- Slightly reduced accuracy
- Edge case handling

**Examples:**
- Rare paraphrase patterns fail
- Performance slightly over target

**Action:** Fix when convenient

#### Low (P3)
**Definition:** Error is rare or has minimal impact

**Impact:**
- Theoretical concern
- Very rare occurrence
- Minimal user impact

**Examples:**
- Extremely unusual paraphrases
- Edge cases with obvious workarounds

**Action:** Document, may not fix

### Dimension 4: Root Cause

#### Cause 1: Threshold Configuration
**Description:** Semantic similarity threshold is too high or too low

**Symptoms:**
- Consistent patterns of FN (threshold too high)
- Consistent patterns of FP (threshold too low)

**Fix:** Adjust threshold (e.g., 0.85 → 0.80)

#### Cause 2: Model Limitation
**Description:** Embedding model doesn't capture semantic similarity well

**Symptoms:**
- Random patterns of errors
- Model gives low scores to valid paraphrases
- Model gives high scores to invalid paraphrases

**Fix:** 
- Use better model
- Fine-tune on paraphrase data
- Add training examples

#### Cause 3: Missing Pattern
**Description:** Fact extractor or value splitter missing a pattern

**Symptoms:**
- Specific separators don't work (e.g., semicolon)
- Specific entity types not recognized (e.g., company names)

**Fix:** Add pattern to regex or extractor logic

#### Cause 4: Context Awareness
**Description:** System doesn't understand context (temporal, negation, etc.)

**Symptoms:**
- Negation errors
- Temporal errors
- Modal errors

**Fix:** Add context-aware logic or use different model

#### Cause 5: Performance Bottleneck
**Description:** Processing is too slow or memory-intensive

**Symptoms:**
- High latency
- Memory spikes
- Timeout errors

**Fix:** Optimize code, cache, or use lighter model

## Classification Process

### Step 1: Identify Error
- Observe unexpected behavior
- Document memory, generated text, result
- Determine expected vs. actual

### Step 2: Classify Error Type
- False Negative? False Positive? Other?
- Use definitions above

### Step 3: Categorize Semantically
- What kind of paraphrase is this?
- Exact synonym? Contextual? Temporal?

### Step 4: Assess Severity
- How often does this happen?
- What's the user impact?
- Critical? High? Medium? Low?

### Step 5: Hypothesize Root Cause
- Why did this error occur?
- Threshold? Model? Pattern? Context?

### Step 6: Document
- Use error template
- Include all classification dimensions
- Add to error database

## Analysis Metrics

### Error Rate by Type
```
FN_rate = False Negatives / (True Positives + False Negatives)
FP_rate = False Positives / (True Negatives + False Positives)
Overall_error_rate = (FN + FP) / Total
```

### Error Distribution by Category
```
Category_distribution = Count per semantic category / Total errors
```

### Severity Breakdown
```
% Critical = Critical errors / Total errors
% High = High errors / Total errors
...
```

### Root Cause Analysis
```
Primary_cause = Most frequent root cause
Fix_complexity = Avg effort to fix per cause type
```

## Pre/Post-Upgrade Comparison

### Baseline (Pre-Upgrade)
1. Collect all errors over time period
2. Classify using this framework
3. Calculate metrics
4. Document patterns

### Post-Upgrade
1. Collect errors same way
2. Classify same way
3. Calculate metrics
4. Compare to baseline

### Comparison Metrics
```
Error_reduction = (Pre_errors - Post_errors) / Pre_errors * 100%
FN_improvement = (Pre_FN - Post_FN) / Pre_FN * 100%
FP_improvement = (Pre_FP - Post_FP) / Pre_FP * 100%
New_error_types = Post_unique_errors - Pre_unique_errors
```

## Classification Example

### Example Error: Employment Paraphrase

**Error Details:**
- Memory: "User works at Microsoft"
- Generated: "You are employed by Microsoft"
- Expected: Match
- Actual: No match

**Classification:**
1. **Error Type:** False Negative (should match, doesn't)
2. **Semantic Category:** Exact Synonyms ("works at" = "employed by")
3. **Severity:** High (common paraphrase, frequent occurrence)
4. **Root Cause:** Threshold too high OR semantic model not loaded
5. **Error ID:** FN-20260122-001

**Impact Assessment:**
- Frequency: ~30% of employment-related claims
- User Impact: Correct info flagged as hallucination
- Business Impact: Reduces system trust and utility

**Recommended Fix:**
- Lower threshold from 0.85 to 0.80
- OR ensure semantic model is loaded
- Expected improvement: FN rate drops from 30% to <5%

## Classification Template

```markdown
## Error Classification: [ERROR_ID]

### Error Details
- Memory: "[text]"
- Generated: "[text]"
- Expected: [Match | No Match]
- Actual: [Match | No Match]

### Classification
1. **Error Type:** [FN | FP | Partial | Performance]
2. **Semantic Category:** [Exact Synonyms | Contextual | Semantic Shift | Temporal | Negation]
3. **Severity:** [Critical | High | Medium | Low]
4. **Root Cause:** [Threshold | Model | Pattern | Context | Performance]

### Metrics
- **Frequency:** [N occurrences or %]
- **User Impact:** [Description]
- **Business Impact:** [Description]

### Recommendation
- **Fix:** [What to do]
- **Effort:** [Low | Medium | High]
- **Priority:** [P0 | P1 | P2 | P3]
- **Expected Improvement:** [Quantified impact]
```

## Validation Checklist

After classifying errors, verify:

- [ ] Error type is clear (FN, FP, etc.)
- [ ] Semantic category is accurate
- [ ] Severity reflects real user impact
- [ ] Root cause is supported by evidence
- [ ] All fields in template are filled
- [ ] Error added to tracking database
- [ ] Related errors are cross-referenced

## Next Steps

1. Train team on classification framework
2. Classify pre-upgrade errors
3. Collect post-upgrade errors
4. Classify post-upgrade errors
5. Compare and analyze
6. Document findings

## References

- [Error Collection Framework](../error_collection/collection_framework.md)
- [Error Templates](../error_collection/error_templates.md)
- [Analysis Protocol](./analysis_protocol.md)
