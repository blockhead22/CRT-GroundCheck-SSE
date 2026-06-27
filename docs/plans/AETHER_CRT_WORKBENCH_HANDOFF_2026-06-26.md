# Aether / CRT / Workbench Handoff - 2026-06-26

This is the clean restart packet for a new Codex thread in `D:\AI_round2`.

Start here. Use the older roadmap docs as references, but do not restart broad
archaeology unless a specific missing concept requires a specific source file.

## Active Lane

```text
aether-core sidecar + Workbench UI
```

Current roadmap position:

```text
Phase 1.5 depth / continuation trace UI      done enough, keep regression evals
Phase 1.6 programming robustness             first pass done, preserve as needed
Phase 1.7 tone / personality / support       implemented and tested
Phase 1.8 contradiction disposition          implemented first pass, tested
Phase 1.9 representation compression evals   implemented first pass, strong signal
Phase 1.10 route/model selection             active, observational only
Phase 1.11 Aether/Aeteros layer split        strategic rule added
Phase 2 governed learner / Mirus loop        scaffolded, review-only
```

Current rule:

```text
Route policy may annotate traces/prompts and recommend models, but it must not
silently switch models, write memory, call tools, import support patterns,
create reflections, or escalate to frontier models.
```

## Read These First

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-26.md
D:\AI_round2\docs\plans\AETHER_ROUTE_CAPABILITY_TABLE_2026-06-25.md
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

Reference docs:

```text
D:\AI_round2\docs\plans\AETHER_RECOVERED_CONCEPT_INTEGRATION_AUDIT_2026-06-24.md
D:\AI_round2\docs\plans\AETHER_ISOLATED_FIXTURE_EVAL_RUNBOOK_2026-06-25.md
D:\AI_round2\docs\plans\AETHER_LEARN_DRAFT_PROMOTION_RUNBOOK_2026-06-25.md
D:\AI_round2\docs\plans\AETEROS_AETHER_LAYER_SPLIT_2026-06-25.md
```

## What Changed Most Recently

### Empty Chat UI Bug Fixed

Nick reported a Workbench UI bug where the empty-chat composer became a giant
vertical panel. Root cause: `ModelPolicySummary` returned `null` when no active
route/model recommendation existed, shifting the CSS grid children so the
composer landed in the flexible chat-history row.

Fix:

```text
D:\AI_round2\workbench\src\components\ModelPolicySummary.tsx
D:\AI_round2\workbench\src\styles.css
D:\AI_round2\workbench\src\App.test.tsx
```

The component now renders a zero-height placeholder when inactive so grid row
alignment stays stable.

Verification:

```text
cd D:\AI_round2\workbench
npm run test:ui -- --run src/App.test.tsx src/components/TraceDrawer.test.tsx
25 passed
npm run build
passed

Browser visual smoke on http://127.0.0.1:5175/
composer height: 75px
conversation height: 461px
console warnings/errors: 0
passed: true
```

### Technical Reasoning / Retry Regression Fixed

Nick tested:

```text
Can you show me a proof of an algorithm that compresses meaning into a
10 dimensional vector space.
try again
```

Bad behavior: Aether treated a general technical/math request as if memory
restrictions blocked it, then answered `try again` as a bare acknowledgement.

Fix:

```text
D:\AI_round2\aether-core\aether\sidecar\route_policy.py
D:\AI_round2\aether-core\aether\sidecar\prompt.py
D:\AI_round2\aether-core\aether\sidecar\app.py
D:\AI_round2\aether-core\tests\test_sidecar_route_policy.py
D:\AI_round2\aether-core\tests\test_sidecar_ingest.py
D:\AI_round2\aether-core\tests\test_sidecar_app.py
```

Behavior:

- new `technical_reasoning` route for general proof, algorithm, embedding,
  vector-space, theorem, and technical reasoning prompts;
- prompt annotation says memory restrictions constrain governed-memory claims,
  not general technical reasoning;
- repair pass catches technical answers that cite memory restrictions and
  regenerates with an honest technical contract;
- bare retry turns like `try again` resolve to the previous substantive user
  request in the same conversation;
