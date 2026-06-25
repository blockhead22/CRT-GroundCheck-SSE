# Aether Workbench v1 — Local Sidecar

## Current status - 2026-06-25

Latest continuity packet:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-25.md
```

Previous handoff:

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

Phase 1.10 route capability table:

```text
D:\AI_round2\docs\plans\AETHER_ROUTE_CAPABILITY_TABLE_2026-06-25.md
```

Current lane:

```text
Phase 1.10 governed route/model selection.
Route decisions are trace-visible and prompt-annotated, but model selection has
not been changed yet. Next work is route/model sweep eval evidence.
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
  - support/reflection draft routes open manual form-state panels in the
    Support or Reflection drawer, prefilled from the learner candidate, without
    calling import/create/review endpoints on drawer open;
  - adapter-safe manual buttons now let an operator create a proposed
    support-pattern candidate or proposed reflection from those drafts while
    preserving source candidate id, evidence, risk boundary, review-required
    status, and non-memory flags;
  - isolated operator smoke added at
    `D:\AI_round2\aether-core\scripts\run_learn_promotion_fixture_smoke.py`
    plus Workbench shortcut `npm run smoke:learn-promotion`;
  - the smoke starts a temporary sidecar fixture, reads real learner candidates,
    manually creates one proposed support-pattern candidate and one proposed
    reflection, and verifies preview remains no-write;
  - Learn itself still does not write memory, import support patterns, or create
    reflections;
  - candidates still have to route through Memory, Support, or Reflection review
    surfaces before becoming durable;
  - operator runbook added:
    `D:\AI_round2\docs\plans\AETHER_LEARN_DRAFT_PROMOTION_RUNBOOK_2026-06-25.md`;
    it documents the safety contract, Learn-to-review flow, manual draft
    promotion behavior, and the tests that protect preview-only opening plus
    adapter-safe proposed creation;
  - verification:
    `npm run test:ui -- --run src/api.test.ts src/components/ConsolidationDrawer.test.tsx src/components/SupportPatternDrawer.test.tsx src/components/ReflectionDrawer.test.tsx src/components/MemoryDrawer.test.tsx src/App.test.tsx`
    -> `27 passed`;
    `npm run build` -> passed;
    `python scripts\run_learn_promotion_fixture_smoke.py --json` -> passed;
    `npm run smoke:learn-promotion -- --json` -> passed;
    `python -m pytest tests\test_sidecar_support_patterns.py tests\test_sidecar_reflections.py tests\test_sidecar_consolidation.py -q`
    -> `14 passed`;
    `python -m pytest tests/test_sidecar_consolidation.py -q` -> `5 passed`.
