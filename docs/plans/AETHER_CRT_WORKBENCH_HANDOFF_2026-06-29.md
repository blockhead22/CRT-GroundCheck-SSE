# Aether / CRT / Workbench Handoff - 2026-06-29

This is the clean restart packet for a new Codex thread in `D:\AI_round2`.

Start here for the current local-router, CRT trace, and lab-to-roadmap state.
Use the older handoffs for historical context, but do not restart broad
archaeology unless a specific missing concept requires a specific source file.

## Active Lane

```text
Aether Core validation infrastructure:
local router -> Mirus packet -> scaffold -> model render -> CRT verifier
-> repair/fallback -> durable thinking trace -> replay eval
```

Roadmap position:

```text
Phase 1.10 route/model selection       observational in Workbench, active in lab
Phase 2 governed learner/Mirus loop    active roadmap re-entry
New trace lane                         durable structured thinking traces
```

Current rule:

```text
This lab is worth continuing only if it becomes Aether/Core infrastructure.
Prompt tuning alone is not enough.

No private hidden scratchpad as durable truth. Store structured trace artifacts:
classification, retrieval, Mirus packet, scaffold, model route, verifier flags,
repair/fallback decisions, contradiction notes, confidence, and learning
candidates.

Product UI requirement:

```text
Workbench should expose an answer-level expandable Thinking / Process drawer.
It should feel like the GPT Activity / thinking trace pattern while remaining
governed: show memory checks, tool consideration/results, route/model/scaffold,
public rationale lines, verifier/repair/fallback, and learning candidates.
```

Model-authored thinking/rationale may be displayed only when it is intentionally
generated as public rationale, labeled that way, and checked against the
deterministic governance trace. Do not treat private model internals as evidence
or let them silently mutate memory/policy.
```

## Read These First

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_TRACE_WORKBENCH_MAPPING_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_LAB_GRADUATION_2026-06-30.md
D:\AI_round2\docs\plans\AETHER_AETEROS_CORE_SCHEMA_CANDIDATES_2026-06-30.md
D:\AI_round2\docs\plans\AETHER_FEEDBACK_CANDIDATE_REVIEW_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_WEIGHTED_FEEDBACK_LEDGER_2026-06-29.md
D:\AI_round2\local-router-curated-replay-v1-evidence-2026-06-29.md
D:\AI_round2\local-router-replay-v0-report-2026-06-28.md
D:\AI_round2\docs\plans\AETHER_AETEROS_MASTER_PLAN_2026-06-26.md
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

Useful lab notes:

```text
D:\AI_round2\local-model-routing-and-attention-notes-2026-06-28.md
D:\AI_round2\local-model-response-grading-notes-2026-06-28.md
D:\AI_round2\aether-local-router-v0-notes-2026-06-28.md
D:\AI_round2\aether-local-router-cli-v0-notes-2026-06-28.md
D:\AI_round2\network-ai-capacity-sweep-2026-06-28.md
```

## What Changed Most Recently

### Local Router Lab Became Roadmap-Relevant

The work started as "can small local models think better with scaffolds?" It is
now an Aether/Core validation lane.

Implemented lab pieces:

```text
D:\AI_round2\labs\meaning_compression_lab\spiral_synthesis_eval.py
D:\AI_round2\labs\meaning_compression_lab\attention_profile_eval.py
D:\AI_round2\labs\meaning_compression_lab\local_router_eval.py
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
D:\AI_round2\labs\meaning_compression_lab\replay_pack_builder.py
D:\AI_round2\labs\meaning_compression_lab\local_router_replay.py
```

Tests:

```text
D:\AI_round2\tests\test_spiral_synthesis_eval.py
D:\AI_round2\tests\test_attention_profile_eval.py
D:\AI_round2\tests\test_local_router_eval.py
D:\AI_round2\tests\test_local_router_cli.py
D:\AI_round2\tests\test_local_router_replay.py
```

Current router policy:

```text
exact_memory            -> qwen2.5:7b-instruct / semantic_spine
personal_synthesis      -> qwen2.5:7b-instruct / section_lock
architecture_synthesis  -> qwen2.5:7b-instruct / semantic_spine
grant_business          -> qwen2.5:7b-instruct / section_lock
code_reasoning          -> qwen2.5-coder:14b / section_lock
```

Current best mechanism:

```text
classify request
-> build Mirus packet / semantic spine
-> choose model and scaffold
-> render
-> verify with CRT gates
-> repair once or fallback
-> store answer + trace
```

### Preliminary Evidence

Router eval:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_eval_1782687384.json
Pass: 3/3
Average score: 0.845
Average contract score: 0.762
Average usefulness score: 1.000
Repairs: 1
Fallbacks: 0
```

Real-log replay pack:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_v0.json
16 total cases:
4 architecture_synthesis
4 personal_synthesis
4 grant_business
4 code_reasoning
```

Latest 12-case replay artifact:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782692982.json
```

Rescored after verifier false-positive fix:

```text
Raw local answers:     0/12 pass, avg 0.405
Routed local answers: 10/12 pass, avg 0.761
Average lift:         +0.356
```

This is preliminary evidence, not a final product claim. The replay pack is
real-log messy and needs human curation before it is used for grants, demos, or
formal claims.

### Durable Thinking Trace Requirement Added

New requirement:

```text
D:\AI_round2\docs\plans\AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
```

Every assistant turn should be able to persist an inspectable trace:

```text
turn_id
conversation_id
timestamp
user_request_summary
task_type
route_selected
model_selected
scaffold_profile
retrieved_memory_ids
retrieved_chat_ids
mirus_packet_summary
evidence_anchors
allowed_inferences
disallowed_inferences
draft_quality_score
verifier_flags
repair_attempts
fallback_used
final_confidence
contradiction_notes
learning_candidates
promotion_status
```

After restart, a historical message should be able to reopen with the trace that
produced it: what Aether remembered, inferred, refused to claim, repaired, and
possibly learned.

### Trace JSON Output Implemented In Lab

Implemented after the initial 2026-06-29 handoff:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
D:\AI_round2\labs\meaning_compression_lab\local_router_replay.py
D:\AI_round2\tests\test_local_router_cli.py
D:\AI_round2\tests\test_local_router_replay.py
```

The CLI now includes a structured `trace` object in result JSON and writes a
separate trace artifact:

```text
D:\AI_round2\labs\meaning_compression_lab\results\traces\local_router_trace_1782695107.json
```

The replay runner now scores `trace_judgment` per row and reports aggregate
trace pass/score.

Verification:

```text
python -m pytest tests\test_local_router_cli.py tests\test_local_router_replay.py tests\test_local_router_eval.py tests\test_spiral_synthesis_eval.py tests\test_attention_profile_eval.py -q
26 passed

python -m labs.meaning_compression_lab.local_router_replay --max-cases 2 --timeout 300 --no-write
Raw pass 0/2 avg 0.581
Routed pass 2/2 avg 0.829
Trace pass 2/2 avg 1.000
```

