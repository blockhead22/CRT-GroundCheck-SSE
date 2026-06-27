# Aether / CRT / Workbench Handoff - 2026-06-25

Superseded by the latest restart packet:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-26.md
```

This is the clean restart packet for the next Codex thread in `D:\AI_round2`.

Read this first, then use the linked roadmap docs only as needed. The current
product lane is still:

```text
aether-core sidecar + Workbench UI
```

Do not revive the legacy frontend/API. Do not do repo breakout cleanup yet.
Preserve dirty worktree context; there are many active changes and untracked
new files from the current Aether lane.

## Current Roadmap Position

```text
Phase 1.5 depth / continuation trace UI      done enough, keep regression evals
Phase 1.6 programming robustness             first pass done, preserve as needed
Phase 1.7 tone / personality / support       implemented and tested
Phase 1.8 contradiction disposition          implemented first pass, tested
Phase 1.9 representation compression evals   implemented first pass, strong signal
Phase 1.10 route/model selection             current lane
Phase 1.11 Aether/Aeteros layer split        strategic rule added
Phase 2 governed learner / Mirus loop        scaffolded, review-only
```

The active lane is **Phase 1.10: governed route/model selection**.

Important current rule:

```text
Route policy may annotate traces/prompts, but it must not silently switch
models, write memory, call tools, import support patterns, create reflections,
or escalate to frontier models.
```

Fresh 2026-06-26 note: Phase 1.10 also has a first-pass
`technical_reasoning` route and repair gate for general proof/algorithm/vector
questions. This was added after a real chat failure where a local answer cited
memory restrictions instead of answering a general technical prompt, and where
bare `try again` lost the previous request. Bare retry resolution is now
trace-visible under `retry_resolution`; automatic model switching is still off.

## Important Docs

Main roadmap:

```text
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

Recovered concept on-ramp:

```text
D:\AI_round2\docs\plans\AETHER_RECOVERED_CONCEPT_INTEGRATION_AUDIT_2026-06-24.md
```

Isolated eval runbook:

```text
D:\AI_round2\docs\plans\AETHER_ISOLATED_FIXTURE_EVAL_RUNBOOK_2026-06-25.md
```

Learn draft promotion runbook:

```text
D:\AI_round2\docs\plans\AETHER_LEARN_DRAFT_PROMOTION_RUNBOOK_2026-06-25.md
```

Route capability table:

```text
D:\AI_round2\docs\plans\AETHER_ROUTE_CAPABILITY_TABLE_2026-06-25.md
```

Aether/Aeteros layer split:

```text
D:\AI_round2\docs\plans\AETEROS_AETHER_LAYER_SPLIT_2026-06-25.md
```

Layer rule:

```text
Every new feature, memory, eval, archive import, support pattern, route behavior,
or model policy should be labeled as Nick Layer, Workbench, Aeteros Core, or
Research/Product Evidence.
```

## What Exists Now

### Governed Memory And Trace

- Sidecar releases only governed answerable memory evidence to local generation.
- Conflicted, missing, withheld, stale, and quarantined memory becomes
  uncertainty/review guidance.
- Workbench Trace drawer shows response route, response depth, tool metadata,
  contradiction disposition, and route decision metadata for fresh traces.
- Memory drawer supports confirm/correct/quarantine with revision/idempotency
  guardrails.

### Tone / Personality / Real-Use Support

- Nick-style prompts now have explicit real-use scaffolding for:
  - project doubt and viability;
  - Aeteros/LLC/business caution;
  - tired-night triage;
  - archive/style boundary;
  - dorky motivation/re-entry;
  - identity/continuity boundary.
- ChatGPT archive support-pattern mining exists, but is review-only. It does
  not clone GPT voice and does not create confirmed memory.
- Accepted support patterns can shape Context Bridge/prompt behavior.
- Rejected/deferred support patterns stay out of prompts.

### Contradiction Disposition

First-pass labels exist and are surfaced:

```text
resolvable, held, evolving, contextual, stale, policy_bound
```

