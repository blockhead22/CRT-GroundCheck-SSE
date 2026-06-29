# Aether Current State

Last updated: 2026-06-29

Start new Codex threads here:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
```

Current lane:

```text
Aether Core validation infrastructure:
local router -> Mirus packet -> scaffold -> model render -> CRT verifier
-> repair/fallback -> durable thinking trace -> replay eval
```

The local-router lab is now roadmap-relevant only as Aether/Core
infrastructure. Do not continue it as loose prompt tuning.

Read next:

```text
D:\AI_round2\docs\plans\AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_FEEDBACK_CANDIDATE_REVIEW_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_TRACE_WORKBENCH_MAPPING_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_WEIGHTED_FEEDBACK_LEDGER_2026-06-29.md
D:\AI_round2\local-router-curated-replay-v1-evidence-2026-06-29.md
D:\AI_round2\local-router-replay-v0-report-2026-06-28.md
D:\AI_round2\docs\plans\AETHER_AETEROS_MASTER_PLAN_2026-06-26.md
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

Current decision:

```text
Keep working on the lab if the next phase builds durable structured trace.
Stop or pause if the work becomes only model shopping or prompt tasting.
Use scheduled work to finish the lab bridge back to the roadmap, but do not
ignore meaningful discoverable tangents if they directly improve evidence,
trace quality, reloadability, or graduation into Workbench.
New feedback-loop decision: do not jump to neural learning. Add a weighted
feedback ledger first, then use repeated tags to tune policies/scaffolds before
considering any predictive scorer.
```

Next work:

```text
1. Run the replay-compatible RAG suite over blind and perturbed packs:
   raw vs plain_rag vs scaffolded_rag vs governed.
2. Decide the narrow anchor-hygiene fix for the repeated perturbed coverage
   pocket:
   - gptlog_017_grant_business_perturb_01 likely needs case-specific
     product/company framing anchors, not default CRT/router anchors.
   - gptlog_019_grant_business_perturb_01 likely needs anchor aliasing or
     replacement for "applied myself" rather than a broad scaffold change.
3. Re-run targeted replay and ablation repeat after any anchor-hygiene change.
4. Expand the blind pack beyond 13 cases while preserving quality filters.
5. Compare blind/perturbed/RAG failures by task type before promoting new policies.
6. Decide whether feedback-ledger candidates should become a guarded sidecar import path or remain fixture/review-only.
```

Completed after this pointer was created:

```text
local_router_cli now writes separate durable trace JSON files.
local_router_replay now grades trace quality alongside answer quality.
local_router_cli can reload a saved result and external trace artifact.
local_router_replay now reports combined_passed and graduation_ready gates.
replay_pack_builder now writes curation metadata and produced a 32-case
candidate pack:
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json
Pack shape: 8 architecture, 8 personal synthesis, 6 grant/business, 2 business_planning, 8 code/process.
Pack taxonomy cleanup after evidence pass:
code_reasoning split into 7 architecture_process cases and 1 code_implementation case.
Explicit replay task labels are now authoritative for routing.
local_router_replay now reads UTF-8 and UTF-8-BOM replay packs.
Quality summary: 27 cases score 5, 5 cases score 4, only starts_with_quote flags.
local_router_replay now includes failure_taxonomy in aggregate output.
Curated-pack smoke:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.516, Routed 4/4 avg 0.795, Trace 4/4 avg 1.000, Combined 4/4.
Curated-pack architecture slice 2:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 4 --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.465, Routed 4/4 avg 0.767, Trace 4/4 avg 1.000, Combined 4/4.
Note: gptlog_008 still looks artifact-ish and should be reviewed before final evidence claims.
Curated-pack personal synthesis slice 1:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 8 --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.326, Routed 3/4 avg 0.714, Trace 4/4 avg 1.000, Combined 3/4.
Failure taxonomy: 1 personal_synthesis answer failure, 0 trace failures, no hard verifier flags.
Interpretation: personal synthesis still needs stronger memory receipts/context to avoid generic advice.
Curated-pack personal synthesis slice 2:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 12 --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.340, Routed 4/4 avg 0.784, Trace 4/4 avg 1.000, Combined 4/4.
Interpretation: the weak personal case appears tied to broad founder-comparison prompts; more concrete personal/emotional prompts held under section-lock.
Curated-pack grant/business slice 1:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 16 --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.392, Routed 3/4 avg 0.777, Trace 4/4 avg 1.000, Combined 3/4.
Failure taxonomy: 1 grant_business answer failure, 0 trace failures, forbidden_hits medical=1, leakage process_theater=1.
Interpretation: grant/business needs stricter user-facing language boundaries around medical/regulated claims and no internal verifier/Mirus process theater in final answer.
Curated-pack grant/business slice 2:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 20 --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.370, Routed 3/4 avg 0.771, Trace 4/4 avg 1.000, Combined 3/4.
Failure taxonomy: 1 grant_business answer failure, 0 trace failures, forbidden_hits guaranteed=1.
Interpretation: grant/business has a repeat answer-side issue around outcome-promise/guarantee language. Trace stays clean, so the next improvement is final-answer restraint, not trace plumbing.
Curated-pack code-reasoning slice 1:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 24 --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.319, Routed 4/4 avg 0.800, Trace 4/4 avg 1.000, Combined 4/4.
Interpretation: first code slice passes, but the bucket is mostly architecture/process reasoning rather than pure implementation patches. Consider splitting this bucket before final evidence claims.
Curated-pack code-reasoning slice 2:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 28 --max-cases 4 --timeout 300 --no-write
returned Raw 0/4 avg 0.405, Routed 4/4 avg 0.757, Trace 4/4 avg 1.000, Combined 4/4.
Curated replay v1 summary:
D:\AI_round2\local-router-curated-replay-v1-evidence-2026-06-29.md
Overall: Raw 0/32, Routed 29/32, Trace 32/32, Combined 29/32, average lift +0.379.
Grant/business final-answer policy added to Mirus packet and section-lock prompt:
avoid guarantees, medical/regulated claims, frontier claims, and internal process theater.
Verification:
python -m pytest tests\test_local_router_cli.py tests\test_attention_profile_eval.py -q
14 passed
Grant smoke passed without forbidden/process leakage, but was lighter than ideal on CRT/verifier anchors.
Personal synthesis receipt gate added to the answer verifier:
broad identity/founder claims now require multiple concrete receipt anchors or a cautious request for more receipts.
Verification:
python -m pytest tests\test_local_router_cli.py tests\test_attention_profile_eval.py -q
17 passed
python -m pytest tests\test_local_router_replay.py -q
9 passed
Latest written trace smoke:
D:\AI_round2\labs\meaning_compression_lab\results\traces\local_router_trace_1782695107.json
Reload proof:
python -m labs.meaning_compression_lab.local_router_cli --load-result labs\meaning_compression_lab\results\local_router_cli_1782695107.json --json
returned trace_source=external and consistent=true.
Trace gate proof:
python -m labs.meaning_compression_lab.local_router_replay --max-cases 2 --timeout 300 --no-write
returned Trace pass 2/2 and Combined pass 2/2.
Relabeled architecture_process slice smoke:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --skip-cases 24 --max-cases 2 --timeout 300 --no-write
returned Raw 0/2 avg 0.347, Routed 2/2 avg 0.823, Trace 2/2 avg 1.000, Combined 2/2.
Focused taxonomy verification:
python -m pytest tests\test_local_router_eval.py tests\test_local_router_replay.py tests\test_local_router_cli.py -q
31 passed
Repair prompt now carries final_answer_policy into revision passes.
Verification:
python -m pytest tests\test_local_router_cli.py tests\test_local_router_eval.py tests\test_local_router_replay.py tests\test_attention_profile_eval.py -q
34 passed
Post-policy full curated replay:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --timeout 300 --no-write
returned Raw 0/32 avg 0.377, Routed 28/32 avg 0.750, Trace 32/32 avg 1.000, Combined 28/32.
Failure taxonomy: 4 answer-side failures, 0 trace failures, 0 forbidden/leakage/weirdness/truncation flags.
Pre-anchor remaining failures: 3 architecture_process and 1 grant_business low-score/coverage cases.
Workbench trace mapping adapter added:
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_adapter.py
Mapping doc:
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_TRACE_WORKBENCH_MAPPING_2026-06-29.md
Boundary: adapted lab traces render route/Mirus/verifier packets but do not turn lab anchors into confirmed memory evidence.
Verification:
python -m pytest tests\test_workbench_trace_adapter.py tests\test_local_router_cli.py tests\test_local_router_replay.py -q
28 passed
python -m py_compile labs\meaning_compression_lab\workbench_trace_adapter.py
passed
Isolated Workbench fixture import added:
D:\AI_round2\labs\meaning_compression_lab\workbench_trace_fixture.py
It writes adapted lab traces through WorkbenchDB begin_turn/save_trace/complete_turn into caller-provided DB paths only and refuses ~/.aether/workbench.db by default.
Verification:
python -m pytest tests\test_workbench_trace_fixture.py tests\test_workbench_trace_adapter.py tests\test_local_router_cli.py tests\test_local_router_replay.py -q
30 passed
python -m py_compile labs\meaning_compression_lab\workbench_trace_fixture.py labs\meaning_compression_lab\workbench_trace_adapter.py
passed
Real TraceDrawer fixture renders adapted local-router trace:
workbench\src\components\TraceDrawer.test.tsx
Verification:
cd D:\AI_round2\workbench
npm run test:ui -- --run src/components/TraceDrawer.test.tsx
12 passed
npm run build
passed
Low-score/no-hard-flag anchor-fit review added:
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md
Conclusion: remaining failures are evidence-targeting problems, not threshold or safety-policy problems.
Recommended: split non-Aether small-business prompts from Aether grant/business, add case-specific architecture_process anchors, then re-run only the four reviewed cases.
Implemented business_planning split, targeted --case-id replay, case-specific architecture_process anchors, and architecture_process final-answer policy.
Targeted reviewed cluster:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --case-id gptlog_019_grant_business --case-id gptlog_027_architecture_process --case-id gptlog_028_architecture_process --case-id gptlog_030_architecture_process --timeout 300
returned Raw 0/4 avg 0.526, Routed 4/4 avg 0.824, Trace 4/4 avg 1.000, Combined 4/4.
Intermediate full curated replay:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --timeout 300
returned Raw 0/32 avg 0.397, Routed 28/32 avg 0.766, Trace 32/32 avg 1.000, Combined 28/32.
Intermediate failure taxonomy moved to 3 personal_synthesis receipt-gate failures and 1 grant_business bounded-claim/guarantee wording failure.
Verification:
python -m pytest tests\test_local_router_eval.py tests\test_local_router_cli.py tests\test_local_router_replay.py -q
36 passed
Personal/founder receipt-request behavior tightened; personal_synthesis fallback now stays inside section_lock.
Grant/business repair now avoids guarantee wording, and gptlog_022 was relabeled to business_planning with concrete photo/video/print-shop anchors.
Consciousness forbidden-word detector now allows sub-conscious/subconscious memory phrasing while still blocking direct conscious overclaims.
Final curated replay:
python -m labs.meaning_compression_lab.local_router_replay --pack labs\meaning_compression_lab\replay_packs\local_router_replay_curated_v1.json --timeout 300
returned Raw 0/32 avg 0.407, Routed 32/32 avg 0.773, Trace 32/32 avg 1.000, Combined 32/32.
Result artifact:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782716566.json
Verification:
python -m pytest tests\test_local_router_cli.py tests\test_local_router_eval.py tests\test_local_router_replay.py -q
38 passed
Weighted feedback ledger implemented as review-only metadata:
D:\AI_round2\labs\meaning_compression_lab\local_router_feedback_ledger.py
Generated feedback artifact:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_feedback_ledger_1782716566.json
Result: 32 feedback rows, 4 Workbench preview candidates, writes_performed=false, memory_ingestion_performed=false.
Tag counts: raw_failed=32, routed_passed=32, routed_improved=32, strong_trace=32, missing_receipts=12, repair_used=5, fallback_used=5.
Verification:
python -m pytest tests\test_local_router_feedback_ledger.py tests\test_local_router_cli.py tests\test_local_router_eval.py tests\test_local_router_replay.py -q
40 passed
Workbench feedback-ledger fixture render added:
D:\AI_round2\workbench\src\fixtures\localRouterFeedbackPreview.ts
D:\AI_round2\workbench\src\App.test.tsx
The real Learn drawer renders the 4 review-only ledger candidates and opens them
as manual Support/Reflect draft handoffs without writes.
Verification:
python -m pytest tests\test_local_router_feedback_ledger.py -q
2 passed
cd D:\AI_round2\workbench
npm run test:ui -- --run src/App.test.tsx
15 passed
Evidence v0 frozen:
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
Feedback candidate review added:
D:\AI_round2\docs\plans\AETHER_FEEDBACK_CANDIDATE_REVIEW_2026-06-29.md
Decision: do not promote the 4 ledger candidates directly from v1; use them to
drive v2 and ablation testing.
Perturbed v2 pack builder added:
D:\AI_round2\labs\meaning_compression_lab\local_router_perturb_pack.py
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_perturbed_v2.json
Ablation harness added:
D:\AI_round2\labs\meaning_compression_lab\local_router_ablation.py
Smoke results:
perturbed v2 first case: raw 0/1 avg 0.537, routed 1/1 avg 0.716, trace 1/1.
ablation first case: raw_no_scaffold 0/1 avg 0.497, full 1/1 avg 0.659, trace 1/1.
Full perturbed v2 replay after detector/scaffold hardening:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782721572.json
returned Raw 1/32 avg 0.489, Routed 32/32 avg 0.770, Trace 32/32 avg 1.000, Combined 32/32.
Narrow hardening implemented:
- no-code-needed detector no longer treats warning labels as direct claims
- section-lock and repair prompts tell the model not to quote forbidden phrases as headings
Verification:
python -m pytest tests\test_local_router_cli.py tests\test_attention_profile_eval.py tests\test_local_router_replay.py -q
36 passed
python -m py_compile labs\meaning_compression_lab\local_router_perturb_pack.py labs\meaning_compression_lab\local_router_ablation.py labs\meaning_compression_lab\attention_profile_eval.py labs\meaning_compression_lab\spiral_synthesis_eval.py
passed
Blind v1 pack builder added:
D:\AI_round2\labs\meaning_compression_lab\local_router_blind_pack.py
Blind pack:
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_blind_v1.json
Selection rule: excludes v1 source conversation ids, v1 prompt dedupe keys,
low-specificity/quote/artifact-like candidate flags, and selects at most one
case per conversation.
Blind replay result:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782745851.json
returned Raw 0/13 avg 0.382, Routed 13/13 avg 0.761, Trace 13/13 avg 1.000, Combined 13/13.
Blind ablation slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782746144.json
returned raw_no_scaffold 0/4 avg 0.463, routed_no_repair 4/4 avg 0.748,
routed_no_fallback 4/4 avg 0.781, full 4/4 avg 0.781.
Interpretation: on the first blind slice, routing/scaffold/Mirus context carried
the lift before repair or fallback were needed. Expand before using as a broad
mechanism claim.
Full blind ablation:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782746575.json
returned raw_no_scaffold 0/13 avg 0.409, routed_no_repair 12/13 avg 0.768,
routed_no_fallback 13/13 avg 0.775, full 13/13 avg 0.774.
Interpretation: route/scaffold/Mirus context carried almost all of the lift;
repair closed one remaining grant_business coverage failure, and fallback was
not required.
Full perturbed ablation:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748218.json
returned raw_no_scaffold 0/32 avg 0.494, routed_no_repair 22/32 avg 0.718,
routed_no_fallback 23/32 avg 0.726, full 28/32 avg 0.757.
Targeted normal replay of the four full-ablation failures passed 4/4 with trace
4/4 and combined 4/4, using 1 repair and 1 fallback.
Interpretation: perturbed wording makes repair/fallback more important, and the
ablation path is stochastic/path-sensitive enough that repeated or stabilized
perturbed ablations are needed before promoting policy changes.
Repeat full-mode ablation on the same four cases:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_ablation_1782748474.json
returned full 2/4 avg 0.673, trace 4/4, repairs 2, fallbacks 1.
Repeated failures: gptlog_017_grant_business_perturb_01 and
gptlog_019_grant_business_perturb_01. Both are answer-quality/coverage failures,
not trace, leakage, or hard-safety failures.
Perturbed anchor-fit review added to:
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md
Conclusion: gptlog_017 looks like default grant_business anchor mismatch for a
product/company framing prompt; gptlog_019 looks partly like brittle exact-anchor
matching around "applied myself".
Replay-compatible RAG suite added:
D:\AI_round2\labs\meaning_compression_lab\local_router_rag_suite.py
Initial blind-v1 smoke:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782749903.json
returned raw 0/1 avg 0.537, plain_rag 0/1 avg 0.480,
scaffolded_rag 1/1 avg 0.710, governed 1/1 avg 0.716 with trace 1/1.
Blind-v1 four-case RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782750349.json
returned raw 0/4 avg 0.405, plain_rag 0/4 avg 0.420,
scaffolded_rag 3/4 avg 0.770, governed 4/4 avg 0.740 with trace 4/4.
The scaffolded_rag miss was a personal_synthesis case where retrieval found the
prompt but not enough real personal receipts, and the model invented generic
productivity/health receipts.
Perturbed-v2 four-case RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782750521.json
returned raw 0/4 avg 0.571, plain_rag 0/4 avg 0.577,
scaffolded_rag 4/4 avg 0.804, governed 4/4 avg 0.767 with trace 4/4.
Perturbed-v2 eight-case RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782752318.json
returned raw 1/8 avg 0.560, plain_rag 0/8 avg 0.549,
scaffolded_rag 6/8 avg 0.748, governed 8/8 avg 0.757 with trace 8/8,
fallbacks 2.
Scaffolded-RAG failures were 2 architecture_synthesis cases with high retrieval
coverage, indicating semantic-boundary drift rather than simple retrieval miss.
Perturbed-v2 personal-synthesis RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782753077.json
returned raw 0/8 avg 0.480, plain_rag 0/8 avg 0.405,
scaffolded_rag 2/8 avg 0.764, governed 8/8 avg 0.778 with trace 8/8.
Retrieval receipt coverage was 0.500 and concept coverage was 0.000.
Scaffolded-RAG failures were 6 personal_synthesis cases, mostly weak-retrieval
drift into generic or identity-like claims.
Perturbed-v2 business/grant RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782754067.json
returned raw 1/8 avg 0.497, plain_rag 0/8 avg 0.439,
scaffolded_rag 1/8 avg 0.522, governed 8/8 avg 0.727 with trace 8/8,
repairs 1, fallbacks 3.
Retrieval receipt coverage was 0.333 and concept coverage was 0.369.
Scaffolded-RAG failures were grant_business 6 and business_planning 1, mostly
plausible business language without enough Aether/CRT/router receipts.
Perturbed-v2 architecture/process RAG slice:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782755020.json
returned raw 0/8 avg 0.439, plain_rag 0/8 avg 0.431,
scaffolded_rag 3/8 avg 0.658, governed 7/8 avg 0.772 with trace 8/8,
repairs 3, fallback 1.
The governed failure was gptlog_026_architecture_process_perturb_01, a
coverage/anchor-fit miss, not a trace, leakage, weirdness, or forbidden-claim
failure.
Perturbed-v2 sliced total across 32 cases:
raw 2/32 avg 0.494, plain_rag 0/32 avg 0.456, scaffolded_rag 12/32 avg 0.673,
governed 31/32 avg 0.758 with trace 32/32, repairs 4, fallbacks 6.
Full blind-v1 RAG run:
D:\AI_round2\labs\meaning_compression_lab\results\local_router_rag_suite_1782751568.json
returned raw 0/13 avg 0.404, plain_rag 0/13 avg 0.384,
scaffolded_rag 7/13 avg 0.664, governed 13/13 avg 0.757 with trace 13/13,
repairs 1, fallbacks 3.
Scaffolded-RAG failures concentrated in personal_synthesis 2,
business_planning 3, and grant_business 1.
Interpretation: raw-only comparison is no longer sufficient. Plain RAG did not
close the first RAG slices, but scaffolded RAG is now the serious baseline.
Governed Aether must prove its value over scaffolded RAG through trace,
repair/fallback, evidence-boundary behavior, weak-retrieval handling, and
adversarial cases. The current strongest Aether-vs-scaffolded-RAG signal is on
the full blind pack, especially personal synthesis and business/grant planning
where retrieved evidence is thin or mismatched. The expanded perturbed slice
adds a second signal: scaffolded RAG can drift semantically even when retrieval
coverage is high. The personal-synthesis perturbed slice strengthens the
weak-retrieval signal: governed Aether's receipt gate matters most when the
retrieved context does not provide enough concrete personal evidence.
The business/grant slice strengthens the low-receipt task-fit signal:
scaffolded RAG can produce plausible business framing while missing the project
receipts the answer is supposed to be grounded in.
The full sliced perturbed picture breaks the suspicious perfect-score pattern:
governed Aether has one coverage miss, but still materially beats scaffolded RAG
while preserving trace on every case.
Verification:
python -m pytest tests\test_local_router_replay.py tests\test_local_router_eval.py -q
22 passed
python -m py_compile labs\meaning_compression_lab\local_router_blind_pack.py labs\meaning_compression_lab\local_router_eval.py labs\meaning_compression_lab\replay_pack_builder.py
passed
```

