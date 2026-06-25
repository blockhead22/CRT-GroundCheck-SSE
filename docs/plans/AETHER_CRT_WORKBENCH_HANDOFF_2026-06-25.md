# Aether / CRT / Workbench Handoff - 2026-06-25

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
Phase 2 governed learner / Mirus loop        scaffolded, review-only
```

The active lane is **Phase 1.10: governed route/model selection**.

Important current rule:

```text
Route policy may annotate traces/prompts, but it must not silently switch
models, write memory, call tools, import support patterns, create reflections,
or escalate to frontier models.
```

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
- eval-only comparison for observational route policy vs prompt-annotated
  route policy:
  `D:\AI_round2\aether-core\scripts\route_policy_annotation_eval.py`.

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
  routes when available.
- `phi3:3.8b` proved small-model scaffold/depth capability, but is not the
  preferred daily model.
- Deterministic routes should stay deterministic; no generative model should
  decide trace/governance facts.

## What Aether Can Do Now

- Answer normal local Workbench chat through Ollama with governed context.
- Answer meta/governance questions deterministically from route/trace metadata.
- Show why an answer stayed local, what route was selected, and what model was
  selected/generated when trace data exists.
- Handle many Nick-style real-use prompts better than the early generic
  baseline.
- Use accepted support patterns as governed behavior guidance.
- Surface conflicted memory as reviewable contradiction, not guessed truth.
- Run code-context/tool-first local programming orientation for tested prompt
  shapes.
- Run isolated eval helpers for disposition, support-pattern, learn promotion,
  representation replay, bridge candidates, route policy, and route annotation.
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
route policy tests                       9/9
route metadata focused coverage          19/19
adjacent sidecar route/app suite         64/64
prompt annotation focused tests          29/29
adjacent sidecar suite after annotation  75/75
route annotation comparison eval         3/3
focused route annotation pytest slice    13/13
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
python -m pytest tests/test_route_policy_annotation_eval.py tests/test_sidecar_route_policy.py tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced -q
```

Result:

```text
route annotation eval: passed true, 3/3 cases
pytest focused slice: 13 passed
```

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

Run isolated Learn promotion smoke:

```powershell
cd D:\AI_round2\workbench
npm run smoke:learn-promotion -- --json
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

2. **Live prompt-annotation comparison**
   - Run sliced live prompts with prompt annotation on current sidecar.
   - Compare answer quality against previous baseline traces where available.
   - Do not add automatic model switching yet.

3. **Model policy proposal**
   - Convert evidence into route/model recommendations:
     deterministic for meta/conflict, `qwen2.5:7b-instruct` as stable default,
     `qwen3:14b` as likely character/support candidate, `phi3:3.8b` as
     small-model stress proof.
   - Show recommended vs selected in traces before actually switching.

4. **Only then consider a steering gate**
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
1. Add a route/model sweep eval pack that compares available local models by
   route: support/personality, depth/spiral, code/tool, contradiction,
   deterministic governance, genericness resistance, and latency.
2. Keep the sweep observational. Do not change automatic model selection yet.
3. If services are available, run sliced live prompt-annotation comparisons;
   otherwise keep the work fixture/deterministic.
4. Update the route capability table with evidence and next model-policy
   recommendations.

Safety contract: no silent durable writes, no support imports, no reflection
creation, no silent frontier escalation, and no model/tool calls inside
route_policy.
```

## One-Line Status

Aether is now a working local governed-memory Workbench with trace-visible
memory release, contradiction disposition, depth/continuation, review-only
support/learner flows, representation compression eval evidence, and
observational route policy. The next frontier is evidence-driven per-route model
selection, not automatic model swapping yet.
