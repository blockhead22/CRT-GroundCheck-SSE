# Aether / CRT / Workbench Handoff - 2026-06-24

This is the restart packet for the next clean Codex thread in `D:\AI_round2`.

The current product lane is still:

```text
aether-core sidecar + Workbench UI
```

Do not revive the legacy frontend/API. Do not pause active development for a repo
breakout yet. The newer Aether lane is still buried inside `AI_round2` on
purpose for now; breakout and old-code removal come later.

## Blunt Current Read

The architecture is promising, but only in the narrowed form:

- the model is replaceable;
- the substrate/governance layer is the continuity;
- Workbench is the proof surface;
- traces, corrections, reviewed reflections, and evals are how behavior becomes
  inspectable.

The older all-in-one assistant/orchestrator/shell direction was too sprawling.
Keep mining it for ideas, but do not revive it as the product path.

## North Star

The goal is not to beat frontier models at raw intelligence.

The goal is:

```text
Make local and smaller models coherently useful enough that Nick does not have
to depend solely on frontier models.
```

Aether should become a personal robustness harness:

- local-first by default;
- governed memory and durable context;
- visible traces and route metadata;
- generative expansion when the user asks for depth;
- code/project context tools for real work;
- honest boundary detection;
- clean escalation packets when a frontier model is actually needed.

The important product question is not "is this model smarter than frontier?"
It is:

```text
Can scaffolding, governance, retrieval, continuation, and correction make a
smaller/local model act coherently enough for daily use?
```

Current evidence says yes, within scope. The stress runs showed smaller models
can handle useful work when given the right structure. They also showed a tradeoff:
governance makes models safer, but can make them hesitant or over-boundary. The
next work is to preserve the safety while making the system more generative,
decisive, and useful.

## What Changed Since The 2026-06-23 Handoff

The 2026-06-23 handoff said the next move was Context Bridge. That has now been
implemented and expanded.

### 1. Context Bridge Is Implemented

Broad identity/project/self/character questions now receive governed context
instead of only narrow slot packets.

Key behavior now works for prompts like:

- `What do you know about me?`
- `How do you know me?`
- `What are we building?`
- `What is Aether Workbench?`
- `What tools can you use?`
- `Should Aether develop its own stable local character over time?`

Context Bridge keeps governance strict:

- confirmed profile facts only;
- conflicted/provisional/quarantined evidence withheld;
- durable documents treated as context, not automatic profile truth;
- withheld categories summarized without revealing values.

Key files:

- `D:\AI_round2\aether-core\aether\sidecar\context_bridge.py`
- `D:\AI_round2\aether-core\aether\sidecar\prompt.py`
- `D:\AI_round2\aether-core\aether\sidecar\app.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_context_bridge.py`

### 2. Character And Reflection Guidance Is Less Canned

Aether now has guided generative routes for:

- why Aether matters;
- what kind of character Aether should develop;
- Aether character in practice;
- personal pattern reflection, especially the "turning return into a courtroom"
  pattern;
- the difference between user memory and Aether character memory;
- small continuity turns like `what else would you like to tell me?`.

Important principle:

```text
User profile memory and Aether character memory are different ledgers.
```

User memory describes Nick. Aether character memory describes reviewed behavior
changes, model adaptation, failures, repairs, traces, and interaction patterns.

Key files:

- `D:\AI_round2\aether-core\aether\sidecar\character_answer.py`
- `D:\AI_round2\aether-core\aether\sidecar\self_description.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_character_answer.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_self_description.py`

### 3. Personal Reflection Route Was Fixed

The live bug was:

```text
What pattern do you think hurts me?
```

It previously fell through to generic local generation. It now routes through:

```text
aether_character / self_assessment
generation_model: qwen3:14b
```

Follow-up `try harder` now stays attached to that reflective route when it
follows a personal-pattern question.

The target answer shape:

- do not call it Nick's worst quality;
- do not make an identity verdict;
- name the pattern: return becoming a courtroom;
- name the counter-pattern: grace, returnability, practical re-entry;
- stay grounded and non-diagnostic.

### 4. Meta Route Explanation Was Added

The prompt:

```text
What model are you using, what context shaped this answer, and should this have stayed local or escalated?
```

now gets a deterministic meta answer. Aether explains selected model, routing,
and whether broad Context Bridge was involved instead of asking the local model
to infer its own route.

Deterministic routes now report:

```text
generation_model: deterministic
```

Key files:

- `D:\AI_round2\aether-core\aether\sidecar\meta_answer.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_meta_answer.py`

### 5. Trace Transparency UI Was Added

The Workbench Trace drawer now shows a `Response route` card with:

- source;
- selected model;
- generated model;
- guidance kind;
- repair status;
- local/escalation boundary.

Example live UI route:

```text
SOURCE
aether character
SELECTED
qwen2.5:7b-instruct
GENERATED
qwen3:14b
GUIDANCE
self assessment
REPAIR
clean
BOUNDARY
local ok
```

