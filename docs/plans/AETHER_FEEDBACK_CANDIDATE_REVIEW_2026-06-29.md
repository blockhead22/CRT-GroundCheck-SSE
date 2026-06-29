# Aether Feedback Candidate Review - 2026-06-29

Source:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_feedback_ledger_1782716566.json
```

## Review Decision

Do not promote any feedback-ledger candidate directly into durable behavior from
the clean v1 replay alone.

Use the four candidates as review signals for v2 replay and ablation testing.

## Candidates

### local_router_feedback_fallback_review

Signal:

```text
5 replay rows needed fallback routing.
```

Review:

```text
This is useful evidence that the fallback mechanism mattered, not evidence that
the fallback should become the default route.
```

Decision:

```text
defer promotion
test with ablation: routed_no_fallback vs full
```

### local_router_feedback_architecture_process_receipts

Signal:

```text
architecture_process had 5 rows with weaker receipt coverage.
```

Review:

```text
Architecture/process answers need anchors, but too much receipt pressure can
make planning answers stiff. Treat this as an eval target, not an immediate
threshold change.
```

Decision:

```text
defer promotion
test in perturbed v2 and look for repeated weak-receipt failures
```

### local_router_feedback_grant_business_receipts

Signal:

```text
grant_business had 2 rows with weaker receipt coverage.
```

Review:

```text
Grant/business already received stricter bounded-claim language. Do not add
more policy until v2 shows whether weak receipts still create overclaim or vague
business framing.
```

Decision:

```text
defer promotion
test against business_planning vs grant_business route split
```

### local_router_feedback_personal_synthesis_receipts

Signal:

```text
personal_synthesis had 5 rows with weaker receipt coverage.
```

Review:

```text
This aligns with the already-added personal/founder receipt gate. The next move
is not to tighten again, but to test whether the current gate survives perturbed
wording without becoming evasive.
```

Decision:

```text
defer promotion
test for both unsupported identity claims and over-cautious refusal
```

## Promotion Rule

A feedback candidate can become a deterministic policy/scaffold change only if:

```text
the same failure repeats in v2 or blind cases
the trace shows which layer failed
the change is specific to the failing route
the change does not weaken safety gates
the change is verified by replay after implementation
```

## Current Next Step

Post-v2 update:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782721572.json

Perturbed v2 passed:
Raw 1/32
Routed 32/32
Trace 32/32
Combined 32/32
```

Decision after v2:

```text
Do not promote the four feedback candidates yet.
The current deterministic hardening was narrower:
- avoid treating warning labels about "no code needed" as direct claims
- tell scaffold/repair prompts not to quote forbidden phrases as headings

Next promotion evidence should come from blind cases, not the mechanically
perturbed v2 pack.
```

Next run:

```text
add blind replay cases not used in policy tuning
```

Then run broader ablation slices:

```text
python -m labs.meaning_compression_lab.local_router_ablation --pack labs\meaning_compression_lab\replay_packs\local_router_replay_perturbed_v2.json --timeout 300 --max-cases 8
```
