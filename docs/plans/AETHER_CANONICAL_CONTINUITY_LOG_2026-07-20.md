# Aether Canonical Continuity Log

**Snapshot date:** 2026-07-20

**Operationally superseded:** 2026-08-04 by
`AETHER_CANONICAL_CONTINUITY_LOG_2026-08-04.md`. Retain this file as detailed
historical product and research context.

**Workspace:** `D:\AI_round2`

**Purpose:** Give Grok, Codex, or another AI engineering agent enough verified
context to continue Aether product work or a named research lane without
repeating archaeology, confusing lab code with production, or weakening the
governance contract.

## Start Here

Read this document first. Then read, in order:

```text
D:\AI_round2\docs\plans\AETHER_UNIFIED_ROADMAP_2026-07-16.md
D:\AI_round2\docs\plans\AETHER_CURRENT_STATE.md
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_TASK_CONTINUATION_SLICE_2_RESULTS_2026-07-19.md
D:\AI_round2\docs\plans\AETHER_TASK_AUTHORITY_SLICE_3_RESULTS_2026-07-19.md
D:\AI_round2\docs\plans\AETHER_TASK_CANDIDATE_AUTHORITY_SLICE_4_RESULTS_2026-07-19.md
D:\AI_round2\docs\plans\AETHER_MIRUS_SEMANTIC_TASK_INTAKE_LAB_2026-07-20.md
```

Use older plans and archived notes only for a named missing mechanism. Do not
restart broad archive archaeology.

## Immediate Agent Rules

1. Preserve both dirty worktrees. Do not reset, clean, or revert unfamiliar
   changes.
2. `D:\AI_round2\aether-core` is a nested Git repository. Root Git status is
   not enough.
3. Confirm production call sites before saying a mechanism is live. An import,
   test, fixture, result file, or architecture note is not live integration.
4. Do not store raw hidden chain-of-thought as truth. Store only intentional
   public rationale and structured governance metadata.
5. Do not grant memory, task, tool, model-routing, or policy authority from a
   model proposal.
6. Prefer focused tests plus direct API and rendered Workbench checks over
   indefinite broad testing.
7. Do not retune a revealed evaluation pack and call the result generalization.
8. Never store credentials, API keys, or authentication material in this repo.

## One-Line Project State

Aether is a working local-first governed-assistant prototype whose strongest
implemented distinction is not a smarter base model, but explicit evidence,
review, contradiction, verification, task-authority, and durable-trace layers
around replaceable local or hosted renderers.

The bounded cross-conversation continuity and reviewed task-authority gate is
closed. The canonical roadmap names desktop distribution readiness as the next
product lane. Nick explicitly passed on distribution work for the current
round and authorized a Mirus semantic-intake lab instead. That lab completed
with a no-ship decision. There is no implied active implementation lane after
this document; ask Nick whether to resume product distribution, reopen a named
research question, or address a concrete daily-use regression.

## Product Thesis

```text
Aether-for-Nick = private daily proof loop and stress test
Aeteros Core    = reusable governed memory, authority, and trace primitives
Product Aether  = Aeteros Core + user-owned memory + polished Workbench
```

Governing rule:

```text
Personalize the content. Generalize the mechanism.
```

Defensible claim:

```text
Moving task classification, evidence authority, memory review, contradiction
handling, verification, repair/fallback, and durable trace outside the language
model can make smaller local-model behavior more reliable and inspectable on
Aether's tested task families.
```

Unsupported claims:

```text
Aether is AGI.
Aether makes local models globally equal to frontier models.
Every research module is live in Workbench.
Perfect curated scores prove broad generalization.
Model rationale is truth or durable memory.
Retrieved conversation text is automatically a confirmed personal fact.
```

## Layer Vocabulary

### Aether

The personal assistant and Workbench product. It combines private user context
with reusable governance mechanisms.

### Aeteros Core

The reusable, non-Nick-specific primitives: evidence receipts, review
candidates, safety contracts, task authority, contradiction boundaries,
verification, and durable trace schemas.

