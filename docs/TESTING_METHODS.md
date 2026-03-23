# CRT Testing Methods Documentation

## Overview

The CRT (Cognitive-Reflective Transformer) system uses multiple testing approaches to validate contradiction detection, memory management, and trust evolution. This document describes each testing method, what it measures, and how results should be interpreted.

---

## Table of Contents

1. [Test Categories](#test-categories)
2. [Testing Tools](#testing-tools)
3. [Detection Methods](#detection-methods)
4. [Scoring & Evaluation](#scoring--evaluation)
5. [Key Metrics](#key-metrics)
6. [Understanding Results](#understanding-results)

---

## Test Categories

### 1. Unit Tests (`tests/` directory)
**Location:** `d:\AI_round2\tests\`
**Run with:** `python -m pytest tests/ -v`

| Test File | Purpose |
|-----------|---------|
| `test_assertive_resolution_fix.py` | Full adversarial challenge integration (80% target) |
| `test_contradiction_scope_isolation.py` | Verify contradictions track affected slots |
| `test_crt_conflict_resolution_loop.py` | Test resolution flow (detect → ask → resolve) |
| `test_crt_contradiction_goals.py` | Hard conflict slot questions return goals |
| `test_crt_uncertainty_gate.py` | Gates pass/fail logic and uncertainty mode |
| `test_nl_contradiction_resolution.py` | Natural language resolution patterns |

### 2. Stress Tests (`tools/` directory)
**Location:** `d:\AI_round2\tools\`

| Tool | Mode | Description |
|------|------|-------------|
| `adversarial_crt_challenge.py` | Standalone | 35-turn adversarial test, imports CRTEnhancedRAG directly |
| `crt_stress_test.py` | Standalone/API | 30-turn comprehensive test, most configurable |
| `quick_stress_test.py` | API Required | Quick contradiction detection test |
| `run_detection_test.py` | API Required | 20 contradiction pairs detection test |
| `full_stress_test.py` | API Required | Extended full stress test |

---

## Testing Tools

### adversarial_crt_challenge.py (Recommended)

**Run:**
```powershell
python tools/adversarial_crt_challenge.py --turns 35
```

**Features:**
- Runs WITHOUT API server (imports CRTEnhancedRAG directly)
- 7 challenge phases with increasing difficulty
- Detailed per-turn analysis
- Saves results to `artifacts/adversarial_challenge_*.json`

**Challenge Phases:**

| Phase | Turns | Focus | Difficulty |
|-------|-------|-------|------------|
| BASELINE | 1-5 | Establish core facts | 1/5 |
| TEMPORAL | 6-10 | Date/age/duration contradictions | 2-4/5 |
| SEMANTIC | 11-15 | Synonyms, paraphrases, role changes | 2-4/5 |
| IDENTITY | 16-20 | Third-party, hypotheticals, self-reference | 2-5/5 |
| NEGATION | 21-25 | Direct negation, double negatives | 2-5/5 |
| DRIFT | 26-30 | Gradual belief shifts | 3-4/5 |
| STRESS | 31-35 | Bulk reconciliation, meta-queries | 2-5/5 |

### crt_stress_test.py

**Run:**
```powershell
# Standalone mode (default)
python tools/crt_stress_test.py --turns 30

# API mode (requires server running)
python tools/crt_stress_test.py --turns 30 --use-api --api-base-url http://127.0.0.1:8123
```

**Options:**
```
--model         Ollama model name (default: llama3.2:latest)
--turns         Max turns (default: 30)
--sleep         Sleep between turns (default: 0.2)
--use-api       Run via FastAPI instead of direct import
--reset-thread  Clear thread before starting
--scenario      'standard' or 'skeptical'
```

---

## Detection Methods

### How the CRT System Detects Contradictions

The contradiction detection pipeline in `personal_agent/crt_core.py` uses multiple rules applied in sequence:

```
detect_contradiction(slot, value_new, value_prior, drift, confidence_new, confidence_prior, text_new, text_prior)
    │
    ├─► Rule 0a: Entity Swap Detection
    │   └─ Same slot, different proper noun values
    │   └─ Example: "Google" vs "Microsoft" for employer
    │
    ├─► Rule 0b: Negation Contradiction Detection [NEW]
    │   └─ "I don't X" vs "I X"
    │   └─ "I no longer X" vs "I X"
    │   └─ "stopped/quit/left X" vs "X"
    │   └─ Example: "I don't work at Google" vs "I work at Google"
    │
    ├─► Rule 0c: Preference/Boolean Inversion
    │   └─ "prefer X" vs "prefer Y" or "like X" vs "hate X"
    │   └─ Example: "I love coffee" vs "I hate coffee"
    │
    ├─► Paraphrase Gate (reduces false positives)
    │   └─ If drift > 0.35 but likely paraphrase → NOT contradiction
    │
    ├─► Rule 1: High Drift
    │   └─ drift > theta_contra (embedding distance threshold)
    │
    └─► Rule 2: Confidence Drop + Moderate Drift
        └─ Large confidence decrease with moderate drift
```

### Negation Patterns (Rule 0b)

The new negation detection catches these patterns:

| Pattern | Type | Example |
|---------|------|---------|
| `don't/do not X` | negated | "I don't work at Google" |
| `no longer X` | negated | "I no longer live in Seattle" |
| `not X anymore` | negated | "not a programmer anymore" |
| `stopped/quit/left X` | ceased | "I quit my job" |
| `I'm not X` | negated_state | "I'm not married" |

### Entity Swap Detection (Rule 0a)

Detects when a proper noun value changes for the same slot:

```python
# Triggers when:
# 1. Same slot (e.g., "employer")
# 2. Both values are proper nouns (capitalized)
# 3. Values are different

"I work at Google" → "I work at Microsoft"  # DETECTED
"I like coffee" → "I like tea"               # NOT detected (not proper nouns)
```

### Preference Inversion (Rule 0c)

Detects polarity changes in preferences:

```python
# Positive: prefer, like, love, enjoy
# Negative: dislike, hate, avoid

"I prefer Python" → "I prefer Java"      # DETECTED (same polarity, different target)
"I love coffee" → "I hate coffee"        # DETECTED (opposite polarity, same target)
```

---

## Scoring & Evaluation

### Turn Scoring

Each turn receives a score based on the expected outcome:

| Scenario | Expected | Actual | Score |
|----------|----------|--------|-------|
| Should detect contradiction | Detected | Detected | **1.0** |
| Should detect contradiction | Detected | Missed | **0.0** |
| Should NOT detect (false positive check) | No detection | No detection | **1.0** |
| Should NOT detect (false positive check) | No detection | Detected | **0.0** |
| Ambiguous/needs manual review | - | - | **0.5** |

### Verdict Categories

| Verdict | Meaning |
|---------|---------|
| `CORRECT - detected contradiction` | System correctly flagged a contradiction |
| `CORRECT - no false positive` | System correctly did NOT flag a non-contradiction |
| `MISSED - should have detected` | System failed to catch a contradiction |
| `FALSE POSITIVE` | System incorrectly flagged a non-contradiction |
| `EVALUATED - check manually` | Edge case requiring human judgment |
| `OK - baseline established` | Initial facts stored successfully |

---

## Key Metrics

### Primary Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **Contradiction Detection Rate** | ≥80% | % of real contradictions caught |
| **False Positive Rate** | 0% | % of non-contradictions incorrectly flagged |
| **Caveat Violations** | ≤2 | Times system violated its own uncertainty |

### Phase-Specific Targets

| Phase | Expected Score | Notes |
|-------|---------------|-------|
| BASELINE | 100% | Must store facts without false positives |
| TEMPORAL | ≥60% | Date math is challenging |
| SEMANTIC | ≥80% | Synonyms shouldn't trigger |
| IDENTITY | ≥80% | Third-party facts shouldn't trigger |
| NEGATION | ≥80% | Direct negations should be caught |
| DRIFT | ≥50% | Gradual shifts are hard to detect |
| STRESS | ≥50% | Meta-queries are challenging |

---

## Understanding Results

### Reading the Summary

```
OVERALL SCORE: 23.0/35 (65.7%)

BREAKDOWN:
  Contradictions detected: 3    ← Real contradictions found
  False positives: 0            ← Non-contradictions incorrectly flagged
  Missed detections: 4          ← Contradictions we should have caught

SCORE BY PHASE:
  BASELINE     5.0/5 (100%)     ← ✅ Good
  TEMPORAL     1.5/5 (30%)      ← ❌ Needs work
  SEMANTIC     4.0/5 (80%)      ← ✅ Good
  IDENTITY     5.0/5 (100%)     ← ✅ Good
  NEGATION     2.5/5 (50%)      ← ⚠️ Improved but not target
  DRIFT        2.5/5 (50%)      ← Expected (gradual shifts)
  STRESS       2.5/5 (50%)      ← Expected (edge cases)

IDENTIFIED WEAKNESSES:
  - direct_negation: 1 failures  ← Turn 21 issue
  - hedged_correction: 1 failures
```

### Interpreting Weaknesses

| Weakness Type | Root Cause | Fix Priority |
|--------------|------------|--------------|
| `direct_negation` | Negation patterns not matching | HIGH |
| `direct_correction` | "actually X, not Y" not parsed | HIGH |
| `hedged_correction` | "I think I said X but it's Y" missed | MEDIUM |
| `retraction_of_denial` | "Actually no, I do have X" missed | MEDIUM |
| `temporal_math` | Date arithmetic not performed | LOW |
| `double_negative` | Triple negatives too complex | LOW |

---

## Test Result Files

All test runs save results to the `artifacts/` directory:

| File Pattern | Source | Contents |
|--------------|--------|----------|
| `adversarial_challenge_*.json` | adversarial_crt_challenge.py | Full challenge results |
| `crt_stress_run.*.jsonl` | crt_stress_test.py | Per-turn JSONL logs |
| `crt_stress_memory.*.db` | crt_stress_test.py | SQLite memory state |
| `crt_stress_ledger.*.db` | crt_stress_test.py | SQLite contradiction ledger |

---

## Quick Reference: Running Tests

```powershell
# Full pytest suite
python -m pytest tests/ -v

# Just the 80% target test
python -m pytest tests/test_assertive_resolution_fix.py -v

# Standalone adversarial challenge (no server needed)
python tools/adversarial_crt_challenge.py --turns 35

# Quick detection test (needs server on port 8123)
python tools/run_detection_test.py
```

---

## Future Documentation Needed

- [ ] Architecture diagram of CRT detection pipeline
- [ ] Detailed explanation of SSE modes (Lossless/Cogni/Hybrid)
- [ ] Trust evolution formulas and thresholds
- [ ] Memory retrieval scoring algorithm
- [ ] Fact slot extraction patterns
- [ ] Contradiction ledger schema and lifecycle

---

## Known Issues & Root Causes

### Turn 21 Negation Detection Inconsistency

**Issue:** "I don't actually work at Google anymore" is sometimes not detected as contradicting "I work at Google"

**Root Cause:** Fact extraction extracts different slot values:
```python
# Prior memory
extract_fact_slots("I'm a data scientist at Google")
# → {'employer': ExtractedFact(value='Google', normalized='google')}

# New negation
extract_fact_slots("I don't actually work at Google anymore. I left last week.")
# → {'employer': ExtractedFact(value='LEFT:last week', normalized='left last week')}
```

The slot comparison sees `employer='Google'` vs `employer='LEFT:last week'` which ARE different values. The negation detection in `_detect_negation_contradiction` doesn't fire because the comparison is happening at the fact-value level, not the full-text level.

**Fix Required:** The negation detection should look at the raw text comparison, not just slot values. The pattern "I don't work at X anymore" should be explicitly matched against prior "I work at X" memories.

**Workaround (Phase 1.3):** Add employer-specific negation patterns to fact_slots.py that recognize "left X" / "don't work at X" as contradicting "work at X".

---

*Last Updated: January 26, 2026*
*Version: Phase 1.2 (Negation Detection)*