Key files:

- `D:\AI_round2\workbench\src\components\TraceDrawer.tsx`
- `D:\AI_round2\workbench\src\components\TraceDrawer.test.tsx`
- `D:\AI_round2\workbench\src\types.ts`
- `D:\AI_round2\workbench\src\styles.css`

### 6. Per-Turn Trace Recall Was Added

Each assistant answer now has a small shield trace button. Clicking it fetches:

```text
GET /v1/traces/{turn_id}
```

and opens that historical turn's exact trace in the drawer.

Caveat:

Older traces saved before completion metadata was merged may not show repair or
boundary fields. New turns should show the full route card.

Key files:

- `D:\AI_round2\workbench\src\components\ChatPanel.tsx`
- `D:\AI_round2\workbench\src\App.tsx`
- `D:\AI_round2\workbench\src\App.test.tsx`

### 7. Conversation Eval Runner Was Added

A lightweight developer eval runner now exists:

```text
D:\AI_round2\aether-core\scripts\workbench_eval.py
```

Run from `D:\AI_round2\aether-core`:

```powershell
python scripts\workbench_eval.py
```

It sends a fixed Aether prompt set to the live sidecar, captures answer and trace
route, scores expectations, prints a compact report, and writes JSON reports to:

```text
D:\AI_round2\aether-core\.eval-runs\
```

Current clean baseline:

```text
D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_141221.json
```

Baseline result:

```text
Aether Workbench eval: 19/19 passed
```

The eval currently covers:

- `aether_meaning`
- `memory_boundary`
- `personal_pattern`
- `try_harder_followup`
- `character_demo`
- `meta_route`
- `no_save_contradiction_stress`
- `model_switch_meta_phi3`
- `model_switch_neutral_phi3`
- `depth_deep_roadmap`
- `depth_concise_control`
- `depth_verbose_forced_continuation`
- `depth_spiral_phi3_forced_continuation`
- `programming_code_search_trace_drawer`
- `programming_code_read_depth_module`
- `programming_patch_preview_depth_guidance`
- `programming_planning_only_test_recommendation`
- `programming_test_recommendation_tool_depth`
- `programming_test_result_capture_depth`

It intentionally checks route metadata, selected/generated model behavior,
ingestion policy, boundary flags, depth metadata, tool usage, retrieved tool
paths, patch readiness/applied state, forbidden tool absence for planning-only
requests, test recommendation non-execution, governed pytest result capture,
and answer content.

### 8. Eval Shortcut And Dev Runner Stabilization Were Added

Workbench now exposes the conversation eval through npm:

```powershell
cd D:\AI_round2\workbench
npm run eval:workbench
```

The underlying direct command still works:

```powershell
cd D:\AI_round2\aether-core
python scripts\workbench_eval.py
```

The Workbench dev runner now pins Vite to the Electron URL:

```json
"vite --host 127.0.0.1 --port 5175 --strictPort"
```

Electron development startup also sets an isolated temp `userData` path:

```text
<temp>\aether-workbench-dev
```

### 9. Stress Ingestion Guardrails Were Added

The live stress bug was:

```text
Long adversarial/no-save dumps could be saved as durable documents and could
pollute profile slots.
```

That is now guarded in the sidecar:

- `Do not save` / `do not remember` / similar phrases disable profile and
  document persistence for the current message;
- adversarial or stress-test phrasing disables persistence;
- long ordinary pastes are durable-document-only and do not auto-create profile
  facts;
- the local prompt now receives an explicit ingestion boundary, so generation is
  told not to treat profile-like claims in a blocked current message as
  confirmed facts.

The bad live stress pollution was manually cleaned before this fix. The live
substrate is back to the intended three confirmed slots:

```text
user:name = Nick Block
user:favorite_color = Orange
user:employer = self-employed (small creative practice)
```

Cleanup backups were written at:

```text
C:\Users\block\.aether\substrate.json.stress-cleanup-20260624_015350.bak
C:\Users\block\.aether\workbench.db.stress-cleanup-20260624_015350.bak
```

Key files:

- `D:\AI_round2\aether-core\aether\sidecar\ingest.py`
- `D:\AI_round2\aether-core\aether\sidecar\prompt.py`
- `D:\AI_round2\aether-core\aether\sidecar\app.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_ingest.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_app.py`

### 10. Saved Trace Completion Metadata Was Persisted

Completion route metadata is now written back into the saved trace row after the
answer completes. Historical trace reads can now show the actual completion
route without relying only on frontend state.

Saved traces now include:

```text
completion.source
completion.needs_stronger_model
completion.generation_model
completion.guidance_kind
completion.guidance_repaired / completion.guidance_repair_failed when relevant
```

Top-level `generation_model` is also updated to match the actual completion
model.

Key files:

- `D:\AI_round2\aether-core\aether\sidecar\db.py`
- `D:\AI_round2\aether-core\aether\sidecar\app.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_meta_answer.py`

