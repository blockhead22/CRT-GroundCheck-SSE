# CRT v0.9-beta Release Notes
**Released:** January 21, 2026  
**Tag:** `v0.9-beta`

## Summary
First beta release implementing **reintroduction invariant enforcement**: contradicted memories MUST be flagged in data and caveated in language. Zero tolerance for silent contradictions.

## Core Feature: Reintroduction Invariant

### Data Layer Enforcement
Every memory with an open contradiction carries `reintroduced_claim: true` flag:
```json
{
  "memory_id": "mem_1769012949418_84",
  "text": "Actually, I work at Amazon, not Microsoft.",
  "reintroduced_claim": true
}
```

**Implementation:** API serialization layer ([crt_api.py](crt_api.py#L1613-L1650))  
**Mechanism:** Direct call to `engine.ledger.has_open_contradiction(memory_id)`  
**Coverage:** All API responses, all engine return paths

### Language Layer Disclosure
Answers using contradicted memories include inline caveats:
```
User: "Where do I work?"
Answer: "Amazon (most recent update)"
```

**Implementation:** Truth coherence disclosure ([crt_rag.py](crt_rag.py#L2337-L2474))  
**Patterns:** "(most recent update)", "though I have conflicting records", "according to latest information"

### Audit Metrics
```
REINTRODUCTION INVARIANT (v0.9-beta):
  Flagged (audited): 12
  Unflagged (violations): 0  ← ZERO TOLERANCE
  Asserted without caveat (violations): 0  ← ZERO TOLERANCE
  ✅ INVARIANT MAINTAINED
```

## Fixes

### API Crash (X-Ray Variable Overwrite)
**Issue:** [crt_api.py](crt_api.py#L1664) overwrote processed `retrieved_mems` with raw engine result  
**Impact:** X-Ray section accessed undefined flag fields, caused crashes  
**Fix:** Reuse processed memories (already have flags), use calculated counts

### Stress Test Integration
**Issue:** `_ApiCrtClient.query()` didn't extract `reintroduced_claims_count` from metadata  
**Impact:** JSONL artifacts showed count=0 even when flags were present  
**Fix:** [tools/crt_stress_test.py](tools/crt_stress_test.py#L283) now extracts all invariant fields

### Caveat Detection False Positives
**Issue:** Error responses flagged as "asserted without caveat" violations  
**Impact:** Ollama failures inflated violation count  
**Fix:** Exclude error responses (`"error" in answer or "ollama" in answer`) from caveat checks

## Verification

### Proof Artifact
**Location:** [artifacts/crt_stress_run.20260121_162816.jsonl](artifacts/crt_stress_run.20260121_162816.jsonl)  
**Generated:** After all fixes applied  
**Result:** 15-turn stress test, 2 contradictions, 12 flagged memories, 0 violations

**Turn 12 Evidence:**
```
Question: "Where do I work?"
Answer: "Amazon (most recent update)"

Data layer:
  • Retrieved memories: 6
  • Flagged as contradicted: 2
  • Count match: ✅ YES

Language layer:
  • Caveat present: ✅ YES ("most recent")

Contradicted memories:
  [mem_1769012949418_84] reintroduced_claim=True
    "Actually, I work at Amazon, not Microsoft."
  [mem_1769012898939_7174] reintroduced_claim=True
    "I work at Microsoft as a senior developer."
```

### Stress Test Report
```
Total Turns: 15
Contradictions Introduced: 2
Eval Pass Rate: 100.0%
Eval Failures: 0

REINTRODUCTION INVARIANT:
  ✅ Flagged (audited): 12
  ✅ Unflagged (violations): 0
  ✅ Asserted without caveat (violations): 0
  ✅ INVARIANT MAINTAINED
```

## Documentation

### New Files
- **[CRT_REINTRODUCTION_INVARIANT.md](CRT_REINTRODUCTION_INVARIANT.md):** Complete invariant specification
  - Data layer rules
  - Language layer rules
  - Measurement methodology
  - Enforcement mechanism
  - Failure modes
  - Watchlist (post-beta limitations)

### Updated Files
- **[crt_api.py](crt_api.py):** Version 0.9-beta, flag enforcement at L1613-1650
- **[tools/crt_stress_test.py](tools/crt_stress_test.py):** Split metrics (flagged/unflagged/asserted)

## Known Limitations (Watchlist)

### 1. Caveat Detection: Keyword-based heuristic
- **Current:** Matches "most recent", "latest", "though", "however", etc.
- **Risk:** Can be gamed with careful phrasing
- **Status:** Acceptable for beta (zero violations in stress test)
- **Future:** Semantic analysis or LLM-based detection

### 2. LLM Dependency: Ollama required
- **Behavior:** Returns error messages when Ollama unavailable
- **Workaround:** Stress tests exclude error responses from caveat checks
- **Action needed:** Document Ollama requirement in quickstart
- **Future:** Add "no-LLM mode" for demos/testing

### 3. UI Enhancement (Planned)
- **Feature:** Hover on contradicted memory shows alternative answer
- **Shows:** "If I used this instead..." + trust/recency/conflict reasoning
- **Benefit:** Context fork preview without full simulation
- **Status:** Design approved, implementation post-beta

## Demo Requirements
Before running demo/stress tests:
1. **Ollama installed and running:** `ollama serve`
2. **Model pulled:** `ollama pull llama3.2:latest`
3. **API server started:** `uvicorn crt_api:app --reload --port 8123`

OR expect error-mode responses (graceful degradation, flags still work).

## Next Steps (Post-Beta)
1. **Soft launch:** 5 testers with DEMO_SCRIPT + BUG_TEMPLATE
2. **Quickstart update:** Add Ollama preconditions
3. **UI hover preview:** Implement alternative answer context fork
4. **Caveat detection:** Upgrade from keywords to semantic analysis
5. **No-LLM mode:** Fallback for testing/demos without Ollama

---

**Reintroduction is now audited disclosure, not silent failure.**  
**v0.9-beta is cleared for controlled beta testing.**