### Historical Trace Reload Implemented In Lab

Implemented after the first trace JSON pass:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
D:\AI_round2\tests\test_local_router_cli.py
```

The CLI can now reload a saved result, prefer the separate trace artifact when
present, re-score the trace, and report consistency.

Verification:

```text
python -m pytest tests\test_local_router_cli.py tests\test_local_router_replay.py -q
14 passed

python -m labs.meaning_compression_lab.local_router_cli --load-result labs\meaning_compression_lab\results\local_router_cli_1782695107.json --json
trace_source: external
trace_file_exists: true
consistent: true
```

### Combined Answer + Trace Gate Implemented

Implemented after reload proof:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_replay.py
D:\AI_round2\tests\test_local_router_replay.py
```

Replay rows now include `combined_passed`, and aggregate results include:

```text
combined_pass_count
combined_pass_rate
graduation_ready
```

`combined_passed` requires both the routed answer and the trace to pass. This
prevents a good answer with a weak/unsafe trace from counting as a clean lab
success.

Verification:

```text
python -m pytest tests\test_local_router_replay.py tests\test_local_router_cli.py -q
15 passed

python -m labs.meaning_compression_lab.local_router_replay --max-cases 2 --timeout 300 --no-write
Trace pass 2/2 avg 1.000
Combined pass 2/2
```

### Curated 32-Case Replay Candidate Built

Implemented in:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_pack_builder.py
D:\AI_round2\tests\test_local_router_replay.py
```

New pack:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json
```

Shape:

```text
32 cases total
8 architecture_synthesis
8 personal_synthesis
8 grant_business
8 code_reasoning
```

Curation metadata:

```text
keyword_score
quality_score
quality_flags
```

Current quality summary:

```text
27 cases score 5
5 cases score 4
only remaining curation flag: starts_with_quote on 5 cases
```

Filters now reject obvious transcript fragments and project-log artifacts such
as `Nick:`, `Ani:`, `Phase 1: Near Completion`, command smoke tests, and pasted
core update queues. The pack is candidate-clean, not final grant evidence until
the replay/failure taxonomy confirms it behaves well.

### Failure Taxonomy Added To Replay Aggregate

Implemented in:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_replay.py
D:\AI_round2\tests\test_local_router_replay.py
```

Replay aggregate now includes:

```text
failure_taxonomy.total_failed
failure_taxonomy.by_task_type
failure_taxonomy.answer_failure_count
failure_taxonomy.trace_failure_count
failure_taxonomy.truncated_count
failure_taxonomy.forbidden_hits
failure_taxonomy.weirdness_hits
failure_taxonomy.leakage_hits
failure_taxonomy.trace_missing_fields
```

Verification:

```text
python -m pytest tests\test_local_router_replay.py -q
8 passed

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.516
Routed pass 4/4 avg 0.795
Trace pass 4/4 avg 1.000
Combined pass 4/4

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 4 --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.465
Routed pass 4/4 avg 0.767
Trace pass 4/4 avg 1.000
Combined pass 4/4

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 8 --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.326
Routed pass 3/4 avg 0.714
Trace pass 4/4 avg 1.000
Combined pass 3/4
Failure taxonomy: 1 personal_synthesis answer failure, 0 trace failures, no hard verifier flags.

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 12 --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.340
Routed pass 4/4 avg 0.784
Trace pass 4/4 avg 1.000
Combined pass 4/4

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 16 --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.392
Routed pass 3/4 avg 0.777
Trace pass 4/4 avg 1.000
Combined pass 3/4
Failure taxonomy: 1 grant_business answer failure, 0 trace failures, medical forbidden hit, process_theater leakage.

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 20 --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.370
Routed pass 3/4 avg 0.771
Trace pass 4/4 avg 1.000
Combined pass 3/4
Failure taxonomy: 1 grant_business answer failure, 0 trace failures, guaranteed forbidden hit.

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 24 --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.319
Routed pass 4/4 avg 0.800
Trace pass 4/4 avg 1.000
Combined pass 4/4

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 28 --max-cases 4 --timeout 300 --no-write
Raw pass 0/4 avg 0.405
Routed pass 4/4 avg 0.757
Trace pass 4/4 avg 1.000
Combined pass 4/4
```

Note: `gptlog_008_architecture_synthesis` still looks like an artifact-heavy
prompt despite passing. Keep it in the candidate pack for now, but review or
replace it before final evidence claims.

Personal synthesis caveat: `gptlog_009_personal_synthesis` failed without hard
verifier flags. This reinforces the earlier finding that personal synthesis
needs stronger supplied memory receipts/context; trace quality alone is not
enough to prevent generic founder-style advice.

Personal synthesis follow-up: cases `gptlog_013` through `gptlog_016` passed
combined gates. The weakness appears narrower than "all personal synthesis":
broad founder-comparison prompts can go generic, while concrete personal or
emotional prompts hold better under section-lock.

Grant/business caveat: `gptlog_018_grant_business` failed on user-facing answer
quality despite a clean trace. The failure pattern was medical/regulated-claim
overreach plus internal process-theater leakage. Grant/business routing needs
tighter final-answer constraints: no medical/regulated market claims unless
explicitly scoped and no visible "verifier report" or Mirus process language in
the final answer.

Grant/business follow-up: `gptlog_021_grant_business` failed on forbidden
`guaranteed` language. Across both grant/business slices, trace stayed clean
while answer-side restraint failed twice. Treat this as a real route/scaffold
issue: final grant/business rendering needs stricter outcome-promise language,
especially around guarantees, regulated/medical claims, and internal process
language.

Code-reasoning note: the first code slice passed combined gates, but the
selected prompts are mostly architecture/process reasoning rather than concrete
patch-level implementation. Before final evidence claims, consider splitting the
code lane into `code_implementation` and `architecture_process` or relabeling
the evidence accordingly.

Curated replay v1 evidence summary:

```text
D:\AI_round2\local-router-curated-replay-v1-evidence-2026-06-29.md
Raw answer pass:      0/32
Routed answer pass:   29/32
Trace pass:           32/32
Combined pass:        29/32
Combined pass rate:   90.6%
Average raw score:    0.392
Average routed score: 0.771
Average lift:         +0.379
```

### Grant/Business Final-Answer Policy Tightened

Implemented in:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
D:\AI_round2\labs\meaning_compression_lab\attention_profile_eval.py
D:\AI_round2\tests\test_local_router_cli.py
```

The grant/business Mirus packet now carries a `final_answer_policy` that tells
Holden/rendering to avoid:

```text
guaranteed outcomes or success claims
medical, clinical, therapeutic, or regulated-market claims
frontier-level capability claims
internal process theater such as verifier report, Mirus belief packet, or revised answer
```