- retry resolution is trace-visible under `retry_resolution`;
- automatic model switching remains off.

Verification:

```text
cd D:\AI_round2\aether-core
python -m pytest tests/test_sidecar_route_policy.py tests/test_sidecar_ingest.py tests/test_sidecar_app.py -q
56 passed

python -m pytest tests/test_sidecar_route_policy.py tests/test_sidecar_ingest.py tests/test_sidecar_app.py tests/test_route_policy_annotation_eval.py -q
58 passed
```

Expected answer shape for the 10D meaning-compression prompt:

```text
No, not as a general lossless proof. You can build approximate embeddings or
task-bounded projections, but arbitrary meaning cannot be proven to compress
faithfully into 10 dimensions without strong assumptions. A useful answer should
name the assumptions, algorithm, loss function, and eval target.
```

## Current Capabilities

- Governed memory release: only answerable evidence goes into local generation.
- Contradiction disposition: `resolvable`, `held`, `evolving`, `contextual`,
  `stale`, `policy_bound` labels are surfaced and traced.
- Workbench Trace drawer: response route, depth, tools, contradiction
  disposition, and route decisions.
- Workbench chat surface: compact model-policy summary when route/model
  recommendation metadata exists.
- Settings: read-only model-policy recommendation readout.
- Model recommendations: trace-visible only, no automatic switching.
- Depth/spiral requests: bounded continuation and trace-visible depth policy.
- Code-tool prompts: tool-first route with workspace search/read/test guidance.
- Technical reasoning prompts: first-pass route plus memory-refusal repair.
- ChatGPT archive support/reflection stance: targeted bootstrap was applied to
  Nick's local system as accepted support/reflection stance, not confirmed
  profile facts.
- Phase 2 learner/Mirus loop: review-only candidate preview and manual
  promotion surfaces; no silent durable writes.

## Current Limitations

- No proven global best local model.
- No automatic per-route model switching yet.
- No silent archive learning for general users.
- No silent learner memory writes.
- Technical reasoning route has only first regression coverage, not broad math
  or programming-theory eval coverage.
- Live support-pattern behavior depends on accepted live candidates.
- All-in-one live evals can time out; use sliced eval commands.
- Workbench is still the proof loop, not product packaging.

## Model Evidence

Current observational read:

```text
qwen2.5:7b-instruct      safest tested daily default
qwen3:14b                better candidate for support/depth when latency is ok
qwen2.5-coder:14b        promising code-tool specialist, thin evidence
phi3:3.8b                small-model stress proof, not daily preference
deterministic routes     should stay deterministic
```

Known route/model evidence:

```text
deterministic_meta: qwen2.5 2/2, phi3 2/2
support_personality: qwen2.5 3/3, qwen3 3/3 slow
depth_spiral: qwen2.5 2/2, qwen3 2/2 slow
code_tool: qwen2.5 1/1, qwen2.5-coder 1/1
pasted-chat regression: qwen2.5 4/4
```

## Dirty Worktree Caution

There are many modified/untracked files from the active Aether lane. Do not
reset or delete them. Treat untracked `aether-core/` content as active work, not
junk.

Current notable areas:

```text
D:\AI_round2\aether-core\
D:\AI_round2\workbench\
D:\AI_round2\docs\plans\
D:\AI_round2\labs\meaning_compression_lab\
D:\AI_round2\tmp\aether-backups\
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
npm run dev -- --host 127.0.0.1 --port 5175
```

If the sidecar is stale:

```powershell
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,State,OwningProcess

Get-Process -Id <PID> | Select-Object Id,ProcessName,Path,CommandLine
```

Only stop a process clearly identified as `python -m aether.sidecar`. Do not
kill unrelated listeners or destructively clean ports.

## Suggested Manual Smoke Tests

After restarting sidecar and Workbench, test:

```text
Aether, what model are you using, what context shaped this answer, and should
this have stayed local or escalated?

Can you show me a proof of an algorithm that compresses meaning into a
10 dimensional vector space.

try again

Aether, you have my GPT corpus right?

What is the point of the project?
```

