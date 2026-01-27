# CRT-GroundCheck-SSE Project Context

> **For AI Agents:** This file provides essential context to understand the codebase quickly. Reference this before starting any task.

---

## What This Is

A **trust-weighted memory system** for AI agents with contradiction detection. When conflicting information is stored, the system:
- Preserves both versions (doesn't silently overwrite)
- Tracks contradictions in a ledger
- Discloses conflicts in responses
- Asks for clarification when appropriate

---

## Current Status

**See [STATUS.md](../../STATUS.md) for live metrics and next actions.**

| Test | Current | Target |
|------|---------|--------|
| crt_stress_test | 91.7% | 90%+ ✅ |
| adversarial_challenge | 65.7% | 80% ❌ |

---

## Key Files

### Core Pipeline
| File | Purpose | Lines |
|------|---------|-------|
| `personal_agent/crt_rag.py` | Main RAG pipeline, contradiction detection | ~4000 |
| `personal_agent/crt_core.py` | CRT math equations, trust scoring | ~1000 |
| `personal_agent/crt_memory.py` | SQLite memory storage | ~1000 |
| `personal_agent/crt_ledger.py` | Contradiction ledger | ~500 |
| `personal_agent/fact_slots.py` | Fact extraction via regex | ~900 |
| `personal_agent/domain_detector.py` | Domain detection (career, hobby, etc.) | ~300 |

### Testing
| File | Purpose | Requires Ollama? |
|------|---------|------------------|
| `tools/adversarial_crt_challenge.py` | 35-turn adversarial test | ❌ No |
| `tools/crt_stress_test.py` | 30-turn general stress test | ✅ Yes |
| `tests/test_phase20_context_aware_memory.py` | Unit tests for Phase 2.0 | ❌ No |

### Configuration
| File | Purpose |
|------|---------|
| `artifacts/crt_features.json` | Feature flags |
| `crt_runtime_config.json` | Runtime config |

---

## Quick Validation

```powershell
# Adversarial test (no Ollama)
python tools/adversarial_crt_challenge.py --turns 35

# Full stress test (needs Ollama running)
python tools/crt_stress_test.py --turns 30

# Pytest suite
python -m pytest tests/ -v --tb=short

# Single module import check
python -c "from personal_agent.crt_rag import CRTEnhancedRAG; print('OK')"
```

---

## Current Thresholds (crt_core.py)

```python
theta_contra = 0.42   # Contradiction detection threshold
theta_align = 0.15    # Alignment threshold  
theta_drop = 0.30     # Trust drop threshold
```

### Paraphrase Detection (crt_core.py ~line 600)
- Drift range: 0.25–0.55
- Key element overlap: >70% blocks contradiction

---

## Architecture Flow

```
User Query
    ↓
[CRTEnhancedRAG.query()]
    ↓
[Fact Extraction] → fact_slots.py extracts slots (name, employer, etc.)
    ↓
[Memory Retrieval] → crt_memory.py fetches relevant memories
    ↓
[Contradiction Detection]
    ├── ML Detector (XGBoost) → ml_contradiction_detector.py
    ├── CRTMath.detect_contradiction() → crt_core.py
    └── Context-aware check → is_true_contradiction_contextual()
    ↓
[Ledger Recording] → crt_ledger.py stores contradiction
    ↓
[Response Generation] → LLM with caveat injection if contradictions exist
    ↓
[GroundCheck Verification] → Ensures contradictions are disclosed
```

---

## Phase Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Self-questioning, caveat injection, feature flags | ✅ Done |
| 1.1 | Wire up CRTMath call sites | ✅ Done |
| 2.0 | Context-Aware Memory (domain/temporal) | ✅ Done |
| 1.2 | Advanced Testing Suite | 📋 Next |
| 2 | UX Enhancements | 📋 Planned |
| 3 | Vector-store-per-fact | 📋 Planned |

---

## Common Tasks

### Add a new fact extraction pattern
Edit `personal_agent/fact_slots.py`, add pattern to relevant `_PATTERNS` dict.

### Adjust contradiction sensitivity
Edit `personal_agent/crt_core.py`, modify `theta_contra` (lower = more sensitive).

### Add a new test scenario
Edit `tools/adversarial_crt_challenge.py`, add to `SCENARIOS` list.

### Debug a false positive
1. Check `is_true_contradiction_contextual()` in crt_core.py
2. Check `_is_likely_paraphrase()` in crt_core.py
3. Check domain overlap in domain_detector.py

---

## Environment Setup

```powershell
cd d:\AI_round2
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
pip install -e groundcheck/

# Start API (optional)
python -m uvicorn crt_api:app --host 127.0.0.1 --port 8123
```

---

## Known Weaknesses (as of 2026-01-26)

| Pattern | Example | Issue |
|---------|---------|-------|
| `direct_correction` | "I'm actually 34, not 32" | Not detected |
| `hedged_correction` | "I said 10 years but it's closer to 12" | Not detected |
| `retraction_of_denial` | PhD → Master's → PhD | Not detected |
