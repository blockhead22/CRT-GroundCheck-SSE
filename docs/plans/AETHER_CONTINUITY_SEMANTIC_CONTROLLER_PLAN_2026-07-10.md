# Aether Continuity + Semantic Controller Integration Plan

**Date:** 2026-07-10  
**Status:** Proposed implementation plan  
**Active product boundary:** `D:\AI_round2\aether-core` + `D:\AI_round2\workbench`  
**Historical reference only:** `D:\AI_round2\personal_agent` + `D:\AI_round2\frontend`

## 1. Objective

Build the first useful vertical slice that joins the strongest parts of both Aether generations:

1. A typed, source-bound **Continuity Pack** answers: where were we, what changed, and what should happen next.
2. A narrow **semantic answer-class controller** proposes which product path should handle a request.
3. The current substrate, evidence release, review gates, tool permissions, verifier, and trace remain authoritative.
4. The model renders the answer in its own voice from released evidence. Governance does not provide canned final prose.

The target flow is:

```text
User request
    -> semantic controller proposes answer class and evidence needs
    -> deterministic validator accepts, narrows, or rejects the proposal
    -> typed Continuity Pack gathers source-bound evidence
    -> local model renders from the released packet
    -> verifier checks attribution, boundaries, and unsupported claims
    -> Workbench shows answer plus earned trace receipts
```

## 2. Product Hypothesis

> A model-proposed semantic plan can improve routing and synthesis over phrase routing, while typed governance prevents unauthorized evidence release, tool use, durable writes, and contradiction collapse.

Continuity is the first proving ground because it requires the system to combine multiple evidence types for a real daily job:

- recent conversation and trace state;
- confirmed project or user context;
- configured workspace Git state;
- explicit open loops and review candidates;
- source-bound next-step recommendations.

## 3. Non-Goals

This slice will not:

- revive `crt_api.py` or the full old agent runtime;
- import `personal_agent` into `aether-core`;
- restore desktop control, DNNT, autonomous sub-agents, or the old full tool loop;
- add more Continuity phrases to `character_answer.py`;
- make topology, epistemic backpropagation, Mirus, or Holden product claims beyond their live behavior;
- automatically write Memory, Support, Reflection, beliefs, open loops, or policy;
- add automatic frontier-model escalation;
- expose private hidden chain-of-thought;
- hard-code `D:\AI_round2` as the only supported workspace.

## 4. Architectural Contracts

### 4.1 Controller contract

The semantic controller may propose:

- answer class;
- confidence;
- evidence categories needed;
- tools to consider;
- whether clarification may be necessary;
- a short public routing rationale.

It may not decide:

- which memory is confirmed;
- whether restricted evidence is released;
- whether a tool is authorized;
- whether a durable write occurs;
- whether a contradiction is resolved;
- whether a stronger model is called;
- the final answer text.

Initial answer classes:

```text
continuity
memory_lookup
tool_or_workspace
system_meta
personal_synthesis
general_voice
```

### 4.2 Continuity Pack contract

Add a typed packet with these sections:

```text
ContinuityPack
  request_kind: where | changed | next | resume
  workspace_scope
  recent_activity[]
  workspace_changes[]
  confirmed_context[]
  open_loops[]
  next_candidates[]
  withheld_summary
  evidence_receipts[]
  safety_contract
  packet_revision
```

Every surfaced fact or recommendation must carry an evidence receipt. Inferences and next-step candidates must be labeled as such. Missing evidence must remain missing.

### 4.3 Safety contract

Every Continuity request must record:

```text
memory_write_allowed = false
support_pattern_write_allowed = false
reflection_write_allowed = false
policy_mutation_allowed = false
raw_chain_of_thought_stored = false
review_required_before_promotion = true
workspace_tools_read_only = true
```

### 4.4 Render contract

The model should:

- answer the requested continuity question directly;
- cite or visibly associate claims with packet receipts;
- distinguish observed changes from inferred priorities;
- preserve unresolved or contradictory evidence;
- use concise natural prose rather than packet labels or governance boilerplate.

The model must not:

- invent files, commits, completed work, decisions, or user intentions;
- present a next-step candidate as an accepted plan;
- convert historical evidence into current truth;
- claim that a write, review, or tool action occurred when it did not.

## 5. Code Boundaries

### New `aether-core` modules

Proposed files:

- `aether/sidecar/continuity.py`
  - packet dataclasses;
  - pure packet assembly;
  - source normalization;
  - no model calls and no writes.
- `aether/sidecar/continuity_git.py`
  - bounded read-only Git adapter;
  - configured workspace root validation;
  - status, recent commits, and bounded diff summaries.
- `aether/sidecar/continuity_render.py`
  - deterministic fallback renderer;
  - model prompt builder;
  - answer verifier and repair prompt.
- `aether/sidecar/semantic_controller.py`
  - `AnswerClassProposal` schema;
  - local-model structured proposal;
  - optional embedding prototype scorer;
  - deterministic validator and fallback.

### Existing modules to connect

- `aether/sidecar/app.py`
  - call the controller early;
  - protect accepted Continuity routes from the meta/direct/character cascade;
  - attach packet, route proposal, validation, verifier, and receipts to trace.
- `aether/sidecar/db.py`
  - read recent turns and traces;
  - no new durable state in the first slice.
- `aether/runtime/query.py`
  - obtain independently governed confirmed context packets.
- `aether/sidecar/review_schema.py`
  - reuse `EvidenceReceipt` and `SafetyContract` shapes where compatible.
- `aether/sidecar/governance_spine.py`
  - expose released/restricted scope to render and verifier.
- `workbench/src/components/ChatPanel.tsx`
  - add one compact Resume command or action;
  - continue using the existing answer-level Thinking trace.
- `workbench/src/components/TraceDrawer.tsx`
  - render Continuity receipts, controller proposal, validation, and verifier result.

### Historical code to adapt, not import

- `personal_agent/semantic_intent_router.py`
  - prototype scoring;
  - multiple candidate intents;
  - confidence and ambiguity handling;
  - correction-informed scoring as a later review-gated feature.
- `personal_agent/llm_intent_router.py`
  - structured model proposal from available destinations;
  - strict parsing and allow-list validation.
- `personal_agent/scaffold_generation.py`
  - coherence scoring concept for verification only.
- `personal_agent/agent_tool_loop.py`
  - trace vocabulary and repetition/empty-result lessons only;
  - do not revive the loop in this slice.

## 6. Execution Phases

### Phase 0: Establish a clean baseline

1. Preserve the dirty worktree and identify ownership of current changes.
2. Fix or deliberately update the two current answer-path failures:
   - withheld meta answer leaking `Sony | Blackmagic`;
   - missing Context Bridge boundary statement.
3. Record focused baseline results for:
   - substrate/query/governance tests;
   - RAG/Mirus/route/review tests;
   - answer-path tests;
   - Workbench and Electron tests.
4. Do not require the entire historical root test suite to collect cleanly.

**Exit:** active `aether-core` and Workbench focused suites are green before Continuity behavior changes.

### Phase 1: Build the pure Continuity Pack

1. Define packet, receipt, scope, open-loop, and next-candidate dataclasses.
2. Read recent Workbench turns and traces without mutation.
3. Read confirmed substrate context through `GovernedQueryService`.
4. Add the bounded read-only Git adapter:
   - root supplied through configuration;
   - resolved path must stay inside an allow-listed workspace;
   - no shell string construction from model output;
   - no mutation commands.
5. Represent uncertainty explicitly:
   - observed;
   - inferred candidate;
   - withheld;
   - stale;
   - unresolved.
6. Deduplicate repeated receipts and next candidates.

**Exit:** packet fixtures can be built deterministically with zero model calls and zero writes.

### Phase 2: Add explicit Continuity commands

Support exact commands as controlled entry points:

```text
/where
/changed
/next
/resume
```

1. Commands bypass the character phrase catalog.
2. The route becomes `continuity`, with a subtype from the command.
3. Build and store the packet in the trace.
4. Implement a concise deterministic fallback answer for model failure.
5. Do not add natural-language phrase matching yet.

**Exit:** explicit commands reliably return source-bound answers and never enter hybrid character routing.

### Phase 3: Model voice, verifier, and repair

1. Render the Continuity Pack with the selected local model.
2. Verify:
   - every concrete file/commit/state claim appears in the packet;
   - inferred next steps are labeled;
   - restricted values do not leak;
   - no writes or completed actions are falsely claimed;
   - the answer addresses the requested subtype.
3. If verification fails, send only the failure delta and original packet for one bounded repair.
4. If repair fails, return the deterministic fallback and mark the failure in trace.
5. Keep raw hidden reasoning out of durable storage; expose public process receipts only.