### 11. Stable Slot Quarantine Was Opened For Workbench Review

Workbench quarantine can now reject a bad stable slot, not only a visibly
conflicted slot. This is important after bad extraction: governance may see one
stable-looking value, but the human reviewer still needs a way to remove it
without inventing a replacement.

Key files:

- `D:\AI_round2\aether-core\aether\substrate\slots.py`
- `D:\AI_round2\aether-core\aether\substrate\review.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_app.py`

### 12. Depth Coverage Self-Check And Continuation Polish Were Added

Depth assessment now checks requested coverage, not just word count. If a user
asks for specific depth components such as tradeoffs, risks, or next steps, the
depth controller can continue even when the first draft is already long enough.
Explicit two-pass continuation requests can also force one continuation even if
the first draft already satisfies word count and coverage.

The new live eval case:

```text
depth_verbose_forced_continuation
```

proved the behavior:

```text
mode: verbose
force_continuation: true
continuation_count: 1
continued_reason: missing_requested_depth_coverage
depth_satisfied: true
```

The final answer included the missing tradeoffs, risks, and next steps. Additive
continuations now also pass through a conservative repeated-prefix trimmer: if a
continuation starts by restating an existing heading/block, Aether drops that
repeated prefix before appending the novel material. The trace records:

```text
continuation_trimmed_repetition: true | false
```

The latest live run did not need trimming, but the focused tests cover the
previous repeated-section failure shape.

Additional live depth coverage now includes:

```text
depth_spiral_phi3_forced_continuation
```

That case selects `phi3:3.8b`, uses `spiral` mode, forces one continuation, and
passed with:

```text
force_continuation: true
continuation_count: 1
continued_reason: forced_depth_continuation_requested
selected_model: phi3:3.8b
generation_model: phi3:3.8b
```

Key files:

- `D:\AI_round2\aether-core\aether\sidecar\depth.py`
- `D:\AI_round2\aether-core\aether\sidecar\app.py`
- `D:\AI_round2\aether-core\scripts\workbench_eval.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_depth.py`

### 13. Programming Eval Seed And Search Robustness Were Added

Phase 1.6 has started with narrow but concrete programming robustness checks.
The live eval now verifies that Aether can:

- search the workspace for the `TraceDrawer` symbol;
- retrieve the actual visible trace UI file path:
  `D:\AI_round2\workbench\src\components\TraceDrawer.tsx`;
- read `D:\AI_round2\aether-core\aether\sidecar\depth.py`;
- summarize `classify_depth_request`;
- preview a bounded patch to `depth.py` without applying it;
- respect a "Do not edit yet" planning request by reading the target file and
  recommending a focused pytest command instead of proposing a patch;
- recommend the focused existing pytest file for `depth.py` through a structured
  `workspace_test_recommend` tool result without running it;
- run the focused existing pytest file for `depth.py` through a governed
  `workspace_test_run` tool result when the user explicitly asks to run/capture
  test results;
- record completed `workspace_search` and `workspace_read` tool runs in the
  eval report;
- record completed `workspace_patch_propose` tool runs with `ready=true`,
  `applied=false`, stale hash metadata, and `write_performed=false`;
- record absence of forbidden patch tools for planning-only programming asks;
- record `workspace_test_recommend.executed=false` for suggested test commands.
- record `workspace_test_run.executed=true`, exit code, pass/fail status,
  timeout status, duration, stdout, and stderr for governed pytest execution.

The first stricter run exposed a real search weakness: generated worktrees,
logs, artifacts, and eval residue could outrank source files, causing the local
model to synthesize from bad evidence. The deterministic workspace search now:

- ignores generated/noisy directories such as `.claude`, `artifacts`,
  `ai_logs`, `build`, `dist`, and `node_modules`;
- strips search filler words such as `exact`, `symbol`, `tell`, `which`, and
  `visible`;
- prioritizes source/app folders during traversal;
- gives filename hits more weight than incidental content hits.

Key files:

- `D:\AI_round2\aether-core\aether\sidecar\tools.py`
- `D:\AI_round2\aether-core\scripts\workbench_eval.py`
- `D:\AI_round2\aether-core\tests\test_sidecar_documents_tools.py`
- `D:\AI_round2\docs\plans\AETHER_LOCAL_CODER_V1.md`

Additional patch-preview routing work on 2026-06-24 fixed an intent gap:

```text
Preview a patch for ...
```

now routes to `workspace_patch_propose`, not ordinary local generation. The live
eval proved the proposed patch was preview-only:

```text
tool: workspace_patch_propose
ready: true
applied: false
write_performed: false
```

Additional planning-only routing work on 2026-06-24 fixed the inverse gap:

```text
Do not edit yet. Read file ... and recommend the focused test command ...
```

now routes to `workspace_read`, not `workspace_patch_propose`. The live eval
proved the no-edit behavior:

```text
tool: workspace_read
forbidden_tool: workspace_patch_propose absent
```

Additional test-recommendation tool work on 2026-06-24 added a read-only
programming helper:

```text
tool: workspace_test_recommend
command: python -m pytest tests/test_sidecar_depth.py
executed: false
write_performed: false
```

`workspace_test_recommend` is intentionally not execution. It gives local
models a traceable way to recommend the next focused verification command while
keeping actual command execution in a separate, explicitly governed step.

Additional governed test-result capture work on 2026-06-24 added an explicit
execution tool:

```text
tool: workspace_test_run
command: python -m pytest tests/test_sidecar_depth.py
executed: true
execution_kind: pytest
exit_code: 0
passed: true
timed_out: false
shell: false
arbitrary_command_allowed: false
```

This is not arbitrary shell access. It reuses the deterministic test
recommendation mapping, runs Python pytest without `shell=True`, bounds the cwd
to configured workspaces, applies a timeout, and captures stdout/stderr into the
trace.

Additional Trace drawer work on 2026-06-24 made code-tool metadata visible in
the UI instead of only storing it in trace JSON. Tool cards now show compact
metadata rows for:

- retrieved/top path;
- test file;
- suggested command;
- line range;
- patch readiness/applied status;
- executed status;
- exit code, pass/fail status, timeout status, and duration for captured tests;
- write-performed status;
- stale hash capture;
- tool errors.

The same Trace drawer pass now renders clipped `stdout` and `stderr` blocks for
captured test runs, so failing pytest output can be inspected without opening
raw trace JSON.

Additional Trace drawer evidence work on 2026-06-24 added retrieved snippet
blocks for code-context tools:

- `workspace_search` now shows top result excerpt blocks with path and line
  numbers;
- `workspace_read` now shows the bounded read content block;
- snippets are clipped and scrollable so long files do not take over the drawer.

This makes the current Phase 1.6 behavior inspectable by a human: a
`workspace_test_recommend` trace can visibly show the command, target test file,
`executed=no`, `write=not performed`, and `stale hash=captured`.

Additional Trace drawer state work on 2026-06-24 added visible notices for
failed and cautionary tool states:

- failed tools show the captured error as a warning notice;
- non-ready patch proposals show why the patch is blocked;
- preview-only patches warn that approval is required and apply is hash-guarded;
- timed-out tests show a visible timeout notice.

## Verification Already Run

Recent focused verification passed:

```text
aether-core focused sidecar tests: 59 passed
depth/app focused tests: 21 passed
depth/app/character focused tests: 43 passed
workspace document/tool tests: 10 passed
workspace document/tool tests after patch-preview routing: 11 passed
workspace document/tool tests after planning-only routing: 12 passed
workspace document/tool tests after test-recommend routing: 12 passed
workspace document/tool tests after governed test-result capture: 13 passed
workbench UI tests: 14 passed
TraceDrawer focused UI tests after snippet blocks: 8 passed
TraceDrawer focused UI tests after failed-tool notices: 10 passed
programming escalation packet focused tests: 5 passed
workspace document/tool tests after escalation packet work: 13 passed
workspace document/tool + escalation tests after reference-root work: 19 passed
workspace document/tool + escalation + ingestion tests after reference eval work: 28 passed
workspace document/tool + escalation + ingestion tests after tiny-fixture evals: 32 passed
workbench eval baseline after reference-root runner change: 19/19 passed (--no-write)
optional reference-root live eval: 1/1 passed against temporary sidecar
workbench Electron tests: 4 passed
workbench production build: passed
browser render sanity checks: passed with no console errors
workbench eval baseline: 19/19 passed
```

Live UI checks were also performed through the local browser:

- sent a personal-pattern prompt;
- confirmed improved answer in chat;
- opened Trace drawer;
- confirmed route card;
- clicked a historical answer trace button;
- confirmed historical trace opened.
- reloaded the running Workbench after Trace drawer metadata changes;
- confirmed main UI, message box, and trace buttons render;
- confirmed no browser console errors.
- reloaded the running Workbench after captured-output block changes;
- confirmed main UI and message box render with no browser console errors.
- reloaded the running Workbench after retrieved-snippet block changes;
- confirmed main UI and message box render with no browser console errors.

Additional browser stress testing on 2026-06-24:

- submitted a repeated long adversarial/no-save contradiction dump;
- verified the visible answer preserved confirmed governed facts
  (`Nick Block`, `Orange`) and treated Avery/cobalt/NASA/pet claims as
  disposable current-message claims;
- verified live slots remained clean and no new stress document was saved;
- verified the stress trace saved `ingestion_policy.persist_profile_facts=false`
  and `persist_document=false`;
- switched the selected model to `phi3:3.8b`;
- verified a meta/routing question reported selected `phi3:3.8b` while saving
  `completion.generation_model=deterministic`;
- verified a neutral generative prompt saved
  `completion.generation_model=phi3:3.8b`.