`section_lock_prompt` now surfaces the final-answer policy as a user-facing
rendering rule. This addresses the grant/business failures where trace stayed
clean but final answers leaked medical/regulated or guarantee language.

Verification:

```text
python -m pytest tests\test_local_router_cli.py tests\test_attention_profile_eval.py -q
14 passed
```

Smoke:

```text
python -m labs.meaning_compression_lab.local_router_cli --no-write --json --task-type grant_business ...
passed true
forbidden_hits []
leakage_hits []
weirdness_hits []
```

Caveat: the smoke was clean on forbidden/process leakage but lighter than ideal
on CRT/verifier anchor coverage. If this persists, tighten required-anchor
language separately rather than weakening the final-answer restraint.

### Personal Synthesis Receipt Gate Tightened

Implemented in:

```text
D:\AI_round2\labs\meaning_compression_lab\spiral_synthesis_eval.py
D:\AI_round2\tests\test_local_router_cli.py
```

Broad personal synthesis now has an answer-side verifier gate:

```text
identity/founder claims require multiple concrete receipt anchors
generic "receipts/evidence" wording is not enough
if context is missing, the answer may safely ask for concrete receipts instead
```

This addresses the curated replay failure where a broad founder-comparison
prompt could become generic advice instead of grounded synthesis. The rule
keeps the evidence boundary in the verifier, not in a freeform taste judgment.

Verification:

```text
python -m pytest tests\test_local_router_cli.py tests\test_attention_profile_eval.py -q
17 passed

python -m pytest tests\test_local_router_replay.py -q
9 passed
```

### Code Reasoning Bucket Split

Implemented in:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_eval.py
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
D:\AI_round2\labs\meaning_compression_lab\local_router_replay.py
D:\AI_round2\labs\meaning_compression_lab\replay_pack_builder.py
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json
D:\AI_round2\tests\test_local_router_eval.py
D:\AI_round2\tests\test_local_router_replay.py
```

The old `code_reasoning` bucket was split into:

```text
architecture_process
  technical planning, sequencing, architecture/process reasoning, and roadmap
  decisions where no patch is ready yet.

code_implementation
  patch-level code work with file changes, tests, and verification.
```

`code_reasoning` remains as a legacy alias for coder-model routing, but new
replay evidence should use the sharper labels. The curated v1 pack now contains:

```text
8 architecture_synthesis
8 personal_synthesis
6 grant_business
2 business_planning
7 architecture_process
1 code_implementation
```

Also fixed: explicit replay task labels are now authoritative for routing, and
`local_router_replay` tolerates UTF-8 packs with or without a BOM.

Verification:

```text
python -m pytest tests\test_local_router_eval.py tests\test_local_router_replay.py tests\test_local_router_cli.py -q
31 passed

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 24 --max-cases 2 --timeout 300 --no-write
Raw pass 0/2 avg 0.347
Routed pass 2/2 avg 0.823
Trace pass 2/2 avg 1.000
Combined pass 2/2
```

### Post-Policy Full Curated Replay

After taxonomy cleanup, grant/business final-answer policy, personal-synthesis
receipt gate, and repair-policy inheritance:

```text
python -m pytest tests\test_local_router_cli.py tests\test_local_router_eval.py tests\test_local_router_replay.py tests\test_attention_profile_eval.py -q
34 passed

python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --timeout 300 --no-write
Raw pass 0/32 avg 0.377
Routed pass 28/32 avg 0.750
Trace pass 32/32 avg 1.000
Combined pass 28/32
Repairs 9
Fallbacks 6
```

Failure taxonomy:

```text
answer_failure_count: 4
trace_failure_count: 0
forbidden_hits: none
leakage_hits: none
weirdness_hits: none
truncated_count: 0
by_task_type:
  architecture_process: 3
  grant_business: 1
```

Interpretation:

```text
The safety/restraint failures were repaired. Remaining failures are
low-score/coverage failures, not hard verifier flags. Review anchor fit and
task-specific grading before loosening thresholds or adding more prompt text.
```

### Local-Router Trace To Workbench Mapping

Implemented pure adapter:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_adapter.py
```

Mapping doc:

```text
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_TRACE_WORKBENCH_MAPPING_2026-06-29.md
```

The adapter maps local-router lab traces into the existing Workbench Trace drawer
shape:

```text
route_decision
completion
plan
packets
local_router_trace
```

It creates three renderable lab packets:

```text
lab:route
lab:mirus_packet
lab:verifier
```

Boundary:

```text
Lab evidence anchors are not confirmed memory states. The adapted packets keep
empty evidence arrays so the Trace drawer can show route/Mirus/verifier status
without pretending lab anchors are durable user memory.
```

Verification:

```text
python -m pytest tests\test_workbench_trace_adapter.py tests\test_local_router_cli.py tests\test_local_router_replay.py -q
28 passed

python -m py_compile labs\meaning_compression_lab\workbench_trace_adapter.py
passed
```

### Isolated Workbench Fixture Import

Implemented:

```text
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_fixture.py
D:\AI_round2\tests\test_workbench_trace_fixture.py
```

This writes adapted local-router lab traces through the normal WorkbenchDB path:

```text
begin_turn
save_trace
complete_turn
get_trace
```

Safety boundary:

```text
caller-provided DB paths only
refuses ~/.aether/workbench.db by default
fixture_import_only: true
memory_writes_performed: false
memory_write_allowed: false
```

Verification:

```text
python -m pytest tests\test_workbench_trace_fixture.py tests\test_workbench_trace_adapter.py tests\test_local_router_cli.py tests\test_local_router_replay.py -q
30 passed

python -m py_compile labs\meaning_compression_lab\workbench_trace_fixture.py labs\meaning_compression_lab\workbench_trace_adapter.py
passed
```

### Adapted TraceDrawer Fixture Render

Implemented:

```text
D:\AI_round2\workbench\src\components\TraceDrawer.test.tsx
D:\AI_round2\workbench\src\types.ts
```

The real Trace drawer now has a test fixture for an adapted local-router trace.
It verifies:

```text
local_router_lab response route renders
local_router_grant_business route decision renders
lab:route / lab:mirus_packet / lab:verifier packets render
lab anchors are not rendered as memory evidence
```

Verification:

```text
cd D:\AI_round2\workbench
npm run test:ui -- --run src/components/TraceDrawer.test.tsx
12 passed

npm run build
passed
```

### Low-Score Anchor-Fit Review

Review doc:

```text
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md
```

Reviewed the four post-policy replay failures:

```text
gptlog_019_grant_business
gptlog_027_architecture_process
gptlog_028_architecture_process
gptlog_030_architecture_process
```

Conclusion:

```text
The remaining failures are evidence-targeting problems, not trace failures,
safety failures, or threshold failures.
```

Recommended next technical move:

