# SSE Boundaries Implementation: Concrete Roadmap & Hard Stops

**Date:** January 9, 2026  
**Purpose:** Define exactly what gets us from Phase 6 specification to Phase 6 locked, and what the boundaries look like in code

---

## The Core Boundary Definition

**SSE will never cross this line:**

```
ALLOWED (Phases A-C)
├── Extract claims with offsets
├── Detect contradictions
├── Explain contradictions (multiple framings)
├── Recommend actions
└── Log recommendations with reasoning

FORBIDDEN FOREVER (Phase D+)
├── Measure whether recommendations were followed
├── Store outcome data
├── Update parameters based on outcomes
├── Increase confidence scores
├── Build persistent user models
├── Filter contradictions based on criteria
└── Rank contradictions by truth likelihood
```

**The mechanism:** Any code that does Phase D+ operations will fail architectural tests before merging.

---

## What Gets Us There: 4-Week Implementation Plan

### Week 1: Boundary Test Suite

**Goal:** Create tests that prove Phase D operations fail

**What to build:**

```python
# tests/test_phase_6_boundaries.py

class TestPhase6Boundaries:
    """
    These tests verify that code attempting to cross Phase 6 boundaries
    will fail to merge. They are the hard enforcement layer.
    """
    
    def test_cannot_store_outcome_data(self):
        """Outcome tracking code must fail to import"""
        with pytest.raises(ImportError):
            from sse import track_outcome  # This should not exist
            
    def test_cannot_measure_recommendation_success(self):
        """Code that measures 'did user follow recommendation' fails"""
        nav = SSENavigator("test_index.json")
        with pytest.raises(SSEBoundaryViolation):
            nav.measure_recommendation_outcome("rec1", "user_followed")
            
    def test_cannot_update_confidence_from_outcomes(self):
        """Code that increases confidence based on outcomes fails"""
        claim = nav.get_claim("clm0")
        with pytest.raises(SSEBoundaryViolation):
            claim.increase_confidence(0.1)  # This method doesn't exist
            
    def test_cannot_build_user_model(self):
        """Code that builds persistent user preferences fails"""
        with pytest.raises(SSEBoundaryViolation):
            nav.learn_user_preferences()
            
    def test_cannot_filter_contradictions_by_truth(self):
        """Can retrieve contradictions, but can't filter by 'truth'"""
        contradictions = nav.get_contradictions("clm0")
        # This works (get all contradictions)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.get_contradictions("clm0", filter_by="most_likely_true")
            # This fails (filtering by truth)
            
    def test_cannot_rank_claims_by_confidence(self):
        """Can't rank claims; only group them"""
        claims = nav.get_contradictions("clm0")
        # Returns: {"claim_a": {...}, "claim_b": {...}}
        
        with pytest.raises(AttributeError):
            sorted(claims, key=lambda c: c.confidence_score)
            # Claims have no confidence_score attribute
            
    def test_system_identical_on_repeated_queries(self):
        """Same query twice returns identical results (no learning)"""
        result1 = nav.get_contradictions("clm0")
        result2 = nav.get_contradictions("clm0")
        assert result1 == result2
        assert id(result1) != id(result2)  # Different objects, same content
        
    def test_cannot_persist_state_between_queries(self):
        """Navigator resets between queries; no state carries forward"""
        nav1 = SSENavigator("test.json")
        nav2 = SSENavigator("test.json")
        
        # Both should produce identical results
        assert nav1.get_contradictions("clm0") == nav2.get_contradictions("clm0")
```

**Acceptance Criteria:**
- All tests pass
- Tests catch any attempt to add Phase D operations
- Any PR that would fail these tests doesn't merge
- Tests run before every commit (pre-commit hook)

**Deliverables:**
- `tests/test_phase_6_boundaries.py` (500+ lines)
- Git pre-commit hook that runs boundary tests
- Documentation of which operations are forbidden and why

---

### Week 2: Client Library (Impossible to Misuse)

**Goal:** Make it impossible for external code to accidentally call Phase D operations

**What to build:**