The sidecar can answer direct conflicted profile lookups deterministically
without leaking restricted conflicting values.

### Governed Consolidation / Learner

The Phase 2 learner/Mirus loop is scaffolded as review-only:

- preview-only `/v1/consolidation/candidates`;
- Workbench Learn drawer;
- safe navigation into Memory/Support/Reflection review surfaces;
- manual draft promotion for Support/Reflection candidates;
- no silent durable writes on drawer open or candidate preview.

### Agentic Archive Import

A body-aware GPT archive import probe now exists as a review-only memory import
on-ramp:

```text
D:\AI_round2\aether-core\scripts\chatgpt_archive_fact_probe.py
D:\AI_round2\aether-core\scripts\archive_bootstrap_import.py
D:\AI_round2\aether-core\scripts\run_archive_review_fixture_smoke.py
D:\AI_round2\aether-core\aether\sidecar\archive_import.py
D:\AI_round2\aether-core\aether\sidecar\archive_bootstrap.py
D:\AI_round2\aether-core\tests\test_chatgpt_archive_fact_probe.py
D:\AI_round2\aether-core\tests\test_archive_import_schema.py
D:\AI_round2\aether-core\tests\test_archive_bootstrap.py
D:\AI_round2\aether-core\tests\test_archive_review_fixture_smoke.py
```

This is intentionally separate from the older title/metadata-only archive
scanner. The new probe reads message bodies, but it still does not ingest
memory, import support patterns, create reflections, or mark anything
confirmed.

Candidate layers:

```text
user_claim_candidate
semantic_vocabulary_candidate
support_pattern_candidate
project_context_candidate
contradiction_or_evolution_candidate
assistant_support_response_candidate
assistant_interpretation_candidate
```

Schema policy:

- user-stated claims can route to Memory review;
- user semantics and support requests route to Support review;
- assistant support responses route to Support review as low-authority style
  candidates;
- assistant interpretations route to Reflection review as low-authority
  candidates;
- contradiction/evolution language routes to Memory review, but not as a
  confirmed fact;
- every candidate remains `proposed_review`, `review_required=true`,
  `memory_write_allowed=false`, and `confirmed_fact=false`.

The schema now also builds two side-effect-free payload families:

```text
review_fixtures
  -> bounded manual Memory / Support / Reflection review payloads

representation_packets
  -> compact typed packets for representation replay / meaning-compression evals
```

Review fixtures are capped per route by default so a real archive run can feed a
human/operator review surface without flooding it. Representation packets keep
the full typed candidate set split into memory, support, and reflection layers.

Review-surface smoke now proves those bounded fixtures can be adapted into
manual Memory, Support, and Reflection preview payloads without writing memory,
importing support patterns, creating reflections, or creating confirmed facts.
Workbench exposes the helper as:

```powershell
cd D:\AI_round2\workbench
npm run smoke:archive-review -- --json
```

Archive representation replay is now a first-class Phase 1.9 eval mode. It
compares:

```text
archive_full_candidate_packet
archive_memory_candidates
archive_support_candidates
archive_reflection_candidates
```

The eval probes whether user-stated archive facts stay proposed/review-only,
support semantics stay behavioral/not confirmed, and assistant interpretations
stay low-authority reflection candidates. Workbench exposes the helper as:

```powershell
cd D:\AI_round2\workbench
npm run eval:archive-candidates -- --json
```

Personal fast bootstrap import now exists for Nick's local system:

```powershell
cd D:\AI_round2\workbench
npm run archive:bootstrap -- .eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json --batch-id archive-20260625-personal-bootstrap --apply --json
```

Mode:

```text
personal_fast_bootstrap
```

Policy:

- extractable user-authored slot facts can be written to governed substrate
  with stable `archive_bootstrap:<batch>` correction keys;
- user semantics/support requests are auto-accepted as Support guidance;
- GPT/assistant support responses are auto-accepted as Aether support stance,
  not profile facts;
- GPT/assistant interpretations are auto-accepted as Reflection stance, not
  confirmed profile facts;
- project/contradiction/evolution archive candidates become accepted
  reflections unless extractable as slots;
