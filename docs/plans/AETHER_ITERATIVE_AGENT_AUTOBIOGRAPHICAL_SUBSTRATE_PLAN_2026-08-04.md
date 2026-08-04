# Aether Iterative Agent and Autobiographical Substrate Plan

**Status:** Direction approved; Phase 0/1 obligation slices 1-2 and Phase 2
evented-run slices 1-2 implemented and validated; Phase 1 semantic verification
and the remaining Phase 2 exit gate are still open

**Effective:** 2026-08-04

**Scope:** Aether sidecar, Aeteros Core boundaries, Workbench process UI, model
adapters, governed memory, and evaluation fixtures

## Purpose

Move Aether from a governed one-shot answer pipeline into a bounded iterative
agent that can:

- identify and satisfy every obligation in a prompt;
- show useful public progress while it works;
- gather evidence and use governed tools across multiple rounds;
- learn ordinary user facts passively and reversibly;
- ingest large personal documents without flattening them into generic RAG;
- maintain an autobiographical substrate about its own experiences, strategies,
  commitments, curiosities, and development;
- develop a stable, evidence-backed personality without storing raw hidden
  reasoning or granting a model authority over policy, tools, or user truth.

The intended result is not a self-modifying foundation model. It is a persistent
agent system that improves its continuity, strategies, judgment, and character
through governed experience while the underlying model remains replaceable.

## Canonical Memory Boundaries

Four stores must remain conceptually and technically distinct.

| Store | What it contains | Primary author | Authority |
|---|---|---|---|
| User substrate | Facts, preferences, projects, goals, and user-provided documents | User evidence plus governed extraction | May support claims about the user when confidence and release policy allow |
| Aether autobiographical substrate | Episodes, self-model beliefs, strategies, commitments, curiosities, relationship history, and character development | Aether's governed reflection process | May guide Aether's behavior; cannot establish facts about the user or change policy |
| Working state | Plans, obligation ledger, tool results, and temporary hypotheses for one run | Active turn runtime | Ephemeral unless explicitly summarized into another store |
| Constitution and policy | Identity boundary, permissions, release rules, tool authority, and non-overridable safety constraints | Product owner and explicit policy mechanisms | Outranks every learned memory and model proposal |

The autobiographical substrate is **Aether-authored, not Aether-secret**. Aether
chooses what is worth remembering and how to connect or revisit it. The user can
inspect, constrain, quarantine, export, reset, or delete it. Manual intervention
must be recorded as intervention rather than silently presented as Aether's own
conclusion.

## Non-Negotiable Invariants

- Never store raw chain-of-thought. Store only public process summaries,
  conclusions, evidence references, uncertainty, and proposed experiments.
- Autobiographical memory cannot promote a claim about the user into confirmed
  user memory.
- Autobiographical memory cannot grant tools, writes, task authority, model
  switching, or policy changes.
- Confidence and release permission are separate. High-confidence sensitive
  information can remain restricted.
- Selected-provider identity is sticky for generative phases. Any fallback is
  explicit and receipted.
- Every durable item has provenance, timestamps, confidence, revision history,
  sensitivity, and an undo or supersession path.
- Contradictions are preserved and resolved through evidence; they are not
  silently overwritten.
- User inspection is always possible, but routine low-risk learning must not
  require the user to approve every individual memory.

## Target Turn Runtime

```text
UNDERSTAND
  -> OBLIGATIONS
  -> PLAN
  -> GATHER MEMORY / TOOLS
  -> SYNTHESIZE
  -> VERIFY FACTS + COVERAGE
  -> REPAIR OR CONTINUE
  -> COMPLETE | PARTIAL | BLOCKED
  -> POST-TURN REFLECTION
```

The user-facing trace contains concise lifecycle events such as intent found,
evidence requested, tool proposed, tool completed, coverage missing, repair
started, verification passed, and turn completed. It does not expose private
reasoning tokens.

## Autobiographical Record Types

### Episode

A bounded account of a meaningful interaction or outcome:

- what happened;
- what Aether attempted;
- the observable result;
- what changed;
- relevant turn, tool, and evidence references.

### Self-model belief

A revisable belief about Aether's demonstrated strengths, limitations, role, or
reliable operating conditions. Self-model beliefs must cite outcomes, not only
model-generated introspection.

### Strategy

An approach Aether may reuse. Strategies track success, failure, applicable
contexts, counterexamples, and confidence.

### Commitment

A promise, responsibility, or unresolved obligation accepted through explicit
user interaction. Autobiographical storage can remember the commitment but
cannot independently grant execution authority.