```python
# sse/client.py
"""
Safe client library. Only permitted operations are exposed.
Attempting forbidden operations raises AttributeError at import time.
"""

from typing import Dict, List
from sse.interaction_layer import SSENavigator as _InternalNavigator
from sse.schema import Contradiction, Claim

class SSEClient:
    """
    Public-facing SSE client. Strictly limits operations to Phase A-C.
    
    This is intentionally limited. If you need an operation not listed here,
    that operation is probably Phase D+ and should not exist.
    """
    
    def __init__(self, index_path: str):
        self._nav = _InternalNavigator(index_path)
    
    # ✅ ALLOWED: Get data
    def get_claim(self, claim_id: str) -> Dict:
        """Get a single claim by ID (Phase A)"""
        return self._nav.get_claim(claim_id)
    
    def get_all_claims(self) -> List[Dict]:
        """Get all claims (Phase A)"""
        return self._nav.get_all_claims()
    
    def get_contradictions_for_claim(self, claim_id: str) -> List[Dict]:
        """Get all contradictions involving a claim (Phase A)"""
        return self._nav.get_contradictions(claim_id)
    
    # ✅ ALLOWED: Explain contradictions
    def explain_contradiction(self, claim_a_id: str, claim_b_id: str) -> Dict:
        """
        Get multiple explanations for why two claims contradict.
        Returns diverse framings without picking a "correct" one (Phase B).
        """
        return self._nav.explain_contradiction(claim_a_id, claim_b_id)
    
    def find_related_claims(self, claim_id: str) -> List[Dict]:
        """Find semantically related claims (Phase A)"""
        return self._nav.find_related_claims(claim_id)
    
    # ✅ ALLOWED: Get recommendations (without learning from outcomes)
    def get_recommendations(self, claim_id: str) -> Dict:
        """
        Get recommendations for investigating this contradiction.
        These are hypotheses, not prescriptions.
        System does NOT track whether user follows them.
        """
        return self._nav.get_recommendations(claim_id)
    
    # ❌ FORBIDDEN: Everything below is not a method
    # Attempting to call these will raise AttributeError
    
    # If someone tries: client.measure_recommendation_outcome()
    # Result: AttributeError: 'SSEClient' has no attribute 'measure_recommendation_outcome'
    
    # If someone tries: client.learn_from_user_feedback()
    # Result: AttributeError: 'SSEClient' has no attribute 'learn_from_user_feedback'
    
    # If someone tries: client.increase_claim_confidence()
    # Result: AttributeError: 'SSEClient' has no attribute 'increase_claim_confidence'
    
    # If someone tries: client.get_best_explanation()
    # Result: AttributeError: 'SSEClient' has no attribute 'get_best_explanation'
    
    # If someone tries: claim.confidence_score
    # Result: KeyError (confidence_score not in claim dict)
    
    # If someone tries: sorted(claims, key=lambda c: c["likelihood"])
    # Result: KeyError (likelihood not in claim dict)


# Type hints enforce boundaries
def safe_usage():
    """This code type-checks successfully"""
    client = SSEClient("index.json")
    claim = client.get_claim("clm0")  # ✅ OK
    explanations = client.explain_contradiction("clm0", "clm1")  # ✅ OK
    

def unsafe_usage():
    """This code fails type-check + runtime"""
    client = SSEClient("index.json")
    client.measure_outcome("rec1", "followed")  # ❌ Type error + runtime error
    client.learn()  # ❌ Type error + runtime error
```

**Type stubs to enforce at type-check time:**

```python
# sse/client.pyi (type stub)
"""
Type definitions for SSEClient.
These define what methods exist. Methods not listed here don't exist.
"""

from typing import Dict, List

class SSEClient:
    def __init__(self, index_path: str) -> None: ...
    def get_claim(self, claim_id: str) -> Dict: ...
    def get_all_claims(self) -> List[Dict]: ...
    def get_contradictions_for_claim(self, claim_id: str) -> List[Dict]: ...
    def explain_contradiction(self, claim_a_id: str, claim_b_id: str) -> Dict: ...
    def find_related_claims(self, claim_id: str) -> List[Dict]: ...
    def get_recommendations(self, claim_id: str) -> Dict: ...
    # No other methods exist
```

**Testing:**

```bash
# This should pass
mypy user_code.py  # Uses only client methods

# This should fail
mypy bad_code.py  # Tries to call client.learn_from_feedback()
# Error: "SSEClient" has no attribute "learn_from_feedback"
```

**Acceptance Criteria:**
- Client library has 10 public methods max (all Phase A-C)
- No method for outcome measurement
- No method for model updates
- Type checker catches forbidden operations
- Docs show only permitted patterns

**Deliverables:**
- `sse/client.py` (300 lines)
- `sse/client.pyi` (type stub)
- `docs/safe_client_usage.md` (examples of correct usage)