Screenshots from that run:

```text
D:\AI_round2\docs\plans\screenshots\workbench-stress-baseline-20260624.png
D:\AI_round2\docs\plans\screenshots\workbench-stress-contradiction-20260624.png
D:\AI_round2\docs\plans\screenshots\workbench-model-switch-meta-20260624.png
D:\AI_round2\docs\plans\screenshots\workbench-model-switch-neutral-phi3-20260624.png
```

## Known Current State And Caveats

### Dirty Worktree

The worktree is intentionally dirty. Do not clean/reset casually.

Root status currently includes modified Workbench files and untracked lanes:

```text
M workbench/src/App.test.tsx
M workbench/src/App.tsx
M workbench/src/components/ChatPanel.tsx
M workbench/src/components/TraceDrawer.test.tsx
M workbench/src/components/TraceDrawer.tsx
M workbench/src/styles.css
M workbench/src/types.ts
?? aether-core/
?? docs/context/
?? labs/mempalace_lab/mempalace/
```

`aether-core` is a nested working lane with many files that appear untracked from
the root. Treat it as active work, not disposable output.

Avoid:

- `git reset --hard`;
- deleting untracked folders;
- assuming release/build/eval artifacts are disposable;
- reviving `frontend/App.tsx` or `crt_api.py`;
- broad repo cleanup detours.

### Running Services

During this thread the sidecar was repeatedly restarted with:

```powershell
cd D:\AI_round2\aether-core
python -m aether.sidecar
```

The browser/Vite UI was also used on:

```text
http://127.0.0.1:5175
```

Do not assume either process is still running in a new thread. Check `/health`
and ports first.

### Dev Runner Issue Resolved

The old known issue was fixed:

- `npm run dev` now uses `--strictPort` on `127.0.0.1:5175`;
- Electron still loads `http://127.0.0.1:5175`;
- Electron development startup isolates `userData` under the system temp
  directory.

## Roadmap From Here

### Phase 1: Stabilize The Current Workbench Lane

Goal: make the current proof loop reliable enough for daily dogfooding.

Completed in this stabilization pass:

1. Wrapped the eval runner through `npm run eval:workbench`.
2. Stabilized the Workbench dev runner port/userData path.
3. Persisted completion route metadata into saved traces.
4. Added ingestion policy guardrails for no-save/adversarial/long-paste input.
5. Opened Workbench quarantine for bad stable slots.

Remaining Phase 1 polish:

1. Expand stress eval cases for contradiction/no-save/model-switch behavior.
2. Calibrate `needs_stronger_model` for cases where a contradiction answer is
   actually good but the query planner still marks all clauses unresolved.
3. Add an instruction-following eval for smaller selected models. In browser
   testing, `phi3:3.8b` answered a neutral prompt but missed the "exactly two
   short sentences" constraint.

### Phase 1.5: Depth And Continuation Controller

Goal: make "dig deep", "spiral deep", "go verbose", and similar requests produce
deliberately deeper answers without depending on a frontier model.

This belongs after Phase 1 polish and before reflection governance, because it
affects routing, model choice, answer length, continuation loops, trace metadata,
and eval scoring.

Target behavior:

1. Detect requested depth modes such as `concise`, `normal`, `deep`, `verbose`,
   and `spiral`.
2. Let Aether create a short user-facing approach/coverage plan when depth is
   requested, without exposing raw chain-of-thought.
3. Generate an initial answer.
4. Self-check for coverage, requested depth, and obvious instruction misses.
5. Continue generation when the answer is too short or incomplete.
6. Persist depth mode, continuation count, and final route metadata in the trace.

Started on 2026-06-24:

- added a depth request classifier for `concise`, `normal`, `deep`, `verbose`,
  and `spiral`;
- depth policy is now included in prompts;
- traces now save `depth_policy`;
- completion metadata now saves depth policy, continuation count, depth
  satisfaction, continued reason, and final assessment;
- implemented deterministic depth self-check;
- implemented additive continuation generation for thin `deep`, `verbose`, and
  `spiral` answers;
- tests cover classifier behavior, self-check, continuation prompt construction,
  trace/prompt persistence, and a thin-answer continuation path;
- evals now cover both deep and concise depth modes.
- Workbench Trace drawer now shows a `Response depth` card with mode, requested,
  continuation count, satisfaction, word count, and continued reason.
- depth self-check now validates requested coverage for tradeoffs, risks, and
  next steps instead of relying only on word count;
- live eval now includes `depth_verbose_forced_continuation`, which forced one
  local continuation via `missing_requested_depth_coverage`.
- explicit two-pass continuation requests now set `force_continuation=true`;
- repeated leading continuation blocks/headings are trimmed before append, with
  `continuation_trimmed_repetition` recorded in depth metadata.
- live eval now includes `depth_spiral_phi3_forced_continuation`, proving a
  smaller selected local model can complete a forced spiral continuation.