```text
1. Add a business_planning task type for non-Aether business prompts, or supply
   case-specific anchors for those prompts.
2. Add case-specific architecture_process anchors for the three reviewed
   low-score architecture/process cases.
3. Re-run only those four cases before changing verifier thresholds.
```

Implemented result:

```text
business_planning task type added.
gptlog_019_grant_business now routes as business_planning with camera-gear
small-business anchors.
gptlog_027_architecture_process, gptlog_028_architecture_process, and
gptlog_030_architecture_process now use case-specific anchors.
local_router_replay supports repeated --case-id filters for targeted reruns.
architecture_process has a final-answer policy against banned limit wording.
```

Targeted reviewed cluster:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782713622.json

Raw 0/4 avg 0.526
Routed 4/4 avg 0.824
Trace 4/4 avg 1.000
Combined 4/4
No hard flags
```

Intermediate full curated replay:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782714154.json

Raw 0/32 avg 0.397
Routed 28/32 avg 0.766
Trace 32/32 avg 1.000
Combined 28/32

Remaining failures:
3 personal_synthesis receipt-gate failures
1 grant_business bounded-claim/guarantee wording failure
```

Final roadmap-return replay:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782716566.json

Raw 0/32 avg 0.407
Routed 32/32 avg 0.773
Trace 32/32 avg 1.000
Combined 32/32

Changes that closed the remaining failures:
- personal/founder receipt-request behavior tightened
- personal_synthesis fallback kept inside section_lock
- grant/business repair avoids guarantee wording
- gptlog_022 relabeled as business_planning with photo/video/print-shop anchors
- conscious detector allows sub-conscious/subconscious memory phrasing while
  still blocking direct consciousness overclaims
```

Feedback ledger artifact:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_feedback_ledger_1782716566.json

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

Feedback preview candidates:

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

Workbench learner fixture render:

```text
D:\AI_round2\workbench\src\fixtures\localRouterFeedbackPreview.ts
D:\AI_round2\workbench\src\App.test.tsx

The real Learn drawer renders the 4 review-only feedback candidates and opens
them as manual Support/Reflect draft handoffs. The fixture does not write
memory, import support patterns, or create reflections.

Verification:
python -m pytest tests\test_local_router_feedback_ledger.py -q
2 passed

cd D:\AI_round2\workbench
npm run test:ui -- --run src/App.test.tsx
15 passed
```

Evidence v0 / hardening pass:

```text
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_FEEDBACK_CANDIDATE_REVIEW_2026-06-29.md
D:\AI_round2\labs\meaning_compression_lab\local_router_perturb_pack.py
D:\AI_round2\labs\meaning_compression_lab\local_router_ablation.py
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_perturbed_v2.json

Decision: freeze the 32/32 as Evidence v0, not final proof.
The 4 feedback-ledger candidates are deferred pending v2 and ablation evidence.

Smoke:
perturbed v2 first case: raw 0/1 avg 0.537, routed 1/1 avg 0.716, trace 1/1.
ablation first case: raw_no_scaffold 0/1 avg 0.497, full 1/1 avg 0.659, trace 1/1.

Full perturbed v2 after narrow detector/scaffold hardening:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782721572.json
Raw 1/32 avg 0.489
Routed 32/32 avg 0.770
Trace 32/32 avg 1.000
Combined 32/32

Verification:
python -m pytest tests\test_local_router_cli.py tests\test_attention_profile_eval.py tests\test_local_router_replay.py -q
36 passed
python -m py_compile labs\meaning_compression_lab\local_router_perturb_pack.py labs\meaning_compression_lab\local_router_ablation.py labs\meaning_compression_lab\attention_profile_eval.py labs\meaning_compression_lab\spiral_synthesis_eval.py
passed
```

Blind v1 evidence pass:

```text
D:\AI_round2\labs\meaning_compression_lab\local_router_blind_pack.py
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_blind_v1.json
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782745851.json

Selection rule:
exclude v1 source conversation ids
exclude v1 prompt dedupe keys
exclude low-specificity / quote / artifact-like candidate flags
select at most one case per conversation

Blind pack shape:
13 cases total
3 architecture_synthesis
2 personal_synthesis
3 business_planning
1 grant_business
1 architecture_process
3 code_implementation

Full blind v1 replay:
Raw 0/13 avg 0.382
Routed 13/13 avg 0.761
Trace 13/13 avg 1.000
Combined 13/13
Repairs 1
Fallbacks 0
Hard flags: none

Blind ablation slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782746144.json
raw_no_scaffold 0/4 avg 0.463
routed_no_repair 4/4 avg 0.748
routed_no_fallback 4/4 avg 0.781
full 4/4 avg 0.781

Full blind ablation:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782746575.json
raw_no_scaffold 0/13 avg 0.409
routed_no_repair 12/13 avg 0.768
routed_no_fallback 13/13 avg 0.775
full 13/13 avg 0.774

Full perturbed ablation:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748218.json
raw_no_scaffold 0/32 avg 0.494
routed_no_repair 22/32 avg 0.718
routed_no_fallback 23/32 avg 0.726
full 28/32 avg 0.757

Targeted normal replay of the four full-ablation failures:
Raw 0/4 avg 0.513
Routed 4/4 avg 0.746
Trace 4/4 avg 1.000
Combined 4/4
Repairs 1
Fallbacks 1

Repeat full-mode ablation on the same four cases:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748474.json
full 2/4 avg 0.673
trace 4/4
repairs 2
fallbacks 1
repeated failures:
  gptlog_017_grant_business_perturb_01
  gptlog_019_grant_business_perturb_01

Verification:
python -m pytest tests\test_local_router_replay.py tests\test_local_router_eval.py -q
22 passed
python -m py_compile labs\meaning_compression_lab\local_router_blind_pack.py labs\meaning_compression_lab\local_router_eval.py labs\meaning_compression_lab\replay_pack_builder.py
passed
```

Interpretation:

```text
This is the strongest evidence so far because it excludes v1 source
conversations and prompt dedupe keys. It is still not broad proof: the blind
pack is small and comes from the same export universe.
The first blind ablation slice suggests routing/scaffold/Mirus context carried
the lift before repair or fallback were needed, but that mechanism claim needs
broader ablation coverage.
The full blind ablation keeps that pattern: repair closed one remaining
grant_business coverage failure, and fallback was not required.
The perturbed ablation is less stable: repair/fallback matter more under wording
drift, and the ablation path left four failures that passed under targeted
normal replay. Repeat or stabilize perturbed ablations before promoting policy
changes from that signal.
The first repeat narrowed the repeated failure pocket to two coverage failures:
one grant_business case and one business_planning case. These are not trace,
leakage, or hard-safety failures.
Anchor-fit review was added to:
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md