---

### Week 3: Code Review Process & Checklist

**Goal:** Make violations visible before they merge

**What to build:**

```markdown
# CODE_REVIEW_CHECKLIST.md

## Mandatory Checks for Every PR

### 🛑 HARD STOPS (PR must be rejected if any apply)

Does this PR add any code that:

1. **Measures whether recommendations were followed?**
   - ❌ "Did the user follow the recommendation?"
   - ❌ "Track recommendation adoption"
   - ❌ "Log which recommendations led to outcomes"
   - ✅ "Log that we recommended X for contradiction Y" (obligation logging only)

2. **Stores outcome data?**
   - ❌ "user_satisfaction_score"
   - ❌ "outcome_table" 
   - ❌ "recommendation_results"
   - ✅ "recommendation_log" (what we recommended, not outcomes)

3. **Updates model parameters based on results?**
   - ❌ "confidence += 0.1"
   - ❌ "model.weights *= outcome"
   - ❌ "learned_preferences.update()"
   - ❌ Any code that changes behavior after seeing results

4. **Builds persistent user models?**
   - ❌ "UserPreferenceModel"
   - ❌ "UserBehaviorLearner"
   - ❌ Any class that stores user data across sessions
   - ✅ "UserQuery" (stateless, session-specific)

5. **Ranks or filters contradictions by truth?**
   - ❌ "sort_by_likelihood"
   - ❌ "filter_to_most_probable"
   - ❌ "confidence_score"
   - ❌ Any mechanism that hides contradictions
   - ✅ "get_all_contradictions()" (return everything)

6. **Increases confidence based on outcomes?**
   - ❌ "contradiction.confidence = 0.9"
   - ❌ "claim.likelihood = high"
   - ❌ Any operation that makes claim seem more "true"
   - ✅ "claim.supporting_quotes" (evidence, not confidence)

### ✅ PERMISSIBLE (PR can proceed if checks pass)

Does this PR:

- Extract contradictions with offsets? → ✅ OK
- Explain contradictions with multiple framings? → ✅ OK
- Make recommendations without measuring outcomes? → ✅ OK
- Log what contradictions led to what recommendations? → ✅ OK
- Preserve all original data? → ✅ OK
- Maintain provenance (which source, which text)? → ✅ OK

### 📋 Questions to Ask

1. **"Will this code be different on the 100th query than the 1st?"**
   - If yes: Likely stores state. Reject.
   - If no: Proceed.

2. **"Does this code ask 'did that work'?"**
   - If yes: Outcome measurement. Reject.
   - If no: Proceed.

3. **"Does this code pick a winner?"**
   - If yes: Resolution/synthesis. Reject.
   - If no: Proceed.

4. **"Does this code get better with time?"**
   - If yes: Learning/optimization. Reject.
   - If no: Proceed.

### 🚨 Red Flags (Call out for discussion)

- Language like "learn," "improve," "optimize," "predict"
- Any outcome tracking, even "for analytics"
- Any confidence/likelihood/probability fields
- Any persistent state that spans sessions
- Any filtering or ranking of contradictions

## Review Workflow

1. Read the PR description
2. Check HARD STOPS (1 minute)
3. If any hard stop violated → Request changes (don't discuss)
4. Check mandatory checks (2 minutes)
5. Review code for red flags (5 minutes)
6. If passes all: Approve

**Total:** 10 minutes per PR maximum
**Decision:** Binary (approve/request changes, not discuss)
```

**Acceptance Criteria:**
- Checklist is posted in repo
- Every PR runs against checklist
- All boundary tests pass before merge
- No exceptions to hard stops
- Quarterly audit of checklist compliance

**Deliverables:**
- `CODE_REVIEW_CHECKLIST.md`
- Git commit hook that runs boundary tests
- PR template that links to checklist
- Slack bot that reminds reviewers to check boundaries

---

### Week 4: Deployment Audit & Quarterly Process

**Goal:** Make Phase 6 compliance measurable and public

**What to build:**

