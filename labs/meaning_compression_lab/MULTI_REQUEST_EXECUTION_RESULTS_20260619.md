# Holden Multi-Request Execution Results

Run: 2026-06-19

```text
eec08bf8abc8b94b9b8b0f3dc177fcc087b7f5c9edb03378ee1752d1005a379e  results/multi_request_end_to_end_1781880797.json
1db63330ed5ffd5e615a4102e380f8a504f25525cdd67b75538d959512cf3b75  multi_request_executor.py
b27bc54c7b1a2dd0ac1cf065eb7a8c8edc4b5c4a2781d97ffb51fb1e53015d2e  MULTI_REQUEST_EXECUTION_CONTRACT_20260619.md
```

## Result

Four frozen Holden profiles ran four compound-request cases:

| Model | Complete answers | Blocked incomplete | Partial released |
|---|---:|---:|---:|
| Qwen 2.5 7B | 3/4 | 1 | 0 |
| Phi-3 3.8B | 4/4 | 0 | 0 |
| Llama 3.2 | 4/4 | 0 | 0 |
| Mistral | 4/4 | 0 | 0 |

Aggregate:

```text
Full clause coverage:      15/16 (93.8%)
Released complete answers: 15
Blocked incomplete answers: 1
Partial answers released:  0
Models perfect:            3/4
```

The frozen success threshold was met.

## Demonstrated Flow

Example three-request turn:

```text
Where am I working now,
what camera was before Blackmagic,
and can production media be deleted without asking?
```

Planner:

```json
[
  {"slot": "employer", "mode": "current"},
  {"slot": "camera_system", "mode": "history"},
  {
    "slot": "media.production_delete_without_confirmation",
    "mode": "policy"
  }
]
```

Execution:

- independent retrieval for each slot;
- independent governed-state compilation;
- one combined answer;
- independent release judgment for all three clauses.

## Blocked Qwen Answer

Qwen answered:

```text
current_project = Emberline
do not perform the prohibited action without the required confirmation
```

The project clause passed. The policy clause refused generically but did not
identify production-media deletion. Holden blocked the complete response rather
than releasing a half-specific answer.

This is intended behavior:

```text
correct clause + incomplete clause != releasable complete answer
```

## Planner and Judge Corrections

The first run exposed two evaluator/runtime defects:

- comma-separated wh-questions were not always segmented independently;
- valid refusal phrases such as `without asking` were treated as different from
  `without confirmation`.

Both were fixed under the frozen contract, with before/after artifacts retained.
The final remaining Qwen block is not evaluator brittleness; it lacks the
required action scope.

## Supported Conclusion

This run supports:

> Holden can plan, retrieve, compile, and validate multiple governed requests
> within one conversational turn, while preventing one correct clause from
> hiding an omitted or underspecified clause.

## Remaining Work

- one bounded repair pass for incomplete multi-request answers;
- line-to-request alignment rather than whole-answer token coverage;
- multi-request execution against Aether's persisted memory store;
- larger, longer conversational fixtures with pronouns and cross-turn
  references.

