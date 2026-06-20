# Frozen Holden Bounded-Fetch Results

Run: 2026-06-19  
Result artifact: `results/bounded_fetch_1781853433.json`

```text
654943d6b7967c98322e3751a908748cf535e774066d14ee57ca7b7bd2b99c12  results/bounded_fetch_1781853433.json
9c06ef4801b84c8b7282ca100cca793a086b190b796baae783b3233d392ceb54  bounded_fetch_eval.py
c2c75355be7bdf47b9167ed8dc140454f4b89cb7358afc0858203fddc5e6a165  untouched_fetch_cases.py
```

## Setup

- Frozen Holden profiles from the governance-dose lab.
- Six new cases authored after profile freeze.
- Four cases with deliberately insufficient initial top-2 evidence.
- Two sufficient controls.
- One authorized slot-constrained fetch maximum.
- One generation call after evidence sufficiency.
- No profile, case, judge, retrieval weight, or expected answer changes after
  model generation began.

## Results

| Model | Frozen dose | Semantic | Full contract | Fetch decisions |
|---|---:|---:|---:|---:|
| Qwen 2.5 7B | 1 | 6/6 | 6/6 | 6/6 |
| Phi-3 3.8B | 1 | 6/6 | 6/6 | 6/6 |
| Llama 3.2 | 5 | 6/6 | 6/6 | 6/6 |
| Mistral | 1 | 6/6 | 6/6 | 6/6 |

Aggregate:

```text
Semantic success:          24/24
Full-contract success:     24/24
Correct fetch decisions:   24/24
Unnecessary fetches:       0
Missed fetches:            0
Fetches above limit:       0
Final evidence sufficient: 24/24
Severe failures:           0
Models perfect:            4/4
```

All frozen success thresholds passed.

## Observed Control Loop

Example:

```text
Question: Where am I currently working?

Initial top-2:
  current working directory = project root
  provisional employer = Northwind Systems

Compiled state:
  no confirmed employer

Holden request:
  requested_slots = ["employer"]
  reason_code = missing_confirmed_current_value

Authorized fetch:
  confirmed employer = Blue Orchard Studio
  provisional employer = Northwind Systems

Recompiled state:
  CURRENT employer = Blue Orchard Studio

Released answer:
  Blue Orchard Studio
```

The model did not choose the slot or decide whether another fetch was allowed.
The question contract and governed-state sufficiency check made that decision.

## Supported Conclusion

This run supports:

> Frozen, calibration-derived Holden profiles can survive model hot-swapping,
> detect when retrieved evidence is insufficient, request one governed slot,
> recompile state, and produce contract-compliant answers on a new challenge
> pack.

This is stronger than prompt optimization because the system controls:

- whether generation is allowed;
- whether more evidence is needed;
- which slot may be fetched;
- how many fetches are permitted;
- how much governance the active model sees.

## Limits

- The challenge pack contains six hand-authored cases.
- The slot needed by each question is declared by the probe contract; general
  natural-language slot induction remains unsolved.
- Slot-constrained retrieval is deterministic metadata filtering, not a
  production vector-store query.
- Llama's policy response included the internal-looking identifier
  `media.production_delete_without_confirmation` in natural prose. The frozen
  judge accepted it because it did not use assignment-style scaffold syntax.
  This is a remaining presentation leak and should be tracked without changing
  this frozen result.
- Independent replication and external benchmarks are still absent.

## Next Threshold

The next credible jump requires:

- 25+ untouched cases;
- automatically inferred question contracts or slot requests;
- an actual persisted retrieval service;
- repeated runs or independent reproduction.