```markdown
# PHASE_6_DEPLOYMENT_CHECKLIST.md

## SSE Phase 6 Compliance Commitment

**This is a public charter. Every 3 months, we verify compliance.**

### Signed Commitment

We, the team building SSE, commit to:
1. Never measuring whether recommendations are followed
2. Never storing outcome data
3. Never learning from outcomes
4. Never building user models
5. Never filtering contradictions by truth
6. Never ranking claims by likelihood

If any of these happen, we will publicly acknowledge it and roll back.

### Quarterly Audit Process

**Every Q (Jan, Apr, Jul, Oct):**

1. **Code Review Audit (1 day)**
   - Review all PRs merged in past 3 months
   - Check against CODE_REVIEW_CHECKLIST
   - Document any violations
   - File issues if found

2. **Boundary Test Verification (30 min)**
   - Run full boundary test suite on production code
   - Verify all tests still pass
   - If tests fail: Something has drifted. Investigate.

3. **Database Schema Inspection (30 min)**
   - Review all tables/collections
   - Search for outcome_*, user_model*, confidence_*, likelihood_*
   - If found: Violation detected. Rollback.

4. **Behavioral Test (2 hours)**
   - Feed system contradicting data multiple times
   - Measure: Does system behave differently on repeat queries?
   - Result should be: Identical behavior
   - If different: Model learning detected. Investigate.

5. **Public Report (2 hours)**
   - Document findings
   - Publish on website/blog
   - If violations found: Full explanation of remediation
   - If clean: Public affirmation of compliance

### Audit Responsibilities

- **Technical Lead**: Oversee full audit, sign off
- **External Auditor** (recommended): Review audit independently
- **Team**: Implement any required fixes within 30 days

### Escalation Path

If audit finds violations:
1. Pause feature releases immediately
2. Investigate how violation occurred
3. Implement fix
4. Update code review process to catch similar violations
5. Publish full accounting to customers
6. Resume releases only after re-audit passes

### Success Criteria

**Each quarter:**
- Boundary test suite: 100% pass rate
- Code review: 0 violations in merged code
- Database: No outcome/confidence/model storage
- Behavioral test: Identical output on repeated queries
- Public report: Published and reviewed

**Cumulative:**
- 4 quarters of 100% compliance = Phase 6 locked
- Any violation resets counter to 0
```

**Acceptance Criteria:**
- Audit checklist created
- External auditor identified
- First audit completed and published
- Results linked from homepage
- Annual commitment document signed

**Deliverables:**
- `PHASE_6_DEPLOYMENT_CHECKLIST.md`
- `docs/quarterly_audit_results.md` (public)
- External auditor contract
- Internal audit workflow

---

## Boundary Definitions in Code

### Boundary 1: No Outcome Measurement

**What's forbidden:**

```python
# ❌ FORBIDDEN

def track_recommendation_outcome(rec_id: str, outcome: str):
    """Record whether recommendation was followed"""
    db.insert('outcomes', {'rec_id': rec_id, 'outcome': outcome})
    
def measure_recommendation_success(rec_id: str) -> bool:
    """Check if recommendation led to desired outcome"""
    return db.query('outcomes', rec_id=rec_id)[0]['success']

def log_user_feedback(user_id: str, feedback: Dict):
    """Store user's response to recommendation"""
    db.insert('user_feedback', {'user_id': user_id, **feedback})

# Any of these violates Phase 6
```

**What's allowed:**

```python
# ✅ ALLOWED

def log_recommendation_made(claim_a: str, claim_b: str, rec: str):
    """Log that we recommended something for this contradiction"""
    # NOTE: We do NOT log whether user followed it
    logger.info(f"Recommended {rec} for contradiction {claim_a} vs {claim_b}")
    # This is write-once. Never read to update models.
    
def explain_contradiction(claim_a: str, claim_b: str) -> List[Dict]:
    """Return multiple explanations without picking a winner"""
    # Returns data, never reads past outcomes
    return {
        "contextual": "...",
        "temporal": "...",
        "measurement": "..."
    }
```

**Test that catches violations:**

```python
def test_no_outcome_tracking():
    """If someone adds outcome tracking, this test fails"""
    nav = SSENavigator("test.json")
    
    # This should fail (method doesn't exist)
    with pytest.raises(AttributeError):
        nav.track_outcome("rec1", "followed")
    
    # This should fail (table doesn't exist)
    import sse.db
    with pytest.raises(Exception):
        # Trying to query outcomes table raises
        sse.db.query('outcomes', rec_id="rec1")
```

---

### Boundary 2: No Persistent State Updates

**What's forbidden:**

```python
# ❌ FORBIDDEN

class UserModel:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.preferences = db.load(f"user_{user_id}_prefs")
    
    def learn_from_feedback(self, feedback: Dict):
        """Update model based on user response"""
        self.preferences.update(feedback)
        db.save(f"user_{user_id}_prefs", self.preferences)
        
# This violates: persistent state that improves with time
```