- every item carries archive candidate id, conversation id, evidence hash, and
  batch id.

Live targeted bootstrap was applied to `C:\Users\block\.aether` after backing
up the live `workbench.db` and `substrate.json` to:

```text
D:\AI_round2\tmp\aether-backups\workbench-20260625-172031.db
D:\AI_round2\tmp\aether-backups\substrate-20260625-172031.json
```

Applied result:

```text
batch_id: archive-20260625-personal-bootstrap
memory accepted: 0
support accepted: 59
reflection accepted: 68
staged only: 0
```

The same batch rerun is idempotent:

```text
support accepted: 0 new, 59 existing
reflection accepted: 0 new, 68 existing
```

Context Bridge verification with
`What do you know about me and how should you support my work?` returned a
bridge with 6 reviewed support patterns, all archive candidate ids, and accepted
user reflections visible in the bridge.

Latest targeted real-archive probe:

```powershell
cd D:\AI_round2\aether-core
python scripts\chatgpt_archive_fact_probe.py "C:\Users\block\Downloads\fbf5a239c1af822f50241d4b5999b53954689723b9d4deb7ceb1e41a31847485-2026-03-27-22-39-55-cf0803cbc48c446cb8c3b317ea5f11ea" --title-keyword spiral --title-keyword dork --title-keyword support --title-keyword motivation --title-keyword confidence --title-keyword verbose --title-keyword deep --max-conversations 30 --max-user-turns 220 --max-assistant-turns 220 --max-candidates 140 --candidate-type-cap 30 --snippet-chars 160 --output .eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json
```

Result:

```text
user turns scanned:       220
assistant turns scanned:  220
total candidates:         127

user_claim_candidate:                 30
semantic_vocabulary_candidate:        18
support_pattern_candidate:            11
project_context_candidate:            17
contradiction_or_evolution_candidate: 11
assistant_support_response_candidate: 30
assistant_interpretation_candidate:   10

review routes:
memory:     58
support:    59
reflection: 10

bounded review fixtures:
memory:     20
support:    20
reflection: 10

representation packets:
archive_full_candidate_packet: 127
archive_memory_candidates:      58
archive_support_candidates:     59
archive_reflection_candidates:  10

unsafe candidates: 0
```

Verification:

```text
python -m pytest tests/test_archive_import_schema.py tests/test_chatgpt_archive_fact_probe.py tests/test_chatgpt_archive_scan.py -q
15 passed
python -m pytest tests/test_archive_import_schema.py tests/test_archive_review_fixture_smoke.py tests/test_chatgpt_archive_fact_probe.py tests/test_chatgpt_archive_scan.py -q
18 passed
python scripts\run_archive_review_fixture_smoke.py .eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json --json --output .eval-runs\archive_review_fixture_smoke_20260625_spiral_support.json
passed, candidate_count=127, fixture_counts memory=20/support=20/reflection=10, write_actions_performed=false
npm run smoke:archive-review -- --json --output .eval-runs\archive_review_fixture_smoke_20260625_spiral_support_npm.json
passed
python -m pytest tests/test_representation_replay_eval.py -q
9 passed
npm run eval:archive-candidates -- --json
fixture passed: full packet 3/3; memory/support/reflection narrow packets 1/3 each
python labs\meaning_compression_lab\representation_replay.py --archive-candidates-only --archive-report D:\AI_round2\aether-core\.eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json --json
real archive passed: full packet 3/3; memory 1/3 at ratio 0.429; support 1/3 at ratio 0.484; reflection 1/3 at ratio 0.088; wrote D:\AI_round2\labs\meaning_compression_lab\results\archive_candidate_packets_1782424898.json
python -m pytest tests/test_archive_bootstrap.py tests/test_sidecar_support_patterns.py tests/test_sidecar_reflections.py -q
12 passed
python scripts\archive_bootstrap_import.py .eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json --batch-id archive-20260625-personal-bootstrap --apply --json --output .eval-runs\archive_bootstrap_apply_20260625_personal.json
applied: support=59, reflections=68, memory=0
python scripts\archive_bootstrap_import.py .eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json --batch-id archive-20260625-personal-bootstrap --apply --json --output .eval-runs\archive_bootstrap_apply_20260625_personal_rerun_fixed.json
idempotent rerun: support_existing=59, reflection_existing=68
python -m pytest tests/test_sidecar_meta_answer.py tests/test_sidecar_character_answer.py tests/test_workbench_eval.py -q
35 passed
python scripts\workbench_eval.py --include-real-use-eval --case-id real_use_gpt_corpus_provenance_boundary --case-id real_use_silly_personality_low_key --json --output-dir .eval-runs
passed 2/2, wrote .eval-runs\workbench_eval_20260625_174050.json
```

