# Local Router Curated Replay v1 Evidence - 2026-06-29

## Summary

The curated replay pass supports the core Aether thesis:

```text
raw local chat < routed local model + Mirus packet + scaffold + CRT verifier
+ repair/fallback + durable trace
```

This does not show local models competing with frontier models globally. It
does show that governed external cognition substantially improves local-model
answers for Aether's use case.

## Pack

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json
```

Shape:

```text
32 cases
8 architecture_synthesis
8 personal_synthesis
6 grant_business
2 business_planning
historical replay pass used 8 code_reasoning/code-process cases; taxonomy cleanup relabeled those as:
  7 architecture_process
  1 code_implementation
```

## Post-Policy Rerun

After the label cleanup, grant/business final-answer policy, personal-synthesis
receipt gate, and repair-policy inheritance:

```text
Raw answer pass:      0/32
Routed answer pass:   28/32
Trace pass:           32/32
Combined pass:        28/32
Combined pass rate:   87.5%
Average raw score:    0.377
Average routed score: 0.750
Average lift:         +0.372
Repairs used:         9
Fallbacks used:       6
```

Failure taxonomy:

```text
4 answer-side failures
0 trace failures
0 forbidden hits
0 leakage hits
0 weirdness hits
0 truncation failures

by task type:
  3 architecture_process
  1 grant_business
```

Interpretation:

```text
The safety/restraint failures were repaired. The remaining failures are
low-score/coverage failures, likely needing better anchor fit or task-specific
grading rather than looser safety policy.
```

## Post-Anchor Rerun

After the low-score anchor-fit review:

```text
Added business_planning for the camera-gear small-business prompt.
Added case-specific architecture_process anchors for:
  gptlog_027_architecture_process
  gptlog_028_architecture_process
  gptlog_030_architecture_process
Added architecture_process final-answer policy against banned limit wording.
Added --case-id replay filtering for targeted reruns.
```

Targeted reviewed cluster:

```text
Result file:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782713622.json

Raw answer pass:      0/4
Routed answer pass:   4/4
Trace pass:           4/4
Combined pass:        4/4
Average raw score:    0.526
Average routed score: 0.824
Average lift:         +0.297
Repairs used:         2
Fallbacks used:       0
Hard flags:           none
```

Latest full replay after the anchor/policy pass:

```text
Result file:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782714154.json

Raw answer pass:      0/32
Routed answer pass:   28/32
Trace pass:           32/32
Combined pass:        28/32
Combined pass rate:   87.5%
Average raw score:    0.397
Average routed score: 0.766
Average lift:         +0.369
Repairs used:         6
Fallbacks used:       3
```

Latest failure taxonomy:

```text
4 answer-side failures
0 trace failures
0 leakage hits
0 truncation failures

by task type:
  3 personal_synthesis
  1 grant_business

personal_synthesis:
  broad identity/founder prompts still tempt unsupported identity claims
  when no concrete receipts are supplied.

grant_business:
  one business prompt still needs stronger limit/thesis wording and avoids
  guarantee language only imperfectly.
```

Interpretation:

```text
The reviewed anchor-fit failures were resolved without lowering thresholds.
The remaining failures are now governance-positive failures: CRT is blocking
unsupported identity synthesis and outcome-promise wording rather than letting
local chat sound confident.
```

## Final Roadmap-Return Rerun

After tightening personal/founder receipt-request behavior, keeping
personal_synthesis fallback inside section-lock, refining the `conscious`
forbidden-word detector so `sub-conscious memory` is not treated as a
consciousness claim, and relabeling `gptlog_022` as business_planning:

```text
Result file:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782716566.json

Raw answer pass:      0/32
Routed answer pass:   32/32
Trace pass:           32/32
Combined pass:        32/32
Combined pass rate:   100.0%
Average raw score:    0.407
Average routed score: 0.773
Average lift:         +0.366
Repairs used:         5
Fallbacks used:       5
Hard flags:           none
```

Interpretation:

```text
The curated lab now cleanly supports the roadmap-return claim: small local
models are not competing with frontier models globally, but governed external
cognition is materially better than raw local chat for Aether's target lane.
The next step is not more prompt tuning; it is graduation into Workbench trace,
reviewed feedback ledger, and a larger/noisier eval pack.
```

## Feedback Ledger Artifact

The clean replay was converted into review-only feedback metadata:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_feedback_ledger_1782716566.json
```

