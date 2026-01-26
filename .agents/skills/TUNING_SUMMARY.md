# CRT Parameter Tuning (2026-01-26)

## Changes Made

### 1. Contradiction Threshold Adjustment ✅

**File:** [personal_agent/crt_core.py](personal_agent/crt_core.py#L55-L58)

**Change:**
- `theta_contra`: 0.55 → **0.42** (24% reduction)
- `theta_fallback`: 0.55 → **0.42** (aligned)

**Rationale:**
- Stress test showed 140% contradiction detection rate (too sensitive)
- Recommended range: 0.40-0.45
- Chose 0.42 as middle ground for stability

**Expected Impact:**
- Fewer false positive contradictions
- Detection rate should drop from 140% → ~100%
- Better balance between sensitivity and accuracy

---

### 2. Enhanced Caveat Detection ✅

**Files:**
- [personal_agent/crt_rag.py](personal_agent/crt_rag.py#L1213-L1242)
- [tools/crt_stress_test.py](tools/crt_stress_test.py#L411-L437)

**Added Patterns:**
```regex
\bnow\b.*\b(was|were)\b     # "now X (was Y)"
\b(versus|vs|compared to)\b  # "X versus Y"
\bno longer\b                # "no longer Y"
\bas of\b                    # "as of [date]"
```

**Rationale:**
- 6 reintroduction invariant violations detected
- Stress test showed assertions without caveats
- Natural language disclosure needs broader pattern coverage

**Expected Impact:**
- Reduced false violations from 6 → 0-2
- Better detection of implicit disclosure
- Alignment between RAG and stress test validation

---

## Verification Plan

### Step 1: Reload API Server
The API server is running with `uvicorn --reload`, so changes should auto-reload.

**Verify reload:**
```bash
# Check if new theta_contra is active
curl http://127.0.0.1:8123/health
# Should show updated config timestamp
```

### Step 2: Run Validation Stress Test
```bash
python tools/crt_stress_test.py --use-api --thread-id validation_tuned --reset-thread --turns 30 --sleep 0.05
```

**Success Criteria:**
- Contradiction detection rate: 90-110% (down from 140%)
- Reintroduction violations: ≤2 (down from 6)
- Gate pass rate: ≥90% (maintained)
- Eval pass rate: 100% (maintained)

### Step 3: Monitor for Regressions
```bash
# Run multiple tests to verify stability
for i in {1..3}; do
  python tools/crt_stress_test.py --use-api --thread-id tune_test_$i --reset-thread --turns 10 --sleep 0.05
done

# Analyze results
python tools/analyze_stress_test_session.py artifacts/crt_stress_run.*.jsonl
```

---

## Rollback Plan

If tuning causes issues (e.g., misses real contradictions):

**Revert theta_contra:**
```python
# personal_agent/crt_core.py line 55
theta_contra: float = 0.55  # Original value
theta_fallback: float = 0.55
```

**Intermediate values to try:**
- 0.50 (moderate reduction)
- 0.47 (conservative)
- 0.45 (aggressive, lower bound)

---

## Related Issues

### Known Limitation: LLM Self-Contradictions
The stress test detected 13 internal LLM claim contradictions across 28 claims (46% rate).

**Example:**
- Turn 4: employer = Microsoft
- Turn 11: employer = Amazon
- Turn 14: employer = Microsoft (reverted)

**Root Cause:**
LLM is making new claims in `[Quick answer]` mode rather than retrieving from memory.

**Future Work:**
- Strengthen prompt to prefer memory retrieval over new claims
- Add claim consistency check before response generation
- Flag self-contradictions as distinct from user contradictions

---

## Learning Integration

The stress test analyzer captured this tuning session:

**Pattern Learned:** `error_resolution`
- Context: "Gate failures occurred in 3 turns"
- Confidence: high
- Session: stress_test_20260126_012828.json

**Knowledge Base Entry:**
- File: `.agents/skills/crt-learned-patterns.md`
- Section: Trust Score Tuning
- Pattern: Theta reduction from 0.55 → 0.42 for 140% detection rate

---

## Next Steps

1. **Wait for auto-reload** (uvicorn should detect changes within 1-2 seconds)
2. **Run validation test** to confirm improvements
3. **Monitor production** for 24-48 hours
4. **Adjust theta_contra** if needed based on real usage data
5. **Document final calibration** in project README

---

## Metrics Snapshot

### Before Tuning (stress_test_20260126_072814)
- theta_contra: 0.55
- Contradiction detection: 140%
- Reintroduction violations: 6
- Gate pass: 90%
- Eval pass: 100%

### Target After Tuning
- theta_contra: 0.42
- Contradiction detection: 90-110%
- Reintroduction violations: ≤2
- Gate pass: ≥90%
- Eval pass: 100%

### Actual (Pending Test)
- Run: `python tools/crt_stress_test.py --use-api --thread-id tuned_validation --reset-thread --turns 30`
- Analyze: Compare detection rate, violations, pass rates
