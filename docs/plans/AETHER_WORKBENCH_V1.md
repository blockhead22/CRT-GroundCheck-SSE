# Aether Workbench v1 — Local Sidecar

## Current status - 2026-06-24

Latest continuity packet:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-24.md
```

Recovered lineage/principles checkpoint:

```text
D:\AI_round2\docs\plans\AETHER_RECOVERED_CORE_PRINCIPLES_2026-06-24.md
```

Recovered concept integration audit:

```text
D:\AI_round2\docs\plans\AETHER_RECOVERED_CONCEPT_INTEGRATION_AUDIT_2026-06-24.md
```

Isolated fixture eval runbook:

```text
D:\AI_round2\docs\plans\AETHER_ISOLATED_FIXTURE_EVAL_RUNBOOK_2026-06-25.md
```

Use the recovered-principles checkpoint as the current-language extraction from
Lumi, CRT, CogniForge, and the original white paper. Do not carry old project
names forward as product surface unless they map cleanly to current Aether
architecture, evals, or trace UI.

Use the integration audit as the on-ramp back to the main roadmap. Broad artifact
dives are paused unless a specific gap requires a specific source file.

The original v1 proof loop is now implemented far enough to dogfood:

- governed broad Context Bridge;
- character/reflection guidance routes;
- visible response route in Trace drawer;
- persisted completion route metadata in saved traces;
- per-turn historical trace recall;
- stress ingestion guardrails for no-save/adversarial/long-paste input;
- stable-slot quarantine from Workbench review;
- local conversation eval runner with a clean `19/19` baseline;
- strict Workbench dev port and isolated Electron dev cache;
- Phase 1.5 depth request classifier, self-check, continuation loop, and trace
  metadata scaffold;
- Response depth card in the Trace drawer;
- coverage-aware depth self-check for requested tradeoffs, risks, and next
  steps;
- explicit two-pass continuation requests with repeated-prefix trimming;
- `phi3:3.8b` spiral continuation eval coverage;
- Phase 1.6 seed programming evals for workspace search/read/patch-preview,
  planning-only behavior, read-only test recommendation behavior, and governed
  pytest result capture;
- first-pass Trace drawer code-tool metadata rows for path, command, test file,
  readiness/applied/executed/write status, test result status, stale hash, and
  errors, plus clipped stdout/stderr blocks for captured tests and retrieved
  search/read snippet blocks;
- visible Trace drawer notices for failed tools, non-ready patches, preview-only
  patches that require approval/hash protection, and timed-out tests;
- first-pass programming escalation packets that include the user ask, local
  attempt, reason, unresolved question, relevant files/snippets, and summarized
  workspace tool results;
- read-only code reference roots for search/read/list, while patch and test
  execution remain limited to writable workspace roots;
- optional live reference-root eval coverage for the downloaded code-tools
  source tree, plus exact-symbol search scoring and path-highlight prompt
  guidance so local models report retrieved paths instead of plausible ones;
- broader tiny-fixture programming evals for failing pytest capture,
  TypeScript package test recommendation, exact-symbol search ranking, and
  prompt path-highlight persistence;
- Code Context Tools v1 contract defined in
  `D:\AI_round2\docs\plans\AETHER_LOCAL_CODER_V1.md`;
- hardened workspace search against generated worktree/log/artifact noise;
- Phase 1.7 target defined for real-use multifactual conversational reliability:
  personality, motivation, practical re-entry, and grounded caution.
- Phase 1.7 personal archive source identified:
  `C:\Users\block\Downloads\fbf5a239c1af822f50241d4b5999b53954689723b9d4deb7ceb1e41a31847485-2026-03-27-22-39-55-cf0803cbc48c446cb8c3b317ea5f11ea`
  contains a full ChatGPT export with 1,275 conversations, `chat.html`, 13
  conversation JSON shards, and attachments. Treat it as a reviewable archive,
  not as Aether voice or confirmed memory.
- Phase 1.7 dry-run archive scanner implemented at
  `D:\AI_round2\aether-core\scripts\chatgpt_archive_scan.py`, with focused
  tests proving private message body strings are not included in reports. The
  scanner now emits review-required support-pattern candidates from title
  category counts only, marked `memory_write_allowed=false` and
  `confirmed_fact=false`.
  Safe real-export scan output:
  `D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_scan_20260624_phase17.json`.
  Latest support-candidate dry run:
  `D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_scan_20260624_support_candidates.json`.
- Phase 1.7 support-pattern review API implemented:
  - DB tables for support-pattern candidates and review receipts;
  - `GET /v1/support-patterns`;
  - `POST /v1/support-patterns/import`;
  - `GET /v1/support-patterns/{candidate_id}`;
  - `POST /v1/support-patterns/{candidate_id}/review`;
  - review actions are revision-guarded and idempotent;
  - accepted/rejected candidates cannot be overwritten by a later archive scan;
  - candidates remain separate from confirmed memory and still do not write
    substrate facts.
- Phase 1.7 accepted support-pattern behavior input implemented:
  - Context Bridge now includes accepted support-pattern candidates as
    `reviewed_support_patterns`;
  - local prompt formatting releases accepted support patterns as behavioral
    guidance with their boundary/risk text;
  - rejected/deferred support patterns stay out of prompts;
  - trace payloads expose which accepted support patterns were released.
- Phase 1.7 support-pattern fixture eval lane implemented:
  - `scripts/workbench_eval.py` now has `--include-support-pattern-eval` for
    opt-in reviewed support-pattern behavior cases;
  - `scripts/run_support_pattern_fixture_eval.py` creates an isolated temporary
    Aether dir, seeds accepted and rejected support-pattern candidates into a
    temporary Workbench DB, starts a temporary sidecar, runs only the
    support-pattern eval cases, and tears the sidecar down;
  - Workbench exposes the helper as `npm run eval:support-patterns`;
  - the fixture verifies accepted support guidance is released through
    `context_bridge.reviewed_support_patterns`, rejected guidance is excluded,
    and generated answers follow the reviewed re-entry/boundary guidance;
  - verification:
    `python scripts\run_support_pattern_fixture_eval.py --no-write` -> `2/2 passed`;
    `npm run eval:support-patterns -- --no-write` -> `2/2 passed`;
    `python -m pytest tests/test_workbench_eval.py tests/test_support_pattern_fixture_eval.py tests/test_sidecar_support_patterns.py -q`
    -> `10 passed`;
    `python -m pytest tests/test_runtime_query.py tests/test_sidecar_context_bridge.py tests/test_sidecar_app.py tests/test_sidecar_ingest.py tests/test_sidecar_direct_answer.py tests/test_workbench_eval.py tests/test_disposition_fixture_eval.py tests/test_sidecar_support_patterns.py tests/test_support_pattern_fixture_eval.py -q`
    -> `64 passed`;
    `npm run build` -> passed.
- Phase 2 governed background consolidation / Mirus learner first slice:
  - design doc added at
    `D:\AI_round2\docs\plans\AETHER_BACKGROUND_CONSOLIDATION_MIRUS_LOOP_2026-06-24.md`;
  - pure review-only candidate planner added at
    `D:\AI_round2\aether-core\aether\sidecar\consolidation.py`;
  - the planner proposes candidate review items from recent turn/trace records
    for contradiction review, support-style review, project-context review, and
    Aether self-improvement reflections;
  - the planner does not persist anything and hard-codes the safety contract:
    `review_required=true`, `memory_write_allowed=false`,
    `confirmed_fact=false`;
  - focused tests verify contradiction candidates do not leak conflicted values
    and all learner outputs stay review-only:
    `python -m pytest tests/test_sidecar_consolidation.py -q` -> `3 passed`;
    `python -m py_compile aether\sidecar\consolidation.py` -> passed;
  - preview-only API added at `GET /v1/consolidation/candidates?limit=...`;
  - the endpoint reads recent Workbench turns/traces and returns preview
    candidates without writing memory, support patterns, or reflections;
  - preview candidates now include `review_route` metadata pointing toward the
    existing review surface: Memory slot review for contradictions, Support
    draft for support-style candidates, and Reflection drafts for project
    context/Aether self-improvement candidates;
  - focused endpoint tests verify preview metadata and read-only behavior:
    `python -m pytest tests/test_sidecar_consolidation.py -q` -> `5 passed`.
- Phase 1.7 Workbench support-pattern review UI implemented:
  - bottom navigation now includes a Support review drawer;
  - candidates can be filtered by review status;
  - title-only evidence, risk boundaries, and "not confirmed memory" guardrails
    are visible before review;
  - proposed/deferred candidates can be accepted, deferred, or rejected from the
    drawer through the revision-guarded review API;
  - focused UI tests and production build are green:
    `npm run test:ui -- --run src/App.test.tsx src/components/SupportPatternDrawer.test.tsx src/components/ReflectionDrawer.test.tsx`
    -> `12 passed`;
    `npm run build` -> passed.
- Phase 1.8 contradiction disposition governance first slice implemented:
  - `GovernedQueryService` now attaches a structured
    `contradiction_disposition` object to conflicted trace packets;
  - first-pass labels are `resolvable`, `held`, `evolving`, `contextual`,
    `stale`, and `policy_bound`;
  - the labels do not resolve or release conflicted values; they give traces
    and review flows a safer explanation of what kind of conflict exists;
  - Workbench Trace drawer now shows the disposition, reason, and confidence on
    conflicted packets;
  - focused and smoke tests are green:
    `python -m pytest tests/test_runtime_query.py -q` -> `9 passed`;
    `python -m pytest tests/test_runtime_query.py tests/test_sidecar_context_bridge.py tests/test_sidecar_app.py -q`
    -> `39 passed`;
    `npm run test:ui -- --run src/components/TraceDrawer.test.tsx src/App.test.tsx src/components/SupportPatternDrawer.test.tsx`
    -> `20 passed`;
    `npm run build` -> passed.
- Phase 1.8 disposition prompt/review slice implemented:
  - prompt memory restrictions now include disposition label/reason/confidence
    without leaking restricted evidence values;
  - prompt instructions map dispositions to safer answer behavior:
    resolvable -> ask for confirmation/correction, held -> name authoritative
    conflict, evolving -> time-change framing, contextual -> ask which context,
    stale -> avoid treating old non-active values as current, policy_bound ->
    preserve policy boundaries;
  - `/v1/slots/{slot_id}` now exposes `contradiction_disposition` for conflicted
    slots;
  - Workbench Memory drawer now shows disposition label, reason, and confidence
    before confirm/correct/quarantine actions;
  - focused and smoke tests are green:
    `python -m pytest tests/test_runtime_query.py tests/test_sidecar_app.py -q`
    -> `30 passed`;
    `python -m pytest tests/test_runtime_query.py tests/test_sidecar_context_bridge.py tests/test_sidecar_app.py tests/test_sidecar_ingest.py -q`
    -> `49 passed`;
    `npm run test:ui -- --run src/App.test.tsx src/components/MemoryDrawer.test.tsx src/components/TraceDrawer.test.tsx src/components/SupportPatternDrawer.test.tsx`
    -> `21 passed`;
    `npm run build` -> passed.
- Phase 1.8 disposition-shaped answer/eval slice implemented:
  - exact direct profile lookups against conflicted packets now return a
    deterministic `aether_direct` review-style answer instead of guessing or
    leaking restricted values;
  - example: a conflicted employer lookup says there is conflicting governed
    evidence, names the disposition, and asks for confirmation/correction;
  - `scripts/workbench_eval.py` now has `--include-disposition-eval` for opt-in
    Phase 1.8 cases;
  - opt-in cases now cover all first-pass dispositions:
    `disposition_resolvable_direct_employer`,
    `disposition_held_direct_favorite_color`,
    `disposition_evolving_direct_camera_system`,
    `disposition_contextual_direct_workspace`,
    `disposition_stale_direct_old_employer`, and
    `disposition_policy_bound_direct_deployment_rule`;
  - each case verifies answer shape, trace-packet disposition metadata, and
    `/v1/slots/{slot_id}` review surfacing;
  - the runner does not seed or mutate live memory; these cases expect a
    controlled sidecar fixture with the conflicted slots present;
  - decision: do not add a live-memory seeding endpoint for this. If live
    fixture automation becomes necessary, use an isolated temporary Aether data
    dir and sidecar, not Nick's live substrate;
  - `scripts/run_disposition_fixture_eval.py` now creates that isolated
    temporary Aether dir, seeds all six synthetic conflicted slots, starts a
    temporary sidecar, runs only the opt-in disposition eval cases, and tears
    the sidecar down;
  - Workbench now exposes the helper as `npm run eval:dispositions`;
  - the isolated eval exposed and repaired a planner ambiguity where
    `old_employer` could tie with generic `employer`; the planner now prefers
    the longer exact slot phrase in close exact-phrase ties and penalizes
    generic `employer` for old/previous/former/past employer wording;
  - focused and smoke tests are green:
    `python -m pytest tests/test_sidecar_app.py -k "direct_conflicted or chat_stream_only_sends" -q`
    -> `2 passed`;
    `python -m pytest tests/test_workbench_eval.py -q` -> `2 passed`;
    `python -m pytest tests/test_sidecar_direct_answer.py tests/test_workbench_eval.py -q`
    -> `5 passed`;
    `python -m pytest tests/test_runtime_query.py tests/test_sidecar_context_bridge.py tests/test_sidecar_app.py tests/test_sidecar_ingest.py tests/test_sidecar_direct_answer.py tests/test_workbench_eval.py -q`
    -> `55 passed`;
    `python -m py_compile scripts\workbench_eval.py` -> passed;
    `python scripts\run_disposition_fixture_eval.py --no-write` -> `6/6 passed`;
    `npm run eval:dispositions -- --no-write` -> `6/6 passed`;
    `python -m pytest tests/test_runtime_query.py tests/test_sidecar_context_bridge.py tests/test_sidecar_app.py tests/test_sidecar_ingest.py tests/test_sidecar_direct_answer.py tests/test_workbench_eval.py tests/test_disposition_fixture_eval.py -q`
    -> `56 passed`;
    `npm run test:ui -- --run src/App.test.tsx src/components/MemoryDrawer.test.tsx src/components/TraceDrawer.test.tsx src/components/SupportPatternDrawer.test.tsx`
    -> `21 passed`;
    `npm run build` -> passed.
- Phase 1.7 opt-in real-use reliability eval cases added to
  `D:\AI_round2\aether-core\scripts\workbench_eval.py` behind
  `--include-real-use-eval`. Targeted real-use prompt scaffolding now covers
  practical permission boundaries, abrupt topic switches, medical-adjacent
  caution, and walking/scale support. Current focused live run:
  `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_165625.json`,
  with `4/4` passing on a fresh sidecar.
- Phase 1.7 variance hardening now includes a real-use depth floor: when
  targeted real-use guidance is present and the first answer is thin, the
  continuation controller can run one bounded additive pass even if the user did
  not explicitly say "deep." Saved focused results:
  - qwen2.5:7b-instruct:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_165625.json`
    (`4/4`);
  - phi3:3.8b:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_170435.json`
    (`4/4`);
  - gemma3:latest:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_170953.json`
    (`4/4`).
