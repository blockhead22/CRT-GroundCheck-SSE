# Holden Multi-Request Contract Planner

Status: frozen before implementation  
Frozen: 2026-06-19

## Core Rule

Finding one valid slot does not complete classification.

Classification is complete only when every meaningful clause is:

- mapped to one or more governed requests;
- explicitly classified as non-memory work; or
- marked unresolved for clarification or semantic fallback.

## Output

```json
{
  "status": "resolved | partial | ambiguous | unknown",
  "requests": [
    {
      "clause_id": "c1",
      "slot": "employer",
      "mode": "current",
      "confidence": 0.91,
      "source": "deterministic | semantic_parser"
    }
  ],
  "clauses": [
    {
      "clause_id": "c1",
      "text": "Where do I work now?",
      "status": "resolved",
      "candidate_slots": ["employer"]
    }
  ],
  "coverage": 1.0,
  "unresolved_clauses": []
}
```

## Stages

1. Clause segmentation.
2. Deterministic multi-label candidate generation.
3. Preserve every high-confidence resolved clause.
4. Route unresolved clauses to a structured semantic parser.
5. Validate parser slots against the live slot catalog.
6. Merge requests without discarding deterministic resolutions.
7. Calculate clause coverage.

## Limits

- Maximum requests per turn in this phase: eight.
- One clause may map to multiple slots when explicitly requested.
- A resolved clause does not suppress later clauses.
- The semantic parser may not invent unavailable slots.
- Parser output must validate against a fixed JSON-like schema.
- Invalid parser output becomes unresolved, not silently repaired.
- Coverage below 1.0 must be surfaced.
- Retrieval is planned per request; one global top-k is not assumed sufficient.

## Success Criteria

- Multi-clause fixtures preserve all requested slots.
- Long prose with two or more memory questions achieves full coverage.
- Ambiguous clauses do not erase resolved clauses.
- Unknown clauses remain unresolved.
- Invented semantic-parser slots are rejected.
- Duplicate requests merge without losing stricter modes.
- At least 90% request recall on the initial planner fixture pack.
- Zero confidently wrong slot assignments on adversarial ambiguity fixtures.