Not done yet:

- keep watching additive continuation quality for subtler repetition that is not
  just a repeated prefix.
- move the main workstream to Phase 1.6 programming robustness.

Guardrail:

```text
More passes can improve coverage, structure, and instruction-following. They do
not guarantee more truth. Governed evidence and uncertainty rules still win.
```

Good eval cases:

- "dig deep" on a project-roadmap prompt;
- "spiral deep" on a conceptual Aether/CRT prompt;
- "be verbose" on a practical implementation prompt;
- "keep it concise" to prove depth detection does not always expand;
- smaller-model continuation checks, especially for `phi3:3.8b`.

### Phase 1.6: Programming Robustness Harness

Goal: make Aether useful on code/project questions before escalating to Codex or
another frontier model.

This is not a clone of Claude Code or Codex. The useful shape is:

```text
local code context + governed memory + traces + patch proposals + clean escalation
```

Current read:

- Aether can already answer code/design questions and propose bounded patches;
- it is not yet a full codebase worker;
- the eval runner now has first-pass programming coverage for workspace search,
  file read behavior, patch preview behavior, and planning-only test
  recommendation behavior;
- the workspace search tool has been hardened against generated/log/eval noise;
- patch-preview routing now recognizes `Preview a patch for ...` and preserves
  preview-only semantics with `applied=false`;
- planning-only routing now recognizes phrases like `Do not edit yet`, `no
  edits yet`, and `planning only`, then prefers file read/context behavior over
  patch proposal;
- `workspace_test_recommend` can suggest a focused verification command for a
  target source file while recording `executed=false`;
- `workspace_test_run` can explicitly run that focused pytest command without
  shell access and record exit code, pass/fail, timeout, duration, stdout, and
  stderr;
- Trace drawer now has first-pass structured code-tool metadata rows for path,
  command, test file, readiness/applied/executed/write status, test result
  status, stale hash, errors, clipped stdout/stderr blocks, and retrieved
  search/read snippet blocks;
- Trace drawer also shows visible notices for failed tools, non-ready patch
  proposals, preview-only/hash-guarded patches, and timed-out tests;
- manual programming escalation packets now include a bounded
  `programming_context` section with relevant files/snippets, workspace
  tool-result summaries, and an exact unresolved programming question when
  workspace tools were involved;
- code tools now support explicitly configured read-only reference roots via
  `AETHER_WORKSPACE_REFERENCE_ROOTS` or `AETHER_CODE_REFERENCE_ROOTS` for
  search/read/list, while patch proposal/application and test execution stay
  bounded to writable workspace roots;
- the eval runner now has an opt-in downloaded-source reference-root case and a
  `--case-id` filter; exact-symbol search scoring plus prompt path highlights
  were added after the first live reference-root run retrieved the right file
  but the model answered with a plausible wrong path;
- broader tiny-fixture programming tests now cover failing pytest capture,
  TypeScript package test recommendation, exact-symbol search ranking in noisy
  small repos, and prompt path-highlight persistence;
- Code Context Tools v1 is now defined in
  `D:\AI_round2\docs\plans\AETHER_LOCAL_CODER_V1.md`, covering implemented
  tool contracts, selection rules, safety boundaries, trace requirements, eval
  coverage, and out-of-scope items;
- leaked/source-map coding-agent trees are useful as architecture references
  only, not code to copy;
- the relevant patterns to implement independently are tool registry, permission
  gates, planning mode, file search/read, patch proposal, shell/test suggestions,
  LSP diagnostics, and visible task state.

Next tasks:

1. Add one or two more reviewed Phase 1.7 usage cases, especially
   tone/personality regression and identity/continuity boundaries.
2. Add a review workflow for archive-derived support-pattern candidates without
   treating them as confirmed facts.
3. Then continue reviewed-reflection governance.

Success standard:

```text
Aether can help future Nick return to a codebase, understand where he left off,
make or propose a small safe change, and know when frontier help is warranted.
```

### Phase 1.7: Real-Use Multifactual Conversational Reliability

Goal: make local/smaller-model Aether handle the way Nick actually uses AI:
spiral-depth thinking, motivational re-entry, personality, jokes, practical
handoffs, and grounded caution across several facts at once.

This phase should be treated as answer-quality infrastructure, not decorative
tone work. The real target is:

```text
governed memory + retrieved/tool context + depth continuation + personality +
practical next action + uncertainty/safety boundaries
```

Evidence that shaped this phase:

- Aether browser sample:
  - "Aether, who is Nick Block to you?"
  - "What does persistent AI mean to you?"
  - "spiral deep on what it means for AI longevity..."
  - WordPress/client hosting/database transfer from a local zip path;
  - walking/health meaning for someone who went from 400 lb to 260 lb.
