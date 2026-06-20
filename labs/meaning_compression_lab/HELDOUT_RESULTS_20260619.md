# CRT Shared-Evidence Held-Out Result

Run: 2026-06-19  
Result artifact: `results/heldout_shared_evidence_1781851548.json`

```text
e46e23a5ce32e6cf2bc1133309ade477ad54e3f1e471b795e1e079c65ea70bd1  results/heldout_shared_evidence_1781851548.json
b3a64a2dda02ff4b9402737af0ea4432c1f9c198257d0ef76691ee87a5132ae4  heldout_shared_evidence_eval.py
```

## Setup

- Six previously unrun held-out cases.
- Seven candidate memories per case.
- Hybrid lexical plus MiniLM retrieval.
- Top four records retrieved once and shared by both arms.
- Same four local executor models used in the prior sweep.
- Scaffold, cases, probes, judge, and thresholds remained frozen.

## Results

| Model | Temporal semantic | Hybrid semantic | Delta | Temporal severe | Hybrid severe |
|---|---:|---:|---:|---:|---:|
| Qwen 2.5 7B | 6/6 | 6/6 | 0.0 pts | 0 | 0 |
| Phi-3 3.8B | 4/6 | 6/6 | +33.3 pts | 0 | 0 |
| Llama 3.2 | 6/6 | 6/6 | 0.0 pts | 0 | 0 |
| Mistral | 6/6 | 4/6 | -33.3 pts | 0 | 0 |

Aggregate:

```text
Temporal semantic: 22/24 (91.7%)
Hybrid semantic:   22/24 (91.7%)
Temporal contract: 22/24 (91.7%)
Hybrid contract:   21/24 (87.5%)
Semantic delta:    0.0 percentage points
Severe failures:   0 for both arms
Model wins:        hybrid 1, temporal 1, tied 2
```

## Failure Categories

### Temporal metadata RAG

Phi-3 leaked stale/provisional explanation on two otherwise correct
current-state answers:

- current name: answered Marcus but also mentioned Daniel;
- current project: answered Juniper but also mentioned Meridian and Harbor.

Earliest responsible layer: `output_scope`.

### Hybrid CRT

Mistral leaked history on the same two current-state cases:

- `Marcus (Previously Daniel)`
- `Juniper (previously Meridian)`

The governed state was correct. The executor did not obey the current-only
query contract. The scaffold's visible history and
`answer_current_with_history` reaction appear to be particularly attractive to
Mistral.

Earliest responsible layer: `output_scope`, with model/scaffold interface
coupling.

Llama 3.2 produced one degraded pass:

```text
CURRENT store_platform = Django commerce service
```

Meaning and scope were correct; internal scaffold syntax leaked.

Earliest responsible layer: `output_format`.

## Frozen-Threshold Reading

On this held-out slice, hybrid CRT met:

- semantic success at least 90%;
- full-contract success at least 80%;
- zero severe failures.

It did not meet:

- at least a 10-point semantic advantage over temporal metadata RAG;
- an advantage on at least three of four model families.

Therefore the decisive architecture claim is not supported by this run. The
result supports a narrower claim: deterministic state compilation can help
weaker metadata reasoning executors such as Phi-3, but the same exposed
structure can hurt other executors such as Mistral. Representation-to-model
compatibility is currently as important as the governance state itself.

No scaffold adjustment should be made until this result is treated as the
baseline for a documented interface ablation.