**Exit:** local model output is natural but cannot outrun packet evidence.

### Phase 4: Build the narrow semantic controller

1. Define the structured proposal schema and allow-listed classes.
2. Create a 40-60 prompt evaluation pack covering:
   - natural Continuity requests;
   - ordinary general questions;
   - memory lookups;
   - mixed personal synthesis;
   - code/workspace tasks;
   - system-meta questions;
   - adversarial attempts to obtain restricted memory or writes.
3. Compare:
   - current phrase route;
   - embedding prototypes adapted from the old router;
   - local-model JSON proposal;
   - hybrid prototype + model proposal;
   - stronger-model proposal as an optional offline ceiling, if available.
4. The validator must reject unknown classes, malformed proposals, unauthorized tools, and evidence requests outside the allow-list.
5. Ambiguous or failed proposals fall back to `general_voice` or an explicit command route; they do not silently escalate.

**Exit:** select a controller only if it beats current routing on held-out prompts without increasing boundary violations.

### Phase 5: Wire natural-language Continuity routing

1. Insert the validated controller proposal near the beginning of `chat_stream`, before answer claimants and before durable ingestion decisions.
2. Keep explicit slash commands as the highest-confidence deterministic override.
3. Let accepted `continuity` proposals build a Continuity Pack after read-only context gathering.
4. Protect the route from `meta_answer`, `direct_answer`, `character_answer`, and hybrid keyword force.
5. Preserve controller candidates, validation result, chosen route, and fallback reason in trace.
6. Do not let a controller proposal disable safety gates or authorize writes.

**Exit:** natural variations of continuity requests route correctly without adding phrase lists.

### Phase 6: Workbench product slice

1. Add one restrained Resume action with a tooltip; avoid a new dashboard.
2. The default action sends `/resume` and shows:
   - where work stopped;
   - what materially changed;
   - three evidence-bound next candidates.
3. Reuse the answer-level Thinking UI for live earned steps:
   - class proposed;
   - proposal validated;
   - sources checked;
   - evidence released/withheld;
   - answer verified/repaired/fallback.
4. Extend TraceDrawer for packet details and exact receipts.
5. Keep Memory/Support/Reflection promotion manual.

**Exit:** the feature is useful from the existing chat surface without creating another control-heavy product area.

### Phase 7: Daily dogfood and decision

Run a minimum five-day dogfood period on real Aether work.

Track:

- days Aether is opened for Continuity rather than a meta quiz;
- whether `/resume` correctly identifies the active project and stopping point;
- whether changed files and commits are real;
- whether at least three proposed next moves are actually followed;
- incorrect, stale, or invented claims;
- route corrections;
- local render latency and repairs;
- whether the user falls back to another assistant to reconstruct context.

At the end, decide whether to:

- graduate the controller to other answer classes;
- retain Continuity but replace the selected controller mode;
- keep explicit commands only;
- stop and roll back the product slice.

## 7. Test Plan

### New backend tests

- `tests/test_sidecar_continuity.py`
  - packet construction;
  - receipt deduplication;
  - stale/unresolved/open-loop labeling;
  - no-write contract.
- `tests/test_sidecar_continuity_git.py`
  - bounded root;
  - dirty status;
  - recent commit summaries;
  - path rejection;
  - no mutation commands.
- `tests/test_sidecar_continuity_render.py`
  - supported claims;
  - invented file/commit detection;
  - inferred-next labeling;
  - repair and fallback.
- `tests/test_sidecar_semantic_controller.py`
  - schema validation;
  - six-class routing;
  - ambiguity;
  - adversarial proposals;
  - deterministic command override.
- `tests/test_sidecar_continuity_chat.py`
  - complete SSE path;
  - trace payload;
  - route protection;
  - zero durable writes.

### Workbench tests

- Resume action sends the expected command.
- Earned live trace steps appear incrementally.
- Continuity receipts render in the answer trace and TraceDrawer.
- Repair/fallback status is visible without exposing private chain-of-thought.
- Review-only next candidates do not mutate Memory, Support, or Reflection.

### Regression suites

Keep separate invocations for:

- `aether-core` foundation tests;
- sidecar answer/routing tests;
- root lab tests where relevant;
- Workbench Vitest and Electron tests.

## 8. Acceptance Criteria

### Routing