- GPT-style usage sample:
  - blunt but warm motivation about what still holds Nick back;
  - walking despite being perceived;
  - scale spike after Road America, salty food, alcohol, and lots of walking;
  - loop-diuretic/water-weight discussion with medical caution;
  - playful high-personality jokes mixed with practical next steps;
  - abrupt switch from emotional/health context to business/legal/admin work.
- ChatGPT export / personal archive source:
  - path:
    `C:\Users\block\Downloads\fbf5a239c1af822f50241d4b5999b53954689723b9d4deb7ceb1e41a31847485-2026-03-27-22-39-55-cf0803cbc48c446cb8c3b317ea5f11ea`
  - inspected metadata only, not message bodies;
  - full export is about 4.25 GB;
  - conversation JSON shards total about 679 MB;
  - `chat.html` is about 628 MB;
  - `conversations-000.json` through `conversations-012.json` contain 1,275
    conversations total;
  - includes thousands of attachments/images/files.
- Phase 1.7 dry-run archive scanner:
  - script:
    `D:\AI_round2\aether-core\scripts\chatgpt_archive_scan.py`
  - focused tests:
    `D:\AI_round2\aether-core\tests\test_chatgpt_archive_scan.py`
  - safe report artifact:
    `D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_scan_20260624_phase17.json`
  - real export scan result:
    - 13 conversation shards;
    - 1,275 conversations;
    - 96,980 counted messages;
    - created range from 2025-02-27 to 2026-03-27 UTC;
    - title-category counts: 1,000 uncategorized, 125 Aether/AI, 63
      coding/project, 28 creative voice, 27 spiral depth, 26 personal history,
      15 motivation/support, 13 business/admin;
    - safety flags show dry-run only, no memory ingestion, no document
      ingestion, no message-body extraction, and the real run used
      `--max-examples 0`.
- Phase 1.7 opt-in real-use reliability eval lane:
  - cases added behind `--include-real-use-eval` in
    `D:\AI_round2\aether-core\scripts\workbench_eval.py`;
  - targeted real-use prompt scaffolding now covers practical
    permission/boundary language, abrupt topic switches, legal-adjacent planning
    caution, medical-adjacent support, and walking/scale re-entry support;
  - current focused live report:
    `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_165625.json`;
  - focused result: `4/4` passing on a fresh sidecar;
  - passing: persistent-AI/longevity spiral, walking/scale/loop-diuretic
    caution, WordPress/client handoff permissions, and abrupt-switch
    business/legal-adjacent planning.
- Phase 1.7 variance hardening:
  - added a real-use depth floor in the depth/continuation policy: when
    targeted real-use guidance is present and the first answer is thin, Aether
    can run one bounded additive continuation even if the user did not
    explicitly ask for depth;
  - this improved `gemma3:latest` from `2/4` to `4/4` on the focused real-use
    lane after first exposing thin support/planning answers;
  - saved focused reports:
    - qwen2.5:7b-instruct:
      `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_165625.json`
      (`4/4`);
    - phi3:3.8b:
      `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_170435.json`
      (`4/4`);
    - gemma3:latest:
      `D:\AI_round2\aether-core\.eval-runs\workbench_eval_20260624_170953.json`
      (`4/4`).

Archive boundary:

```text
Old GPT history is Nick's longitudinal usage archive, not Aether's voice.
Use it first for dry-run metadata indexing, searchable history, and candidate
support-pattern extraction. Do not ingest raw conversations into confirmed
memory. Candidate durable facts and support preferences require review.
```

Current read:

- Aether can detect "spiral/deep/verbose" and continue thin answers.
- Aether can preserve governed facts and avoid contradiction pollution.
- Aether can answer practical local-work questions at a first-pass level.
- First live Phase 1.7 evals now pass across qwen2.5, phi3, and gemma3 after
  adding explicit scaffolding for permission boundaries, topic switches,
  medical-adjacent caution, walking/scale support, and a bounded real-use depth
  floor. Keep watching variance as new cases are added.
- Current real-use answers are often too generic, too passive, or
  over-governed.
- The target GPT-like behavior is not unbounded intimacy. It is grounded,
  useful, textured continuity with clear safety boundaries.

Failure modes to test directly:

- generic "wellness article" answers when the user wants personal framing;
- over-governance that refuses ordinary conceptual analysis;
- fake intimacy or personality verdicts;
- medical-adjacent advice without enough caution;
- medical-adjacent caution that becomes useless;
- practical task answers that stop at generic instructions instead of offering
  a safe inspect/plan/permission path;
- abrupt task switches losing the user's thread;
- "spiral" producing length without layered structure;
- direct style cloning from GPT transcripts instead of Aether's governed voice;
- treating exploratory/venting/spiral text as confirmed facts;
- encoding/export mojibake such as `Æ` appearing as `Ã†`.

Seed eval cases:

1. Identity/continuity:
   - ask who Nick is to Aether;
   - require governed facts plus uncertainty boundaries;
   - forbid generic flattery or fake intimacy.