- Phase 1.7 expanded qwen lane includes identity/continuity and
  tone/personality regression cases. The pre-repair saved six-case report:
  `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_173249.json`
  (`5/6`). Identity/continuity passed; tone/personality exposed a
  variance-prone drift into generic/code-flavored motivation and missed the
  requested dork/courtroom wording. The later repair/fallback path now passes
  focused verification and the fresh split full-lane verification below.
- Recovered concept integration audit added:
  `D:\AI_round2\docs\plans\AETHER_RECOVERED_CONCEPT_INTEGRATION_AUDIT_2026-06-24.md`.
  Broad artifact diving is paused; the main roadmap can resume from the audit.
- Phase 1.7 tone/personality repair pass implemented for real-use dork/courtroom
  motivation prompts. Aether now buffers that narrow repairable path, checks the
  full final answer for required style anchors and unrequested code/coding
  drift, asks for one repair when needed, and falls back to a deterministic
  governed answer if the local model keeps violating the hard anchors.
- Phase 1.7 project-business continuity repair added after live testing exposed
  a generic answer to the prompt about refiling an LLC and possibly registering
  Aeteros as an AI company. Context Bridge now treats Aeteros/LLC/AI-company
  prompts as project context, preserves the exact Aeteros spelling, connects the
  answer to the Aeteros/Aether/CORE-CRT/Aether Workbench lineage, avoids generic
  startup checklists, applies the real-use depth floor, and adds
  `real_use_aeteros_llc_ai_company` to the opt-in real-use eval lane. Focused
  verification:
  `python -m pytest tests/test_sidecar_context_bridge.py tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_aeteros_business_repairs_generic_startup_checklist tests/test_sidecar_depth.py tests/test_workbench_eval.py -q`
  -> `33 passed`; broader sidecar smoke:
  `python -m pytest tests/test_sidecar_context_bridge.py tests/test_sidecar_app.py tests/test_sidecar_depth.py tests/test_workbench_eval.py tests/test_sidecar_ingest.py tests/test_runtime_query.py tests/test_sidecar_direct_answer.py tests/test_sidecar_consolidation.py tests/test_support_pattern_fixture_eval.py tests/test_disposition_fixture_eval.py tests/test_sidecar_support_patterns.py -q`
  -> `89 passed`.
