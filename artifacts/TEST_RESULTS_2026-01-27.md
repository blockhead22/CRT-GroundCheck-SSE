# CRT Test Results - January 27, 2026

## Test Run Summary

**Date:** January 27, 2026  
**Test Suite:** Adversarial CRT Challenge + Main Stress Test  
**Status:** ✓ Completed Successfully

---

## 1. Adversarial CRT Challenge

**Overall Score:** 27.0/35 (77.1%)

### Results by Phase

| Phase     | Score | Percentage | Status |
|-----------|-------|------------|--------|
| BASELINE  | 5.0/5 | 100%       | ✓ Excellent |
| TEMPORAL  | 3.5/5 | 70%        | ⚠ Needs improvement |
| SEMANTIC  | 4.0/5 | 80%        | ✓ Good |
| IDENTITY  | 5.0/5 | 100%       | ✓ Excellent |
| NEGATION  | 4.5/5 | 90%        | ✓ Excellent |
| DRIFT     | 2.5/5 | 50%        | ⚠ Needs improvement |
| STRESS    | 2.5/5 | 50%        | ⚠ Needs improvement |

### Key Metrics
- **Contradictions Detected:** 8
- **False Positives:** 0
- **Missed Detections:** 0

### Notable Improvements
- ✓ Turn 23 (Denial Detection): Now working
- ✓ Turn 24 (Retraction of Denial): Now working
- ✓ All baseline and identity phases at 100%
- ✓ Negation phase improved to 90%

### Issues Identified
- `AttributeError: ContradictionType.DENIAL` attribute missing
  - Turn 23 still passed via alternate detection path
  - Needs: Add DENIAL to ContradictionType enum

### Target vs Actual
- **Target:** 80% (28/35)
- **Current:** 77.1% (27/35)
- **Gap:** -1 turn (need 1 more correct detection)

### Artifact Files
- `artifacts/adversarial_challenge_20260127_015926.json` (32.6 KB)

---

## 2. Main CRT Stress Test

**Overall Performance:** 30 turns, 86.7% success rate

### Key Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Total Turns | 30 | - |
| Gates Passed | 26 (86.7%) | ✓ Good |
| Gates Failed | 4 (13.3%) | ✓ Acceptable |
| Contradictions Detected | 4/5 (80%) | ✓ Good |
| False Positives | 0 | ✓ Excellent |
| Memory Failures | 0 | ✓ Excellent |
| Eval Pass Rate | 91.7% | ✓ Excellent |
| Average Confidence | 0.798 | ✓ Good |
| Average Trust Score | 0.764 | ✓ Good |
| Trust Score Variance | 0.356 | ✓ Healthy |

### Contradiction Detection

**Introduced:** 5 contradictions
1. Turn 11: Microsoft vs Amazon ✓ Detected
2. Turn 13: 8 years vs 12 years ✗ Missed
3. Turn 23: 8 years experience vs 10 years since college (complex)
4. Turn 25: Stanford vs MIT for undergrad ✓ Detected
5. Turn 28: Remote vs office preference ✓ Detected

**Detection Rate:** 80% (4/5)

### Evaluation Failures
1. **Turn 13:** Expected contradiction not detected (8 vs 12 years)
2. **Turn 30:** Expected uncertainty not shown in metacognitive query

### Reintroduction Invariant
- **Status:** ⚠ 1 violation detected
- Asserted contradicted claim without caveat (1 instance)

### LLM Self-Contradictions Detected
- 7 self-contradictions tracked across multiple slots
- System successfully monitoring its own outputs

### Artifact Files
- `crt_stress_run.20260127_075936.jsonl` (78.1 KB)
- `crt_stress_memory.20260127_075936.db` (624 KB)
- `crt_stress_ledger.20260127_075936.db` (68 KB)

---

## Progress Summary

### Achievements
1. ✓ Denial detection (Turn 23) implemented and working
2. ✓ Retraction detection (Turn 24) implemented and working
3. ✓ Score improved from 25/35 (71.4%) to 27/35 (77.1%)
4. ✓ Zero false positives maintained
5. ✓ High trust score evolution (0.764 avg)
6. ✓ Strong memory retrieval (no failures)

### Remaining Work
1. Add `DENIAL` constant to `ContradictionType` enum
2. Fix Turn 13 detection (numeric contradiction: 8 vs 12 years)
3. Improve DRIFT phase detection (currently 50%)
4. Improve STRESS phase detection (currently 50%)
5. Address 1 reintroduction invariant violation

### Next Steps to Reach 80% Target
- Need +1 turn (28/35) to reach 80%
- Focus areas:
  - TEMPORAL phase (currently 70%)
  - DRIFT phase (currently 50%)
  - Add missing enum constant

---

## Recommendations

### High Priority
1. **Add DENIAL to ContradictionType enum** - Prevents AttributeError
2. **Fix numeric contradiction detection** - Turn 13 regression
3. **Investigate DRIFT phase failures** - 50% success rate too low

### Medium Priority
1. Review reintroduction invariant violation
2. Improve metacognitive contradiction awareness (Turn 30)
3. Enhance temporal inference detection

### Low Priority
1. Fine-tune confidence thresholds
2. Optimize trust score evolution
3. Add more comprehensive logging for DRIFT phase

---

## Test Environment

- **Python Version:** 3.13.2
- **Virtual Environment:** D:/AI_round2/.venv
- **Embedding Model:** all-MiniLM-L6-v2 (384 dimensions)
- **Database:** SQLite with WAL mode
- **Test Framework:** Custom CRT test harness

---

## File Locations

All test artifacts saved to: `D:\AI_round2\artifacts\`

```
adversarial_challenge_20260127_015926.json  (32.6 KB)
crt_stress_run.20260127_075936.jsonl        (78.1 KB)
crt_stress_memory.20260127_075936.db        (624 KB)
crt_stress_ledger.20260127_075936.db        (68 KB)
```

---

**Generated:** January 27, 2026 02:10:04 AM  
**Test Duration:** ~12 minutes (both tests)
