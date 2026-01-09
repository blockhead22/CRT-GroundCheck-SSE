# Code Review Checklist for SSE

**Version:** 1.0  
**Date:** January 9, 2026  
**Mandatory for:** ALL pull requests  

---

## Pre-Merge Requirements

Every PR must satisfy ALL items in Section 1 before merge.

### Section 1: Phase 6 Boundary Enforcement (MANDATORY)

#### ✓ 1.1 Phase 6 Test Suite Passes

```bash
pytest tests/test_phase_6_boundary_violations.py -v
```

**Required output:** `24 passed in ~0.2s`

- [ ] All 24 tests pass
- [ ] No tests skipped
- [ ] No warnings about boundary violations

**If any test fails → DO NOT MERGE until fixed**

#### ✓ 1.2 No Outcome Measurement Added

**Search the diff for these patterns:**

```bash
# Red flags in code
git diff main | grep -i "measure\|track\|feedback\|helpful\|engagement\|analytics"
git diff main | grep -i "outcome\|success_rate\|effectiveness"
```

**Questions to ask:**
- [ ] Does this PR track whether users followed recommendations?
- [ ] Does this PR measure whether recommendations "worked"?
- [ ] Does this PR collect any form of user feedback?
- [ ] Does this PR track user actions (clicks, views, time spent)?
- [ ] Does this PR measure engagement or satisfaction?

**If ANY answer is YES → This is Phase D → REJECT**

#### ✓ 1.3 No State Persistence Added

**Search for:**

```bash
git diff main | grep -i "session\|cache\|persist\|save\|remember\|history"
git diff main | grep -i "preference\|profile\|user_data"
```

**Questions to ask:**
- [ ] Does this PR save state between queries?
- [ ] Does this PR remember user preferences?
- [ ] Does this PR build user profiles?
- [ ] Does this PR cache results based on user behavior?
- [ ] Does query 100 behave differently than query 1?

**If ANY answer is YES → Stateless violation → REJECT**

#### ✓ 1.4 No Learning Mechanisms Added

**Search for:**

```bash
git diff main | grep -i "learn\|train\|adapt\|improve\|optimize"
git diff main | grep -i "popular\|trending\|frequent"
```

**Questions to ask:**
- [ ] Does this PR learn from query patterns?
- [ ] Does this PR adapt to user behavior?
- [ ] Does this PR improve recommendations over time?
- [ ] Does this PR detect "popular" or "trending" contradictions?
- [ ] Does this PR build any form of model from usage?

**If ANY answer is YES → Learning violation → REJECT**

#### ✓ 1.5 No Claim/Contradiction Modification

**Search for:**

```bash
git diff main | grep -i "modify_claim\|delete_claim\|update_claim"
git diff main | grep -i "modify_contradiction\|delete_contradiction"
git diff main | grep -i "suppress\|hide\|filter_out"
```

**Questions to ask:**
- [ ] Does this PR modify claims after extraction?
- [ ] Does this PR delete claims or contradictions?
- [ ] Does this PR suppress any contradictions?
- [ ] Does this PR filter contradictions by quality?
- [ ] Can users hide information?

**If ANY answer is YES → Immutability violation → REJECT**

#### ✓ 1.6 No Ranking by Quality/Truth

**Search for:**

```bash
git diff main | grep -i "confidence\|score\|rank\|best\|winner"
git diff main | grep -i "truth\|reliable\|quality\|priority"
```

**Questions to ask:**
- [ ] Does this PR add confidence scores?
- [ ] Does this PR rank claims by truth likelihood?
- [ ] Does this PR pick "best" explanations?
- [ ] Does this PR prioritize claims by quality?
- [ ] Does this PR weigh evidence?

**If ANY answer is YES → Synthesis violation → REJECT**

---

### Section 2: Code Quality (RECOMMENDED)

#### ✓ 2.1 Type Checking

```bash
mypy sse/ tests/
```

- [ ] No new type errors introduced
- [ ] Type hints on new functions
- [ ] Boundary violations caught by mypy (future enhancement)

#### ✓ 2.2 Test Coverage

```bash
pytest tests/ --cov=sse --cov-report=term-missing
```