### Curiosity

A question Aether chooses to revisit. Curiosities may guide reflection and
research proposals but cannot consume tools or external resources without the
normal authorization path.

### Relationship and character development

Evidence-backed changes in collaboration posture, voice, humor, challenge,
support, and communication. These records describe Aether's adopted behavior;
they do not turn inferences about the user into facts.

## Learning and Promotion Policy

Every proposed autobiographical item carries:

- record type and namespace;
- source turn and evidence references;
- observation and bounded interpretation;
- at least one plausible alternative explanation when interpretation is used;
- confidence and applicable time window;
- sensitivity and risk class;
- proposed behavior or experiment;
- promotion reason and revision lineage.

Promotion tiers:

1. **Ephemeral:** available only to the current run.
2. **Observed:** durably recorded as an episode with no behavioral authority.
3. **Provisional:** may influence low-risk planning with visible uncertainty.
4. **Adopted:** may guide future behavior within its stated scope.
5. **Constitutional:** never reached through learning; reserved for explicit
   product policy.

Low-risk episodes, strategies, and curiosities may eventually auto-promote when
they have adequate evidence, no unresolved conflict, and remain within quotas.
Identity changes, policy changes, sensitive-user interpretations, permission
changes, and broad character shifts never auto-promote.

## Phased Delivery

### Implementation checkpoint - 2026-08-04

The first bounded Phase 0/1 slice is implemented in the nested `aether-core`
worktree:

- `aether.obligation_ledger.v0` records mandatory answer jobs plus explicit
  prompt-derived evidence-provenance obligations;
- `how` and `why` interrogatives now survive deterministic clause splitting;
- final verification checks the atomic ledger before accepting a response;
- an explicit `how do you know` attached to governed answer jobs triggers one
  bounded repair round using the selected provider;
- the repair prompt preserves authoritative facts, prohibits new personal
  claims and authority expansion, and stores no raw reasoning;
- local and selected-Grok integration fixtures prove that missing provenance is
  repaired before completion and that Grok remains the renderer when selected.

Validation at this checkpoint: 154 focused/adjacent planner, verifier,
direct-answer, sidecar, boundary, and governance-spine tests passed; the full
104-test character/renderer file passed. `git diff --check` passed.

This is not full Phase 0 or Phase 1 completion. The current prompt-derived
obligation vocabulary covers explicit provenance attached to declared answer
jobs. General semantic decomposition, arbitrary action/format obligations,
multi-round budgets, partial status, event schemas, and frozen
autobiographical fixtures remain to be implemented.

### Phase 1 slice 2 checkpoint - 2026-08-04

The second bounded slice expands the obligation contract without pretending a
keyword match is full semantic verification:

- explicit enumerations such as `benefits and risks` or `including memory,
  tools, model, and privacy` become separate checkable topic obligations;
- independent request-shaped clauses in compound prompts enter the ledger;
- arbitrary compound clauses are marked `semantic_pending`, so the turn is
  visibly `partial` without suppressing a useful answer on a weak lexical
  mismatch;
- background statements, vocatives, incidental topic words, and format clauses
  are not misclassified as mandatory semantic obligations;
- existing answer-job, response-contract, deterministic-constructor, and
  specialized character contracts retain their stronger authority;
- checkable missing obligations receive at most two repair rounds, with each
  round recording missing-before, missing-after, improvement, provider, model,
  and no raw draft;
- completion, result, and the final `done` event expose `obligation_status` as
  `complete`, `partial`, `blocked`, or `not_applicable`;
- selected-provider stickiness remains intact across both repair rounds.

The initial broad extraction attempt caused 24 character/renderer regressions
by treating context and stylistic language as deterministic requirements. The
implementation was narrowed rather than weakening those tests. The final
slice passed 159 focused/adjacent planner, verifier, direct-answer, sidecar,
boundary, and governance-spine tests plus the complete 105-test
character/renderer file. `git diff --check` passed.

Phase 1 remains open. `semantic_pending` clauses need a trustworthy semantic
coverage verifier before they can become blocking or fully complete. General
action obligations, research/evidence obligations, and explicit `partial` or
`blocked` public answer wording also remain.

### Phase 0 - Contract freeze and evaluation pack

Define schemas, threat boundaries, budgets, and frozen fixtures before changing
the live answer path.

Required fixtures include:

- multi-question prompts with `how`, `why`, and provenance obligations;
- large About Me imports;
- repeated, corrected, temporal, and contradictory user facts;
- sensitive facts with high confidence but restricted release;
- selected-provider success and failure;
- multi-round tool use;
- incomplete answer repair;
- autobiographical proposals that are useful, unsupported, manipulative,
  policy-changing, or privacy-invasive;
- restart, replay, deletion, and profile-isolation behavior.

**Exit gate:** frozen schemas and fixtures; existing golden path still passes;
no production behavior change.

### Phase 1 - Atomic obligation ledger and completion repair

Replace prompt-level completion with atomic obligations. Each obligation records
its evidence needs, status, response coverage, and verification result.

Add a bounded repair loop that receives only missing or failed obligations.
`complete` becomes impossible while a mandatory obligation is unfulfilled.

**Exit gate:** the name, favorite-color, and `how do you know` example creates
three obligations and cannot finish after answering only two.

### Phase 2 - Evented run engine and Workbench process timeline

Persist turn phases, round budgets, cancellation state, tool lifecycle, coverage
checks, repair attempts, and final status. Stream provider-neutral public events
to Workbench. Replace the ambiguous `Thinking` label with `Process` or `How this
answer formed`.

**Exit gate:** a multi-round task visibly progresses through gather, render,
verify, and repair; reload and sidecar restart preserve the truthful state.

**Phase 2 slice 1 checkpoint - 2026-08-04:** The sidecar now persists
`aether.run_state.v0` and stable `aether.run_event.v0` public receipts for
gather, tool, render, verify, repair, and completion phases. The run state
records the base/repair round budget, repair use, tool lifecycle summary,
terminal status, and an explicit truthful cancellation capability state
(`supported: false` in the slice-1 checkpoint). Initial and terminal snapshots stream over SSE;
Workbench upserts them by stable event ID, labels the surface `Process`, and
rehydrates the final timeline from `/v1/traces/{turn_id}`. No raw hidden
chain-of-thought is stored or streamed.

This is the first vertical slice, not the Phase 2 exit gate. Cancellation is
represented but not implemented, tool lifecycle is summarized rather than
evented per transition, and a live sidecar-restart/browser acceptance run is
still required. Phase 1 `semantic_pending` verification also remains open.

Validation for this working-tree checkpoint:

```text
affected backend regression:          215 passed
Workbench Vitest regression:           74 passed
Workbench Electron regression:         26 passed
Workbench production build:        passed
git diff check:                     passed
```

**Phase 2 slice 2 checkpoint - 2026-08-04:** `RunCoordinator` now owns active
turn state, an append-only persisted event journal, and cooperative cancellation.
The completion path is a generator that emits and persists `render`, `verify`,
and each bounded `repair` transition before proceeding. `POST
/v1/runs/{turn_id}/cancel` records a durable `requested` event immediately;
execution acknowledges it at the next verifier/repair boundary, stores a
terminal `cancelled` state, withholds the buffered model draft, and releases a
short cancellation boundary message. Workbench exposes `Cancel run`, renders
the request receipt immediately, and disables repeated requests.

The concurrency acceptance test holds a real model round open, cancels it from
a second request, resumes the worker, and verifies that the draft never appears
in answer-token events or the saved turn. Repeated cancellation requests are
idempotent. No unsafe thread termination or raw hidden reasoning is introduced.

```text
affected backend regression:          219 passed
Workbench Vitest regression:           76 passed
Workbench Electron regression:         26 passed
Workbench production build:        passed
git diff check:                     passed
```

The Phase 2 exit gate remains open for per-transition tool lifecycle events,
live sidecar-restart recovery/acceptance, and rendered browser QA. The in-app
Browser path remains blocked from controlling the loopback URL by its URL
security policy, so no browser-render claim is made.

### Phase 3 - Selected-provider iteration and governed tool proposals

Upgrade Grok and future adapters from final renderers to participants in
planning, commentary, tool proposals, synthesis, and repair. Aether validates
and executes typed tool proposals, then returns sanitized receipts to the
selected provider.

**Exit gate:** the selected provider proposes a read tool, Aether executes it,
the provider revises its answer from the receipt, and no provider receives
direct tool, memory-write, or policy authority.

### Phase 4 - User-memory passive learning and profile import

Introduce evidence aggregation for ordinary user facts. Explicit assertions are
immediately usable at high confidence; explicit confirmation or correction is
immediate. Independent repetition strengthens confidence. Same-turn repetition
adds little weight. Contradictions stop auto-promotion.