### Mirus

Intake, evidence organization, semantic structure, memory proposals,
contradiction awareness, and review-candidate formation. Mirus may notice or
propose. It does not own truth or authority.

### Holden

Expression and rendering. A local or hosted language model can turn a governed
packet into useful prose. Holden is replaceable vocal output, not the source of
memory, task, tool, or release authority.

### CRT

Contradiction-resilient trust and governance: source boundaries, held claims,
verification, repair/fallback, confidence, and explicit refusal to turn
plausible language into unsupported truth.

### Workbench

The React/Electron operator surface for chat, public trace, memory review,
support/reflection review, learner candidates, and task-candidate promotion or
rejection.

## Repository Topology

```text
D:\AI_round2\                         root research/product workspace
D:\AI_round2\aether-core\             nested Python repository and sidecar
D:\AI_round2\workbench\               React + Electron Workbench
D:\AI_round2\labs\                    isolated research/evaluation lanes
D:\AI_round2\docs\plans\              current plans, evidence, and handoffs
D:\AI_round2\docs\archive\            historical notes, not current authority
D:\AI_round2\artifacts\                generated/isolated evidence, often ignored
```

Current runtime defaults and local endpoints:

```text
Ollama:          http://127.0.0.1:11434
Aether sidecar:  http://127.0.0.1:8765
Workbench Vite:  http://127.0.0.1:5175
Default model:   qwen3:14b
Fast lab model:  qwen2.5:7b-instruct
```

Re-probe services before making runtime claims. A healthy sidecar does not
prove that Vite or Electron is usable.

## Live Runtime Chain

The defensible live path is:

```text
Workbench ChatPanel
-> POST /v1/chat/stream
-> Aether sidecar routing and continuity policy
-> governed substrate/evidence/context assembly
-> deterministic answer or selected local/hosted renderer
-> response contract and completion verification
-> persisted conversation answer and structured trace
-> Workbench inline Thinking/Process and Trace drawer
```

Primary call sites:

```text
D:\AI_round2\workbench\src\components\ChatPanel.tsx
D:\AI_round2\workbench\src\components\TraceDrawer.tsx
D:\AI_round2\workbench\src\components\ConsolidationDrawer.tsx
D:\AI_round2\workbench\src\api.ts
D:\AI_round2\workbench\electron\main.cjs
D:\AI_round2\workbench\electron\sidecar.cjs
D:\AI_round2\aether-core\aether\sidecar\app.py
D:\AI_round2\aether-core\aether\sidecar\governance_trace.py
```

Important live endpoints include:

```text
POST /v1/chat/stream
GET  /v1/traces/{turn_id}
GET/POST /v1/continuity/open-loops
GET/POST /v1/continuity/artifacts
GET/POST /v1/continuity/constraints
GET  /v1/consolidation/candidates
POST /v1/consolidation/task-candidates/{candidate_id}/review
```

## What Is Live

### Governed conversation and trace

- Conversations and completion traces persist in the sidecar database.
- Public traces expose classification, route/model choice, retrieval receipts,
  memory checks, tool consideration/results, verifier findings,
  repair/fallback, and review-only candidates.
- The UI intentionally resembles a readable Activity/Thinking trace without
  treating private model scratchpad as evidence.
- Compound system questions can preserve multiple requested answer jobs rather
  than letting runtime-model identity replace the purpose answer.

### Governed memory and learner review

- Confirmed narrow facts can enter the substrate only through existing explicit
  capture/review contracts.
- Soft signals, contradictions, archive evidence, support candidates, and
  reflection candidates remain review-only until accepted through their
  appropriate surface.
- Reject/defer decisions are behaviorally inert.
- Candidate generation is not a memory write.
- Historical user text is evidence of what the user said, not automatic proof
  that the statement is a current durable fact.

### Cross-conversation continuity

- Bounded archive retrieval can cite and align explicitly selected prior
  conversation evidence.
