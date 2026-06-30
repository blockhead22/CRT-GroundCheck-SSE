# Aether Current State

Last updated: 2026-06-30

Start new Codex threads here:

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
```

## Current Lane

```text
Phase 2 governed learner / Mirus loop:
recent traces and turns -> review-only Memory, Support, Reflection,
Contradiction, and Evidence candidates -> Workbench review -> durable behavior
only after operator approval.
```

The local-router / durable trace / RAG-baseline lab is graduated as
Aether/Core validation infrastructure. Do not continue it as loose prompt
tuning, model shopping, or repeated adversarial v1/v2 tuning.

## Read First

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_LAB_GRADUATION_2026-06-30.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_AETEROS_CORE_SCHEMA_CANDIDATES_2026-06-30.md
D:\AI_round2\docs\plans\AETHER_LOCAL_ROUTER_TRACE_WORKBENCH_MAPPING_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_LOW_SCORE_ANCHOR_FIT_REVIEW_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_FEEDBACK_CANDIDATE_REVIEW_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_WEIGHTED_FEEDBACK_LEDGER_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_AETEROS_MASTER_PLAN_2026-06-26.md
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

## Current Decision

```text
The lab proved a useful bounded claim:
governed external cognition can make small/local model behavior more reliable,
inspectable, and reviewable than raw local chat or plain/scaffolded RAG for
Aether's target cases.
```

This is evidence for governance, not evidence that local models compete with
frontier models globally.

The useful architecture is:

```text
intent/task classification
-> evidence and memory retrieval
-> Mirus packet / semantic spine
-> scaffold or answer spine
-> model rendering when needed
-> CRT verifier
-> repair/fallback
-> durable trace
-> review-only learning candidates
```

## Latest Implementation State

Phase 2 learner/review loop:

```text
Sidecar consolidation surfaces review-only Memory, Support, Reflection,
Contradiction, and Evidence candidates from explicit trace metadata.

Memory fact candidates are limited to explicit trace.memory_candidates rows
with review_required true/implicit, memory_write_allowed false, and
confirmed_fact false.

Workbench learner candidates show a why-this-exists strip with first receipt,
review boundary, and review destination.

Trace-proposed memory facts can open Memory with a manual review-only draft
panel. It does not prefill corrections, confirm candidates, quarantine, or
write memory.
```

Reject/defer boundary:

```text
Accepted reflections can enter future context.
Rejected and deferred reflections do not.
Workbench Defer Session and Hide Session remain local review-queue states and
do not open review routes or call additional APIs.
```

Workbench/lab bridge:

```text
Local-router RAG evidence can be shown as review-only trace/review metadata.
Trace fixture attachment refuses the live DB by default.
Live DB attachment requires:
--allow-live-db --confirm-live-db ATTACH_REVIEW_ONLY_TRACE_EVIDENCE
Even then, it writes only trace JSON.
```

## Aeteros Core Extraction State

Implemented first reusable schema extraction:

```text
D:\AI_round2\aether-core\aether\sidecar\review_schema.py
```

Contains:

```text
EvidenceReceipt
ReviewCandidate
SafetyContract
review_only_candidate_flags
```

Wired into:

```text
D:\AI_round2\aether-core\aether\sidecar\consolidation.py
D:\AI_round2\aether-core\aether\sidecar\archive_import.py
```

Do not extract yet:

```text
ReviewDecision
ContradictionMarker
TraceEvent
TracePacket
FeedbackLedgerRow
```

Why:

```text
ReviewDecision waits for a durable Memory candidate/decision adapter.
ContradictionMarker waits until the same marker object drives at least two live
behaviors such as route policy and Memory conflict review.
TracePacket should be extracted before TraceEvent only after the same packet
object is used unchanged by at least two live call sites.
FeedbackLedgerRow waits for a non-lab feedback source.
```

Keep out of Core:

```text
local-router pack names
evaluator thresholds
Workbench session state
local_router_trace.evidence_review metadata
adversarial case ids
grant/product wording anchors
model names and fallback profiles
```

## Generative Governance

Generative governance is a strong roadmap hypothesis:

```text
Governance may generate structured answer spines, evidence boundaries,
insufficient-evidence responses, contradiction/review warnings, deterministic
meta/direct answers, and model render contracts before Holden/model rendering.
```

It must not:

```text
generate unreviewed truth
silently mutate memory or policy
store raw hidden chain-of-thought
become a second hidden chatbot
```

Current code already has narrow "governance can speak first" paths:

```text
D:\AI_round2\aether-core\aether\sidecar\meta_answer.py
D:\AI_round2\aether-core\aether\sidecar\direct_answer.py
```

First observational answer-spine implementation:

```text
D:\AI_round2\aether-core\aether\sidecar\governance_spine.py
D:\AI_round2\aether-core\tests\test_governance_spine.py
```

The sidecar now stores `governance_answer_spine` in each chat trace before
model rendering. This is trace-only in the first pass: it does not change the
prompt, write memory, import support, create reflections, or mutate policy.

Verified boundaries:

```text
restricted packet values are not leaked into the spine
model-rendered answers still call Ollama normally
deterministic meta/direct answers remain deterministic
the spine carries memory_write_allowed=false
the spine carries raw_chain_of_thought_stored=false
```

The next practical version is:

```text
Mirus generates the answer spine and evidence boundary.
Holden/model renders only when language nuance is useful.
CRT verifies the rendered answer against the spine.
Workbench stores trace and review candidates.
```

## Next Work

Do next:

```text
1. Improve learner review queue dogfooding only where it helps daily use.
2. Look for a real Memory candidate/decision adapter need before extracting
   ReviewDecision.
3. Keep regression tests around review-only and reject/defer non-effect.
4. Treat generative governance as an answer-spine experiment, not a schema
   extraction yet.
```

Do not do next:

```text
do not retune adversarial v1/v2
do not return to raw-only model comparisons
do not add import surfaces without product need
do not create automatic memory/support/reflection writes
do not expand schemas speculatively
```

## Safety Contract

```text
Do not store raw hidden chain-of-thought as truth.
Do store structured CRT trace artifacts:
classification, retrieval, Mirus packet, route, scaffold, verifier flags,
repair/fallback, confidence, contradiction notes, and learning candidates.

No automatic memory writes.
No automatic support-pattern imports.
No automatic reflection creation.
No silent model switching.
No silent policy mutation.
```