Contract:

```text
Do not store raw hidden chain-of-thought as truth.
Do store structured CRT trace artifacts:
classification, retrieval, Mirus packet, route, scaffold, verifier flags,
repair/fallback, confidence, contradiction notes, and learning candidates.
Do not treat thumbs up/down as enough learning signal. Store feedback as
scores/tags/notes tied to answer + trace.
```

Scheduler operating rule:

```text
The scheduled evening work should move toward lab exit and roadmap return.
Explore viable tangents only when they are high leverage for:
- stronger replay evidence
- trace/reload durability
- failure taxonomy
- route/model assignment evidence under the same scaffold
- review-only learning candidate extraction
- Workbench Activity/Trace schema mapping
- feedback-ledger review-only candidate import

Do not spend scheduled cycles on low-leverage tangents:
- more random model downloads
- Raspberry Pi / Jetson shopping
- persona-only voice tuning
- internal "make the model think" speculation
- huge context-window experiments before retrieval discipline
- polished UI before trace schema/reload proof
```

Evidence read:

```text
Current evidence supports the governance path, not frontier-model competition.
The useful claim is: governed external cognition improves raw local chat for
Aether's use case. Current strongest line: curated v1 raw 0/32 vs routed
32/32, perturbed v2 raw 1/32 vs routed 32/32, and blind v1 raw 0/13 vs routed
13/13, with clean trace and combined gates on all governed runs. Ablations now
show the strongest mechanism signal on blind v1 and a repair/fallback-sensitive
but less stable mechanism signal on perturbed v2. This must now be checked
against RAG baselines before being used as a stronger product or funding claim.
```
