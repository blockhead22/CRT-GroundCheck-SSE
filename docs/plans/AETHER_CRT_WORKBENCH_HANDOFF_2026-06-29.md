# Aether / CRT / Workbench Handoff - 2026-06-29

This is the clean restart packet for a new Codex thread in `D:\AI_round2`.

Start here for the current local-router, CRT trace, and lab-to-roadmap state.
Use the older handoffs for historical context, but do not restart broad
archaeology unless a specific missing concept requires a specific source file.

## Active Lane

```text
Aether Core validation infrastructure:
local router -> Mirus packet -> scaffold -> model render -> CRT verifier
-> repair/fallback -> durable thinking trace -> replay eval
```

Roadmap position:

```text
Phase 1.10 route/model selection       observational in Workbench, active in lab
Phase 2 governed learner/Mirus loop    active roadmap re-entry
New trace lane                         durable structured thinking traces
```

Current rule:

```text
This lab is worth continuing only if it becomes Aether/Core infrastructure.
Prompt tuning alone is not enough.

No raw hidden chain-of-thought as truth. Store structured trace artifacts:
classification, retrieval, Mirus packet, scaffold, model route, verifier flags,
repair/fallback decisions, contradiction notes, confidence, and learning
candidates.
```

## Read These First

```text
D:\AI_round2\docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
D:\AI_round2\docs\plans\AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
D:\AI_round2\local-router-replay-v0-report-2026-06-28.md
D:\AI_round2\docs\plans\AETHER_AETEROS_MASTER_PLAN_2026-06-26.md
D:\AI_round2\docs\plans\AETHER_WORKBENCH_V1.md
```

Useful lab notes:

```text
D:\AI_round2\local-model-routing-and-attention-notes-2026-06-28.md
D:\AI_round2\local-model-response-grading-notes-2026-06-28.md
D:\AI_round2\aether-local-router-v0-notes-2026-06-28.md
D:\AI_round2\aether-local-router-cli-v0-notes-2026-06-28.md
D:\AI_round2\network-ai-capacity-sweep-2026-06-28.md
```

## What Changed Most Recently

### Local Router Lab Became Roadmap-Relevant

The work started as "can small local models think better with scaffolds?" It is
now an Aether/Core validation lane.

Implemented lab pieces:

```text
D:\AI_round2\labs\meaning_compression_lab\spiral_synthesis_eval.py
D:\AI_round2\labs\meaning_compression_lab\attention_profile_eval.py
D:\AI_round2\labs\meaning_compression_lab\local_router_eval.py
D:\AI_round2\labs\meaning_compression_lab\local_router_cli.py
D:\AI_round2\labs\meaning_compression_lab\replay_pack_builder.py
D:\AI_round2\labs\meaning_compression_lab\local_router_replay.py
```

Tests:

```text
D:\AI_round2\tests\test_spiral_synthesis_eval.py
D:\AI_round2\tests\test_attention_profile_eval.py
D:\AI_round2\tests\test_local_router_eval.py
D:\AI_round2\tests\test_local_router_cli.py
D:\AI_round2\tests\test_local_router_replay.py
```

Current router policy:

```text
exact_memory            -> qwen2.5:7b-instruct / semantic_spine
personal_synthesis      -> qwen2.5:7b-instruct / section_lock
architecture_synthesis  -> qwen2.5:7b-instruct / semantic_spine
grant_business          -> qwen2.5:7b-instruct / section_lock
code_reasoning          -> qwen2.5-coder:14b / section_lock
```

Current best mechanism:

```text
classify request
-> build Mirus packet / semantic spine
-> choose model and scaffold
-> render
-> verify with CRT gates
-> repair once or fallback
-> store answer + trace
```

### Preliminary Evidence

Router eval:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_eval_1782687384.json
Pass: 3/3
Average score: 0.845
Average contract score: 0.762
Average usefulness score: 1.000
Repairs: 1
Fallbacks: 0
```

Real-log replay pack:

```text
D:\AI_round2\labs\meaning_compression_lab\replay_packs\local_router_replay_v0.json
16 total cases:
4 architecture_synthesis
4 personal_synthesis
4 grant_business
4 code_reasoning
```

Latest 12-case replay artifact:

```text
D:\AI_round2\labs\meaning_compression_lab\results\local_router_replay_1782692982.json
```

Rescored after verifier false-positive fix:

```text
Raw local answers:     0/12 pass, avg 0.405
Routed local answers: 10/12 pass, avg 0.761
Average lift:         +0.356
```

This is preliminary evidence, not a final product claim. The replay pack is
real-log messy and needs human curation before it is used for grants, demos, or
formal claims.

### Durable Thinking Trace Requirement Added

New requirement:

```text
D:\AI_round2\docs\plans\AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
```

Every assistant turn should be able to persist an inspectable trace:

```text
turn_id
conversation_id
timestamp
user_request_summary
task_type
route_selected
model_selected
scaffold_profile
retrieved_memory_ids
retrieved_chat_ids
mirus_packet_summary
evidence_anchors
allowed_inferences
disallowed_inferences
draft_quality_score
verifier_flags
repair_attempts
fallback_used
final_confidence
contradiction_notes
learning_candidates
promotion_status
```

After restart, a historical message should be able to reopen with the trace that
produced it: what Aether remembered, inferred, refused to claim, repaired, and
possibly learned.

## Concept Mapping

Use this current interpretation:

```text
Mirus
  Evidence intake, belief state, authority boundaries, contradiction state,
  allowed/disallowed claims, and learning candidates.

