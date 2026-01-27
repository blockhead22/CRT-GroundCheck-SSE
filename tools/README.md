# Tools Directory

Testing and validation utilities for CRT-GroundCheck-SSE.

---

## Primary Testing Tools

| Tool | Purpose | Requires Ollama? |
|------|---------|------------------|
| **adversarial_crt_challenge.py** | 35-turn adversarial test (7 phases) | ❌ No |
| **crt_stress_test.py** | 30-turn general stress test | ✅ Yes |

---

## Quick Commands

### Adversarial Challenge (Primary Test)
```powershell
python tools/adversarial_crt_challenge.py --turns 35
```
Tests: baseline, temporal, semantic, identity, negation, drift, stress

**Target:** ≥80% overall score

### CRT Stress Test (Full Test)
```powershell
# Start Ollama first
ollama serve

# Run test
python tools/crt_stress_test.py --turns 30
```

**Target:** ≥90% eval pass rate

---

## All Tools

| File | Description |
|------|-------------|
| `adversarial_crt_challenge.py` | Multi-phase adversarial contradiction testing |
| `crt_stress_test.py` | General stress test with API or direct mode |
| `full_stress_test.py` | Extended stress test suite |
| `quick_stress_test.py` | Fast validation (subset of scenarios) |
| `nl_resolution_stress_test.py` | Natural language resolution testing |
| `check_ledger_db.py` | Inspect contradiction ledger database |

---

## Test Phases (adversarial_crt_challenge.py)

| Phase | Turns | What It Tests |
|-------|-------|---------------|
| BASELINE | 1-5 | Basic fact storage and recall |
| TEMPORAL | 6-10 | Time-based inference conflicts |
| SEMANTIC | 11-15 | Meaning-equivalent contradictions |
| IDENTITY | 16-20 | Name/entity changes |
| NEGATION | 21-25 | "I don't X anymore" patterns |
| DRIFT | 26-30 | Gradual value shifts |
| STRESS | 31-35 | Rapid-fire contradictions |

---

## Current Results (2026-01-26)

| Metric | crt_stress_test | adversarial_challenge |
|--------|-----------------|----------------------|
| **Score** | 91.7% | 65.7% |
| **Target** | 90% | 80% |
| **Status** | ✅ PASSING | ⚠️ In progress |
