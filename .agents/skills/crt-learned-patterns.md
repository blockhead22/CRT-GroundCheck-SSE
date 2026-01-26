# CRT Memory System - Learned Patterns Knowledge Base

This document captures reusable patterns learned from development sessions.

## Pattern Categories

### 1. Contradiction Handling

**Common Patterns:**
- Always check ledger state before asserting facts
- Use `contradiction_detected` flag in responses
- Implement caveat disclosure when conflicts exist
- Trust scores decay on contradiction, boost on confirmation

**Edge Cases:**
- Temporal contradictions (8 years vs 10 years since college)
- Semantic equivalence (Seattle vs Bellevue)
- Upgrades vs changes (Senior → Principal)

### 2. Trust Score Tuning

**Effective Ranges:**
- Initial trust: 0.7
- Contradiction decay: -0.3 to -0.4
- Confirmation boost: +0.1 to +0.2
- Variance sweet spot: 0.3-0.4 for healthy signal

**Debugging Trust Issues:**
- Log trust before/after each operation
- Track trust_weighted retrieval scores
- Verify decay applied to contradicted claims

### 3. GroundCheck Verification

**Invariant Patterns:**
- Reintroduction invariant: All contradicted claims must be flagged
- No bare assertions of contradicted facts
- Caveats required: "changed from X", "previously Y"

**Common Failures:**
- Missing disclosure on recall questions
- Stale contradiction flags after resolution
- Assertion without caveat

### 4. Fact Extraction

**Reliable Patterns:**
- Name extraction: First occurrence in greeting
- Slot-based facts: employer, location, title
- Temporal facts: years_of_experience, college_year

**Tricky Cases:**
- Compound facts (both undergrad AND masters)
- Implicit contradictions (preference reversals)
- Context-dependent extraction

### 5. Memory Operations

**Best Practices:**
- Close API server before DB cleanup
- Use `ignore_errors=True` for Windows file locks
- Implement `onerror` callbacks for permission issues
- Database paths: thread-specific or shared

### 6. Debugging Techniques

**Effective Approaches:**
- Add `print()` at state transitions
- Check database with SQL directly
- Verify embedding retrieval with manual query
- Trace trust score calculations step-by-step

**Common Bug Patterns:**
- SQLite file locks on Windows
- Embedding dimension mismatches
- Trust score not propagating
- Contradiction ledger out of sync

---

## Session-Specific Learnings

_Auto-populated from analyzed sessions_

### Session: 20260126_011855
**Type:** Windows File Permission Handling
- **Pattern:** Use `os.chmod(path, stat.S_IWRITE)` before deletion
- **Context:** PermissionError on `shutil.rmtree`
- **Solution:** Add `onerror` callback with permission reset + retry

---

## To Add New Patterns

Run after significant sessions:
```powershell
.\tools\review_learned_skills.ps1 -Approve -SessionId YYYYMMDD_HHMMSS
```

Or from stress tests:
```bash
python tools/analyze_stress_test_session.py artifacts/crt_stress_run.TIMESTAMP.jsonl
```
