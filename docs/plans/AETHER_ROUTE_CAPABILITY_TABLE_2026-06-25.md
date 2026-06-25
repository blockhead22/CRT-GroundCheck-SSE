# Aether Route Capability Table - 2026-06-25

This is the Phase 1.10 on-ramp from the Phase 1.6/1.7/1.8/1.9 evidence into
governed model and route selection.

The core rule:

```text
The local model may request help, but it does not decide the route.
The governed system decides route, model policy, tools, repair, and escalation.
```

## Safety Contract

- Local-first by default.
- Deterministic answers when the answer is available from trace, route,
  governance, memory review, or eval metadata.
- No silent frontier escalation.
- No silent durable memory writes from routing.
- Model choice is policy output, not the model's self-rating.
- Tool use stays governed and trace-visible.
- Weak local answers may mark `needs_stronger_model`, but that is a reviewable
  signal, not automatic escalation.
- High-stakes prompts can recommend qualified professional review; stronger
  generation is not treated as final authority.

## Capability Evidence

| Route | Primary trigger | Evidence currently passing | Preferred execution | Repair or escalation rule | Trace fields |
| --- | --- | --- | --- | --- | --- |
| `deterministic_meta` | User asks what model/route/context shaped an answer, whether it should have escalated, or how governance behaved. | Meta route answers are deterministic and explain selected/generated model and Context Bridge involvement. | Sidecar deterministic answer. No local generation needed. | No escalation unless operator explicitly asks for broader analysis. | `response_route`, `selected_model`, `generated_model`, `boundary`, `route_reason` |
| `memory_review` | Exact profile/slot lookup, especially direct personal facts. | Slot detail endpoint, Memory drawer review, deterministic direct conflicted answers. | Query governed memory and answer from confirmed or review-state metadata. | If conflicted, route to review language and Memory drawer actions instead of guessing. | `slot_id`, `slot_status`, `contradiction_disposition`, `withheld_summary` |
| `contradiction_review` | Conflicting facts, evolving beliefs, old/current values, policy-bound evidence. | Phase 1.8 labels: `resolvable`, `held`, `evolving`, `contextual`, `stale`, `policy_bound`; isolated eval covers all six. | Deterministic or tightly constrained local answer shaped by disposition. | Ask user to confirm/correct when needed; do not leak restricted values. | `contradiction_disposition`, `reason`, `confidence`, `review_route` |
| `context_bridge_broad` | Broad identity, project, relationship, "what are we building?", "how do you know me?", business/project synthesis. | Context Bridge real-use prompts and identity/tone/depth slices pass in sliced evals. | Local generation with governed Context Bridge packet and repair gates. | If answer is generic/thin, repair once using anchors; mark `needs_stronger_model` if still weak. | `context_bridge.intents`, `reviewed_reflections`, `reviewed_support_patterns`, `repair` |
| `real_use_support` | Nick-style project doubt, return/re-entry, tired-night triage, motivation, "be honest but not generic." | Harsh real-use pack reached 4/4 after targeted repairs; archive-derived support-pattern fixture passes 2/2. | Local generation with character/support anchors, accepted support patterns, and lived-quality repair. | Do not invent therapeutic certainty; if generic after repair, provide a deterministic grounded fallback or mark escalation candidate. | `character_route`, `support_patterns`, `real_use_anchors`, `repair` |
| `depth_synthesis` | User asks for deep, spiral, verbose, dig deep, or a long multifactual synthesis. | Phase 1.5 depth classifier, continuation loop, depth trace card, forced continuation checks. | Local generation with depth budget, self-check, bounded continuation, and prefix trimming. | Continue only within bounded policy; if still missing requested coverage, mark `needs_stronger_model`. | `response_depth`, `continuation_count`, `coverage`, `needs_continuation` |
| `code_tool` | Repository/file/search/test/programming question. | Phase 1.6 code-context evals, endpoint orientation repair for `GET /v1/consolidation/candidates`, tool trace UI. | Tool-first workspace search/read/test recommendation; local model synthesizes from retrieved evidence. | If tool evidence is insufficient, ask for a specific file/path or create an escalation packet. | `tool_policy`, `workspace_search`, `workspace_read`, `test_result`, `programming_context` |
| `bridge_candidate_packet` | Review-only learner candidates for project/support/reflection behavior. | Phase 1.9 bridge candidate packet eval: full packet 3/3, typed packets preserve their own candidate behavior at lower size. | Use narrow typed packets when only project, support, or reflection candidates are needed. | Route to review surfaces; no automatic acceptance. | `candidate_packet_type`, `candidate_ids`, `review_route`, `memory_write_allowed` |
| `compression_replay_eval` | Questions about memory-state compression, representation replay, or eval commands/results. | Phase 1.9 representation replay: governed scaffold and CRT compressed state both 19/19; Context Bridge candidates 10/19. | Deterministic eval summary from current run outputs and docs. | Do not ask local model to infer eval meaning without results. | `eval_name`, `representations`, `scores`, `ratio`, `interpretation` |
| `high_stakes_caution` | Medical, legal, financial, business registration, health, safety, or regulated advice. | Real-use medical-adjacent and Aeteros/business prompts repaired toward grounded caution. | Bounded local answer with clear uncertainty and practical next step. | Recommend qualified review where appropriate; stronger model can research but not decide. | `risk_level`, `caution_reason`, `professional_review_recommended` |
| `general_local` | Ordinary non-risk conversational or creative prompt with no special memory/tool/depth need. | Baseline conversation evals and local generation path. | Local model with standard prompt and trace. | Repair only if route-specific hard anchors fail. | `selected_model`, `route_reason`, `repair` |
| `escalation_candidate` | Multi-step frontier-worthy work, repeated local failure, missing tools, weak answer after repair, or user explicitly asks for stronger model. | Existing `needs_stronger_model` trace boundary and programming escalation packet shape. | Local attempt plus clean escalation packet. User remains in control. | Never silently send private context to a frontier model. | `needs_stronger_model`, `escalation_allowed`, `escalation_reason`, `scrub_required` |