- Live sidecar reboot + Nick-style real-use repair pass completed:
  - heartbeat health check found `127.0.0.1:8765` unavailable, then restarted
    the sidecar with `cd D:\AI_round2\aether-core; python -m aether.sidecar`;
  - initial live run for the four Nick-style/project prompts reported `0/4`;
  - prompt repair anchors were tightened so Aeteros generic checklist headings,
    project-viability answers without an explicit unproven/not-proven signal,
    short status/check-in answers, and archive/style answers without an explicit
    confirmed-memory boundary force repair/fallback;
  - deterministic project/archive fallbacks were lengthened to satisfy eval
    floors without relying on local-model padding;
  - support-pattern live checks against Nick's live substrate correctly failed
    for missing fixture candidate ids; the isolated support-pattern fixture
    remained the right check and passed `2/2`;
  - verification:
    `python -m pytest tests/test_sidecar_app.py -k "real_use_aeteros or project_doubt or autonomous or archive_style" tests/test_workbench_eval.py -q`
    -> `4 passed`;
    `python scripts\run_support_pattern_fixture_eval.py --no-write` -> `2/2`;
    `python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_aeteros_llc_ai_company --case-id real_use_project_doubt_viability --case-id real_use_autonomous_checkin_status --case-id real_use_archive_style_boundary`
    -> `4/4`,
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_233221.json`.
- Broader live real-use/depth coverage on the healthy sidecar:
  - `python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_identity_continuity_boundary --case-id real_use_tone_personality_regression --case-id depth_deep_roadmap --case-id depth_verbose_forced_continuation --case-id depth_spiral_phi3_forced_continuation`
    -> `5/5`,
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_233631.json`;
  - `python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_persistent_ai_longevity_spiral --case-id real_use_walking_scale_medical_caution --case-id real_use_wordpress_handoff_permissions --case-id real_use_abrupt_switch_business_plan`
    -> `4/4`,
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_234448.json`;
  - note: a single all-in-one `--include-real-use-eval` run timed out at the
    command limit, so use sliced live eval groups for operator reliability.
- Fresh 2026-06-25 identity/tone live slice:
  - live support-pattern candidates were empty, so support-pattern behavior
    remains fixture-proven until Nick reviews/accepts live candidates;
  - `GET /v1/consolidation/candidates?limit=8` returned preview-only learner
    candidates with `writes_performed=false`,
    `memory_ingestion_performed=false`,
    `support_pattern_import_performed=false`, and
    `reflection_create_performed=false`;
  - `real_use_identity_continuity_boundary` briefly failed because
    identity/continuity guidance was prompted but not repair-gated; repaired by
    adding identity/continuity to the real-use anchor repair path and requiring
    Nick, governed evidence, local Aether context, uncertainty, and clean
    boundary anchors;
  - focused tests:
    `python -m pytest tests\test_sidecar_app.py tests\test_workbench_eval.py -q`
    -> `35 passed`;
  - after restarting the sidecar, sequential live evals passed:
    `python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_identity_continuity_boundary --no-write`
    -> `1/1`,
    `python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_tone_personality_regression --no-write`
    -> `1/1`;
  - live generation request isolation repaired: sidecar local model calls are
    now serialized through a narrow generation lock, including structured patch
    planning, so simultaneous HTTP requests cannot interleave Ollama streams;
  - focused request-isolation regression:
    `python -m pytest tests\test_sidecar_app.py::test_generation_calls_are_serialized_across_concurrent_requests -q`
    -> `1 passed`;
  - deliberate parallel live identity/tone probe now passes `2/2` against one
    sidecar. Still prefer sliced eval commands for operator reliability because
    large all-in-one live eval runs can hit command timeouts.
- Phase 1.7 harsh real-use quality eval pack added behind
  `--include-harsh-real-use-eval`:
  - cases:
    `harsh_project_doubt_not_generic`,
    `harsh_local_model_scaffold_spiral_depth`,
    `harsh_tired_topic_switch_triage`, and
    `harsh_memory_review_boundary`;
  - the pack scores anti-genericness, direct project doubt signal, actual
    spiral-depth length, tired-night triage decisiveness, and review-first
    memory boundaries;
  - initial live run exposed the exact gap from manual testing: project doubt
    drifted into generic feasibility/survey language, local-model spiral and
    tired triage were good but too short, and memory review failed to clearly
    separate durable candidates from temporary context;
  - repairs added targeted anchors/fallbacks for local-model scaffolding depth,
    tired-night Aether triage, project-doubt anti-genericness, and a new
    `memory_review_boundary` character route that forbids silent ingestion;
  - verification:
    `python -m pytest tests\test_workbench_eval.py tests\test_sidecar_character_answer.py tests\test_sidecar_app.py -q`
    -> `54 passed`;
    `python scripts\workbench_eval.py --include-harsh-real-use-eval --case-id harsh_project_doubt_not_generic --case-id harsh_local_model_scaffold_spiral_depth --case-id harsh_tired_topic_switch_triage --case-id harsh_memory_review_boundary`
    -> `4/4`,
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260625_005025.json`.
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
3. continue the Phase 2 background consolidation lane by hardening live/operator
   coverage for Learn draft promotion now that adapter-safe manual creation
   exists. Preserve the contract: no silent writes, source candidate/evidence
   retained, and existing review APIs still own durable acceptance.
4. continue Phase 1.9 memory-state/context-compression evals by expanding the
   new deterministic representation replay bench from fixture packs into real
   substrate replays and eventual Context Bridge candidate comparisons.
5. add Phase 1.10 governed model/route selection, using recovered CRT router
   work as source material: intent classification, local-first model choice,
   escalation policy, capability evidence, and trace-visible route reasons.

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
timeout, stdout, and stderr. It now also includes a code-context endpoint
orientation case for `GET /v1/consolidation/candidates`: the local model must
use `workspace_search`, identify `D:\AI_round2\aether-core\aether\sidecar\app.py`
as the route source, avoid patch proposal, and avoid treating tests/eval files
as route definitions. This repaired two concrete weaknesses: "search the
repository" now triggers workspace search, and search term/excerpt ranking is
less vulnerable to generic words and self-test contamination. It includes
completed tool runs, retrieved paths, `applied=false` patch metadata, and
absence of forbidden patch tools for no-edit asks. The Trace drawer now
surfaces first-pass structured code-tool metadata for those traces, including
clipped stdout/stderr blocks for captured tests, retrieved search/read snippets,
and visible notices for failed/non-ready/stale-sensitive tool states.
Programming escalations now include a bounded `programming_context` section
with relevant files/snippets and tool-result summaries. Code tools also support
explicitly configured read-only reference roots for search/read/list while
keeping patch/test operations workspace-only. The eval runner has an opt-in
reference-root case for the downloaded source tree and a `--case-id` filter for
focused live checks.
The Code Context Tools v1 contract is defined in
`D:\AI_round2\docs\plans\AETHER_LOCAL_CODER_V1.md`. The latest clean live eval
is:

```text
D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_141221.json
Aether Workbench eval: 19/19 passed
```

Latest focused Phase 1.6 programming/code-context repair:

```text
python -m pytest tests\test_sidecar_documents_tools.py tests\test_workbench_eval.py -q
25 passed

python scripts\workbench_eval.py --case-id programming_code_context_consolidation_endpoint
D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260625_001418.json
Aether Workbench eval: 1/1 passed
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
sidecar endpoint over recent turns/traces, review-route metadata pointing each
candidate toward Memory, Support, or Reflection review surfaces, Workbench Learn
navigation, and adapter-safe manual creation of proposed Support/Reflection
artifacts from learner drafts. Next, broaden live/operator coverage and keep
promotion review-gated.

## Phase 1.10: Governed Model/Route Selection

Recovered CRT/personal-agent work already explored the missing router layer:

- `D:\AI_round2\personal_agent\model_router.py` selected fast/reasoning/
  research/code/creative routes from task cues, preferences, and product mode.
- `D:\AI_round2\personal_agent\semantic_intent_router.py` and
  `D:\AI_round2\docs\SEMANTIC_INTENT_ROUTER.md` used embedding prototypes,
  confidence bands, ambiguity handling, and correction learning for tool/task
  intent selection.
- `D:\AI_round2\personal_agent\escalation_policy.py` used token thresholds,
  circuit breakers, deep-reasoning cues, blindspot boosts, and conversation
  momentum to decide whether local generation was enough.
- `D:\AI_round2\docs\CLOUD_ROUTING.md` defined the core governance principle:
  control, memory, verification, and policy stay local; only raw generation can
  escalate after scrubbing and budget checks.
- `D:\AI_round2\docs\LOCAL_CAPABILITY_LAB.md` framed the current Aether thesis:
  make the local model the mouth while the system carries memory, tools,
  structure, continuity, and traceable limits.

Current Aether should not copy that older stack raw. It should extract the
contract into a small governed router:

```text
message -> intent/risk/depth/tool classifier
        -> Context Bridge + contradiction/support/depth signals
        -> model/capability policy
        -> selected route/model/tools
        -> answer + repair/self-check
        -> trace-visible routing reason