- Phase 1.7 Nick-style real-use proxy expansion added for autonomous testing:
  - new opt-in eval cases:
    `real_use_project_doubt_viability`,
    `real_use_autonomous_checkin_status`,
    `real_use_archive_style_boundary`;
  - prompt scaffolding now covers project doubt/viability questions, autonomous
    status/check-in questions, and GPT archive/style-mining boundary questions;
  - these lanes are repairable/buffered before streaming and receive the
    real-use depth floor when triggered;
  - body-safe ChatGPT archive scan rerun with no title examples:
    `D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_scan_20260624_220305_style_proxy.json`;
  - scan result: 1,275 conversations, 96,980 messages counted,
    `message_bodies_extracted=false`, `memory_ingestion_performed=false`;
    review-required support-pattern candidates remain title/category-derived
    only: Aether/AI, coding/project, creative voice, spiral depth, motivation
    support, business/admin, and personal-history warning;
  - verification:
    `python -m pytest tests/test_sidecar_app.py tests/test_sidecar_depth.py tests/test_workbench_eval.py tests/test_sidecar_context_bridge.py tests/test_sidecar_ingest.py tests/test_runtime_query.py tests/test_sidecar_direct_answer.py tests/test_sidecar_consolidation.py tests/test_support_pattern_fixture_eval.py tests/test_disposition_fixture_eval.py tests/test_sidecar_support_patterns.py -q`
    -> `93 passed`;
    `python -m py_compile aether\sidecar\prompt.py aether\sidecar\app.py aether\sidecar\depth.py scripts\workbench_eval.py`
    -> passed.