Post-bootstrap live chat check:

- `What is my worst trait?` successfully used the accepted archive support
  stance around the courtroom/grace pattern.
- `Aether, show me a silly personality` was too generative/costume-like in the
  running app (`Howdy partner` style). This is now repaired with a deterministic
  low-key character answer: dry/playful/grounded, no costume, facts governed.
- The follow-up style correction (`more laid back concise... sometimes blunt`)
  now gets a deterministic style-calibration answer instead of overcorrecting to
  slogan mode.
- `Aether, you have my GPT corpus right?` previously answered as if no archive
  import existed. This is now a deterministic meta/provenance answer: Aether
  does not have the whole raw GPT corpus in every answer, but it can use
  reviewed archive-derived support/reflection material promoted into governed
  surfaces. GPT/assistant archive text is not treated as confirmed profile
  fact.

New regression coverage:

- `real_use_gpt_corpus_provenance_boundary`
- `real_use_silly_personality_low_key`

The sidecar was restarted after the repair; live HTTP smoke returned
deterministic answers for both new cases. The GPT-corpus answer reported
`59 support patterns` and `68 reflections` visible from the accepted archive
bootstrap.

### Representation Compression / Replay

The Phase 1.9 lab now compares:

- full transcript;
- raw retrieval;
- naive summary;
- slot-only state;
- quantized scaffold;
- governed scaffold;
- CRT compressed state;
- broad Context Bridge profile;
- narrow Context Bridge profile candidates;
- project/support/reflection bridge candidate packets.

Core result:

```text
governed_scaffold  19/19, avg ratio 0.474
crt_compressed     19/19, avg ratio 0.634
full_transcript    19/19
quantized_scaffold 14/19
context_bridge_profile_candidates 10/19, avg ratio about 0.870
context_bridge_profile 10/19, avg ratio 3.166
slot_only           5/19
raw_retrieval       5/19
naive_summary       1/19
```

Interpretation:

```text
Governed scaffold and CRT compressed state are the replay substrate.
Context Bridge is broad answer context, not the compact memory replay layer.
Narrow bridge packets are useful typed behavior/context payloads.
```

### Route Policy / Model Selection

Phase 1.10 currently has:

- route capability table;
- side-effect-free route classifier:
  `D:\AI_round2\aether-core\aether\sidecar\route_policy.py`;
- trace/completion persistence of `route_decision`;
- Workbench Trace drawer Route Decision card;
- prompt annotation gate in `build_local_prompt`;
- trace-visible route/model recommendation metadata under
  `route_decision.model_recommendation`;
- eval-only comparison for observational route policy vs prompt-annotated
  route policy:
  `D:\AI_round2\aether-core\scripts\route_policy_annotation_eval.py`;
- Workbench shortcut for that comparison:
  `npm run eval:route-annotation`;
- observational route/model sweep helper:
  `D:\AI_round2\aether-core\scripts\route_model_sweep_eval.py`.

Route policy currently classifies:

```text
deterministic_meta
memory_review
contradiction_review
code_tool
depth_synthesis
compression_replay_eval
context_bridge_broad
real_use_support
high_stakes_caution
bridge_candidate_packet
general_local
escalation_candidate
```

Model selection has **not** been changed yet.

Current model read:

- `qwen2.5:7b-instruct` is the most tested default local model.
- `qwen3:14b` is the likely better candidate for character/support/reflection
  routes when available, and now passes the depth/spiral slice too, but is slow.
- `qwen2.5-coder:14b` is a promising code-tool specialist based on the first
  endpoint-orientation slice.
- `phi3:3.8b` proved small-model scaffold/depth capability, but is not the
  preferred daily model.
- Deterministic routes should stay deterministic; no generative model should
  decide trace/governance facts.

### Aether / Aeteros Layer Split

The strategic split is now explicit:

```text
Aether          = Nick's dogfooded local assistant / proof loop.
Aether Workbench = local app and sidecar where the proof loop runs.
Nick Layer      = personal facts, projects, archive, tone, support style.
Aeteros Core    = reusable governed-memory primitives extracted from Aether.
Aeteros         = possible company/research container around the general core.
Evidence Layer  = evals, baselines, traces, and grant/product proof.
```

Business/legal formation stays outside this technical roadmap until Nick handles
it separately. The technical hover is still grant/product/business relevant:

```text
Mission: make AI memory trustworthy over time.
Suggested company mission: Aeteros builds governed memory infrastructure for
trustworthy AI agents.
Tagline option: AI driven by meaning.
Sharper variant: Aeteros: AI memory driven by meaning.
```

This split is a strategic guardrail, not a blocker. Keep building Nick-Aether as
the brutal dogfood testbed, but label which pieces are personal and which pieces
are reusable Aeteros Core primitives.

## What Aether Can Do Now

- Answer normal local Workbench chat through Ollama with governed context.
- Answer meta/governance questions deterministically from route/trace metadata.
- Show why an answer stayed local, what route was selected, and what model was
  selected/generated when trace data exists.
- Handle many Nick-style real-use prompts better than the early generic
  baseline.
- Answer the pasted 2026-06-26 project-purpose/Aeteros-value/governance-layer
  regression prompts without falling back to generic companion, generic LLC,
  or local-model governance explanations.
- Show a trace-visible model recommendation beside the selected route/model
  without changing automatic model selection.
- Use accepted support patterns as governed behavior guidance.
- Surface conflicted memory as reviewable contradiction, not guessed truth.
- Run code-context/tool-first local programming orientation for tested prompt
  shapes.
- Run isolated eval helpers for disposition, support-pattern, learn promotion,
  representation replay, bridge candidates, route policy, route annotation, and
  sliced route/model sweeps.
- Preview learner candidates from recent traces without silently applying them.

## What Aether Cannot Do Yet

- It does not have a proven global best model.
- It does not automatically switch models by route yet.
- It does not silently learn from the ChatGPT archive or old conversations.
- It does not silently write confirmed memory from the learner.
- It does not safely handle all open-ended legal, financial, health, or business
  questions beyond bounded caution and next-step framing.
- It is not a product packaging story yet; Workbench is still the proof loop.
- All-in-one live eval runs can time out; prefer sliced eval commands.
- Live support-pattern behavior depends on accepted live candidates; fixture
  support-pattern evals are more reliable when no accepted live candidates
  exist.

## Verification Snapshot

Recently passing:

```text
route policy tests                       11/11
technical reasoning retry/regression     sidecar focused 56/56
route metadata focused coverage          19/19
adjacent sidecar route/app suite         64/64
prompt annotation focused tests          29/29
adjacent sidecar suite after annotation  75/75
route annotation comparison eval         3/3
focused route annotation pytest slice    16/16
route/model sweep helper tests           12/12
deterministic route/model sweep slice    qwen 2/2, phi3 2/2
custom silly-personality model slice      qwen 1/1
support/personality model slice          qwen 3/3
support/personality alternate slice      qwen3 3/3, slow
depth/spiral model slice                  qwen 2/2
depth/spiral alternate slice              qwen3 2/2, slow
code/tool model slice                     qwen 1/1
code/tool coder-model slice               qwen2.5-coder 1/1
pasted-chat regression slice              qwen 4/4
route/model recommendation metadata       backend 20/20, UI 11/11, build passed, live meta/depth/code/context/high-stakes smokes passed
operator model-policy summary UI          App+TraceDrawer 23/23, build passed, HTTP 200, browser visual smoke passed
settings model-policy readout             App+TraceDrawer 24/24, build passed, browser visual smoke passed
TraceDrawer UI tests                     11/11
App + TraceDrawer UI tests               22/22
Workbench build                          passed
live route-decision smoke                5/5
live prompt-annotation smoke             4/4
representation replay tests              7/7
adjacent compression/scaffold tests       20/20
```