## Immediate Implementation Slice

Build a small deterministic route policy module before changing model behavior.

Proposed contract:

```text
message + trace/memory/context signals
    -> candidate_routes
    -> selected_route
    -> selected_model_policy
    -> tool_policy
    -> repair_policy
    -> escalation_allowed
    -> route_reason
```

Initial tests should verify:

- meta/governance prompt -> `deterministic_meta`;
- exact conflicted slot prompt -> `contradiction_review`;
- repository search prompt -> `code_tool`;
- deep/spiral/verbose prompt -> `depth_synthesis`;
- Aeteros/LLC business prompt -> `context_bridge_broad` plus
  `high_stakes_caution`;
- personal project doubt prompt -> `real_use_support`;
- representation replay command/results prompt -> `compression_replay_eval`;
- weak local answer signal -> `escalation_candidate` without silent escalation.

## Trace Fields To Add

- `route_decision`
- `candidate_routes`
- `selected_route`
- `selected_model_policy`
- `route_reason`
- `route_confidence`
- `risk_level`
- `tool_policy`
- `repair_policy`
- `escalation_allowed`
- `escalation_reason`

## Open Questions

- Should route selection run before Context Bridge build, after the first intent
  pass, or both?
- Should model capability policy live in static config first, then later be
  updated by eval evidence?
- How much route detail should Workbench show without making the Trace drawer
  noisy?
- How do we avoid overfitting route policy to the current small eval packs?
- How should live accepted support-pattern candidates become route evidence once
  Nick has reviewed real candidates?

## Next Step

The smallest tested route policy slice now exists:

```text
D:\AI_round2\aether-core\aether\sidecar\route_policy.py
D:\AI_round2\aether-core\tests\test_sidecar_route_policy.py
```

It classifies:

- meta/governance -> `deterministic_meta`;
- conflicted memory signals -> `contradiction_review`;
- repository/code/test questions -> `code_tool`;
- deep/spiral/verbose requests -> `depth_synthesis`;
- Aeteros/LLC business prompts -> `context_bridge_broad` with
  `high_stakes_caution` as a candidate;
- project doubt/support prompts -> `real_use_support`;
- representation replay/compression eval prompts -> `compression_replay_eval`;
- failed local/repair signals -> `escalation_candidate`.

Verification:

```text
python -m pytest tests/test_sidecar_route_policy.py -q
9 passed

python -m pytest tests/test_sidecar_meta_answer.py tests/test_sidecar_depth.py tests/test_sidecar_direct_answer.py tests/test_sidecar_route_policy.py -q
34 passed
```

Next implementation step: wire this side-effect-free decision into the sidecar
trace/completion metadata without changing generation behavior yet. The route
decision may shape traces and later answer policy, but it must not write memory,
import support patterns, create reflections, or silently escalate.

## Trace Metadata Slice

The route decision is now attached to sidecar trace/completion metadata:

```text
D:\AI_round2\aether-core\aether\sidecar\app.py
```

Behavior boundary:

- route metadata is computed after context/tools/depth guidance are available;
- `trace.route_decision` is saved with the initial trace;
- `completion.route_decision` is saved through the existing completion route
  helper;
- generation behavior is not changed yet;
- route policy still does not call models, tools, memory writers, support
  imports, reflection creation, or escalation.

Focused coverage proves metadata appears for:

- meta/governance -> `deterministic_meta`;
- conflicted direct memory lookup -> `contradiction_review`;
- repository search/code prompt -> `code_tool`;
- explicit deep request -> `depth_synthesis`;
- Aeteros/LLC business prompt -> `context_bridge_broad` with
  `high_stakes_caution` candidate;
- project doubt prompt -> `real_use_support`.

Verification:

```text
python -m pytest tests/test_sidecar_meta_answer.py tests/test_sidecar_app.py::test_direct_conflicted_profile_lookup_uses_disposition_without_leaking_values tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_deep_request_records_depth_policy_and_prompt_guidance tests/test_sidecar_app.py::test_code_tool_route_decision_is_traced_without_changing_tool_behavior tests/test_sidecar_route_policy.py -q
19 passed

python -m pytest tests/test_sidecar_meta_answer.py tests/test_sidecar_depth.py tests/test_sidecar_direct_answer.py tests/test_sidecar_route_policy.py tests/test_sidecar_app.py -q
64 passed
```

Next implementation step: expose `route_decision` in Workbench Trace UI, keeping
it compact enough that it clarifies routing without cluttering the trace drawer.

## Workbench Trace UI Slice

Workbench now exposes route decisions in the Trace drawer:

```text
D:\AI_round2\workbench\src\components\TraceDrawer.tsx
D:\AI_round2\workbench\src\types.ts
D:\AI_round2\workbench\src\components\TraceDrawer.test.tsx
```

UI shape:

- a compact `Route decision` card appears between `Response route` and
  `Response depth` when `trace.route_decision` or
  `completion.route_decision` exists;
- fields shown: selected route, model policy, tool policy, repair policy, risk
  level, and escalation eligibility;
- historical traces without route metadata keep rendering normally;
- the existing Response Route and Response Depth cards are unchanged.

Verification:

```text
npm run test:ui -- --run src/components/TraceDrawer.test.tsx
11 passed

npm run test:ui -- --run src/App.test.tsx src/components/TraceDrawer.test.tsx
22 passed

npm run build
passed
```

Browser smoke on `http://127.0.0.1:5175/`:

- page title: `Aether Workbench`;
- page rendered nonblank;
- console errors/warnings: `0`;
- Trace drawer opened from bottom navigation;
- historical trace button opened an older saved trace with Response Route and
  Response Depth still intact;
- visible historical trace did not show Route Decision because it predates the
  new sidecar route metadata. Generate a fresh trace after restarting the
  sidecar to see the new card live.

Next implementation step: run a sliced live route-decision smoke after the
sidecar is restarted, then decide whether route decisions should begin shaping
answer policy or stay observational for another eval round.

## Live Route-Decision Smoke

The running sidecar was initially healthy but stale: a meta smoke produced a
valid deterministic answer without `route_decision`. The listener on port `8765`
was verified as `python.exe -m aether.sidecar`, then restarted from
`D:\AI_round2\aether-core` and health returned cleanly.

Fresh sliced live smoke against the restarted sidecar:

| Case | Expected route | Trace route | Saved completion route | Notes |
| --- | --- | --- | --- | --- |
| `meta_governance` | `deterministic_meta` | `deterministic_meta` | `deterministic_meta` | deterministic answer, no memory writes |
| `code_tool` | `code_tool` | `code_tool` | `code_tool` | tool-first policy, no memory writes |
| `depth_synthesis` | `depth_synthesis` | `depth_synthesis` | `depth_synthesis` | depth controller policy, no memory writes |
| `aeteros_business_caution` | `context_bridge_broad` | `context_bridge_broad` | `context_bridge_broad` | includes `high_stakes_caution` candidate, no memory writes |
| `real_use_support` | `real_use_support` | `real_use_support` | `real_use_support` | support-anchor policy, no memory writes |

Result:

```text
fresh live route-decision smoke: 5/5 passed
```

Workbench browser verification:

- reloaded `http://127.0.0.1:5175/`;
- selected the fresh `real_use_support` conversation from the conversation
  picker;