- Isolated fixture eval runbook added:
  `D:\AI_round2\docs\plans\AETHER_ISOLATED_FIXTURE_EVAL_RUNBOOK_2026-06-25.md`.
  Workbench npm aliases now include:
  - `npm run eval:dispositions:no-write`;
  - `npm run eval:dispositions:keep`;
  - `npm run eval:support-patterns:no-write`;
  - `npm run eval:support-patterns:keep`.
  The runbook documents why direct `--include-disposition-eval` requires a
  controlled fixture sidecar and should not be run against Nick's live substrate
  expecting seeded synthetic conflicts.
- Workbench learner preview UI added for the Phase 2 governed consolidation /
  Mirus lane:
  - bottom navigation now includes a read-only `Learn` drawer;
  - the drawer calls `GET /v1/consolidation/candidates?limit=20`;
  - it shows preview-only safety flags, inspected-turn count, review-route
    surfaces, proposed actions, risk boundaries, and evidence summaries;
  - each mapped route can open the existing Memory, Support, or Reflection
    review drawer without approving or applying the candidate;
  - contradiction-review routes pass their `slot_id` into Memory, preselect the
    exact slot detail, and show a learner-origin review banner without mutating
    memory;
  - support/reflection candidates with adapter drafts now show a bounded draft
    payload preview so the review step is concrete without submitting anything;
  - it does not write memory, import support patterns, or create reflections;
  - candidates still have to route through Memory, Support, or Reflection review
    surfaces before becoming durable;
  - verification:
    `npm run test:ui -- --run src/components/ConsolidationDrawer.test.tsx src/components/MemoryDrawer.test.tsx src/App.test.tsx`
    -> `15 passed`;
    `npm run build` -> passed;
    `python -m pytest tests/test_sidecar_consolidation.py -q` -> `5 passed`.