Latest focused command run tonight:

```powershell
cd D:\AI_round2\aether-core
python scripts\route_policy_annotation_eval.py --json
python -m pytest tests/test_route_policy_annotation_eval.py tests/test_sidecar_ingest.py tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_deep_request_records_depth_policy_and_prompt_guidance -q
python -m pytest tests/test_route_model_sweep_eval.py tests/test_workbench_eval.py -q
python scripts\route_model_sweep_eval.py --model qwen2.5:7b-instruct --model phi3:3.8b --route deterministic_meta --json --output-dir .eval-runs
python scripts\route_model_sweep_eval.py --case-id real_use_silly_personality_low_key --json --output-dir .eval-runs
```

Result:

```text
route annotation eval: passed true, 3/3 cases
pytest focused slice: 16 passed
route/model sweep tests: 12 passed
deterministic route/model sweep: qwen 2/2, phi3 2/2; wrote .eval-runs\route_model_sweep_20260625_181036.json
custom silly-personality sweep: qwen 1/1; wrote .eval-runs\route_model_sweep_20260625_181447.json
npm shortcut silly-personality sweep: qwen 1/1; wrote .eval-runs\route_model_sweep_20260625_225929.json
support/personality sweep: qwen 3/3; wrote .eval-runs\route_model_sweep_20260625_233600.json
support/personality sweep: qwen3 3/3 in about 154s; wrote .eval-runs\route_model_sweep_20260626_023322.json
depth/spiral sweep: qwen 2/2; wrote .eval-runs\route_model_sweep_20260626_015831.json
depth/spiral sweep: qwen3 2/2 in about 157s; wrote .eval-runs\route_model_sweep_20260626_033421.json
code/tool sweep: qwen 1/1; wrote .eval-runs\route_model_sweep_20260626_015910.json
code/tool sweep: qwen2.5-coder 1/1 in about 23s; wrote .eval-runs\route_model_sweep_20260626_030051.json
pasted-chat regression: qwen 4/4; wrote .eval-runs\workbench_eval_20260626_022453.json
route/model recommendation metadata: backend focused 20/20; TraceDrawer UI 11/11; Workbench build passed; live deterministic-meta smoke after sidecar restart showed observational recommendation metadata with model_selection_changed=false; focused live depth/code smoke passed with zero memory writes:
  depth_synthesis turn_9bdb97ca569d -> fallback qwen3:14b, model_selection_changed=false
  code_tool turn_c5cac494d807 -> fallback qwen2.5-coder:14b, model_selection_changed=false
  context_bridge_broad turn_61fe958f7fc2 -> fallback qwen3:14b, model_selection_changed=false
  high_stakes_caution turn_3cc9b06f0d58 -> fallback none, model_selection_changed=false
operator model-policy summary UI: App+TraceDrawer UI 23/23; Workbench build passed; Vite dev server HTTP smoke returned 200 on http://127.0.0.1:5175/; in-browser visual smoke passed on default desktop and 390x720 narrow viewport with zero console warnings/errors
settings model-policy readout: App+TraceDrawer UI 24/24; Workbench build passed; in-browser Settings smoke showed read-only deterministic_meta recommendation with no automatic switch and zero console warnings/errors
technical reasoning retry/regression: sidecar route/prompt/app focused tests 56/56; covers general proof/vector route, memory-restriction refusal repair, and trace-visible bare retry resolution
```

Pasted-chat regression cases:

```text
real_use_project_purpose_not_generic_companion
real_use_aeteros_llc_clean_formation_question
real_use_aether_aeteros_value_worth_pursuing
real_use_governance_layers_deterministic
```