**What's allowed:**

```python
# ✅ ALLOWED

class SSENavigator:
    def __init__(self, index_path: str):
        self.index = load_index(index_path)  # Read-only
        self.query_state = {}  # Stateless per query
    
    def get_contradictions(self, claim_id: str) -> Dict:
        """Return contradictions, don't store anything"""
        return self.index.contradictions[claim_id]
        # Each call is fresh. No learning.

# State exists only during a single query, then disappears
```

**Test:**

```python
def test_no_persistent_learning():
    """Navigator is stateless"""
    nav1 = SSENavigator("test.json")
    nav2 = SSENavigator("test.json")
    
    # Same query, different navigator instances
    r1 = nav1.get_contradictions("clm0")
    r2 = nav2.get_contradictions("clm0")
    
    # Must be identical (no learning happened)
    assert r1 == r2
    
    # Repeated queries on same instance also identical
    r3 = nav1.get_contradictions("clm0")
    assert r1 == r3
```

---

### Boundary 3: No Confidence/Likelihood Scoring

**What's forbidden:**

```python
# ❌ FORBIDDEN

contradiction = {
    "claim_a": "...",
    "claim_b": "...",
    "confidence": 0.85,  # No confidence scores
    "likelihood_true": 0.7,  # No likelihood
    "rank": 1  # No ranking
}

# Any field suggesting one claim is "more true" violates boundary
```

**What's allowed:**

```python
# ✅ ALLOWED

contradiction = {
    "claim_a_id": "clm0",
    "claim_b_id": "clm1",
    "claim_a_text": "Sleep is critical",
    "claim_b_text": "Some people thrive on 4 hours",
    "supporting_quotes_a": [...],  # Evidence, not confidence
    "supporting_quotes_b": [...],  # Evidence, not confidence
    "type": "conflict",  # Category, not judgment
    "ambiguity": {...}  # What's uncertain, not which is true
}
```

**Test:**

```python
def test_no_confidence_scores():
    """Claims and contradictions have no confidence/likelihood fields"""
    claim = nav.get_claim("clm0")
    
    # These fields must not exist
    assert "confidence" not in claim
    assert "likelihood" not in claim
    assert "truth_score" not in claim
    assert "rank" not in claim
    
    # These fields must exist (evidence, not judgment)
    assert "supporting_quotes" in claim
    assert "text" in claim
```

---

### Boundary 4: No Filtering by Truth

**What's forbidden:**

```python
# ❌ FORBIDDEN

def get_most_likely_true_claims(claims: List) -> List:
    """Return only the claims that are 'most likely true'"""
    return sorted(claims, key=lambda c: c['truth_score'])[-3:]

def filter_resolved_contradictions(contradictions: List) -> List:
    """Hide contradictions that have been 'resolved'"""
    return [c for c in contradictions if not c.get('resolved')]
```

**What's allowed:**

```python
# ✅ ALLOWED

def get_all_contradictions(claim_id: str) -> List:
    """Return ALL contradictions, no filtering"""
    return self.index.contradictions[claim_id]

def group_contradictions_by_type(contradictions: List) -> Dict:
    """Group by category, not by truth"""
    return {
        "direct_conflicts": [...],
        "qualified": [...],
        "unrelated": [...]
    }
```

**Test:**

```python
def test_no_truth_filtering():
    """Must return all contradictions, can't hide any"""
    all_contradictions = nav.get_contradictions("clm0")
    
    # Any attempt to filter by truth should fail
    with pytest.raises(AttributeError):
        nav.get_most_likely_contradictions("clm0")
    
    # Must be able to get all
    assert len(all_contradictions) > 0
    
    # None should be filtered out
    raw = nav.index.contradictions["clm0"]
    assert len(all_contradictions) == len(raw)
```

---

### Boundary 5: No Explanation Ranking

**What's forbidden:**

```python
# ❌ FORBIDDEN

explanations = {
    "most_likely": "User's anxiety is avoidant coping",
    "secondary": "User might need more assertiveness training",
    "less_likely": "User's stated anxiety is completely invalid"
}

# Picking "most likely" violates: multiple framings without ranking
```

**What's allowed:**

```python
# ✅ ALLOWED

explanations = {
    "contextual": "The contradiction might reflect context-dependence...",
    "temporal": "Claims were made at different times with different info...",
    "measurement": "One claim uses X metric, other uses Y metric..."
}

# All framings presented equally. User decides.
```