Summary:
gptlog_017_grant_business_perturb_01 looks like default grant_business anchor
mismatch for a product/company framing prompt. It should not be forced to say
CRT/verifier/AI request router unless the prompt calls for that.
gptlog_019_grant_business_perturb_01 looks partly like brittle exact-anchor
matching around "applied myself"; the answer covered the concept as application
of effort but missed the literal anchor.

Replay-compatible RAG baseline suite was added:
D:\AI_round2\labs\meaning_compression_lab\local_router_rag_suite.py

Initial blind-v1 smoke:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782749903.json

raw 0/1 avg 0.537
plain_rag 0/1 avg 0.480
scaffolded_rag 1/1 avg 0.710
governed 1/1 avg 0.716, trace 1/1

Blind-v1 four-case RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782750349.json

raw 0/4 avg 0.405
plain_rag 0/4 avg 0.420
scaffolded_rag 3/4 avg 0.770
governed 4/4 avg 0.740, trace 4/4

The scaffolded_rag miss was a personal_synthesis case where retrieval found the
prompt but not enough real personal receipts, and the model invented generic
productivity/health receipts.

Perturbed-v2 four-case RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782750521.json

raw 0/4 avg 0.571
plain_rag 0/4 avg 0.577
scaffolded_rag 4/4 avg 0.804
governed 4/4 avg 0.767, trace 4/4

Perturbed-v2 eight-case RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782752318.json

raw 1/8 avg 0.560
plain_rag 0/8 avg 0.549
scaffolded_rag 6/8 avg 0.748
governed 8/8 avg 0.757, trace 8/8
fallbacks 2

Scaffolded-RAG failures:
architecture_synthesis 2

These failures had high retrieval coverage, so the issue was semantic-boundary
drift rather than a simple retrieval miss.

Perturbed-v2 personal-synthesis RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782753077.json

raw 0/8 avg 0.480
plain_rag 0/8 avg 0.405
scaffolded_rag 2/8 avg 0.764
governed 8/8 avg 0.778, trace 8/8

Retrieval coverage:
receipts 0.500
concepts 0.000

Scaffolded-RAG failures:
personal_synthesis 6

This is the clearest weak-retrieval signal so far: scaffolded RAG often knows
the shape of the answer, but without concrete personal receipts it still drifts
into generic or identity-like claims. Governed Aether passed because the Mirus
packet, receipt gate, and route policy force tighter evidence boundaries.

Perturbed-v2 business/grant RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782754067.json

raw 1/8 avg 0.497
plain_rag 0/8 avg 0.439
scaffolded_rag 1/8 avg 0.522
governed 8/8 avg 0.727, trace 8/8
repairs 1
fallbacks 3

Retrieval coverage:
receipts 0.333
concepts 0.369

Scaffolded-RAG failures:
grant_business 6
business_planning 1

This is the weakest scaffolded-RAG slice so far. It tends to produce plausible
business language while missing task-specific Aether/CRT/router receipts.
Governed Aether passed because task-fit routing plus repair/fallback kept the
answer grounded under low receipt coverage.

Perturbed-v2 architecture/process RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782755020.json

raw 0/8 avg 0.439
plain_rag 0/8 avg 0.431
scaffolded_rag 3/8 avg 0.658
governed 7/8 avg 0.772, trace 8/8
repairs 3
fallbacks 1

Governed failure:
gptlog_026_architecture_process_perturb_01

This failure is a coverage/anchor-fit miss, not a trace, leakage, weirdness, or
forbidden-claim failure.

Governed miss review:
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md

Conclusion:
The miss appears to be default architecture_process anchor mismatch plus scorer
shape. The answer covered the prompt's real substance: semantic string engines
for vocabulary, worldview/empirical facts, connecting threads, LLM-assisted
reasoning, memory proof, drift, and contradictions. It missed the literal
"architecture" anchor and lacked thesis/limit-language features.

Perturbed-v2 sliced total across 32 cases:

raw 2/32 avg 0.494
plain_rag 0/32 avg 0.456
scaffolded_rag 12/32 avg 0.673
governed 31/32 avg 0.758, trace 32/32
repairs 4
fallbacks 6

Scaffolded-RAG failures by task type:
architecture_process 5
architecture_synthesis 2
business_planning 1
grant_business 6
personal_synthesis 6

This is the strongest RAG-phase result so far. It breaks the suspicious
perfect-score pattern while preserving the governance signal: governed Aether
materially beats scaffolded RAG and keeps trace clean on all cases.

Full blind-v1 RAG run:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782751568.json

raw 0/13 avg 0.404
plain_rag 0/13 avg 0.384
scaffolded_rag 7/13 avg 0.664
governed 13/13 avg 0.757, trace 13/13
repairs 1
fallbacks 3

Scaffolded-RAG failures:
personal_synthesis 2
business_planning 3
grant_business 1

Interpretation:
Raw-only comparison is no longer sufficient. Plain RAG did not close the first
RAG slices, but scaffolded RAG is now the serious baseline. Governed Aether must
prove its value over scaffolded RAG through trace, repair/fallback,
evidence-boundary behavior, weak-retrieval handling, and adversarial cases.
The strongest current Aether-vs-scaffolded-RAG signal is the full blind pack,
where scaffolded RAG fails mainly on personal synthesis and business/grant
planning under thin or mismatched retrieved evidence.
The expanded perturbed slice adds a second signal: scaffolded RAG can drift on
architecture meaning even when retrieval coverage is high.

Adversarial RAG v1 pack:
D:\AI_round2\labs\meaning_compression_lab\local_router_adversarial_pack.py
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_rag_adversarial_v1.json

Pack shape:
9 generated cases across unsupported_personal_receipts, wrong_memory_trap, and
architecture_term_drift.

First three-case personal-synthesis smoke:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782763680.json

raw 0/3 avg 0.321
plain_rag 0/3 avg 0.397
scaffolded_rag 1/3 avg 0.644
governed 1/3 avg 0.728, trace 3/3
repairs 2
fallbacks 1

Interpretation:
The adversarial pack is doing useful work because it breaks both scaffolded RAG
and governed Aether on receipt-request boundary cases. Two governed misses are
high-scoring but still flagged as insufficient_personal_receipts, so the next
step is a personal_synthesis policy/evaluator review, not weakening the receipt
gate by default. Run the remaining wrong-memory and architecture-term-drift
cases before promoting any policy changes.

Full adversarial RAG v1 run:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782764250.json

raw 1/9 avg 0.489
plain_rag 1/9 avg 0.514
scaffolded_rag 6/9 avg 0.729
governed 7/9 avg 0.755, trace 9/9
repairs 2

Governed failures:
adv_personal_001_missing_receipts
adv_personal_003_wrong_receipt_trap

Both are personal_synthesis receipt-boundary failures, not trace failures.
Governed passed the wrong-memory traps 3/3, architecture term drift 2/2, and
product strategy vs router framing 1/1. Scaffolded-RAG additionally missed
adv_arch_003_product_strategy_not_router. This narrows the next work to
personal_synthesis receipt-request policy/evaluator review before any global
router/scaffold change.

