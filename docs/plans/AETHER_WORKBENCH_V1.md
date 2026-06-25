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
1. add Workbench UI affordances for support-pattern candidate review.
2. fold recovered-principles work into evals: contradiction dispositions,
   memory-state/context compression, belief/speech separation, and trace-as-
   training-signal review.
3. start Phase 1.8 contradiction disposition governance.

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
candidates. Accepted support patterns now influence behavior through governed
Context Bridge/prompt inputs without becoming confirmed facts. Next, add
Workbench UI review affordances and continue into contradiction disposition
governance. Do not inject the GPT voice into Aether.

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