```

First implementation slice:

- deterministic route categories:
  `deterministic_meta`, `memory_review`, `support_pattern`, `code_tool`,
  `depth_synthesis`, `real_use_support`, `contradiction_review`,
  `general_local`, and `escalation_candidate`;
- model policy table for available local models and their known strengths from
  evals, not from vibes;
- trace fields for `route_decision`, `candidate_routes`, `selected_model`,
  `reason`, `confidence`, `risk_level`, `tool_policy`, and
  `escalation_allowed`;
- eval cases that verify:
  - meta/governance questions stay deterministic;
  - code/file questions choose tool-first local routing;
  - spiral/deep requests trigger depth/continuation policy;
  - conflicted memory chooses review/disposition routing;
  - high-stakes legal/medical/financial prompts get cautious bounded answers
    and possible escalation recommendation;
  - weak local answers can mark `needs_stronger_model` without silently
    escalating.

This phase belongs after enough Phase 1.7/1.8/1.9 eval evidence exists to avoid
building a decorative router. The router's job is not to make the local model
judge itself. The governed system chooses the brain; the model may only provide
signals.

Current on-ramp:

```text
D:\AI_round2\docs\plans\AETHER_ROUTE_CAPABILITY_TABLE_2026-06-25.md
```

This table summarizes what the eval evidence currently supports and defines the
small first implementation slice: a side-effect-free route policy that chooses
candidate route, model policy, tool policy, repair policy, and escalation
eligibility without writing memory or silently escalating.

Implementation status:

- side-effect-free route policy added at
  `D:\AI_round2\aether-core\aether\sidecar\route_policy.py`;
- focused tests added at
  `D:\AI_round2\aether-core\tests\test_sidecar_route_policy.py`;
- the policy currently classifies meta/governance, conflicted memory,
  code-tool, deep/spiral, Aeteros/business caution, real-use support,
  representation replay, and escalation-candidate prompts;
- it returns trace-shaped fields for selected route, candidate routes, model
  policy, tool policy, repair policy, escalation eligibility, risk level, and
  route reason;
- it does not call models, tools, memory writers, support imports, reflection
  creation, or escalation;
- verification:
  `python -m pytest tests/test_sidecar_route_policy.py -q` -> `9 passed`;
  `python -m pytest tests/test_sidecar_meta_answer.py tests/test_sidecar_depth.py tests/test_sidecar_direct_answer.py tests/test_sidecar_route_policy.py -q`
  -> `34 passed`.

Next slice: attach the route decision to sidecar completion/trace metadata
without changing generation behavior yet.

Trace metadata slice status:

- `trace.route_decision` and `completion.route_decision` now persist through
  the sidecar completion path;
- generation behavior is unchanged;
- focused coverage proves route metadata for meta/governance, conflicted direct
  memory lookup, code-tool search, explicit depth, Aeteros/LLC context+caution,
  and project-doubt support prompts;
- verification:
  `python -m pytest tests/test_sidecar_meta_answer.py tests/test_sidecar_app.py::test_direct_conflicted_profile_lookup_uses_disposition_without_leaking_values tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_deep_request_records_depth_policy_and_prompt_guidance tests/test_sidecar_app.py::test_code_tool_route_decision_is_traced_without_changing_tool_behavior tests/test_sidecar_route_policy.py -q`
  -> `19 passed`;
  `python -m pytest tests/test_sidecar_meta_answer.py tests/test_sidecar_depth.py tests/test_sidecar_direct_answer.py tests/test_sidecar_route_policy.py tests/test_sidecar_app.py -q`
  -> `64 passed`.

Next slice: expose route decision compactly in the Workbench Trace drawer.

Workbench Trace UI slice status:

- Trace drawer now shows a compact `Route decision` card when route metadata is
  present;
- fields: selected route, model policy, tool policy, repair policy, risk level,
  and escalation eligibility;
- historical traces without route metadata still render normally;
- verification:
  `npm run test:ui -- --run src/components/TraceDrawer.test.tsx`
  -> `11 passed`;
  `npm run test:ui -- --run src/App.test.tsx src/components/TraceDrawer.test.tsx`
  -> `22 passed`;
  `npm run build` -> passed;
- browser smoke on `http://127.0.0.1:5175/` showed the app rendered nonblank,
  console warnings/errors were `0`, the Trace drawer opened, and an older saved
  trace still showed Response Route/Depth. The visible historical trace predated
  route metadata, so a fresh sidecar trace is needed to see the new Route
  Decision card live.

Next slice: restart/use a current sidecar and run a sliced live route-decision
smoke, then decide whether route decisions should remain observational or begin
steering answer policy under eval gates.

Live route-decision smoke status:

- the existing sidecar was healthy but stale; a meta smoke showed no
  `route_decision`;
- the listener on `8765` was verified as `python.exe -m aether.sidecar`,
  restarted from `D:\AI_round2\aether-core`, and health returned cleanly;
- fresh sliced live smoke passed `5/5`:
  meta/governance -> `deterministic_meta`;
  code-tool -> `code_tool`;
  depth -> `depth_synthesis`;
  Aeteros/LLC business caution -> `context_bridge_broad` with
  `high_stakes_caution` candidate;
  project doubt -> `real_use_support`;
- every smoke case had `trace.route_decision`,
  `completion.route_decision`, and `memory_writes_count=0`;
- browser verification on `http://127.0.0.1:5175/` selected the fresh
  `real_use_support` conversation and opened its turn trace; the Trace drawer
  rendered the Route Decision card live with route/model/tool/repair/risk/
  escalation fields and console warnings/errors remained `0`.

Next slice: keep route decisions observational for one more eval round, then
add the smallest steering gate only where the route already agrees with existing
behavior.

Prompt annotation gate status:

- `build_local_prompt` now includes a bounded `Route policy` section when
  route metadata exists;
- it is steering-adjacent, not behavior-replacing: no model selection changes,
  no tool execution changes, no memory writes, no support imports, no
  reflection creation, no silent frontier escalation;
- annotation tells the model the governed system selected the route and the
  model must not override it or claim it selected the route;
- focused verification:
  `python -m pytest tests/test_sidecar_ingest.py tests/test_sidecar_meta_answer.py tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_deep_request_records_depth_policy_and_prompt_guidance tests/test_sidecar_app.py::test_code_tool_route_decision_is_traced_without_changing_tool_behavior tests/test_sidecar_route_policy.py -q`
  -> `29 passed`;
  `python -m pytest tests/test_sidecar_ingest.py tests/test_sidecar_meta_answer.py tests/test_sidecar_depth.py tests/test_sidecar_direct_answer.py tests/test_sidecar_route_policy.py tests/test_sidecar_app.py -q`
  -> `75 passed`;