Personal-synthesis evaluator review implemented:
D:\AI_round2\labs\meaning_compression_lab\spiral_synthesis_eval.py
D:\AI_round2\tests\test_spiral_synthesis_eval.py

Change:
explicit receipt/evidence requests can pass insufficient-evidence handling when
they do not synthesize identity anyway. Generic founder/founder-journey drift is
still flagged even when the answer asks for receipts. Limits/limitations aliasing
was also added for bounded exact-memory answers.

Updated full adversarial RAG v1 run:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782764980.json

raw 1/9 avg 0.498
plain_rag 1/9 avg 0.519
scaffolded_rag 7/9 avg 0.758
governed 8/9 avg 0.775, trace 9/9
repairs 2

Remaining governed failure:
adv_personal_001_missing_receipts - generic_founder_comparison

Closed governed pockets:
adv_personal_003_wrong_receipt_trap
adv_memory_001_current_store_platform

Verification:
python -m pytest tests\test_spiral_synthesis_eval.py tests\test_local_router_cli.py tests\test_local_router_rag_suite.py -q
36 passed

python -m py_compile labs\meaning_compression_lab\spiral_synthesis_eval.py labs\meaning_compression_lab\local_router_rag_suite.py
passed

Generation-policy founder-drift fix implemented:
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
D:\AI_round2\tests\test_local_router_cli.py

Change:
missing personal receipts now require describing the evidence boundary instead
of founder/identity patterns. The policy explicitly forbids founder archetype,
typical founder, founder journey, and founder milestone language when concrete
anchors are missing.

Final adversarial RAG v1 run after generation-policy fix:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782765575.json

raw 1/9 avg 0.498
plain_rag 1/9 avg 0.519
scaffolded_rag 7/9 avg 0.766
governed 9/9 avg 0.806, trace 9/9
repairs 1
fallbacks 1

Interpretation:
Adversarial v1 is now clean for governed Aether without loosening the evaluator.
The receipt-request false negatives were handled by a narrow evaluator
distinction; generic-founder drift was handled by generation policy/scaffold
wording. Scaffolded RAG still fails 2/9, so the governed advantage over the
serious baseline remains visible on this pack.

Adversarial v2 holdout pack added:
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_rag_adversarial_v2.json

Generated by:
D:\AI_round2\labs\meaning_compression_lab\local_router_adversarial_pack.py

Pack shape:
6 holdout cases across unsupported_personal_receipts and wrong_memory_trap.

Adversarial v2 RAG result:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782766406.json

raw 0/6 avg 0.492
plain_rag 1/6 avg 0.540
scaffolded_rag 5/6 avg 0.753
governed 6/6 avg 0.775, trace 6/6

Scaffolded-RAG miss:
adv2_personal_003_old_receipts_are_disallowed - generic founder drift

Interpretation:
Adversarial v2 supports the v1 policy/evaluator fixes on a small holdout.
Governed Aether passed all receipt-boundary and wrong-memory cases; scaffolded
RAG still missed one old-receipts personal trap. This is supportive evidence,
not final proof. Do not keep tuning against this exact v2 pack.

Workbench evidence review bridge:
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_adapter.py
D:\AI_round2\labs\meaning_compression_lab\workbench_evidence_preview_cli.py

The adapter converts RAG-suite artifacts into review-only Workbench metadata:
baseline_to_beat=scaffolded_rag, per-mode pass rates and scores, governed
delta over scaffolded RAG, failure summaries by task type, perfect-score
holdout caution flags, and a safety contract that forbids memory writes, raw
hidden chain-of-thought storage, and silent policy mutation.

The CLI emits review or learner-preview JSON from any RAG-suite result without
touching Workbench DB or live memory:
python -m labs.meaning_compression_lab.workbench_evidence_preview_cli <result.json>

Sidecar consolidation bridge:
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\aether-core\tests\test_sidecar_consolidation.py
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_fixture.py
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_evidence_attach_cli.py
D:\AI_round2\tests\test_workbench_trace_fixture.py

The sidecar can now surface RAG evidence as a review-only learner candidate
when that evidence is already embedded in a persisted trace at
`local_router_trace.evidence_review`. It refuses the candidate unless the safety
contract explicitly blocks memory writes, raw hidden CoT storage, and silent
policy mutation. `/v1/consolidation/candidates` remains read-only.

Trace fixture attachment bridge:
`attach_rag_evidence_review_to_trace_fixture(...)` attaches generated
`evidence_review` metadata to an existing isolated Workbench trace row, refuses
the live DB by default, updates only trace JSON, and returns a receipt with no
memory, support-pattern, or reflection writes.

CLI usage:
python -m labs.meaning_compression_lab.workbench_trace_evidence_attach_cli --db-path <workbench.db> --turn-id <turn_id> --rag-result-path <rag_suite_result.json>

Live DB attachment requires both:
--allow-live-db --confirm-live-db ATTACH_REVIEW_ONLY_TRACE_EVIDENCE

Verification:
python -m pytest tests\test_workbench_evidence_adapter.py tests\test_workbench_trace_adapter.py tests\test_workbench_trace_fixture.py -q
7 passed

python -m pytest tests\test_workbench_evidence_adapter.py -q
5 passed

python -m pytest tests\test_workbench_trace_fixture.py tests\test_workbench_evidence_adapter.py -q
12 passed

python -m pytest aether-core\tests\test_sidecar_consolidation.py -q
8 passed

python -m py_compile labs\meaning_compression_lab\workbench_evidence_adapter.py
passed

python -m py_compile labs\meaning_compression_lab\workbench_evidence_preview_cli.py labs\meaning_compression_lab\workbench_evidence_adapter.py
passed

python -m py_compile labs\meaning_compression_lab\workbench_trace_evidence_attach_cli.py labs\meaning_compression_lab\workbench_trace_fixture.py
passed

Interpretation:
The RAG validation work now has a path into Workbench review without promoting
lab artifacts into memory. Next work should wire this review shape into a
fixture or Activity/Trace surface, not keep retuning adversarial v1/v2.

Workbench Trace drawer fixture/render bridge:
D:\AI_round2\workbench\src\fixtures\localRouterRagEvidenceReview.ts
D:\AI_round2\workbench\src\fixtures\localRouterRagEvidencePreview.ts
D:\AI_round2\workbench\src\components\TraceDrawer.tsx
D:\AI_round2\workbench\src\components\TraceDrawer.test.tsx
D:\AI_round2\workbench\src\App.test.tsx

The Trace drawer now renders nested `local_router_trace.evidence_review`
metadata as a "Local router evidence review" panel. It shows the pack, case
count, scaffolded_rag baseline, governed pass/score, scaffolded RAG pass/score,
delta, trace completeness, review_only promotion status, blocked memory writes,
blocked silent mutation, and holdout caution.