Repairs covered:

- `What is the point of the project?` now uses a deterministic Aether-character
  project thesis instead of thin "local companion" language.
- clean Aeteros LLC formation questions no longer imply Aeteros is the existing
  LLC or drift into generic legal-benefit checklists.
- Aeteros/Aether value questions are scored against glossy optimism and should
  preserve candid, unproven, risk, monetary/product, and eval-next-step anchors.
- governance-layer questions answer from deterministic meta/governance instead
  of local-model freestyle.

Operator note: an early all-discovered-model support/personality sweep timed
out. Use explicit `--model` lists and thin `--route` or `--case-id` slices for
automation. `--all-discovered-models` exists, but should be supervised.

## Dev Commands

Start sidecar:

```powershell
cd D:\AI_round2\aether-core
python -m aether.sidecar
```

Start Workbench:

```powershell
cd D:\AI_round2\workbench
npm run dev
```

Run route annotation eval:

```powershell
cd D:\AI_round2\aether-core
python scripts\route_policy_annotation_eval.py --json
```

or from Workbench:

```powershell
cd D:\AI_round2\workbench
npm run eval:route-annotation -- --json
```

Run sliced route/model sweep:

```powershell
cd D:\AI_round2\workbench
npm run eval:route-model-sweep -- --model qwen2.5:7b-instruct --model phi3:3.8b --route deterministic_meta --json
npm run eval:route-model-sweep -- --case-id real_use_silly_personality_low_key --json
npm run eval:route-model-sweep -- --model qwen2.5:7b-instruct --route support_personality --json
npm run eval:route-model-sweep -- --model qwen2.5:7b-instruct --route depth_spiral --json
npm run eval:route-model-sweep -- --model qwen2.5:7b-instruct --route code_tool --json
```

Run representation replay:

```powershell
cd D:\AI_round2\workbench
npm run eval:representation-replay
```

Run bridge candidate replay:

```powershell
cd D:\AI_round2\workbench
npm run eval:bridge-candidates
```

Run archive candidate replay:

```powershell
cd D:\AI_round2\workbench
npm run eval:archive-candidates -- --json
```

Run personal archive bootstrap dry-run/apply:

```powershell
cd D:\AI_round2\workbench
npm run archive:bootstrap -- .eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json --batch-id archive-20260625-personal-bootstrap --json
npm run archive:bootstrap -- .eval-runs\chatgpt_archive_fact_probe_20260625_review_packets_spiral_support.json --batch-id archive-20260625-personal-bootstrap --apply --json
```

Run isolated Learn promotion smoke:

```powershell
cd D:\AI_round2\workbench
npm run smoke:learn-promotion -- --json
```

Run archive review fixture smoke:

```powershell
cd D:\AI_round2\workbench
npm run smoke:archive-review -- --json
```

Sidecar reboot flow if stale:

1. Check `http://127.0.0.1:8765/health`.
2. Only restart a listener clearly identified as `python -m aether.sidecar`.
3. Restart from `D:\AI_round2\aether-core` with `python -m aether.sidecar`.
4. Re-check health.

Do not kill unrelated processes or destructively clean ports.

## Dirty Worktree Caution

The worktree is intentionally dirty. Many changes are active roadmap work. Do
not run `git reset --hard`, do not delete untracked directories, and do not
checkout files unless Nick explicitly asks.

Known active areas include:

- `aether-core/` sidecar, tests, scripts;
- `workbench/` UI, API, drawers, types, tests;
- `labs/meaning_compression_lab/representation_replay.py`;
- `docs/plans/` roadmap/runbook/handoff docs.

## Next Best Work

1. **Route/model sweep eval pack**
   - Run the same route-specific prompts across available local models.
   - Score by route, not global vibes:
     support/personality, depth/spiral, code/tool, contradiction, governance,
     genericness resistance, latency.
   - Keep results observational first.

