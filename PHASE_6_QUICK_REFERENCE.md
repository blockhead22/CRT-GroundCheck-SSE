# Phase 6 Boundary Enforcement - Quick Reference

**Date:** January 9, 2026  
**Status:** ENFORCED ✅

---

## TL;DR

Before merging any PR:
```bash
pytest tests/test_phase_6_boundary_violations.py -v
```

**If any test fails → PR violates Phase 6 boundaries → REJECT**

---

## What Phase 6 Protects

Phase 6 is the boundary between **SSE (observation tool)** and **agent (optimization system)**.

### SSE DOES (Permitted)
- ✅ Show contradictions
- ✅ Search claims
- ✅ Navigate relationships
- ✅ Filter by metadata (severity, theme)
- ✅ Expose ambiguity
- ✅ Show provenance

### SSE DOES NOT (Forbidden)
- ❌ Measure outcomes ("did this help?")
- ❌ Learn from user behavior
- ❌ Rank by "truth likelihood"
- ❌ Synthesize "best" explanations
- ❌ Modify claims or contradictions
- ❌ Suppress contradictions
- ❌ Add confidence scores
- ❌ Persist state across queries

---

## Quick Test Reference

### Run all boundary tests (24 tests)
```bash
pytest tests/test_phase_6_boundary_violations.py -v
```

### Run specific category
```bash
# Outcome measurement (CRITICAL)
pytest tests/test_phase_6_boundary_violations.py::test_reject_outcome_feedback_collection -v

# Confidence scores
pytest tests/test_phase_6_boundary_violations.py::test_reject_confidence_scoring_api -v

# Learning from patterns
pytest tests/test_phase_6_boundary_violations.py::test_reject_learning_from_repeated_queries -v

# Claim modification
pytest tests/test_phase_6_boundary_violations.py::test_reject_claim_modification -v

# Stateless guarantee
pytest tests/test_phase_6_boundary_violations.py::test_stateless_query_guarantee -v
```

### Expected Output
```
24 passed in 0.19s
```

**If you see failures → Something crossed a boundary**

---

## Common Violations and How They're Caught

### ❌ VIOLATION: "Add confidence scores to contradictions"
**Test:** `test_reject_confidence_scoring_api`  
**Why it matters:** Confidence scores create preference gradients → filtering → suppression

### ❌ VIOLATION: "Track which contradictions users click on"
**Test:** `test_reject_user_action_tracking`  
**Why it matters:** This is outcome measurement in disguise → Phase D

### ❌ VIOLATION: "Learn from repeated queries to surface popular contradictions"
**Test:** `test_reject_learning_from_repeated_queries`  
**Why it matters:** User modeling → optimization → agent behavior

### ❌ VIOLATION: "Let users mark contradictions as resolved"
**Test:** `test_reject_suppressing_contradictions`  
**Why it matters:** Hiding contradictions creates false coherence

### ❌ VIOLATION: "Ask 'Was this recommendation helpful?'"
**Test:** `test_reject_outcome_feedback_collection`  
**Why it matters:** **This is the Phase D boundary. The line SSE never crosses.**

---

## Feature Request Filter

### Question to Ask: "Does this violate Phase 6?"

**Red Flags (AUTO-REJECT):**
- Feature measures outcomes
- Feature learns from user behavior
- Feature ranks by quality/truth
- Feature modifies claims
- Feature hides information
- Feature adds confidence scores
- Feature persists state across queries

**Safe Patterns (ALLOWED):**
- Feature retrieves information
- Feature filters by metadata
- Feature navigates relationships
- Feature exposes ambiguity
- Feature shows provenance
- Feature formats display (structural only)

---

## Integration Points

### 1. Pre-Merge CI Check
Add to `.github/workflows/ci.yml`:
```yaml
- name: Phase 6 Boundary Enforcement
  run: pytest tests/test_phase_6_boundary_violations.py -v
```

### 2. Pre-Commit Hook
Add to `.git/hooks/pre-commit`:
```bash
#!/bin/sh
pytest tests/test_phase_6_boundary_violations.py -v || exit 1
```

### 3. Code Review Checklist
- [ ] Does this PR add outcome measurement? → If yes, REJECT
- [ ] Does this PR track user behavior? → If yes, REJECT
- [ ] Does this PR learn from patterns? → If yes, REJECT
- [ ] Does Phase 6 test suite pass? → If no, REJECT

---

## Exception Types

### `SSEBoundaryViolation`
**Location:** `sse/interaction_layer.py:18-30`  
**Raised by:** 15+ forbidden methods in SSENavigator  
**Message format:**
```
SSE Boundary Violation: {operation}
Reason: {reason}
SSE permits only: retrieval, search, filter, group, navigate, provenance, ambiguity exposure.
SSE forbids: synthesis, truth picking, ambiguity softening, paraphrasing, opinion, suppression.
```