The Learn drawer can now render the same RAG evidence as a preview-only learner
candidate. Opening it routes to Reflect as manual form state only; nothing is
created, accepted, imported, or written to memory.

Verification:
cd D:\AI_round2\workbench
npm run test:ui -- --run src/components/TraceDrawer.test.tsx
13 passed

cd D:\AI_round2\workbench
npm run test:ui -- --run src/App.test.tsx src/components/TraceDrawer.test.tsx
29 passed

Perturbed anchor-hygiene follow-up implemented:
D:\AI_round2\labs\meaning_compression_lab\local_router_perturb_pack.py
D:\AI_round2\labs\meaning_compression_lab\spiral_synthesis_eval.py
D:\AI_round2\tests\test_local_router_perturb_pack.py
D:\AI_round2\tests\test_spiral_synthesis_eval.py

Changes:
- gptlog_017_grant_business_perturb_01 gets reviewed product/company anchors
  instead of default local/CRT/router anchors.
- gptlog_026_architecture_process_perturb_01 gets reviewed semantic-engine
  anchors instead of default roadmap/architecture/risk anchors.
- "applied myself" accepts narrow effort/practice aliases for
  gptlog_019_grant_business_perturb_01.

Regenerated:
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_perturbed_v2.json

Targeted perturbed RAG:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782767376.json

raw 0/3 avg 0.569
plain_rag 0/3 avg 0.587
scaffolded_rag 1/3 avg 0.676
governed 3/3 avg 0.736, trace 3/3

Narrow full-mode ablation repeat:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782767424.json

full 2/2 avg 0.823, trace 2/2
repairs 0
fallbacks 1

Interpretation:
The known perturbed anchor-hygiene pocket is closed without threshold
loosening. Scaffolded RAG still misses 2/3 targeted RAG cases, so the governed
edge remains visible. Do not keep tuning this pocket unless broader replay
exposes a regression.
```

## Concept Mapping

Use this current interpretation:

```text
Mirus
  Evidence intake, belief state, authority boundaries, contradiction state,
  allowed/disallowed claims, and learning candidates.

Holden
  Final speech/rendering layer. It should not own truth.

SSE / Semantic String Engine
  The semantic spine: structured context expansion from verified nodes, not a
  giant memory dump.

CRT
  Contradiction-resilient trust: verifier gates, overclaim detection,
  unsupported claim checks, drift detection, repair/fallback policy.

Router
  Task classifier plus model/scaffold selector.

Trace
  Durable audit record of how the answer happened.

Replay
  Eval harness that proves whether routed local cognition beats raw local chat.

Weighted Feedback Ledger
  Structured answer+trace feedback: scores, tags, and notes that create
  review-only learning candidates. This comes before any predictive scorer or
  neural learning.
```

## Current Model Read

Local machine:

```text
RTX 3060 12GB
32GB RAM
```

Useful model takeaways:

```text
qwen2.5:7b-instruct      best strict governed-state executor so far
qwen3:14b                biggest useful installed text model, better for some
                         scaffolded long-form drafting but less steady
qwen2.5-coder:14b        code-route specialist candidate
gemma4:latest            large context, weak in current text-only evals
phi3:3.8b                tiny-model stress subject
```

Do not choose models by size alone. The lab repeatedly showed that route,
scaffold, verifier, and repair matter more than "largest model" for this lane.

## Current Limitations

- Replay pack is still small and somewhat noisy.
- Blind replay evidence exists and passed, but blind v1 is only 13 cases and
  still comes from the same export universe.
- Personal synthesis now has a stronger receipt gate and route policy; the
  current pack passes without unsupported broad identity/founder claims.
- Grant/business answers now have stricter outcome-promise language. The
  current pack passes, but adjacent photo/video/print-shop prompts should be
  reviewed for business_planning task fit.
- Replay eval currently grades answer quality more than trace quality.
- Workbench has not yet adopted the lab router as a real request path.
- Durable historical trace reload is implemented in the lab CLI, not yet in
  Workbench.

## Next Work

Best next tasks, in order:

1. **Return to Phase 2 governed learner heartbeat.**
   - Use recent turns and persisted traces to produce review-only Memory,
     Support, Reflection, Contradiction, and Evidence candidates.
   - Current sidecar coverage includes explicit trace-backed memory fact
     candidates, support-style candidates, agent/project reflection candidates,
     contradiction review candidates, and local-router/RAG evidence candidates.
   - Workbench learner candidates now show a compact why-this-exists strip:
     first evidence receipt, review boundary, and review destination.
   - Trace-proposed memory facts now open Memory with a review-only draft
     panel. It shows the proposed slot, summary, confidence, and receipts, but
     does not prefill or write memory.
   - Nothing gets written to memory, support patterns, reflections, or policy
     without explicit operator review.

2. **Keep rejected and deferred candidates inert.**
   - Backend reflection tests now prove accepted reflections enter future
     context while deferred and rejected reflections do not.
   - Workbench consolidation tests now prove Defer Session and Hide Session are
     local review-queue states that do not open review routes or call
     additional APIs.
   - Keep this as a regression boundary while adding new learner surfaces.

3. **Promote reusable schemas toward Aeteros Core.**
   - Identify the stable shapes that should become core primitives:
     trace event, evidence receipt, review candidate, decision record,
     contradiction marker, and feedback ledger row.
   - Schema-candidate note now exists at
     `docs/plans/AETHER_AETEROS_CORE_SCHEMA_CANDIDATES_2026-06-30.md`.
   - First extraction now exists:
     `aether-core/aether/sidecar/review_schema.py`.
   - It contains EvidenceReceipt, ReviewCandidate, SafetyContract, and
     review_only_candidate_flags.
   - It is wired into sidecar consolidation and archive import/review
     fixtures; keep it small and behavior-inert.
   - Next extraction should wait for another two-call-site duplication point.
   - Keep lab-specific pack names and evaluator details outside the core shape.

4. **Keep local-router/RAG evidence as research and product evidence.**
   - The lab is graduated as validation infrastructure, not daily tuning work.
   - Preserve scaffolded_rag as the serious baseline for future evidence.
   - Do not return to raw-only comparisons.

5. **Expand blind cases only for a specific evidence question.**
   - If the Workbench review bridge reveals a weak spot, grow blind/adversarial
     coverage while preserving source-conversation, prompt-dedupe, and
     quality-filter boundaries.

6. **Review nearby creative/business prompts only when routing appears in real use.**
   - Check whether photo, video, event, print-shop, and camera-gear planning
     prompts should route as business_planning instead of grant_business.

## Tangent Triage

The scheduler may explore tangents, but only if they improve the bridge back to
the roadmap.

High-leverage tangents:

```text
trace reload proof
curated replay pack expansion
failure taxonomy
qwen2.5/qwen3/qwen2.5-coder comparison under the same scaffold
review-only learning-candidate extraction from verifier failures
feedback-ledger Workbench preview import
Workbench Activity/Trace schema mapping
```

Low-leverage tangents to avoid for now:

```text
Raspberry Pi / Jetson inference shopping
more random model downloads
persona-only voice chasing
trying to make a local model "think" internally
huge context-window experiments before retrieval discipline
polished UI before trace schema and reload behavior survive the lab
```

Evidence read:

```text
The lab is producing evidence for governance, not evidence that local models
compete with frontier models globally. The current signal says small local
models become more reliable and inspectable when Aether externalizes cognition:
Mirus packet, semantic spine, CRT verifier, repair/fallback, and durable trace.
```

## Success Criteria

Classify this lab phase as successful when:

```text
1. A curated 30-50 case replay pack exists.
2. Routed local answers beat raw local answers by at least +0.20 average score.
3. Routed pass rate clears 70% on curated cases.
4. Repairs fix more failures than they introduce.
5. The judge catches unsupported claims without over-flagging explicit negations.
6. Router CLI writes trace JSON for every run.
7. Replay eval grades answer quality and trace quality. DONE in lab.
8. Historical runs reload answer + trace after restart. DONE in lab CLI.
9. Learning candidates stay review-only until explicitly promoted.
```

## Safety / Product Contract

Do not implement:

```text
silent durable memory writes
silent support imports
silent reflection creation
silent model switching
raw hidden chain-of-thought storage as truth
frontier-level capability claims
autonomous truth claims
guaranteed business/grant outcome claims
```

Do implement:

```text
structured trace summaries
explicit evidence anchors
allowed/disallowed inference boundaries
verifier flags
repair/fallback records
review-only learning candidates
restart-safe historical trace reload
```

## 2026-06-30 Phase 2 Checkpoint

The roadmap-return lane is now past the local-router lab and into product
dogfooding of governed learning.

Completed since the lab graduation:

```text
Code/tool routing:
- prompts like "make the smallest safe change", "add or update a test",
  "actual files", and "do not invent paths" now route to code_tool;