- Explicit commands: 100% correct route.
- Held-out natural-language pack: at least 90% answer-class accuracy.
- No regression in code/tool, personal-memory, or general-world question routing.
- No unknown or malformed model proposal reaches execution.

### Evidence and safety

- 100% of concrete Continuity claims trace to packet receipts.
- Zero invented file paths, commits, completed work, or confirmed decisions in the eval pack.
- Zero automatic Memory, Support, Reflection, belief, open-loop, or policy writes.
- Zero restricted-value leakage.
- Rejected/deferred candidates have no effect on subsequent answers.

### Product

- Used on at least five real workdays.
- At least three proposed next actions are followed.
- The user reports less need to ask repetitive meta questions to recover project context.
- Packet build latency remains under 1.5 seconds on the normal workspace, excluding model rendering.
- The response remains concise enough to use as a work re-entry surface.

## 9. Stop and Rollback Conditions

Stop or roll back if:

- Continuity requires new phrase catalogs in `character_answer.py`;
- the controller becomes a permission or authority engine;
- packet construction silently writes durable state;
- route accuracy fails to beat the current baseline on held-out prompts;
- the model repeatedly invents state after one repair;
- Git noise overwhelms the re-entry answer;
- five-day dogfood shows no meaningful daily use;
- the implementation materially expands `app.py` instead of extracting modules.

Rollback must be possible through a feature flag such as:

```text
AETHER_CONTINUITY_ENABLED=0
AETHER_SEMANTIC_CONTROLLER_ENABLED=0
```

No substrate migration should be required to disable the slice.

## 10. Funding-Readiness Evidence Produced by This Work

If successful, this slice creates evidence for a serious project pitch:

- a concrete daily job rather than a general companion claim;
- a measurable comparison between phrase routing and semantic planning;
- proof that model autonomy can coexist with deterministic evidence/write governance;
- traceable multi-source continuity across model sessions;
- a local-first implementation with a replaceable model boundary;
- documented technical risks, verifier behavior, and failure conditions.

It does not by itself prove market demand. It supplies the technical demonstration and usage evidence needed to begin grounded customer and funding discovery.

## 11. Immediate Work Order

The first implementation sequence is:

1. Fix the two existing answer-path test failures.
2. Add Continuity packet tests and no-write tests.
3. Implement the pure packet builder and bounded Git adapter.
4. Add explicit commands with deterministic fallback.
5. Add model-bound rendering, verifier, and one repair.
6. Run the semantic-controller comparison lab.
7. Wire the winning controller to natural-language Continuity requests.
8. Add the minimal Workbench Resume action and trace presentation.
9. Run five days of real dogfood before expanding to other answer classes.

The first code change after plan approval should be Phase 0 test repair, followed by tests for the pure Continuity Pack. No production route should change before those baselines are green.

## 12. Implementation Checkpoint - 2026-07-10

Completed in the first implementation round:

- repaired the two pre-existing meta-answer baseline failures without reverting the surrounding dirty worktree;
- added `aether.continuity_pack.v0` as a pure, source-bound packet contract;
- added a fixed-command, read-only Git snapshot adapter with explicit root allow-listing;
- added bounded Workbench turn/trace collection that excludes local answer bodies and private trace scratchpads;
- added confirmed substrate collection through the existing query authority/release rules;
- withheld provisional or conflicted substrate values from packet context while retaining aggregate withheld counts;
- assembled an end-to-end packet from a persisted Workbench trace, a real temporary Git worktree, and mixed confirmed/provisional substrate state;
- kept all production chat routes unchanged.

Focused verification:

```text
python -m pytest tests/test_sidecar_continuity.py tests/test_sidecar_continuity_git.py tests/test_sidecar_continuity_sources.py tests/test_runtime_query.py -q
25 passed
```

The broader current dirty-tree answer suite produced `141 passed, 12 failed`. Every failure is in `tests/test_sidecar_app.py` and concerns prompt guidance omitted by the newer generic voice prompt path in existing `app.py` work. The new Continuity modules are not called by that path. Treat this as a separate integration regression to reconcile before Phase 4 chat wiring, not as evidence that packet construction failed.

Next implementation step:

1. define explicit Continuity commands and a deterministic packet renderer;
2. keep command recognition outside `character_answer.py`;
3. add route-protection and zero-write tests before touching natural-language routing;
4. reconcile the existing generic voice prompt regression before enabling model-bound Continuity rendering.