- `/resume` can use durable `user_explicit` or `review_confirmed` open loops.
- When multiple loops exist, Workbench requires an explicit revision-bound
  selection and fails closed on stale or unavailable choices.
- Task artifacts and constraints are persistent, project-scoped, typed, and
  revisioned.
- Revoked constraints remain visible as history but cannot authorize current
  continuation.
- Continuity does not grant automatic execution, workspace tools, memory
  writes, or general reconstruction of arbitrary task state from prose.

### Mirus task candidates

- A narrow deterministic intake notices direct first-person planning actions
  and selected schedule/conditional constraints.
- It emits review-only trace candidates with exact user receipts.
- Workbench Learn -> Tasks can explicitly promote or reject a candidate.
- Promotion creates one existing `review_confirmed` open-loop or constraint
  record. Rejection creates no task authority.
- Decisions survive page reload and sidecar restart.
- Quoted-note and planner-example wording is now explicitly blocked after the
  2026-07-20 development pack found two false candidates.

### Local and hosted rendering

- Local Ollama rendering is supported. `qwen3:14b` is the normal default;
  `qwen2.5:7b-instruct` is a useful faster lab/fallback model.
- A governed hosted Grok renderer path has bounded evidence. Aether still owns
  retrieval, memory, validation, release, and final verification.
- Hosted rendering is not an independent authority or permission grant.
- No silent model switching is allowed.

### Narrow critic-repair runtime

- Selected abstract governance/epistemic character routes can carry a public
  critic contract.
- The sidecar records pre/post findings and repair triggers.
- This is bounded public metadata over a draft, not hidden chain-of-thought or
  self-authorized policy learning.

## What Is Not Live

The following must not be described as ordinary Workbench capability without a
new call-site audit:

- the 2026-07-20 semantic task-intake model proposer;
- generative-governance spike code as a general response path;
- Mirus belief-map experiments;
- learned Mirus scorer experiments;
- J-lens/Fisher-Rao/backpropagation research modules;
- broad GroundCheck or boundary-audit demos as universal chat behavior;
- the governed hosted read-only tool broker;
- unrestricted shell, write, retrieval, or autonomous execution tools;
- neural or silent self-modification from thumbs-up/down feedback;
- automatic memory, support, reflection, task, or policy writes.

The hosted read-only tool experiment permits only isolated, path-bounded
`workspace_read`, `git_status`, and `git_diff` operations under a capability
grant. It is not wired into ordinary Workbench. Before any opt-in product mode,
it still needs adversarial packet/tool-output injection testing and adaptive
multi-step read-only planning evidence.

## Product Milestone Log

### Conversation-control and Workbench baseline

- Route/model policy, retry resolution, deterministic concept answers, memory
  authority, and public trace display were stabilized through June and July.
- Profile isolation, backup/restore, interrupted resume, installed Python, and
  Windows Electron lifecycle received bounded tests.
- Do not revive legacy frontends or APIs without a named product need.

### Task continuation Slice 1 - 2026-07-18

- Introduced explicit `TaskContinuationPacket` behavior.
- Exactly one durable reviewed/explicit loop could authorize conversational
  continuation.
- Tools, execution, memory, and writes remained blocked.

### Task continuation Slice 2 - 2026-07-19

- Added explicit Workbench selection when multiple loops exist.
- Selection is revision-bound and project-scoped.
- Stale, incomplete, or unavailable selections fail closed.

### Task authority Slice 3 - 2026-07-19

- Added persistent typed artifacts and active/revoked constraints.
- Frozen 36-case white-box task-state pack passed 36/36 through the real
  sidecar with zero model calls, tool runs, memory writes, or execution grants.
- This is white-box contract evidence, not arbitrary task-recovery proof.

### Task candidate authority Slice 4 - 2026-07-19

- Connected deterministic Mirus intake to trace and learner review.
- Added explicit promote/reject decision receipts.
- Browser dogfood proved promotion, rejection non-effect, reload, and fresh
  sidecar rehydration.
- Verification checkpoint: 143 backend tests, 73 Workbench component tests,
  26 Electron tests, and a passing production build.
