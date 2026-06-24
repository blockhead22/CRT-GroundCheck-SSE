# Aether Workbench v1 — Local Sidecar

## Current status - 2026-06-24

Latest continuity packet:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-24.md
```

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
  tests proving private message body strings are not included in reports.
  Safe real-export scan output:
  `D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_scan_20260624_phase17.json`.
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

North star:

```text
Make local and smaller models coherently useful enough that Nick does not have
to depend solely on frontier models.
```

This is not a competition with frontier systems. Aether's value is the harness:
governed memory, traces, retrieval, continuation, correction, local tools, and
clean escalation when frontier help is truly needed.

Next work should stabilize this lane rather than revive legacy code:

1. add one or two more reviewed Phase 1.7 usage cases, especially tone/personality
   regression and identity/continuity boundaries;
2. add a review workflow for archive-derived support-pattern candidates without
   treating them as confirmed facts;
3. make reviewed reflections stronger but still governed behavior input.

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
metadata. Next, use reviewed title buckets to seed reliability evals and send
candidate durable facts or support preferences through review. Do not inject the
GPT voice into Aether.

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
