# Holden Slot-Inference Results

Run: 2026-06-19

```text
55ae95a156373881e6334f0a854acb93cc4d458b35c934da339cf5a1691fc76d  results/slot_inference_ablation_1781879672.json
9b4c20a7a656ac91b19b109f7b9f92161b00d208262de4ac0f89df314739d8b2  results/inferred_bounded_fetch_1781879719.json
5165c376a831e6950231b3ee7bab2fa7c4665f20f2fed378e74db9f693506efc  slot_request_inference.py
f9193f0b8e4bec1404bc12ba405b5a240ff9252163834b0a9e8209dd71409198  SLOT_INFERENCE_CONTRACT_20260619.md
```

## Oracle Ablation

The inference layer received only:

- the user question;
- available slot names.

It did not receive probe names, expected answers, model names, or stored values.

```text
Resolved correct slots: 5/6
Safe abstentions:       1
Confidently wrong:      0
Contract kinds correct: 6/6
```

Resolved:

- employer;
- camera system history;
- production-media deletion policy;
- current project;
- store platform.

Abstained:

```text
Question: What name should appear in generated files?

Candidates:
  file_naming  0.530
  name         0.399

Action:
  block automatic fetch and ask whether the user means file naming or
  personal name.
```

This is the correct safety behavior. The wording does not uniquely identify a
personal-name request.

## Inference-Backed Fetch Run

Frozen profiles and the existing one-fetch protocol were run without declared
slot mappings:

```text
Automated model-cases:    20/24
Automated semantic:       20/20
Automated full contract:  20/20
Confidently wrong slots:  0
Blocked clarifications:   4
Severe failures:          0
```

Each model automatically handled five of six cases. All four blocked the same
ambiguous naming case before retrieval or generation.

## Supported Conclusion

This run supports:

> Holden can infer common governed slots and contract types from the question
> and substrate schema, automate high-confidence requests, and abstain rather
> than perform a wrong fetch when the request is ambiguous.

It does not yet support general slot induction. The current inference engine is
a standalone deterministic semantic registry with confidence and margin rules.

## Next Step

Implement clarification resolution:

```text
ambiguous inference
-> present two candidate meanings
-> user selects or rephrases
-> rerun inference
-> authorize one slot fetch
```

After that, move the inference and bounded-fetch protocol onto Aether's actual
persisted slot catalog and retrieval store.