- This closed the bounded reviewed-task-authority gate.

## Research and Lab Log

### Local router, RAG baseline, and durable trace - graduated

Original question: can externalized governance make a smaller local model more
coherent, evidence-bound, and inspectable?

Key progression:

```text
curated v1: raw 0/32, governed 32/32, trace 32/32
blind v1:   raw 0/13, governed 13/13, trace 13/13
perturbed RAG total:
  scaffolded_rag 12/32 avg 0.673
  governed       31/32 avg 0.758, trace 32/32
adversarial v1: scaffolded_rag 7/9, governed 9/9
adversarial v2: scaffolded_rag 5/6, governed 6/6
```

Interpretation:

- Raw chat was not the serious comparator; scaffolded RAG was.
- Governance showed a bounded advantage in receipt discipline, weak or
  mismatched retrieval, semantic-boundary control, repair/fallback, and trace.
- Perfect curated scores were treated as suspicious, which led to blind,
  perturbed, RAG, adversarial, and ablation comparisons.
- Do not keep tuning adversarial v1/v2.
- Any future comparison must retain `scaffolded_rag` as the serious baseline.

Graduation evidence:

```text
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_LAB_GRADUATION_2026-06-30.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
```

### Generative governance / Mirus-before-Holden - promising research

The lab generated a clear-text governance state before model rendering:

```text
intent
evidence state
USER_SELF vs AETHER_SELF boundary
allowed and blocked claims
response spine
answerability
model-render-needed decision
review candidates
vectorizable public trace text
```

Evidence:

```text
expanded qwen2.5 governed path 24/24; model-only 8/24
expanded qwen3/no_think governed path 24/24; model-only 9/24
governance avoided six model calls in boundary/conflict cases
```

Interpretation:

- Governance-only can answer weak-evidence and conflict boundaries.
- A model remains useful for rich grounded synthesis.
- This supports "Mirus structures; Holden renders" as an architecture, not a
  consciousness claim.
- The spike is research evidence and is not a universal live response path.

### Critic-repair - narrow runtime slice

- Lab critic and governed repair passed the recorded small pack.
- A narrow abstract governance/epistemic contract is live.
- Do not generalize it to every response without a demonstrated failure.

### Governed learner and feedback ledger - graduated baseline

- Memory, Support, Reflection, Contradiction, and Evidence candidates can be
  surfaced from explicit trace metadata.
- The weighted feedback ledger is reviewed metadata, not neural learning.
- There are no automatic memory/support/reflection writes or silent policy
  changes.
- Reopen only for a concrete daily-use review problem.

### Belief map, learned scorer, J-lens, and coherence-decay work - parked

- These lanes retain experimental value and source material.
- They are not required for current product operation.
- Do not extract new Core schemas or revive them merely because files exist.

### Governed hosted read-only tool lab - contained, not product-enabled

- The Aether-owned broker validates typed requests against a fixed capability
  grant, hashes observations, and checks workspace state.
- The synthetic lab preserved zero writes and explicit observation citations.
- It does not grant ordinary Workbench tool access.

### Mirus semantic task-intake lab - completed no-ship, 2026-07-20

Question: can `qwen2.5:7b-instruct` find indirect task meaning while CRT holds
speaker, commitment, evidence, and authority boundaries?

Mechanism:

```text
deterministic baseline
-> model structured proposal
-> exact source receipt
-> deterministic speaker/modality/category checks
-> review-only contract
-> deterministic-first hybrid merge
```

Development pack:

```text
32 cases
baseline precision 1.0000, recall 0.2857
semantic precision 1.0000, recall 0.7143
hybrid precision 1.0000, recall 0.7619
```

First holdout initially failed with nine high-risk false candidates. After the
revealed failures drove speaker/modality hardening, the repaired pack reached
precision 1.0000 and recall 0.9167. That is post-reveal regression evidence.

Untouched second holdout:

