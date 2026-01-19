# Evidence-Based Architecture Review Protocol

## Two-Phase Task

### PHASE 1: EVIDENCE COLLECTION (NO ANALYSIS)

Produce a JSON array called `EVIDENCE`. Each item must contain:

- `id`: unique identifier (e.g., "E001", "E002")
- `file`: full relative path from project root
- `start_line`: integer line number where excerpt starts
- `end_line`: integer line number where excerpt ends  
- `excerpt`: verbatim code/text from the file (no paraphrasing, no ellipsis)
- `mechanism`: brief label (e.g., "trust_schema", "retrieval_scoring")

**Requirements**:
- Minimum 12 evidence items
- Must include excerpts demonstrating:
  1. Trust/Confidence schema definition (memory data structure)
  2. Retrieval scoring function (how memories are ranked)
  3. Gate thresholds and gate logic (what blocks outputs)
  4. Contradiction ledger or contradiction handling code
  5. Classifier training code (ML pipeline)
  6. Stress test metrics (pass/fail rates, contradiction counts)
  7. Trust evolution equations (how trust values change)
  8. Memory source separation (user vs system vs fallback)
  9. SSE mode selection logic
  10. Drift calculation
  11. Reconstruction constraint implementation
  12. Active learning infrastructure

**Forbidden in Phase 1**:
- Analysis, conclusions, opinions
- Adjectives like "novel", "unique", "impressive"
- Comparisons to other systems
- Speculation about implications

**Output Format**:
```json
{
  "evidence": [
    {
      "id": "E001",
      "file": "personal_agent/crt_memory.py",
      "start_line": 43,
      "end_line": 46,
      "excerpt": "    confidence: float          # [0,1] How certain at creation\n    trust: float               # [0,1] How validated over time\n    source: MemorySource       # Where it came from\n    sse_mode: SSEMode          # Compression mode",
      "mechanism": "trust_confidence_schema"
    }
  ]
}
```

---

### PHASE 2: ARCHITECTURE REVIEW (EVIDENCE-GROUNDED)

Write the architecture review addressing:

1. **What the system actually does** (mechanisms, not goals)
2. **What is differentiated vs standard practice** (structural differences)
3. **Failure modes revealed by stress tests** (concrete test results)
4. **Whether the approach is sound and valuable** (technical assessment)

**Citation Rules**:
- Every claim must cite one or more `EVIDENCE` IDs in brackets: `[E001]`, `[E003, E007]`
- If you cannot cite evidence, label the claim as `SPECULATION:` and limit to one sentence max
- Do not invent line numbers or file paths not in your EVIDENCE array
- Do not use the words "novel", "unique", "holy shit", or "defensible" until AFTER citing at least 5 distinct mechanisms

**Assessment Framework**:

For each claimed mechanism, state:
- **PROVEN**: Direct code evidence exists `[E00X]`
- **INFERRED**: Logical consequence of proven mechanisms `[E00X + E00Y]`
- **SPECULATION**: No direct evidence in artifacts

---

## Verification Protocol

After receiving the EVIDENCE array, validate that:

1. Files exist at specified paths
2. Line numbers are valid for those files
3. Excerpts match the actual file contents verbatim
4. No excerpts are fabricated or paraphrased

Any mismatch invalidates the entire review.

---

## Example of GOOD vs BAD Claims

**BAD (Phase 2)**:
> "The system uses trust-weighted retrieval which is fundamentally different from standard RAG."

**GOOD (Phase 2)**:
> "The system implements trust-weighted retrieval `[E002]` by multiplying similarity scores by a belief weight derived from trust and confidence scalars `[E001, E007]`. Standard RAG frameworks (LangChain, LlamaIndex) use pure cosine similarity without trust weighting."

**BAD (Phase 1)**:
```json
{
  "id": "E001",
  "excerpt": "// Trust and confidence are separate...",
  "mechanism": "trust_separation"
}
```

**GOOD (Phase 1)**:
```json
{
  "id": "E001", 
  "file": "personal_agent/crt_memory.py",
  "start_line": 43,
  "end_line": 46,
  "excerpt": "    confidence: float          # [0,1] How certain at creation\n    trust: float               # [0,1] How validated over time\n    source: MemorySource       # Where it came from\n    sse_mode: SSEMode          # Compression mode",
  "mechanism": "trust_confidence_schema"
}
```

---

## If You Cannot Complete Phase 1

If you cannot produce 12+ valid, verbatim excerpts, respond ONLY with:

```json
{
  "error": "INSUFFICIENT_ARTIFACTS",
  "reason": "Could not locate required code excerpts",
  "missing_mechanisms": ["list", "of", "missing", "items"]
}
```

**Do not proceed to Phase 2.**