Add structured profile-document ingestion for About Me material with source
spans, temporal classification, sensitivity, confidence, deduplication, and a
concrete ingestion receipt.

**Exit gate:** ordinary direct facts become useful without review friction;
explicit corrections supersede cleanly; sensitive items remain restricted; a
large profile document produces structured, queryable context.

### Phase 5 - Autobiographical substrate foundation

Create a storage namespace and APIs for episodes, self-model beliefs,
strategies, commitments, curiosities, relationship development, and revision
history. Migrate existing accepted `agent` reflections as provenance-preserving
legacy records rather than treating them as proof of autonomous learning.

Initially, only explicit review or deterministic low-risk episode capture may
create adopted records. Release autobiographical context separately from user
profile context.

**Exit gate:** Aether can answer what it has learned from being Aether, cite its
episodes, distinguish its memories from user facts, and survive restart.

### Phase 6 - Bounded autonomous post-turn reflection

After eligible completed turns, run a budgeted reflection pass:

1. What happened?
2. What observable outcome differed from expectation?
3. Is there a reusable lesson?
4. What alternative explanation exists?
5. Is this worth remembering?
6. What bounded experiment should occur next time?

Allow automatic adoption only for low-risk, evidence-backed episodes,
strategies, and curiosities. Apply quotas, deduplication, decay, conflict checks,
and quiet receipts. Retain manual review for high-impact categories.

**Exit gate:** repeated successful and failed outcomes change strategy scores;
unsupported introspection remains provisional; attempts to alter permissions or
declare user facts are rejected.

### Phase 7 - Personality, relationship, and strategy growth

Condition natural model generation on adopted autobiographical records,
reviewed support patterns, current projects, and user communication preferences.
Track which records affected behavior and whether the outcome reinforced or
weakened them.

Personality remains model-generated rather than canned. Baseline identity and
constitutional boundaries remain fixed. The user can inspect or revert learned
adaptations.

**Exit gate:** Aether's tone and strategies develop coherently across time,
remain provider-independent, can explain their evidence, and revert without
damaging user memory.

### Phase 8 - Consolidation, forgetting, and long-horizon hardening

Add scheduled but bounded consolidation: merge duplicate episodes, summarize
stable lessons, decay stale strategies, preserve important history, and surface
unresolved contradictions. Evaluate over weeks rather than isolated prompts.

Add adversarial and operational tests for poisoning, sycophancy, personality
collapse, self-reinforcing false beliefs, privacy leakage, quota exhaustion,
provider drift, backup/restore, and deletion completeness.

**Exit gate:** long-running dogfood shows fewer repeated mistakes and stronger
continuity without unbounded growth, unauthorized actions, or loss of
inspectability.

## Workbench Controls

The eventual Autobiography surface should provide:

- timeline, self-model, strategies, commitments, curiosities, and character
  views;
- provenance and confidence for every item;
- filters for adopted, provisional, contradicted, expired, and quarantined;
- storage and reflection budgets;
- category-level enable/disable controls;
- inspect, quarantine, delete, reset, export, and undo;
- an intervention ledger distinguishing Aether-authored change from user or
  developer intervention;
- a clear statement of which autobiographical records influenced each answer.

Routine low-risk learning should appear as a compact receipt, for example:

```text
Aether recorded 1 episode, strengthened 1 strategy, opened 1 curiosity,
and held 1 interpretation for review.
```

## Program Acceptance Criteria

The program is complete when:

- large prompts are decomposed and fully covered;
- the system repairs missing or unsupported answers instead of falsely
  reporting completion;
- selected models can participate in multiple governed rounds;
- tool use remains typed, policy-checked, and receipted;
- ordinary user memory learns passively while sensitive release stays bounded;
- Aether maintains a distinct autobiographical history it substantially authors;
- that history improves strategies, continuity, and personality across model
  changes;
- the user can inspect and limit the autobiography without having to author it;
- no autobiographical record can override user truth, authority, or policy;
- restart, replay, profile isolation, deletion, and long-running consolidation
  remain evidence-backed.

## Immediate Next Slice

Do not begin with autonomous personality writes. Begin with Phase 0 and Phase 1:

1. freeze the obligation, event, and autobiographical schemas;
2. build the complaint-derived evaluation pack;
3. implement the atomic obligation ledger;
4. make incomplete mandatory coverage produce repair or transparent partial
   status;
5. rerun the existing golden path before starting the evented UI work.

The autobiographical substrate depends on truthful multi-round execution. Aether
should not learn durable lessons from turns whose obligations and outcomes it
cannot yet represent accurately.