```text
20 cases
semantic/hybrid precision 0.7143
semantic/hybrid recall 1.0000
false positives 4
high-risk false positives 3
authority-contract violations 0
```

Decision:

- Do not wire the semantic proposer into `create_app`, trace, Workbench, or the
  learner queue.
- Do not continue prompt tuning against these packs.
- The model found latent tasks, but speaker ownership and non-commitment remain
  unsafe.
- Review-only containment worked: even failed classification produced zero
  authority-contract violations.
- Reopen only with a stronger clause-aware speaker/modality mechanism or a
  separately trained boundary classifier, followed by a new untouched holdout.

Implementation and evidence:

```text
D:\AI_round2\aether-core\aether\sidecar\semantic_task_intake.py
D:\AI_round2\aether-core\scripts\semantic_task_intake_eval.py
D:\AI_round2\aether-core\tests\fixtures\semantic_task_intake_v0.json
D:\AI_round2\aether-core\tests\fixtures\semantic_task_intake_holdout_v1.json
D:\AI_round2\aether-core\tests\fixtures\semantic_task_intake_holdout_v2.json
D:\AI_round2\docs\plans\AETHER_MIRUS_SEMANTIC_TASK_INTAKE_LAB_2026-07-20.md
```

Latest focused regression for this lane: 131 tests passed.

## Current Git State

Snapshot taken 2026-07-20. Re-check before editing.

Root repository:

```text
path:   D:\AI_round2
branch: codex/repo-cleanup-archive
HEAD:   8b6417899 updates
dirty:
  M docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
  M docs/plans/AETHER_CURRENT_STATE.md
  M docs/plans/AETHER_UNIFIED_ROADMAP_2026-07-16.md
  ?? docs/plans/AETHER_MIRUS_SEMANTIC_TASK_INTAKE_LAB_2026-07-20.md
  ?? docs/plans/AETHER_CANONICAL_CONTINUITY_LOG_2026-07-20.md
```

Nested `aether-core` repository:

```text
path:   D:\AI_round2\aether-core
branch: master
HEAD:   ec49abb updates
dirty:
  M aether/sidecar/semantic_task_intake.py
  M tests/test_semantic_task_intake.py
  ?? tests/fixtures/semantic_task_intake_holdout_v1.json
  ?? tests/fixtures/semantic_task_intake_holdout_v2.json
```

Some generated result artifacts under `labs/.../results` are intentionally
ignored. Their existence is evidence support, not proof that they are committed.
Do not stage generated outputs blindly.

## Safety and Authority Invariants

These are not optional style preferences:

```text
No raw hidden chain-of-thought stored as truth.
No automatic profile-memory writes.
No automatic support-pattern imports.
No automatic reflection creation.
No automatic task authority from prose or model output.
No automatic workspace execution from continuity alignment.
No silent tool escalation.
No silent model switching.
No silent policy mutation.
No cross-profile evidence leakage.
No stale-revision acceptance.
Rejected and revoked state must remain behaviorally inert.
```

Allowed durable thinking/process trace:

```text
classification
retrieval query and source receipts
Mirus/governance packet
route and renderer selection
scaffold or response spine
allowed and blocked claims
verifier findings
repair/fallback decision
confidence and contradiction notes
review-only learning candidates
explicit review decisions
```

## Verification Commands

Always run root and nested checks separately.

Git:

```powershell
cd D:\AI_round2
git status --short
git diff --check
git -C aether-core status --short
git -C aether-core diff --check
```

Current semantic-intake and adjacent backend regression:

```powershell
cd D:\AI_round2\aether-core
python -m pytest tests\test_task_candidate_intake.py tests\test_semantic_task_intake.py tests\test_semantic_task_intake_eval.py tests\test_sidecar_consolidation.py tests\test_sidecar_character_answer.py -q
```

Workbench:

```powershell
cd D:\AI_round2\workbench
npm test
npm run build
```

