# Bug Fix Validation Report

**Date:** 2026-01-22 20:37:38
**Baseline:** 57% (before fixes)
**Target:** 75-85% (after fixes)

---

## Executive Summary

**Overall Success Rate: 52.8%**

Improvement: **-4.2pp** vs baseline

**Verdict: INSUFFICIENT**

---

## Detailed Results

### 1. Contradiction Detection
- **Rate:** 25.0% (5/20 detected)
- **Change:** +5.0pp vs baseline (20%)
- **Status:** ❌ INSUFFICIENT

### 2. Gate Blocking
- **Rate:** 100.0% (4/4 blocked)
- **Change:** +100.0pp vs baseline (0%)
- **Status:** ✅ WORKING

### 3. Resolution Policies
- **Rate:** 33.3%
- **OVERRIDE:** ❌ BROKEN (500 error)
- **PRESERVE:** ✅ WORKING
- **ASK_USER:** ❌ BROKEN (no contradiction created)
- **Status:** ❌ NEEDS WORK

---

## Analysis

### What's Working:
- ✅ **Gate Blocking (100%)** - The system correctly blocks confident answers when contradictions exist
- ✅ **PRESERVE Policy** - Additive facts (skills, interests) are handled correctly

### What Needs Improvement:
- ❌ **Detection Rate (25%)** - Only 5 of 20 contradiction pairs were detected
  - Detected: employer (Microsoft→Amazon), location (Seattle→NY), marital status, introvert/extrovert, handedness
  - Missed: age, coffee preference, pets, diet, language, car ownership, sleep schedule, weather preference, hobbies, allergies
- ❌ **OVERRIDE Policy** - Returns 500 Internal Server Error (likely missing `deprecated` column in some databases)
- ❌ **ASK_USER Test** - No contradiction was created for the test case

---

## Root Cause Analysis

1. **Low Detection Rate**: The ML classifier may not be extracting features correctly, or the model thresholds need tuning. The detected contradictions share patterns (clear factual conflicts about identity attributes).

2. **OVERRIDE 500 Error**: The database migration for adding the `deprecated` column may not have run on the test thread's memory database.

3. **ASK_USER No Contradiction**: The phrases "I prefer remote work" and "I don't like working from home" may not be flagged as contradictory by the classifier (semantic similarity vs explicit contradiction).

---

## Recommendations

1. **Debug Detection Pipeline** - Check ML classifier is being called and features are extracted
2. **Fix OVERRIDE Policy** - Ensure database migrations run before resolution
3. **Review Semantic Similarity** - Contradictions like "prefer remote" vs "don't like working from home" should be detected
4. **Do Not Deploy Yet** - More engineering work needed

---

## Evidence Files

- `retest_detection_results.json` - Detection test details
- `retest_gate_blocking.json` - Gate blocking evidence
- `retest_resolution.json` - Resolution policy test
- `RETEST_SUMMARY.json` - Overall metrics

---

*Generated automatically after bug fix validation*