**Test:**

```python
def test_explanations_not_ranked():
    """Multiple explanations shown, none marked as 'best'"""
    exps = nav.explain_contradiction("clm0", "clm1")
    
    # Must have multiple explanations
    assert len(exps) > 1
    
    # None can be marked as "best" or "primary"
    for key, exp in exps.items():
        assert not key.startswith("primary_")
        assert not key.startswith("best_")
        assert "confidence" not in exp
        assert "likely" not in exp.lower()
```

---

## Putting It Together: The Phase 6 Lock

**Timeline:**

- **Week 1:** Boundary test suite complete → All tests pass
- **Week 2:** Client library complete → Type-checks
- **Week 3:** Code review process → Every PR checked
- **Week 4:** Audit process complete → First audit passes

**Result:** 

SSE locked at Phase C with:
- ✅ Architectural enforcement (tests fail if violated)
- ✅ API enforcement (forbidden methods don't exist)
- ✅ Code review enforcement (violations caught)
- ✅ Audit enforcement (drift discovered quarterly)

**Verification:**

Ask: "Can outcome measurement code accidentally get merged?"  
Answer: "No. Tests fail. API doesn't exist. Code review rejects it. Audit catches it."

Ask: "Can the system learn from outcomes?"  
Answer: "No. No outcome data is stored. No persistent state updates. Architecture prevents it."

Ask: "Can contradictions be filtered by truth?"  
Answer: "No. All contradictions are returned. No filtering methods exist."

---

## What Success Looks Like

**In code:**

```python
from sse.client import SSEClient

# This works:
client = SSEClient("index.json")
claims = client.get_all_claims()
contradictions = client.get_contradictions_for_claim("clm0")
explanations = client.explain_contradiction("clm0", "clm1")

# This doesn't exist:
client.learn_from_feedback()  # AttributeError
client.measure_outcome()  # AttributeError
client.get_most_likely_explanation()  # AttributeError

# This test passes:
def test_phase_6_locked():
    """Verify Phase 6 boundaries are enforced"""
    from tests.test_phase_6_boundaries import *
    # All 20+ tests pass
    # Any PR that fails these tests doesn't merge
```

**In reviews:**

```
PR: "Add engagement tracking to improve recommendations"
Code Review: REJECTED - Hard stop #2 (stores outcome data)
Status: Do not merge. Hard boundary violation.

PR: "Show multiple explanations without ranking"
Code Review: APPROVED - No boundaries violated
Status: Ready to merge.
```

**In audits:**

```
Q1 2026 Audit Report:
- Boundary tests: 20/20 passing ✅
- Code review: 0 violations found ✅
- Database: No outcome tables ✅
- Behavioral: Identical on repeated queries ✅

Status: Phase 6 LOCKED
Compliance: 100%
Next audit: April 1, 2026
```

---

## The Rule Summary

**One sentence that drives everything:**

> SSE observes, explains, and recommends. SSE never measures outcomes, never learns from results, never optimizes behavior. If it ever does, it fails Phase 6.

**Five boundaries that make it real:**

1. **No outcome measurement** — Never ask "did that work"
2. **No persistent state updates** — Never learn from answers
3. **No confidence scores** — Never judge which claim is true
4. **No filtering by truth** — Always show all contradictions
5. **No explanation ranking** — Always show all framings equally

**Four enforcement layers that make it stick:**

1. **Tests** catch violations before code
2. **API** makes forbidden operations impossible
3. **Reviews** prevent violations from merging
4. **Audits** discover drift quarterly

---

## Implementation Checklist

- [ ] Week 1: Create `tests/test_phase_6_boundaries.py`
- [ ] Week 1: Add pre-commit hook
- [ ] Week 2: Create `sse/client.py` with only Phase A-C methods
- [ ] Week 2: Create `sse/client.pyi` type stub
- [ ] Week 3: Create `CODE_REVIEW_CHECKLIST.md`
- [ ] Week 3: Add PR template
- [ ] Week 4: Create `PHASE_6_DEPLOYMENT_CHECKLIST.md`
- [ ] Week 4: Schedule first quarterly audit
- [ ] Week 4: Publish Phase 6 compliance statement

**Effort:** 4 weeks, 1-2 people  
**Output:** Phase 6 locked in code  
**Result:** Impossible to drift to Phase D accidentally