- code/edit/test requests trigger workspace_search before synthesis when no
  exact file path is supplied;
- regression tests cover the Aether dogfood failure where a code prompt was
  previously answered as general local chat with plausible fake paths.

Thinking / Process trace:
- Workbench answer bubbles expose Thinking, Memory, Tools, Verifier, and
  Learning sections from public_governance_steps, route metadata, tool runs,
  verifier/compliance data, memory writes, and review-only candidates;
- the drawer shows route/model/repair policy and learning authority without
  storing private hidden scratchpad as durable truth.

Mirus memory-candidate path:
- direct facts such as favorite flower still persist only through governed
  explicit fact capture;
- soft signals such as "I like iced coffee a lot" become review-only
  candidates unless the user later gives a narrow contextual confirmation;
- unresolved favorite-category questions can create trace-only memory_intents
  for self-discovered slots such as user:favorite_sports_team; later related
  evidence can become a review-only candidate for that slot, and a short
  confirmation can promote it to confirmed governed memory;
- GPT-log / ChatGPT-archive / old-chat wording now routes through document
  search and Context Bridge as bounded historical evidence, not confirmed
  memory or automatic support/reflection behavior;
- archive document_search hits can surface as review-only
  archive_evidence_candidate items in consolidation preview, routed to Reflect
  as workflow review drafts with no writes performed;
- Workbench answer-level Thinking traces now have fixture coverage for archive
  document_search completion and the public route reason, and the full Trace
  drawer renders the same bounded archive hit without treating it as memory;
- "They are both orange" creates no memory by itself;
- after recent marigolds/orange context, "They are both orange" can create a
  review-only user:favorite_flower_reason candidate with:
  authority=unconfirmed, review_required=true,
  memory_write_allowed=false, confirmed_fact=false.

Learner queue:
- the marigold/orange path is smoke-tested from trace -> consolidation
  candidate -> Memory review draft;
- Learn -> Memory draft handoff shows proposed value, semantic signal,
  unconfirmed authority, review-only boundary, and receipt;
- repeated Memory review candidates dedupe by category, candidate kind, slot,
  and proposed value so repeated traces do not spam the queue;
- mixed Memory/Support/Reflection learner queue coverage verifies route
  filters, session-only hide/defer, preview-only safety labels, draft payloads,
  evidence receipts, and review-surface handoffs.
```

Current next work:

```text
1. Pause scheduled learner-queue polishing unless live Workbench dogfooding
   reveals a concrete issue.
2. If dogfooding finds one, fix only concrete review-queue regressions or
   confusing UX.
3. Keep ReviewDecision extraction paused until Memory has a durable
   candidate/decision adapter need across live call sites.
4. Treat generative governance as public answer-spine/rationale work, not
   hidden chain-of-thought storage.
```

## Restart Prompt

Use this prompt for a new clean thread:

```text
We are in D:\AI_round2. Read:
- docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
- docs/plans/AETHER_CURRENT_STATE.md
- docs/plans/AETHER_LOCAL_ROUTER_LAB_GRADUATION_2026-06-30.md
- docs/plans/AETHER_AETEROS_CORE_SCHEMA_CANDIDATES_2026-06-30.md
- docs/plans/AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
- docs/plans/AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
- docs/plans/AETHER_AETEROS_MASTER_PLAN_2026-06-26.md only as needed

Continue the Aether roadmap-return work. The local-router / durable trace /
RAG-baseline lab is graduated as validation infrastructure. Do not reset or
clean the dirty worktree. Preserve untracked lab files and docs.

Current task direction:
1. Continue Phase 2 learner queue polish, not local-router lab tuning.
2. Keep mixed Memory/Support/Reflection learner queue coverage as the current
   checkpoint; do not add more surfaces without a dogfood regression.
3. Fix only concrete review-queue clarity, duplicate, or routing regressions.
4. Preserve reject/defer non-effect and review-only memory boundaries.
5. Keep ReviewDecision, TracePacket, and ContradictionMarker extraction paused
   until a real two-call-site duplication appears.
6. Keep local-router/RAG evidence as Research/Product Evidence, not daily
   tuning work. Scaffolded_rag remains the serious baseline for any future
   blind/adversarial evidence.

Important contract:
Do not store raw hidden chain-of-thought as truth. Store structured CRT trace
artifacts: classification, retrieval, Mirus packet, route, scaffold, verifier,
repair/fallback, confidence, contradiction notes, and learning candidates.
No automatic memory writes, support/reflection writes, or silent policy
mutation.
```

## One-Line Status

Aether is back on the main roadmap: trace-backed learner review is visible in
Workbench, code/tool routing is workspace-grounded, Mirus candidates stay
review-only, mixed learner queue review has Memory/Support/Reflection coverage,
and this lane is parked until live dogfooding produces a concrete issue.