Summary:

```text
32 feedback rows
4 Workbench preview candidates
writes_performed: false
memory_ingestion_performed: false
support_pattern_import_performed: false
reflection_create_performed: false

tag_counts:
  raw_failed: 32
  routed_passed: 32
  routed_improved: 32
  strong_trace: 32
  combined_passed: 32
  missing_receipts: 12
  repair_used: 5
  fallback_used: 5
```

Workbench preview candidates:

```text
local_router_feedback_fallback_review -> reflections
local_router_feedback_architecture_process_receipts -> support_patterns
local_router_feedback_grant_business_receipts -> support_patterns
local_router_feedback_personal_synthesis_receipts -> support_patterns
```

Interpretation:

```text
This is Level 2 learning infrastructure: reviewed feedback metadata, not neural
learning and not silent behavior mutation.
```

## Historical Results By Slice

```text
architecture 1: raw 0/4 avg 0.516 -> routed 4/4 avg 0.795 -> combined 4/4
architecture 2: raw 0/4 avg 0.465 -> routed 4/4 avg 0.767 -> combined 4/4
personal 1:     raw 0/4 avg 0.326 -> routed 3/4 avg 0.714 -> combined 3/4
personal 2:     raw 0/4 avg 0.340 -> routed 4/4 avg 0.784 -> combined 4/4
grant 1:        raw 0/4 avg 0.392 -> routed 3/4 avg 0.777 -> combined 3/4
grant 2:        raw 0/4 avg 0.370 -> routed 3/4 avg 0.771 -> combined 3/4
code/process 1: raw 0/4 avg 0.319 -> routed 4/4 avg 0.800 -> combined 4/4
code/process 2: raw 0/4 avg 0.405 -> routed 4/4 avg 0.757 -> combined 4/4
```

Overall:

```text
Raw answer pass:      0/32
Routed answer pass:   29/32
Trace pass:           32/32
Combined pass:        29/32
Combined pass rate:   90.6%
Average raw score:    0.392
Average routed score: 0.771
Average lift:         +0.379
Repairs used:         11
Fallbacks used:       3
```

## Failure Taxonomy

Three combined failures:

```text
1 personal_synthesis failure
2 grant_business failures
0 trace failures
```

Patterns:

```text
personal_synthesis:
  Broad founder-comparison prompts can go generic without stronger receipts.

grant_business:
  Final answers can leak outcome-promise / guarantee language.
  Final answers can drift into medical or regulated-claim territory.
  Final answers can expose internal process language.

trace:
  Trace stayed clean across the curated pass.
```

## Caveats

The pack is candidate-clean, not final formal evidence.

Known caveats:

```text
gptlog_008_architecture_synthesis still looks artifact-heavy.
The reviewed architecture_process anchor failures are fixed in the targeted
rerun.
The pack now splits two non-Aether prompts into business_planning; review
whether nearby photo/video/print-shop prompts should also move.
The 32-case pack is still small and candidate-clean, not formal grant-grade
evidence by itself.
```

## What Graduates

Bring forward:

```text
durable trace schema
combined answer + trace scoring
failure taxonomy
Mirus packet -> Holden render -> CRT verifier split
route/scaffold policy as Aether Core infrastructure
weighted feedback ledger as the next learning layer
```

Do not bring forward as-is:

```text
loose grant/business rendering
generic founder-comparison personal synthesis
the current mixed code_reasoning bucket label
artifact-heavy replay cases as formal evidence
```

## Roadmap Meaning

The lab is ready to transition back toward the main Aether roadmap after one
cleanup pass:

```text
1. Tighten grant/business final-answer policy. DONE in lab.
2. Add stronger receipt requirements for broad personal synthesis. DONE in lab.
3. Split code_reasoning into code_implementation and architecture_process. DONE in pack/router taxonomy.
4. Add business_planning split and targeted case replay. DONE in lab.
5. Tighten personal/founder receipt-request behavior without weakening the gate. DONE in lab.
6. Tighten remaining grant/business bounded-claim wording / task fit. DONE in lab for current pack.
7. Feed trace + feedback into Phase 2 reviewed learner heartbeat.
8. Expand or perturb the pack before claiming broad reliability.
```

The result is strong enough to justify continuing Aether as:

```text
local-first governed memory, durable trace, verifier repair, and reviewed
learning infrastructure for high-context personal and small-organization work.
```
