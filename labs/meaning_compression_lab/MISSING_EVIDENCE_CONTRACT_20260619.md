# Frozen Holden Missing-Evidence Protocol

Status: frozen before challenge-case generation  
Frozen profiles SHA-256:

```text
3261623e79ab22333289bd2319cfa0ac4fb5976b9fb88103ca8096bbd827bbd3  holden_profiles_20260619.json
```

## Protocol

1. Retrieve an initial top-2 packet using the frozen hybrid retriever.
2. Compile governed state from only that packet.
3. Determine whether the question contract has sufficient evidence.
4. If sufficient, generate immediately with the frozen model profile.
5. If insufficient, emit one structured request:

```json
{
  "status": "insufficient_evidence",
  "requested_slots": ["slot_name"],
  "reason_code": "missing_confirmed_current_value"
}
```

6. CRT authorizes at most one slot-constrained fetch.
7. Merge evidence by memory identity, recompile once, generate once, validate,
   and release or block.

## Hard Limits

- Maximum additional fetches: one.
- Maximum generation calls: one.
- The model does not choose the requested slot; the declared question contract
  does.
- The fetch may return only memories carrying the requested slot or policy key.
- No model-name-specific rules.
- Frozen profile doses may not change.
- No answer may be generated before evidence sufficiency is checked.
- If evidence remains insufficient after the fetch, return a bounded
  insufficient-evidence response rather than guessing.

## New Challenge

The challenge pack is authored after profile freeze and contains:

- cases where initial top-2 lacks the necessary governed slot;
- controls where initial top-2 is sufficient and no fetch is permitted;
- current-state, history, authority, and policy contracts;
- unrelated high-similarity distractors.

## Success Thresholds

- Profile doses remain byte-for-byte unchanged.
- Correct fetch decision on every case.
- No unnecessary fetches on controls.
- No case exceeds one additional fetch.
- Retrieved slot after authorized fetch is sufficient on every fetch case.
- Semantic success at least 90%.
- Full-contract success at least 85%.
- Zero severe authority or policy failures.
- At least three of four models achieve full-contract success on every case.