Fast runtime checks:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-WebRequest http://127.0.0.1:5175/ -UseBasicParsing
```

Rendered frontend work requires actual browser verification, not tests alone:

- nonblank page;
- expected trace/review content;
- no console errors or warning regressions;
- no error overlay;
- no incoherent overlap or horizontal overflow;
- persistence after page reload and sidecar restart where applicable.

## Roadmap Position and User Disposition

Canonical roadmap state:

```text
bounded governed continuity: complete with explicit review limits
desktop distribution readiness: next product lane
external pilots/grants/company structure: gated
```

Current user disposition:

```text
Nick passed on desktop distribution for this round.
Nick authorized the Mirus semantic-intake lab.
That lab is complete and failed its live-integration gate.
Do not silently begin distribution or wire the failed proposer.
```

When work resumes, get or infer a clear selection among:

1. **Product:** resume desktop distribution readiness, including product
   metadata, signing readiness, Ollama/model prerequisite onboarding,
   deliberate update/rollback, and another-user install proof.
2. **Research:** reopen semantic intake only with a materially stronger
   clause-aware speaker/modality mechanism and a new untouched holdout.
3. **Dogfood:** address a concrete daily Aether/Workbench failure and add the
   smallest regression that proves the system-level repair.

Do not substitute random lab expansion for a selected lane.

## Funding and Novelty Boundary

The project has credible research and product evidence, but no formal novelty
or prior-art determination has been completed. Defensible differentiators are
the composition and enforcement of:

- source-bounded semantic packets;
- reviewed memory and task authority;
- contradiction-aware release;
- deterministic/model hybrid routing;
- durable public governance trace;
- explicit repair/fallback and non-effect receipts;
- local-first operation with hosted escalation kept downstream of Aether.

For grants or business material, claim tested reliability, inspectability,
privacy, and governance mechanisms. Do not claim AGI, consciousness, universal
truthfulness, frontier-model equivalence, or proven legal novelty.

## Clean Restart Prompt

```text
We are continuing Aether in D:\AI_round2.

Read first:
1. docs/plans/AETHER_CANONICAL_CONTINUITY_LOG_2026-07-20.md
2. docs/plans/AETHER_UNIFIED_ROADMAP_2026-07-16.md
3. docs/plans/AETHER_CURRENT_STATE.md
4. docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md

Important repository state:
- D:\AI_round2 is the root repo on codex/repo-cleanup-archive.
- D:\AI_round2\aether-core is a separate nested repo on master.
- Both may be dirty. Do not reset, clean, or revert unfamiliar changes.
- Check both Git statuses before editing.

Current product state:
- The bounded cross-conversation continuity and reviewed task-authority gate is
  complete.
- Workbench can review and explicitly promote/reject deterministic Mirus task
  candidates with durable receipts.
- Automatic memory, task authority, tools, execution, model switching, and
  policy mutation remain blocked.

Latest research state:
- The qwen2.5 semantic task proposer improved recall substantially.
- The untouched v2 holdout failed with precision 0.7143 and three high-risk
  false candidates.
- It is not wired into live Aether, trace, Workbench, or the learner queue.
- Do not prompt-tune the revealed packs or integrate the proposer.

Nick passed on desktop distribution for the previous round. Before beginning a
new lane, confirm whether to resume distribution, investigate a stronger
clause-aware speaker/modality mechanism with a new holdout, or repair a concrete
daily-use regression.

Do not store hidden chain-of-thought as truth. Preserve structured public CRT
trace only: classification, receipts, Mirus packet, route, scaffold, verifier,
repair/fallback, confidence, contradiction notes, and review candidates.
```

## Final Continuity Statement

Mirus and Holden are no longer only names for hypothetical components. Their
bounded forms exist: deterministic and review-only intake structures meaning,
and replaceable models render governed context. The latest semantic-intake lab
also showed the remaining gap clearly: a small model can notice latent tasks,
but it cannot yet be trusted to decide whose obligation a sentence contains or
whether the sentence creates a real commitment. Aether's governance layer
successfully prevented those mistakes from becoming authority. The next agent
should preserve that distinction rather than chasing a prettier demo score.