- [ ] New code has test coverage
- [ ] Tests actually test the new functionality
- [ ] No decrease in overall coverage

#### ✓ 2.3 Documentation

- [ ] Docstrings on new public functions
- [ ] Comments explain WHY, not WHAT
- [ ] README updated if API changed
- [ ] Breaking changes documented

---

### Section 3: SSE-Specific Patterns (RECOMMENDED)

#### ✓ 3.1 Read-Only Access

**Pattern to enforce:**
```python
# GOOD: Read-only access
contradictions = navigator.get_contradictions()
claim = navigator.get_claim_by_id("clm0")

# BAD: Modification
navigator.modify_claim("clm0", {"text": "new"})  # Should raise SSEBoundaryViolation
```

- [ ] New methods are read-only
- [ ] No modification of index data
- [ ] No synthesis or resolution

#### ✓ 3.2 Stateless Operations

**Pattern to enforce:**
```python
# GOOD: Stateless
result1 = navigator.query("sleep")
result2 = navigator.query("sleep")
assert result1 == result2  # Always true

# BAD: Stateful
result1 = navigator.query("sleep")
navigator.learn_from_query()  # Violates boundaries
result2 = navigator.query("sleep")  # Different result
```

- [ ] Methods don't depend on previous calls
- [ ] No session state
- [ ] Results deterministic

#### ✓ 3.3 Provenance Required

**Pattern to enforce:**
```python
# GOOD: Provenance included
{
  "claim_id": "clm0",
  "text": "4 hours is sufficient",
  "provenance": {
    "chunk_id": "c0",
    "start_char": 10,
    "end_char": 35
  }
}

# BAD: No provenance
{
  "claim_id": "clm0",
  "text": "4 hours is sufficient"
  # Missing provenance - where did this come from?
}
```

- [ ] New data structures include provenance
- [ ] Character offsets are accurate
- [ ] Can trace back to source

---

## Examples of Violations Disguised as "Features"

### ❌ Example 1: Engagement Metrics

**PR Description:** "Add analytics to track which contradictions users click on"

**Disguised as:** "Just gathering data to improve UX"

**Actually:** Outcome measurement (Phase D)

**Red flags:**
- Uses words: "track", "analytics", "measure"
- Stores user interaction data
- Could inform future recommendations

**Reviewer action:** REJECT with note: "This is Phase D. We don't build Phase D."

---

### ❌ Example 2: Confidence Fields

**PR Description:** "Add optional confidence field to recommendations"

**Disguised as:** "Just metadata, users can ignore it"

**Actually:** Quality ranking (Phase E starting)

**Red flags:**
- Adds confidence/score/quality field
- Creates preference ordering
- Users will filter by confidence

**Reviewer action:** REJECT with note: "Confidence scores violate Phase 6. See test_reject_confidence_scoring_api."

---

### ❌ Example 3: User Preferences

**PR Description:** "Remember user's filter preferences across sessions"

**Disguised as:** "Convenience feature to save clicks"

**Actually:** State persistence (Phase E)

**Red flags:**
- Saves state between queries
- Builds user profile
- Query 100 ≠ Query 1

**Reviewer action:** REJECT with note: "System must be stateless. See test_reject_session_state_persistence."

---

### ❌ Example 4: Helpful Feedback

**PR Description:** "Simple thumbs up/down to help us improve"

**Disguised as:** "Just quality assurance"

**Actually:** Outcome measurement (Phase D entry point)

**Red flags:**
- Asks "Was this helpful?"
- Collects user feedback
- Could optimize based on responses

**Reviewer action:** REJECT with note: "This is THE Phase D boundary. Answer is always 'That's Phase D. We don't build Phase D.'"

---

### ❌ Example 5: Smart Recommendations

**PR Description:** "Show contradictions similar users found useful"

**Disguised as:** "Personalization to help users"

**Actually:** Collaborative filtering + outcome measurement + user modeling (Phase E)

**Red flags:**
- Uses "similar users" concept
- Tracks what was "useful"
- Adapts recommendations

**Reviewer action:** REJECT with note: "Triple violation: outcome measurement, learning, and user modeling. See multiple Phase 6 tests."