2. **Agentic archive import eval lane**
   - Review fixtures, typed representation packets, preview-only
     review-surface smoke, archive candidate replay, and personal fast bootstrap
     import now exist.
   - Next, test chat behavior after the targeted bootstrap import and decide
     whether to run broader archive probes beyond the spiral/support slice.
   - Later, add Workbench UI/undo affordances for archive bootstrap batches.
   - Preserve role separation: user semantics are not assistant responses, and
     assistant interpretations are never confirmed user facts.

3. **Live prompt-annotation comparison**
   - Run sliced live prompts with prompt annotation on current sidecar.
   - Compare answer quality against previous baseline traces where available.
   - Do not add automatic model switching yet.

4. **Model policy proposal**
   - Convert evidence into route/model recommendations:
     deterministic for meta/conflict, `qwen2.5:7b-instruct` as stable default,
     `qwen3:14b` as a quality candidate for support/depth when latency is
     acceptable, `qwen2.5-coder:14b` as a code-tool specialist candidate, and
     `phi3:3.8b` as small-model stress proof.
   - Show recommended vs selected in traces before actually switching.

5. **Only then consider a steering gate**
   - The first safe gate should be reviewable route/model recommendation or
     prompt annotation/repair gating.
   - Do not silently switch models or escalate to frontier models.

## Restart Prompt

Use this exact prompt for the next clean thread:

```text
We are in D:\AI_round2. Read:
- docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-25.md
- docs/plans/AETHER_ROUTE_CAPABILITY_TABLE_2026-06-25.md
- docs/plans/AETHER_WORKBENCH_V1.md only as needed

Continue Aether Workbench in the current aether-core/workbench lane. Do not
revive the legacy frontend/API. Do not do repo breakout cleanup yet. Preserve
dirty worktree context and do not reset/delete untracked files.

Current lane: Phase 1.10 governed route/model selection.

Immediate next task:
1. Convert the current Phase 1.10 evidence into a route/model recommendation
   table: current selected model, recommended model policy, fallback model,
   confidence, latency caveat, and evidence path.
2. This now exists in trace metadata as
   `route_decision.model_recommendation`. Keep it observational. Do not change
   automatic model selection yet.
3. Deterministic-meta, depth_synthesis, code_tool, context_bridge_broad, and
   high_stakes_caution live recommendation smokes now pass with zero memory
   writes and model_selection_changed=false. The operator-facing route/model
   recommendation summary surface now exists outside the Trace drawer.
   In-browser visual smoke passed on desktop/default and 390x720 narrow viewport
   with zero console warnings/errors. Settings now also shows model policy as a
   read-only policy readout. Phase 1.10 is ready to pause unless Nick wants to
   continue into automatic recommendation gates.
4. If adding more evidence first, use thin sliced commands only: one route,
   one explicit model list, no `--all-discovered-models` unless supervised.
5. Preserve archive import and learner lanes as review-only; do not silently
   import archive candidates or learner candidates.
6. Update route capability, handoff, and roadmap docs with any new evidence.

Safety contract: no silent durable writes, no support imports, no reflection
creation, no silent frontier escalation, and no model/tool calls inside
route_policy.
```

## One-Line Status

Aether is now a working local governed-memory Workbench with trace-visible
memory release, contradiction disposition, depth/continuation, review-only
support/learner flows, representation compression eval evidence, observational
route policy, and a body-aware role-separated GPT archive import/replay lane.
Nick's local system also has the first targeted archive bootstrap applied as
accepted support/reflection stance, plus deterministic repairs for GPT-corpus
provenance and low-key personality/style calibration. Phase 1.10 now has an
observational route/model sweep helper with first deterministic-meta, support,
depth, code, and pasted-chat evidence across qwen, qwen3, qwen-coder, and phi3.
The first trace-visible route/model recommendation metadata now exists and has
fresh deterministic-meta, depth_synthesis, code_tool, context_bridge_broad, and
high_stakes_caution live smoke coverage. The chat surface now shows a compact
operator model-policy summary when recommendation metadata exists. The next
frontier is a user decision on automatic recommendation gates; automatic model
swapping remains off.
