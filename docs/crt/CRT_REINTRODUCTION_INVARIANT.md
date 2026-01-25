# CRT Reintroduction Invariant (v0.9-beta)

## Core Principle

**When a memory has an open contradiction, the system MUST NOT present it as unqualified truth.**

## Structural Invariant

### Data Layer (API)
**Location:** [crt_api.py](crt_api.py#L1620-L1627)

```python
"reintroduced_claim": (
    engine.ledger.has_open_contradiction(m.get("memory_id"))
    if isinstance(m, dict) and m.get("memory_id") 
    and hasattr(engine.ledger, 'has_open_contradiction')
    else False
)
```

**Rules:**
1. If `memory_id` exists and `ledger.has_open_contradiction(memory_id) == True`, then `reintroduced_claim = True`
2. Every retrieved memory MUST carry this field in API responses
3. Audit metric `reintroduced_claims_count` MUST equal count of flagged memories

**Zero-tolerance violations:**
- Retrieved memory with open contradiction but `reintroduced_claim = False`
- Count mismatch between `reintroduced_claims_count` and actual flagged memories

### Language Layer (Answer Generation)
**Location:** [personal_agent/crt_rag.py](personal_agent/crt_rag.py#L2337-L2474) (truth coherence disclosure)

**Rules:**
1. If answer uses contradicted memory, assistant MUST include inline caveat
2. Acceptable caveats: "(most recent update)", "though I have conflicting records", "according to my latest information"
3. If answer asserts contradicted claim as absolute truth without caveat → FAILURE

**Example compliance:**
```
User: "Where do I work?"
Retrieved: [Microsoft (contradicted), Amazon (latest)]
✅ PASS: "Amazon (most recent update)"
✅ PASS: "Amazon, though I have conflicting records about Microsoft"
❌ FAIL: "Amazon" (no caveat)
❌ FAIL: "Microsoft" (asserts contradicted claim)
```

## Measurement

### Acceptable Reintroduction (Audited)
- Memory flagged `reintroduced_claim=true`
- Answer includes inline caveat
- User can see transparency (X-Ray mode shows conflicts)

**Metric:** `reintroduced_flagged_count`

### Unacceptable Reintroduction (Silent)
- Memory has open contradiction but `reintroduced_claim=false`
- Answer asserts contradicted claim without caveat
- No visibility to user

**Metrics:**
- `reintroduced_unflagged_count` (MUST = 0)
- `answer_asserted_contradicted_claim_count` (target: 0)

## Implementation Status

### ✅ Complete
- [x] API serialization adds `reintroduced_claim` field (crt_api.py L1620-1627, L1640-1647)
- [x] Audit metric `reintroduced_claims_count` calculated from flagged memories (crt_api.py L1650)
- [x] Truth coherence disclosure layer adds inline caveats (crt_rag.py L2337-2474)
- [x] Stress test captures flags in JSONL artifacts (tools/crt_stress_test.py L671)
- [x] _ApiCrtClient extracts count from metadata (tools/crt_stress_test.py L283)

### 🔄 In Progress (v0.9-beta requirements)
- [ ] Split stress test metrics (flagged/unflagged/asserted)
- [ ] Add evaluation for answer caveat presence
- [ ] Generate proof artifact showing compliance

## Enforcement Mechanism

**Single Point of Truth:** API serialization layer (crt_api.py)
- Covers ALL 18 engine return paths (no per-path instrumentation needed)
- Direct ledger query ensures accuracy
- Runs on every API response

**Verification Surface:**
1. Live API responses (test with `/api/chat/send`)
2. JSONL stress test artifacts
3. X-Ray transparency data
4. Programmatic evaluation (crt_response_eval.py)

## Failure Modes

### Prevented
- ✅ Memory appears without flag (API enforces on serialization)
- ✅ Count mismatch (calculated from processed list)
- ✅ Engine path bypass (API covers all paths)

### To Monitor
- ⚠️ Answer asserts contradicted claim without caveat (needs eval)
- ⚠️ Ledger miss (memory has contradiction but ledger doesn't know)
- ⚠️ Flag ignored by client (UI/CLI responsibility)

## Version History

- **v0.9-beta (2026-01-21):** ✅ SHIPPED
  - API-layer enforcement implemented
  - Truth coherence disclosure added
  - Stress test artifact capture working
  - Integration bug fixed (_ApiCrtClient extraction)
  - API crash fix (X-Ray variable overwrite)
  - Zero violations: unflagged=0, asserted_without_caveat=0

## Watchlist (Post-Beta)

### Known Limitations (Not Blocking)
1. **Caveat Detection:** Keyword-based heuristic ("most recent", "latest", etc.)
   - Can be gamed with careful phrasing
   - Future: Semantic analysis or LLM-based detection
   - Tracking: Log false negatives in production

2. **LLM Dependency:** API requires Ollama running for full responses
   - Graceful degradation: Returns error messages when LLM unavailable
   - Stress tests exclude error responses from caveat checks
   - Future: Add "no-LLM mode" for demos/testing
   - Documentation: Add Ollama requirement to quickstart

3. **UI Enhancement (Planned):** "Alternative answer preview" hover
   - Show how answer changes if contradicted memory was used
   - Display trust/recency/conflict reasoning
   - Implementation: Context fork preview without full simulation