Expected checks:

- meta/governance answer is deterministic;
- technical prompt does not blame memory restrictions;
- `try again` answers the previous technical prompt, not the literal retry;
- GPT corpus answer distinguishes reviewed archive-derived stance from raw
  corpus access or confirmed profile facts;
- empty chat composer remains compact;
- route/model policy surfaces remain read-only and say no automatic switch.

## What Is Next

Best next work, in order:

1. **Pause Phase 1.10 as observational unless Nick explicitly wants automatic
   model gates.**
   - Route decisions, recommendation metadata, Trace drawer, chat summary, and
     Settings readout exist.
   - Automatic switching should not happen until there is more evidence and a
     user-visible override/undo story.

2. **Add a small route/model operator gate, not silent auto-switching.**
   - Best shape: a read-only recommendation plus optional manual "try with
     recommended model" action.
   - Keep deterministic/meta routes deterministic.
   - Keep frontier escalation user-approved only.

3. **Broaden technical reasoning evals.**
   - Add proof/impossibility, algorithm tradeoff, embeddings, compression, and
     programming-theory prompts.
   - Compare qwen2.5 vs qwen3 on a small explicit slice.
   - Do not use `--all-discovered-models` unsupervised.

4. **Continue archive/import onboarding carefully.**
   - For Nick, personal fast bootstrap is acceptable.
   - For product/open-source users, keep import reviewable and provenance-rich.
   - Separate user-authored claims, user semantics, assistant support stance,
     and assistant interpretations.

5. **Move toward the Phase 2 background learner heartbeat.**
   - It should propose reviewable facts, contradictions, support patterns,
     reflections, and self-improvement notes.
   - It must not silently write confirmed memory.

6. **Keep the Aether/Aeteros split visible.**
   - Aether: Nick's dogfooded local proof loop.
   - Aeteros Core: reusable governed-memory primitives.
   - Aeteros: future company/research wrapper.

## Restart Prompt

Use this prompt for the next clean thread:

```text
We are in D:\AI_round2. Read:
- docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-26.md
- docs/plans/AETHER_ROUTE_CAPABILITY_TABLE_2026-06-25.md
- docs/plans/AETHER_WORKBENCH_V1.md only as needed

Continue Aether Workbench in the current aether-core/workbench lane. Do not
revive the legacy frontend/API. Do not do repo breakout cleanup yet. Preserve
dirty worktree context and do not reset/delete untracked files.

Current lane: Phase 1.10 governed route/model selection is functionally
observational and ready to pause unless Nick wants manual model gates.

Current status:
- route_policy is side-effect-free;
- route_decision is trace-visible and prompt-annotated;
- route_decision.model_recommendation exists but does not switch models;
- Trace drawer, chat surface, and Settings show route/model policy readouts;
- empty-chat composer grid bug is fixed via ModelPolicySummary placeholder;
- technical_reasoning route fixes proof/algorithm prompts that incorrectly cite
  memory restrictions;
- bare retry turns such as "try again" resolve to the previous substantive user
  request and are trace-visible under retry_resolution;
- archive-derived support/reflection stance exists for Nick's local system, but
  archive import remains provenance-bound and should not become confirmed facts
  without explicit policy.

Immediate next task:
1. Restart sidecar/Workbench if needed.
2. Run a manual smoke with meta/governance, technical proof, "try again",
   GPT-corpus provenance, and project-purpose prompts.
3. If stable, either pause Phase 1.10 and start broader technical-reasoning evals,
   or design a manual "try recommended model" gate. Do not silently switch
   models.

Safety contract: no silent durable writes, no support imports, no reflection
creation, no silent frontier escalation, and no model/tool calls inside
route_policy.
```

## One-Line Status

Aether is a working local governed-memory Workbench with trace-visible memory
release, contradiction disposition, depth/continuation, review-only
support/learner flows, archive-derived support/reflection stance, representation
compression eval evidence, and observational route/model policy. The next
frontier is not "more magic"; it is stable manual/operator model routing,
broader technical reasoning evals, and a review-only background learner loop.
