# Holden Selective Multi-Request Repair Results

Run: 2026-06-19

```text
f464d99d0a273f94d2eb8d42fac0447fee313d46f84ca9437d36cff73e5c80eb  results/multi_request_end_to_end_1781884920.json
1d75323c3afeaae0284da8273c641c74a3584987097e127f1544fc65ebf8c297  results/multi_request_structured_repair_replay_1781884677.json
83731c26afba45aeb19f58a68b604aec9177e068c3a8db9a24b0ccbde8d623fa  multi_request_executor.py
4f1aa362f7c3fd534eb527a0333c08b40ff80a79fa30834e87b365a2e7ef688d  MULTI_REQUEST_REPAIR_CONTRACT_20260619.md
```

## Result

```text
Full clause coverage:       16/16
Complete answers released:  16
Incomplete answers released: 0
Repair calls:               1
Successful repairs:         1
Models perfect:             4/4
```

## Natural Repair

Qwen produced:

```text
current_project = Emberline
do not perform the prohibited action without the required confirmation
```

Clause one passed. Clause two failed because it did not identify
production-media deletion.

Holden sent only clause two to the repair call using a structured JSON contract:

```json
{
  "repairs": [
    {
      "request_index": 2,
      "answer": "No, production media cannot be deleted without confirmation."
    }
  ]
}
```

Final:

```text
1. current_project = Emberline
2. No, production media cannot be deleted without confirmation.
```

The passing segment was preserved exactly. The repaired answer passed complete
coverage.

## Safety Behavior

- Maximum repair generations remained one.
- Invalid or incomplete structured repair output blocks release.
- A controlled two-failure probe showed Qwen repairing only one of two failed
  clauses; Holden rejected that repair rather than releasing it.
- Passing clauses are not regenerated.
- No retrieval or profile changed during repair.

## Limitation

Byte-preserving passing segments also preserves cosmetic defects. In the
natural repair, `current_project = Emberline` remained protocol-flavored.
Semantic coverage passed, but a future line-level format gate should classify
that segment as repairable presentation leakage.

The correct future ordering is:

```text
semantic/scope coverage
-> line-level format validation
-> selective repair
-> final release
```

## Supported Conclusion

This run supports:

> Holden can repair one failed component of a compound answer without
> regenerating correct components, while enforcing a one-call limit and
> withholding incomplete repair output.