- Fresh focused verification after restarting the live sidecar:
  - `python -m pytest tests/test_sidecar_app.py -k "real_use_tone_personality" -q`
    -> `3 passed`;
  - `python -m pytest tests/test_sidecar_app.py -q` -> `21 passed`;
  - `python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_tone_personality_regression`
    -> `1/1` passing,
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_183328.json`;
  - `python scripts\workbench_eval.py --include-real-use-eval --case-id memory_boundary --case-id real_use_identity_continuity_boundary`
    -> `2/2` passing,
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_183421.json`.
  A full live run before restarting the stale sidecar reported `22/25`, but the
  focused failures passed after restart.
- Fresh split full-lane verification on the restarted sidecar passed `25/25`
  across core, depth, programming, and real-use cases:
  - core/governance/model-switch slice:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_184401.json`
    (`9/9`);
  - depth/continuation slice:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_184439.json`
    (`4/4`);
  - programming/code-tool slice:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_184530.json`
    (`6/6`);
  - Phase 1.7 real-use slice:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_184657.json`
    (`6/6`).
  The single monolithic `--include-real-use-eval` command timed out before
  writing a report, so use split slices or a longer timeout for full-lane live
  verification.

North star:

```text
Make local and smaller models coherently useful enough that Nick does not have
to depend solely on frontier models.
```