Holden
  Final speech/rendering layer. It should not own truth.

SSE / Semantic String Engine
  The semantic spine: structured context expansion from verified nodes, not a
  giant memory dump.

CRT
  Contradiction-resilient trust: verifier gates, overclaim detection,
  unsupported claim checks, drift detection, repair/fallback policy.

Router
  Task classifier plus model/scaffold selector.

Trace
  Durable audit record of how the answer happened.

Replay
  Eval harness that proves whether routed local cognition beats raw local chat.
```

## Current Model Read

Local machine:

```text
RTX 3060 12GB
32GB RAM
```

Useful model takeaways:

```text
qwen2.5:7b-instruct      best strict governed-state executor so far
qwen3:14b                biggest useful installed text model, better for some
                         scaffolded long-form drafting but less steady
qwen2.5-coder:14b        code-route specialist candidate
gemma4:latest            large context, weak in current text-only evals
phi3:3.8b                tiny-model stress subject
```

Do not choose models by size alone. The lab repeatedly showed that route,
scaffold, verifier, and repair matter more than "largest model" for this lane.

## Current Limitations

- Replay pack is still small and somewhat noisy.
- Personal synthesis can become generic without stronger memory receipts.
- Grant/business answers need stricter outcome-promise language.
- The router CLI does not yet persist full trace JSON per run.
- Replay eval currently grades answer quality more than trace quality.
- Workbench has not yet adopted the lab router as a real request path.
- Durable historical trace reload is specified, not implemented.

## Next Work

Best next tasks, in order:

1. **Add trace JSON writing to `local_router_cli`.**
   - Store answer, route, scaffold profile, verifier flags, repair/fallback,
     confidence, and learning candidates.

2. **Update replay eval to grade trace quality.**
   - A good answer with a bad trace should not count as fully successful.

3. **Curate a 30-50 case replay pack.**
   - Keep architecture, personal synthesis, grant/business, exact memory,
     creative-production planning, code reasoning, and multi-turn correction.

4. **Prove restart reload.**
   - A historical run should reload answer + trace after process restart.

5. **Only then wire into Workbench.**
   - Add a compact Activity/Trace panel fed by structured trace summaries.
   - Keep raw hidden chain-of-thought out of the product contract.

6. **Return trace artifacts to Phase 2 learner heartbeat.**
   - Learning candidates remain pending until reviewed, rejected, or promoted.

## Success Criteria

Classify this lab phase as successful when:

```text
1. A curated 30-50 case replay pack exists.
2. Routed local answers beat raw local answers by at least +0.20 average score.
3. Routed pass rate clears 70% on curated cases.
4. Repairs fix more failures than they introduce.
5. The judge catches unsupported claims without over-flagging explicit negations.
6. Router CLI writes trace JSON for every run.
7. Replay eval grades answer quality and trace quality.
8. Historical runs reload answer + trace after restart.
9. Learning candidates stay review-only until explicitly promoted.
```

## Safety / Product Contract

Do not implement:

```text
silent durable memory writes
silent support imports
silent reflection creation
silent model switching
raw hidden chain-of-thought storage as truth
frontier-level capability claims
autonomous truth claims
guaranteed business/grant outcome claims
```

Do implement:

```text
structured trace summaries
explicit evidence anchors
allowed/disallowed inference boundaries
verifier flags
repair/fallback records
review-only learning candidates
restart-safe historical trace reload
```

## Restart Prompt

Use this prompt for a new clean thread:

```text
We are in D:\AI_round2. Read:
- docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
- docs/plans/AETHER_DURABLE_THINKING_TRACE_REQUIREMENT_2026-06-29.md
- local-router-replay-v0-report-2026-06-28.md
- docs/plans/AETHER_AETEROS_MASTER_PLAN_2026-06-26.md only as needed

Continue the Aether local-router / durable trace lab in
labs/meaning_compression_lab. Do not reset or clean the dirty worktree. Preserve
untracked lab files and docs.

Current task direction:
1. Add durable trace JSON output to local_router_cli.
2. Make local_router_replay grade trace quality as well as answer quality.
3. Curate and expand the replay pack to 30-50 clean cases.
4. Prove a historical answer + trace can reload after restart.
5. Bring the trace pattern back into Workbench only after the lab evidence holds.

Important contract:
Do not store raw hidden chain-of-thought as truth. Store structured CRT trace
artifacts: classification, retrieval, Mirus packet, route, scaffold, verifier,
repair/fallback, confidence, contradiction notes, and learning candidates.
```

## One-Line Status

Aether is at the point where the lab can become the Core: small local models are
not being made "magical"; they are becoming more useful through governed
external cognition, durable trace, verifier repair, and replay evidence.
