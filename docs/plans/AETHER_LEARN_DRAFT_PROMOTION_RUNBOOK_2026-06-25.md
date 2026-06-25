# Aether Learn Draft Promotion Runbook - 2026-06-25

Purpose: operate the Phase 2 learner preview without turning suggestions into
silent durable memory, support patterns, or reflections.

The Learn drawer is a review router. It is not an apply button.

## Safety Contract

- `GET /v1/consolidation/candidates` is preview-only.
- Learner candidates are not confirmed facts.
- Learner candidates do not write memory.
- Learner candidates do not import support patterns.
- Learner candidates do not create reflections.
- Opening a target drawer only preselects review context or fills editable form
  state.
- Support and Reflection drawers may create proposed review artifacts only after
  an explicit operator click inside that drawer.
- Durable changes still require existing Memory, Support, or Reflection review
  actions.

## Operator Flow

1. Open Workbench and choose `Learn`.
2. Check the safety row:
   - mode should be `preview only`;
   - writes should be `no`;
   - memory should be `no`;
   - support import should be `no`;
   - reflection create should be `no`.
3. Read the candidate:
   - `Candidate` is the learner summary;
   - `Proposed action` is the suggested review route;
   - `Risk boundary` is what must not be inferred or applied;
   - `Evidence` is the trace or turn excerpt that made the candidate appear.
4. Use the route button only when the candidate is worth reviewing:
   - `Open Memory` opens the exact slot detail and shows the learner-origin
     review banner;
   - `Open Support` opens editable support-pattern draft form state;
   - `Open Reflect` opens editable reflection draft form state.
5. Review manually:
   - for Memory, use confirm/correct/quarantine only after checking the slot
     history, disposition, and evidence;
   - for Support, treat the draft as behavior guidance only, not a fact, then
     use `Create Proposed Candidate` only if the candidate should enter
     support-pattern review;
   - for Reflection, treat the draft as a hypothesis about Aether, workflow, or
     project behavior, not a personality verdict, then use
     `Create Proposed Reflection` only if the hypothesis should enter
     reflection review.
6. If evidence is thin, leave it unpromoted.

## Current Limits

- Learn itself remains preview-only and does not call import/create/review
  endpoints.
- Support draft promotion now uses an adapter-safe manual button that calls
  `/v1/support-patterns/import` with `status=proposed_review`,
  `review_required=true`, `memory_write_allowed=false`, and
  `confirmed_fact=false`.
- Reflection draft promotion now uses an adapter-safe manual button that calls
  `/v1/reflections` to create a proposed reflection with source evidence and
  learner risk boundary preserved.
- Manual creation is not durable acceptance. Support candidates and reflections
  still need the existing review actions before they can shape behavior.

## Verification

From `D:\AI_round2\workbench`:

```powershell
npm run test:ui -- --run src/api.test.ts src/components/ConsolidationDrawer.test.tsx src/components/MemoryDrawer.test.tsx src/components/SupportPatternDrawer.test.tsx src/components/ReflectionDrawer.test.tsx src/App.test.tsx
npm run smoke:learn-promotion -- --json
```

Expected protected behavior:

- Learn candidates render preview-only safety flags.
- Memory route opens the selected slot without mutation.
- Support draft handoff does not call support review/import endpoints.
- Reflection draft handoff does not call reflection review/create endpoints.
- Support and Reflection adapter payloads preserve source evidence, risk
  boundaries, review-required status, and non-memory flags.
- API transport uses the intended proposed-review endpoints and request
  envelopes for manual Support/Reflection draft creation.
- App-level Learn-to-drawer navigation keeps handoffs manual.
- The isolated Learn promotion smoke starts a temporary sidecar fixture, reads
  real learner candidates from `/v1/consolidation/candidates`, manually creates
  one proposed support-pattern candidate and one proposed reflection, and
  confirms preview itself still reports no writes/imports/creates.

From `D:\AI_round2\aether-core`:

```powershell
python -m pytest tests/test_sidecar_support_patterns.py tests/test_sidecar_reflections.py tests/test_sidecar_consolidation.py -q
```

Expected protected behavior:

- consolidation candidates remain review-required;
- `memory_write_allowed` remains false;
- `confirmed_fact` remains false;
- preview endpoint reports no writes/imports/creates.

## Promotion Standard

Promote only when the candidate is:

- repeated or strongly evidenced;
- useful as a behavior/review rule;
- bounded by clear risk language;
- routed through the correct existing review surface;
- reversible or rejectable by the user.

Do not promote:

- one-off mood or late-night wording as identity truth;
- ChatGPT archive style as Aether voice cloning;
- contradiction candidates without checking disposition and slot evidence;
- project momentum as a confirmed fact without user confirmation.