This is not a competition with frontier systems. Aether's value is the harness:
governed memory, traces, retrieval, continuation, correction, local tools, and
clean escalation when frontier help is truly needed.

Next work should stabilize this lane rather than revive legacy code. The
integration audit is complete enough to resume implementation work:

0. consult the integration audit before pulling recovered concepts forward;
1. continue Phase 1.8 contradiction disposition governance by broadening review
   surfacing only if needed; the isolated disposition fixture runner now exists.
2. fold recovered-principles work into evals: contradiction dispositions,
   memory-state/context compression, belief/speech separation, and trace-as-
   training-signal review.
3. continue the Phase 2 background consolidation lane by adding Workbench UI
   affordances for previewed consolidation candidates using their
   `review_route` metadata.
4. then continue Phase 1.9 memory-state/context-compression evals.

Depth mode should be implemented as a governed multi-pass answer-quality loop:
detect requested depth, optionally make a short user-facing approach plan,
generate, self-check for coverage/length/instruction fit, continue if needed,
and persist depth/continuation metadata in the trace. The classifier, self-check,
continuation loop, metadata persistence, and Trace drawer depth card are in
place; a live verbose eval now forces continuation through missing requested
coverage, explicit two-pass prompts can force one continuation, and repeated
leading continuation blocks are trimmed before append. A `phi3:3.8b` spiral
continuation eval now passes. Keep watching continuation quality, but the main
workstream can move to Phase 1.6. It should not expose raw chain-of-thought or
treat longer output as inherently more true.

