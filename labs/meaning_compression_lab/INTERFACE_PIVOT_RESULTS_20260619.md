# CRT Interface Pivot Results

Run: 2026-06-19  
Result artifact: `results/interface_pivot_ablation_1781852132.json`

```text
0361ac5aafe9538100c8e8861085867e02ee216d68ba9b973e3f471096d8a970  results/interface_pivot_ablation_1781852132.json
da687924b0394cc9da785b94094f0c0cac8befb1066461ae56808a739952e930  interface_pivot_eval.py
3d3795c5b2d3a409127d6919092848b34bbf596d9075e0fb8a2361d3e280d6d8  INTERFACE_PIVOT_CONTRACT_20260619.md
```

## Result

| Model | Full scaffold semantic | Projected semantic | Gated semantic |
|---|---:|---:|---:|
| Qwen 2.5 7B | 6/6 | 6/6 | 6/6 |
| Phi-3 3.8B | 6/6 | 6/6 | 6/6 |
| Llama 3.2 | 6/6 | 6/6 | 6/6 |
| Mistral | 4/6 | 6/6 | 6/6 |

Aggregate:

```text
Semantic full/projected/gated: 22/24 | 24/24 | 24/24
Contract full/projected/gated: 21/24 | 24/24 | 24/24
Deterministic repairs:          0
Blocked releases:               0
False repairs:                  0
```

All pivot success criteria were met.

## What Changed

No retrieval, canonical state, case, probe, judge, or model-specific rule
changed. The complete governed state remained available internally.

For current-only questions, the executor saw only:

```text
CURRENT relevant_slot = current_value
AUTHORITY relevant_slot = confirmed
```

History, contradiction, provisional alternatives, and unrelated reaction rules
were withheld from the generation context.

## Mistral Result

Full scaffold:

```text
Marcus (Previously Daniel)
Juniper (previously Meridian)
```

Projected scaffold:

```text
Marcus (confirmed)
Juniper (confirmed)
```

Mistral retained the correct current values and stopped exposing prior values.
This supports the diagnosis that its failures came from visible irrelevant
state, not incorrect governed-state construction.

## Gate Interpretation

The deterministic gate was implemented and exercised by unit tests, including:

- stale-history leak repair;
- internal scaffold syntax repair;
- policy non-refusal repair;
- release of compliant drafts without modification.

The live ablation triggered zero repairs because projection prevented every
scored violation before release. Therefore this run empirically demonstrates
projection, while the repair path remains unit-tested rather than
model-triggered in this result.

## Human-Audit Limitation

One projected Mistral answer was:

```text
Django commerce service (CURRENT)
```

The frozen judge accepted this because it does not match the defined
field-assignment syntax pattern. It is still mildly protocol-flavored. This
must be recorded as judge/interface follow-up rather than silently changing the
frozen result. A broader protocol-label gate requires a documented before/after
ablation.

## Supported Conclusion

This run supports:

> Query-shaped projection removes the observed model/scaffold compatibility
> failures while preserving the benefits of deterministic governed state.

It does not establish a broad accuracy advantage over temporal metadata RAG.
On the six-case slice, temporal RAG scored 22/24 and projected CRT scored 24/24,
an 8.3-point gain—the mathematical maximum available on this slice, but below
the original ten-point comparative threshold.