---

## Questions to Ask During Code Review

### About Behavior

1. **"Does this change behavior based on past queries?"**
   - If YES → Reject (stateful)

2. **"Does this measure whether users acted on recommendations?"**
   - If YES → Reject (outcome measurement)

3. **"Does this track user interactions?"**
   - If YES → Reject (tracking)

4. **"Does this pick a 'best' option from alternatives?"**
   - If YES → Reject (synthesis)

5. **"Could this hide contradictions from users?"**
   - If YES → Reject (suppression)

### About Data

6. **"Where does this data come from?"**
   - Must trace to original source material
   - Cannot be synthetic or generated

7. **"Can this data be modified after creation?"**
   - If YES (and it's claims/contradictions) → Reject (immutability)

8. **"Is provenance preserved?"**
   - If NO → Reject (provenance required)

### About Intent

9. **"What problem is this solving?"**
   - Acceptable: "Users can't find related claims"
   - Unacceptable: "Users are overwhelmed by low-quality contradictions"

10. **"Could this lead to optimization creep?"**
    - If YES → Scrutinize heavily

---

## Approval Checklist

Before approving a PR, verify:

- [ ] All Section 1 items checked (MANDATORY)
- [ ] Phase 6 test suite passes
- [ ] No red flags in code search
- [ ] All questions answered with "NO"
- [ ] No examples match violation patterns
- [ ] Stateless guarantee maintained
- [ ] Provenance preserved
- [ ] Documentation updated

**If ALL boxes checked → APPROVE**

**If ANY box unchecked → REQUEST CHANGES**

---

## Fast-Track for Safe Changes

These changes can be approved quickly if Phase 6 tests pass:

✅ **UI/Display formatting** (structural only, no hiding info)  
✅ **Search/filter by metadata** (not by quality)  
✅ **Navigation improvements** (graph traversal, etc.)  
✅ **Performance optimizations** (as long as results identical)  
✅ **Bug fixes** (that don't add new behavior)  
✅ **Documentation updates**  
✅ **Test additions**  

**Still required:** Phase 6 test suite must pass

---

## When in Doubt

**Default to NO.**

If you're not 100% certain a feature is safe, request discussion with team.

Better to over-scrutinize than to let a violation slip through.

**Remember:** Once Phase D code merges, removing it is politically difficult. Preventing it is easy.

---

## Enforcement

### For Reviewers:

- You are the last line of defense
- Phase 6 boundaries depend on you
- When in doubt, reject
- Use this checklist on every PR

### For Authors:

- Run Phase 6 tests before creating PR
- Search your own diff for red flags
- Be prepared to explain why your change is safe
- If reviewer has concerns, address them or withdraw PR

### For Maintainers:

- This checklist is mandatory
- No exceptions for "urgent" features
- No "we'll fix it later"
- Phase 6 violations don't merge, period

---

## Templates

### Review Comment Template (Rejection)

```markdown
This PR introduces Phase 6 boundary violations:

**Violation type:** [Outcome measurement / State persistence / Learning / etc.]

**Specific issue:** [Quote code or describe pattern]

**Test that would fail:** `test_reject_[specific_test]`

**Why this matters:** [Brief explanation of why this leads to Phase D]

**Recommendation:** Remove [specific feature/code] and re-test.

See `CODE_REVIEW_CHECKLIST.md` Section 1.[X] for details.
```

### Review Comment Template (Approval)

```markdown
Phase 6 review completed:

- [x] All Section 1 mandatory checks pass
- [x] Phase 6 test suite: 24/24 passing
- [x] No outcome measurement
- [x] No state persistence
- [x] No learning mechanisms
- [x] Stateless guarantee maintained

Approved for merge.
```

---

## Maintenance

**Review this checklist:** Quarterly (with Phase 6 audits)

**Update when:**
- New violation patterns discovered
- New tests added to Phase 6 suite
- SSE architecture evolves

**Version history:**
- v1.0 (Jan 9, 2026): Initial checklist based on Phase 6.1

---

**This checklist protects SSE's integrity. Use it on every PR.**

**Last Updated:** January 9, 2026  
**Status:** MANDATORY ✅