Programming robustness is the next proof lane after depth. Aether should learn
to search/read project context, explain code, propose bounded patches, recommend
focused tests, capture governed test results, and package clean escalation
packets. The point is not to clone a frontier coding agent; it is to make local
code/project work coherent, traceable, and good enough for the first pass.

Phase 1.6 has started. The eval runner now checks a `TraceDrawer` workspace
search, a `depth.py` file-read explanation, a preview-only bounded patch, a
planning-only no-edit test recommendation, and a structured
`workspace_test_recommend` result with `executed=false`, plus a governed
`workspace_test_run` pytest result with `executed=true`, exit code, pass/fail,
timeout, stdout, and stderr. It includes completed tool runs, retrieved paths,
`applied=false` patch metadata, and absence of forbidden patch tools for no-edit
asks. The Trace drawer now surfaces first-pass structured code-tool metadata for
those traces, including clipped stdout/stderr blocks for captured tests,
retrieved search/read snippets, and visible notices for failed/non-ready/stale-
sensitive tool states. Programming escalations now include a bounded
`programming_context` section with relevant files/snippets and tool-result
summaries. Code tools also support explicitly configured read-only reference
roots for search/read/list while keeping patch/test operations workspace-only.
The eval runner has an opt-in reference-root case for the downloaded source tree
and a `--case-id` filter for focused live checks.
The Code Context Tools v1 contract is defined in
`D:\AI_round2\docs\plans\AETHER_LOCAL_CODER_V1.md`. The latest clean live eval
is:

```text
D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_141221.json
Aether Workbench eval: 19/19 passed
```

After Phase 1.6, add a real-use reliability lane. The target behavior is not
only "answer deeply"; it is the way Nick actually uses GPT: dorky but grounded
motivation, spiral-depth synthesis, personal continuity, practical task
handoff, and high-stakes caution without becoming generic or inert. Seed cases
should cover walking/weight-scale support, persistent AI/longevity synthesis,
WordPress/client setup permission boundaries, abrupt task switching, and
over-governance regression checks.

The ChatGPT export now has a dry-run personal archive scanner before any
ingestion. It parses metadata/titles, labels likely
spiral/support/project/history threads, counts structure, and writes explicit
`memory_ingestion_performed=false` / `message_bodies_extracted=false` safety
metadata. It now also emits review-required support-pattern candidates from
title-category counts only, and the sidecar now has a revision-guarded,
idempotent review API for importing/listing/detailing/reviewing those
candidates. Workbench now has a Support review drawer for filtering and
accepting/deferring/rejecting those candidates. Accepted support patterns now
influence behavior through governed Context Bridge/prompt inputs without
becoming confirmed facts. Next, continue into contradiction disposition
governance. Do not inject the GPT voice into Aether.

Background consolidation heartbeat is now a planned Phase 2 bridge from OG
Mirus into current Aether language. It should periodically inspect recent
conversations, traces, failed/repair routes, contradictions, and accepted/rejected
review items to produce reviewable candidates:

- user/project/work context candidates;
- speaking-cadence and support-style candidates;
- contradiction review candidates for resolvable/evolving/contextual conflicts;
- Aether self-improvement reflection candidates when traces show thin answers,
  over-governance, missed tone, wrong route, weak tool use, or repair fallback.

Guardrail:

```text
observe -> summarize -> classify -> propose -> review -> apply
```

The heartbeat is allowed to learn patterns. It is not allowed to become a quiet
memory ingestion crawler.

The first safe slices are implemented: a pure candidate planner, a preview-only
sidecar endpoint over recent turns/traces, and review-route metadata pointing
each candidate toward Memory, Support, or Reflection review surfaces. Next, add
Workbench UI affordances for those previewed candidates without applying them
directly.

## Developer shortcuts

Run the focused conversation eval against the live sidecar from either location:

```powershell
cd D:\AI_round2\aether-core
python scripts\workbench_eval.py
```

Run the opt-in Phase 1.7 real-use reliability eval lane:

```powershell
cd D:\AI_round2\aether-core
python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_persistent_ai_longevity_spiral --case-id real_use_walking_scale_medical_caution --case-id real_use_wordpress_handoff_permissions --case-id real_use_abrupt_switch_business_plan
```

Run the isolated Phase 1.8 contradiction-disposition fixture eval without
touching live memory:

```powershell
cd D:\AI_round2\aether-core
python scripts\run_disposition_fixture_eval.py
```

or:

```powershell
cd D:\AI_round2\workbench
npm run eval:dispositions
```

Run the isolated reviewed support-pattern fixture eval without touching live
memory:

```powershell
cd D:\AI_round2\aether-core
python scripts\run_support_pattern_fixture_eval.py
```

or:

```powershell
cd D:\AI_round2\workbench
npm run eval:support-patterns
```

Run the Phase 1.7 dry-run ChatGPT archive scanner without printing title
examples:

```powershell
cd D:\AI_round2\aether-core
python scripts\chatgpt_archive_scan.py "C:\Users\block\Downloads\fbf5a239c1af822f50241d4b5999b53954689723b9d4deb7ceb1e41a31847485-2026-03-27-22-39-55-cf0803cbc48c446cb8c3b317ea5f11ea" --max-examples 0
```

or:

```powershell
cd D:\AI_round2\workbench
npm run eval:workbench
```

Run the Workbench dev shell with the fixed Vite port:

```powershell
cd D:\AI_round2\workbench
npm run dev
```

The dev script binds Vite to `127.0.0.1:5175` with `--strictPort`; if that port
is already occupied, startup fails clearly instead of letting Electron wait for
or load the wrong server. In development, Electron also uses an isolated temp
`userData` directory so stale packaged or prior-dev cache does not bleed into
the Workbench proof loop.

## Goal

Ship a Windows-first, independently runnable Aether companion that proves the
governed-memory loop without reviving the legacy harness.

```text
Narrow Electron dock
  -> Aether governed context
  -> qwen2.5:7b-instruct through Ollama
  -> local response and visible release trace
  -> memory correction drawer
  -> optional manual Codex escalation
```

## Today’s vertical slice

- New `aether.sidecar` FastAPI service bound to `127.0.0.1`.
- SQLite persistence at `~/.aether/workbench.db`.
- Existing slot substrate at `~/.aether/substrate.json`.
- Governed, streaming Ollama chat.
- Trace and memory inspection.
- Explicit confirm, correct, and quarantine writes.
- Manual, bounded `codex exec` escalation.
- New isolated `workbench/` Electron + React/Vite application.

## Sidecar API

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/stream`
- `GET /v1/slots`
- `GET /v1/slots/{slot_id}`
- `POST /v1/slots/{slot_id}/confirm`
- `POST /v1/slots/{slot_id}/correct`
- `POST /v1/slots/{slot_id}/quarantine`
- `POST /v1/escalations`
- `GET /v1/traces/{turn_id}`

## Response policy

For every user message, Aether plans all clauses and independently retrieves
each requested slot. Only `answerable` evidence enters the local model context.
Conflicted, withheld, missing, and quarantined state becomes an explicit
uncertainty instruction. Full release decisions remain visible in the trace.

Codex escalation is manual only. It receives the question, local attempt,
unresolved clauses, governed answerable evidence, and escalation reason. It
never receives the complete substrate.

## Desktop behavior

- 420px full-height left-edge snap overlay.
- Optional always-on-top.
- Toggle to a normal floating window.
- Tray hide/show.
- Trace or Memory drawer expands the window to approximately 780px.

## Explicit exclusions

No scheduling, auth, cloud sync, agents, jobs, loops, telemetry, desktop
control, plugin marketplace, automatic frontier escalation, or legacy
`crt_api.py` startup.

## Acceptance

1. Chat locally through Ollama.
2. Inspect clause-level release decisions and evidence.
3. Correct a temporary slot and observe the next response use it.
4. Manually invoke Codex and retain an escalation receipt.
5. Build and run without starting the legacy frontend or API.