- opened its turn trace;
- confirmed the Trace drawer rendered the new `Route decision` card live with:
  selected route `real use support`, model policy `local with support anchors`,
  tool policy `tools optional`, repair policy
  `real use anchor repair then fallback`, risk `low`, escalation `no`;
- console warnings/errors remained `0`.

Next implementation step: keep route decisions observational for one more eval
round, then add the smallest route-policy steering gate only where the route
already matches existing behavior (for example, trace/prompt annotation rather
than changing model selection).

## Prompt Annotation Gate

The first steering-adjacent gate is implemented as prompt annotation only:

```text
D:\AI_round2\aether-core\aether\sidecar\prompt.py
D:\AI_round2\aether-core\aether\sidecar\app.py
```

Boundary:

- `build_local_prompt` now includes a compact `Route policy` section when a
  route decision exists;
- the annotation names selected route, model policy, tool policy, repair
  policy, risk, escalation eligibility, and route reason;
- the annotation explicitly says the governed system selected the policy and
  the model must not override it or claim it selected the route;
- it explicitly does not grant permission to write memory, import support
  patterns, create reflections, call tools, or escalate silently;
- model selection, deterministic routing, tool execution, depth controller, and
  repair behavior are unchanged.

Focused verification:

```text
python -m pytest tests/test_sidecar_ingest.py tests/test_sidecar_meta_answer.py tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_deep_request_records_depth_policy_and_prompt_guidance tests/test_sidecar_app.py::test_code_tool_route_decision_is_traced_without_changing_tool_behavior tests/test_sidecar_route_policy.py -q
29 passed

python -m pytest tests/test_sidecar_ingest.py tests/test_sidecar_meta_answer.py tests/test_sidecar_depth.py tests/test_sidecar_direct_answer.py tests/test_sidecar_route_policy.py tests/test_sidecar_app.py -q
75 passed
```

Live smoke after restarting the current sidecar:

| Case | Expected route | Trace route | Saved route | Memory writes |
| --- | --- | --- | --- | --- |
| `meta_governance` | `deterministic_meta` | `deterministic_meta` | `deterministic_meta` | `0` |
| `code_tool` | `code_tool` | `code_tool` | `code_tool` | `0` |
| `depth_synthesis` | `depth_synthesis` | `depth_synthesis` | `depth_synthesis` | `0` |
| `real_use_support` | `real_use_support` | `real_use_support` | `real_use_support` | `0` |

Result:

```text
prompt annotation live smoke: 4/4 passed
```

Next implementation step: keep this as the only steering-adjacent behavior until
a dedicated eval proves a stronger gate is useful. The next safe option is an
eval-only comparison of observational route policy versus prompt-annotated route
policy for thin/generic answer repair, not a model-selection change.

## Prompt Annotation Comparison Eval

The eval-only comparison now exists:

```text
D:\AI_round2\aether-core\scripts\route_policy_annotation_eval.py
D:\AI_round2\aether-core\tests\test_route_policy_annotation_eval.py
```

It compares the same prompt in two forms:

```text
observational route policy -> route decision is computed but not included
prompt-annotated policy    -> route decision is included in build_local_prompt
```

Current deterministic cases:

| Case | Expected route | Repair policy proven in annotation |
| --- | --- | --- |
| `annotation_project_doubt_anti_generic` | `real_use_support` | `real_use_anchor_repair_then_fallback` |
| `annotation_aeteros_business_caution` | `context_bridge_broad` | `context_anchor_repair_then_fallback` |
| `annotation_local_model_spiral_depth` | `depth_synthesis` | `bounded_continuation_self_check` |

The eval verifies that prompt annotation:

- is additive over the observational baseline;
- includes the selected route and route repair policy;
- preserves existing anti-generic/real-use answer guidance;
- explicitly preserves the no-write, no-tool-call, and no-silent-escalation
  safety boundary;
- does not change model selection or generation behavior.

Verification:

```text
python scripts\route_policy_annotation_eval.py --json
passed: true, 3/3 cases

python -m pytest tests/test_route_policy_annotation_eval.py tests/test_sidecar_route_policy.py tests/test_sidecar_app.py::test_real_use_aeteros_business_guidance_is_prompted_and_traced tests/test_sidecar_app.py::test_real_use_project_doubt_guidance_is_prompted_and_traced -q
13 passed
```

Next implementation step: run a sliced live comparison only if services are
available, then start a route/model sweep that records which local models handle
each route best. Model swapping should remain eval evidence first; automatic
model switching should wait until the route capability table has repeated
per-route results.