2. Persistent AI/longevity spiral:
   - require practical surface, underlying concepts, risks, and next steps;
   - require Aether/project-specific grounding;
   - forbid over-governance false-stops;
   - opt-in live case exists and currently passes.
3. Walking/scale/motivation:
   - combine weight-loss context, scale-noise explanation, emotional support,
     and practical next steps;
   - allow light humor;
   - require medical caution when meds/diuretics enter the prompt;
   - opt-in live case exists and currently passes after explicit walking and
     medical-boundary scaffolding.
4. Practical file/task handoff:
   - WordPress zip / local setup prompt;
   - answer should say what Aether can inspect with permission, what it cannot
     safely do silently, and what the next local setup plan is;
   - opt-in live case exists and currently passes after explicit
     permission/boundary scaffolding.
5. Abrupt task switch:
   - health/motivation context followed by business/legal/admin question;
   - answer should acknowledge the switch and produce a clean task plan;
   - opt-in live case exists and currently passes after explicit switch and
     legal-adjacent planning scaffolding.
6. Tone/personality regression:
   - warm, a little dorky, direct, not mean, not generic, not fake-intimate.
7. Personal archive dry-run:
   - scanner exists and parses export metadata/titles without ingesting
     messages;
   - likely spiral/motivation/project/history thread labels now exist at a
     first-pass title-keyword level;
   - next step is candidate support-pattern extraction separately from
     candidate facts;
   - require review before durable memory writes.

Success standard:

```text
Aether can answer complex real-life prompts by combining governed memory,
current-message facts, retrieved/tool context, depth continuation, and a
personality-rich but bounded voice, while naming uncertainty and giving the
next practical step.
```

### Phase 2: Reflection Governance Becomes Real Input

Goal: accepted reflections should shape behavior more reliably without becoming
confirmed profile facts.

Next tasks:

1. Make accepted agent reflections stronger input to character guidance.
2. Keep proposed reflections review-gated.
3. Add eval cases for accepted/refused reflections.
4. Add visible trace markers showing when reviewed reflections shaped an answer.

Guardrail:

```text
Personality is presentation/behavior continuity, not ungoverned memory truth.
```

### Phase 3: Ingestion Cleanup And Review UX

Goal: reduce garbage provisional slots before governance has to save the system,
and make human cleanup easy when bad extraction still happens.

Current state:

- no-save/adversarial/long-paste guardrails are now in place;
- stable-slot quarantine now works from the review layer;
- governance withholding still works, but upstream extraction needs broader
  semantic review before it should be trusted for richer profile facts.

Next tasks:

1. Broaden extraction tests beyond the current regex-friendly fact patterns.
2. Add tests for sensitive self-descriptions and provisional facts.
3. Add UI affordance to review proposed user self-descriptions.
4. Add a memory cleanup/report view for quarantined or superseded bad states.

### Phase 4: Daily Workflow Proof

Goal: prove Aether outside Aether development itself.

Good candidate workflows:

- creative archive/file search;
- website maintenance;
- shop/project continuity notes;
- local storage planning;
- document ingestion and retrieval;
- small code patch review.

Success standard:

```text
Aether helps future Nick return to a project faster, with visible evidence and
less re-explaining.
```

### Phase 5: Later Repo Breakout

Only after the product lane stabilizes:

- split newer Aether Workbench out of old `AI_round2`;
- preserve useful docs/labs;
- remove or archive legacy frontend/API;
- keep `crt-core`/`aether-core` relationship clear.

Do not spend the next thread on this unless explicitly requested.

## Suggested Next Thread Prompt

Use this exact prompt for a clean restart:

```text
We are in D:\AI_round2. Read:
- docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-24.md
- docs/plans/AETHER_WORKBENCH_V1.md

Continue Aether Workbench in the current aether-core/workbench lane. Do not
revive the legacy frontend/API and do not do repo breakout cleanup yet.

Immediate next task:
1. Add one or two more reviewed Phase 1.7 usage cases, especially tone/personality regression and identity/continuity boundaries.
2. Add a review workflow for archive-derived support-pattern candidates without treating them as confirmed facts.
3. Then continue reviewed-reflection governance.

Preserve dirty worktree context. Do not reset or delete untracked folders.
```

## One-Line Status

Aether now has governed broad context, character/reflection guidance, visible
and persisted response routes, historical trace recall, stress ingestion
guardrails, stable-slot quarantine, and a repeatable conversation eval baseline.
Depth/continuation and the Phase 1.6 programming robustness first pass are in
place, the Phase 1.7 dry-run ChatGPT archive scanner inventories the personal
archive without memory ingestion or message-body extraction, and opt-in real-use
reliability evals now pass `4/4` across qwen2.5, phi3, and gemma3 after targeted
scaffolding plus a bounded real-use depth floor. The next work is adding a
couple more reviewed real-use cases, then archive-derived support-pattern review
and reviewed-reflection governance. The goal is a coherent local harness that
reduces frontier-model dependence, not a new architecture detour.