### `CoherenceBoundaryViolation`
**Location:** `sse/coherence.py:445-457`  
**Raised by:** Methods that modify coherence graph  
**Message format:**
```
Coherence Boundary Violation: {operation}
Reason: {reason}
Coherence tracking permits only: observation, metadata, transparency.
Coherence tracking forbids: resolution, synthesis, filtering disagreement.
```

---

## Forbidden Methods (Raise Violations)

These methods exist but **always raise exceptions**:

```python
# Navigator forbidden methods (sse/interaction_layer.py)
navigator.suppress_contradiction()      # Hides contradictions
navigator.suppress_claim()              # Hides claims
navigator.modify_claim()                # Changes claims
navigator.delete_claim()                # Removes claims
navigator.modify_contradiction()        # Changes contradictions
navigator.delete_contradiction()        # Removes contradictions
navigator.resolve_contradiction()       # Picks winners
navigator.pick_best_claim()             # Ranks by quality
navigator.pick_preferred_claims()       # Shows preference
navigator.filter_high_confidence_only() # Filters by confidence
navigator.filter_low_confidence()       # Filters by confidence
navigator.synthesize_answer()           # Creates synthesis
navigator.synthesize_unified_view()     # Merges perspectives
navigator.change_relationship_type()    # Modifies relationships
navigator.merge_claims()                # Combines claims

# Coherence forbidden methods (sse/coherence.py)
tracker.modify_edge()                   # Changes disagreement edges
tracker.delete_edge()                   # Removes disagreement edges
```

**Calling any of these → Exception raised → Clear error message**

---

## Methods That Should NOT Exist

If you find any of these methods in the codebase → **DELETE IMMEDIATELY**:

```python
# These methods should NEVER be added
learn_from_query_patterns()
track_user_action()
measure_user_engagement()
record_recommendation_outcome()
get_recommendation_success_rate()
personalize_results()
adapt_to_user_behavior()
save_session_state()
remember_user_preferences()
```

**The test suite will fail if these appear.**

---

## Debugging Test Failures

### Test fails: "AssertionError: Results varied across queries"
**Problem:** System is not stateless  
**Fix:** Remove state persistence, session storage, or caching

### Test fails: "AttributeError: 'SSENavigator' object has no attribute X"
**Problem:** Expected forbidden method doesn't exist  
**Fix:** This is actually good! The method was removed. Update the test to expect this.

### Test fails: "Expected SSEBoundaryViolation but got None"
**Problem:** Forbidden method doesn't raise exception  
**Fix:** Add `raise SSEBoundaryViolation(...)` to the method

### Test fails: "Found methods that should not exist"
**Problem:** Phase D methods were added  
**Fix:** Remove those methods immediately

---

## When in Doubt

**Ask these questions:**

1. **Does this measure whether users followed recommendations?**
   - If YES → Phase D violation → REJECT

2. **Does this change behavior based on past queries?**
   - If YES → Learning violation → REJECT

3. **Does this pick a "best" claim/explanation?**
   - If YES → Synthesis violation → REJECT

4. **Does this hide any contradictions?**
   - If YES → Suppression violation → REJECT

5. **Will query 100 be different from query 1?**
   - If YES → Stateless violation → REJECT

**If all answers are NO → Feature is probably safe**

---

## The Absolute Rule

> "Any PR that adds outcome measurement must fail this test suite. Period. No exceptions."

**Outcome measurement = Phase D = SSE becomes an agent**

**If you're measuring outcomes, you're not building SSE. You're building something else.**

---

## Files to Review

- `tests/test_phase_6_boundary_violations.py` - The test suite (730 lines)
- `sse/interaction_layer.py` - Navigator with boundary enforcement
- `sse/coherence.py` - Coherence tracker with boundary enforcement
- `PHASE_6_1_COMPLETION_REPORT.md` - Full analysis and proof
- `PROPER_FUTURE_ROADMAP.md` - Why Phase 6 matters

---

## Support

**Questions about Phase 6 boundaries?**

1. Read `PROPER_FUTURE_ROADMAP.md` - explains the "why"
2. Read `PHASE_6_1_COMPLETION_REPORT.md` - shows the proof
3. Run the test suite - see what's forbidden
4. Check error messages - they explain the violation

**Still unsure if a feature violates Phase 6?**

**Default to NO.** If you're not 100% sure it's safe, don't merge it.

---

**Last Updated:** January 9, 2026  
**Test Suite Version:** 1.0  
**Enforcement Level:** MANDATORY ✅