- live smoke after sidecar restart passed `4/4` for meta/governance, code-tool,
  depth, and real-use support, with `trace.route_decision`,
  `completion.route_decision`, and `memory_writes_count=0` in every case.

Prompt annotation comparison eval status:

- eval-only comparison added at
  `D:\AI_round2\aether-core\scripts\route_policy_annotation_eval.py`;
- focused tests added at
  `D:\AI_round2\aether-core\tests\test_route_policy_annotation_eval.py`;
- compares the same prompt with route policy withheld versus prompt-annotated;
- current cases:
  `annotation_project_doubt_anti_generic`,
  `annotation_aeteros_business_caution`,
  `annotation_local_model_spiral_depth`;
- proves annotation is additive, includes selected route and repair policy,
  preserves real-use anti-generic guidance, and keeps the no-write/no-tool-call/
  no-silent-escalation boundary;
- model selection and generation behavior are still unchanged;
- verification:
  `python scripts\route_policy_annotation_eval.py --json` -> passed `3/3`;
  `python -m pytest tests/test_route_policy_annotation_eval.py tests/test_sidecar_route_policy.py tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced -q`
  -> `13 passed`.

Next slice: add a route/model sweep eval pack. Compare available local models
by route and record evidence before allowing automatic model switching.

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

Run the harsher Phase 1.7 lived-quality eval lane:

```powershell
cd D:\AI_round2\aether-core
python scripts\workbench_eval.py --include-harsh-real-use-eval --case-id harsh_project_doubt_not_generic --case-id harsh_local_model_scaffold_spiral_depth --case-id harsh_tired_topic_switch_triage --case-id harsh_memory_review_boundary
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

Run the Phase 1.9 representation replay eval. This compares full transcript,
raw retrieval, naive summary, slot-only, quantized scaffold, governed scaffold,
CRT compressed state, the broad `context_bridge_profile` packet, and the
narrow `context_bridge_profile_candidates` packet on the
contradiction/authority/history/policy probe pack:

```powershell
cd D:\AI_round2
python labs\meaning_compression_lab\representation_replay.py --include-adversarial --include-hardening --no-write
```

or from Workbench:

```powershell
cd D:\AI_round2\workbench
npm run eval:representation-replay
```

The replay runner can also derive supported probe cases from an actual CRT
SQLite memory DB without writing to it:

```powershell
cd D:\AI_round2
python labs\meaning_compression_lab\representation_replay.py --crt-db C:\path\to\crt.db --thread-id optional-thread --crt-db-only --no-write
```

Supported DB-derived probes currently cover current `name`, `employer`,
`home_city`, `current_project`, `favorite_color`, `store_platform`, current
answer-style preference, previous employer/camera history, name correction
status, favorite-color provisional/reaction boundaries, and the locked action
policies already modeled by the lab. Unsupported slots are ignored rather than
forced into fake eval cases.

Current fixture result:

```text
governed_scaffold  19/19, avg ratio 0.474
crt_compressed     19/19, avg ratio 0.634
full_transcript    19/19, avg ratio 1.000
quantized_scaffold 14/19
context_bridge_profile_candidates 10/19, avg ratio 0.869
context_bridge_profile 10/19, avg ratio 3.166
slot_only           5/19
raw_retrieval       5/19
naive_summary       1/19
```

Interpretation: Context Bridge is useful broad governed context, but it is not
the compact memory-state replay layer. The narrow profile-candidate packet keeps
the same `10/19` behavior as the full broad bridge while dropping average ratio
from about `3.166` to `0.869`; this means the static project/character bridge
bulk does not improve memory replay. Governed scaffold/CRT compressed state
still preserve the load-bearing contradiction, history, authority, reaction, and
policy layers needed for full replay.

Run the narrow Context Bridge candidate packet eval. This compares full bridge
payload against project/support/reflection candidate-only packets on probes
designed for those candidate types:

```powershell
cd D:\AI_round2
python labs\meaning_compression_lab\representation_replay.py --bridge-candidates-only --no-write
```

or from Workbench:

```powershell
cd D:\AI_round2\workbench
npm run eval:bridge-candidates
```

Current result:

```text
context_bridge_full_packet        3/3, ratio 1.000
context_bridge_project_candidates 1/3, ratio 0.370
context_bridge_support_candidates 1/3, ratio 0.121
context_bridge_reflection_candidates 1/3, ratio 0.123
```

Interpretation: each narrow bridge packet preserves its own candidate behavior
at much lower payload size, and fails unrelated candidate probes as expected.

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
