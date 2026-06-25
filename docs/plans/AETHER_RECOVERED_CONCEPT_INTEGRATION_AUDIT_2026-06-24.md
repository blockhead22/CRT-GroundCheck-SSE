# Aether Recovered Concept Integration Audit - 2026-06-24

Purpose: create the on-ramp from recovered artifacts back into the main Aether Workbench roadmap.

This is not another archaeology pass. It answers:

```text
Which old concepts make current Aether more robust, where do they already exist,
what is still missing, and what should not be revived?
```

Source docs:

- `D:/AI_round2/docs/plans/AETHER_MEMORY_LANE_CLIPBOARD_2026-06-24.md`
- `D:/AI_round2/docs/plans/AETHER_RECOVERED_CORE_PRINCIPLES_2026-06-24.md`
- `D:/AI_round2/docs/plans/AETHER_FILECOMPRESSION_DEEP_DIVE_2026-06-24.md`
- `D:/AI_round2/docs/plans/AETHER_WORKBENCH_V1.md`
- `D:/AI_round2/docs/plans/AETHER_CRT_WORKBENCH_HANDOFF_2026-06-24.md`

Recovered sources:

- `C:/filecompression`
- `H:/holder/lumi_ai/lumi_ai`
- `D:/CRT`
- `H:/holder/CogniForge`
- `C:/Users/block/Downloads/src/src`
- `D:/AI_round2/data/chatgpt_export`

## Integration Rule

Bring concepts forward only when they become one of:

- an existing Aether capability with better language;
- a measurable eval;
- a trace/debugging surface;
- a governed memory/reflection mechanism;
- a bounded research lane.

Do not bring forward:

- mythic naming as product surface;
- arbitrary file-compression claims;
- unreviewed memory mutation;
- self-awareness language;
- old code wholesale when the current Aether implementation already has the safer pattern.

## Status Legend

| Status | Meaning |
| --- | --- |
| Already exists | Current Aether already has the core mechanism. Improve only if needed. |
| Exists but weak | Present, but reliability/visibility/eval coverage is not enough. |
| Missing and worth building | Useful recovered concept with no adequate current implementation. |
| Research lane | Worth testing, but not a product dependency. |
| Do not revive | Keep as history or caution only. |

## Audit Table

| Recovered concept | Current Aether language | Status | Current evidence | Gap | Phase | Eval needed | Implementation target | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lumi continuity assistant | Durable personal/project continuity | Already exists | Context Bridge, governed profile facts, trace recall | Needs richer real-use reliability | 1.7 | real-use multifactual prompts | sidecar context bridge, prompt assembly, Workbench trace | Keep and harden |
| Lumi simple memory | Governed memory candidates | Already exists | Aether sidecar memory/profile/context paths | Review workflow still thin | 1.7/2 | candidate memory review cases | memory review UI/sidecar review routes | Keep current Aether version |
| Lumi self-questioning/background loop | Reviewed reflection/background consolidation heartbeat | Exists but weak | reflection guidance exists, accepted/proposed distinction exists; Phase 2 heartbeat now planned | Accepted reflections do not yet strongly shape behavior; no periodic learner candidate pass exists yet | 2 | accepted/refused reflection and learner-candidate evals | character guidance, reflection ledger, trace markers, background consolidation worker | Build reviewed version only |
| Mirus | Governed intake-belief learner/background consolidation heartbeat | Exists but weak | slot extraction, stable-slot quarantine, source/authority logic, contradiction dispositions, support-pattern review path, pure review-only consolidation candidate planner, preview-only consolidation candidate endpoint, review-route metadata to Memory/Support/Reflection surfaces | No scheduler or Workbench consolidation drawer yet | 1.8/2 | belief intake + contradiction disposition + learner candidate cases | memory extraction, slot governance, trace metadata, background consolidation worker | Rename and consolidate as governed learner |
| Holden | Reconstruction-speech layer | Exists but weak | response routes, depth continuation, code/tool context packaging | Belief/speech gap not visible enough | 1.7/1.8 | belief/speech gap eval | prompt assembly, answer quality self-check, trace drawer | Rename and make inspectable |
| Master Mirus Holden | Variance/coherence regulator | Missing and worth building | variance labs measure drift; Phase 1.7 depth floor repairs thin answers | No general repair pass for missing required anchors | 1.7/1.8 | rerun variance probes across models | response repair controller, eval runner | Build as repair/regulator, not old MMH |
| CogniMap | Meaning trace graph/evolution log | Exists but weak | saved traces, Trace drawer, route metadata, per-turn trace recall | No graph of memory evolution, contradiction, compression, repair | 2 | trace mutation/replay eval | saved trace schema, Workbench trace graph | Build incrementally |
| CRT contradiction as disposition | Contradiction disposition governance | Exists but weak | conflicted query packets now carry `contradiction_disposition` labels; prompt contracts use label/reason/confidence without leaking restricted values; Trace and Memory drawers show label/reason/confidence; direct conflicted profile lookups produce deterministic review-style answers; opt-in eval cases cover resolvable/held/evolving/contextual/stale/policy-bound fixtures; isolated fixture runner starts a temporary sidecar without touching live memory; fixture eval repaired `old_employer` vs generic `employer` routing | Broader review surfacing may still need live-use coverage | 1.8 | review-surfacing evals and support-pattern/disposition interaction checks | memory governance, prompt contracts, trace drawer, memory review UI, eval runner | Continue Phase 1.8 |
| Memory as splat/region | Memory uncertainty/volatility state | Research lane | belief variance `variance_to_splats.py`; Fisher-Rao/fidelity bench | Not wired into Workbench memory behavior | 1.8/1.9 | uncertainty/volatility retention cases | memory schema, retrieval scoring, fidelity bench | Prototype after dispositions |
| Filecompression raw byte latent | Arbitrary learned file compression | Do not revive | `C:/filecompression/compress.py`, broken 15-byte reconstructions | Fails byte-exact round-trip | Boundary only | byte-exact sanity test | none/product claim guard | Keep as caution |
| Filecompression text/image bottlenecks | Representation compression replay bench | Research lane | 384D->4D text embedding, 2048D->16D image feature experiments | Old baselines weak; downstream behavior untested | 1.9 | raw vs summary vs PCA/SVD vs quantization vs autoencoder vs scaffold | `labs/meaning_compression_lab`, new replay runner | Build benchmark, not product dependency |
| CogniForge autoencoder | Learned semantic codec | Research lane | 384D->128D autoencoder, PCA-initialized, self-training loop | Needs fair baselines and behavior metrics | 1.9 | representation + answer-fidelity replay | meaning compression lab | Test only after simple baselines |
| CogniForge GFN router | Governed routing/task graph | Exists but weak | current route metadata, code tool selection, escalation packets | Route graph not explicit; repair/escalation policy thin | 1.6/1.8 | route-choice evals | sidecar routing, trace drawer | Keep pattern, not old implementation |
| Neural Narrative Weave | Depth expansion/non-repetition scaffold | Exists but weak | depth classifier, continuation loop, repetition trimming, Phase 1.7 tone repair/fallback, fresh split full-lane `25/25` verification | Continue watching continuation quality and repetition over broader prompts | 1.5/1.7 | deep/spiral/tone regression cases | depth controller, repair pass | Use conceptually |
| Emotion engine | Tone/support state | Exists but weak | character guidance and real-use eval prompts | Must avoid fake intimacy or mood theater | 1.7 | motivation/support/personality evals | answer guidance, style-anchor repair | Build as support-mode cues, not emotion claims |
| Blockhead fallback | Low-confidence humanistic fallback | Missing and worth building | uncertainty/scaffold boundaries exist | fallback phrasing can be generic or over-governed | 1.7/1.8 | low-confidence support responses | prompt templates, route fallbacks | Build bounded fallback language |
| Soft config toggles | Feature flags/dev controls | Already exists | eval flags, env roots, model selection, dev scripts | Need clearer operator docs over time | 1.6+ | config regression smoke | docs/dev shortcuts, app settings later | Keep current approach |
| Claude Code source patterns | Code Context Tools v1 architecture | Already integrated conceptually | `AETHER_LOCAL_CODER_V1.md`, reference-root eval, trace code metadata | Need more programming robustness and diagnostics | 1.6 | programming eval expansion | code tools, trace drawer, escalation packet | Continue Phase 1.6 path |
| ChatGPT archive | Longitudinal support-pattern archive | Exists but weak | dry-run scanner, title buckets, no message-body ingestion, review-required support-pattern candidates from title-category counts, revision-guarded import/list/detail/review API, accepted patterns released through Context Bridge/prompt guidance, Workbench Support review drawer, isolated support-pattern fixture eval proving accepted guidance is released and rejected guidance is excluded | Needs eventual broader model sweep, but the fixture behavior lane exists | 1.7/2 | archive-derived candidate review eval and later model sweep | archive scanner, review queue, support-pattern review UI, eval runner | Build reviewed extraction only |
| Belief variance labs | Variance measurement and repair | Exists but weak | variance probes, density/splats docs, Phase 1.7 model sweeps | Repair mechanisms lag measurement | 1.7/1.8 | repeated model/case variance evals | eval runner, repair controller, route metadata | Convert measurement into repair |
| Fidelity bench | Belief/speech gap measurement | Exists but weak | Fisher-Rao/cosine A/B, belief/speech rows | Workbench does not yet expose gap clearly | 1.8/1.9 | belief/speech trace eval | trace drawer, fidelity scoring hooks | Surface as diagnostic |

## Immediate On-Ramp

Before continuing feature work, use this audit to lock the next roadmap sequence:

1. Phase 1.7 stabilization:

   - stabilize tone/personality regression with a small repair pass for missing required style anchors;
   - Workbench review UI for support-pattern candidates is implemented;
   - isolated support-pattern fixture eval now verifies accepted/rejected
     guidance release boundaries;
   - keep archive material out of confirmed memory until reviewed.

2. Phase 1.8 contradiction disposition governance:

   - first-pass disposition labels are implemented in conflicted query packets:
     resolvable, held, evolving, contextual, stale, policy-bound;
   - saved trace packets, prompt restrictions, and memory review affordances now
     surface disposition label/reason/confidence without releasing restricted
     evidence values;
   - exact conflicted profile lookups now produce deterministic review-style
     answers;
   - opt-in eval cases now cover resolvable, held, evolving, contextual, stale,
     and policy-bound fixture conflicts;
   - `scripts/run_disposition_fixture_eval.py` creates an isolated temporary
     sidecar fixture for those cases and does not touch live memory.

3. Phase 1.9 memory-state/representation compression evals:

   - add representation compression replay bench inspired by `C:/filecompression` and CogniForge;
   - compare raw, summary, PCA/SVD, quantization, learned codec, and structured scaffold;
   - score behavior survival, not just vector reconstruction.

4. Phase 2 meaning trace graph:

   - connect traces, memory candidates, contradiction dispositions, route choices, compression decisions, and reviewed reflections.

5. Phase 2 background consolidation heartbeat:

   - implement a governed Mirus-style learner loop over recent turns/traces;
   - propose user/project/work context candidates, speaking-cadence/support-style
     candidates, contradiction review candidates, and Aether self-improvement
     reflections;
   - require review before applying any durable memory or behavior change;
   - treat failed routes, thin answers, over-governance, missed tone, wrong
     tools, and repair fallback as self-improvement evidence;
   - first safe slices exist as a pure candidate planner in
     `aether-core/aether/sidecar/consolidation.py` and a preview-only API at
     `/v1/consolidation/candidates`;
   - preview candidates include `review_route` metadata for Memory, Support, or
     Reflection surfaces; next add Workbench review affordances.

## Already Existing Enough To Avoid Rebuilding

Do not rebuild these from old code:

- legacy Flask compression API;
- old all-in-one Lumi/CRT assistant shell;
- old web frontend/API;
- raw FAISS memory stores without current governance;
- old mythology-heavy identity modules;
- arbitrary learned file compression.

Use old code only as evidence or inspiration unless an eval proves a current gap.

## Current Best Next Implementation Task

The Phase 1.7 repair pass now has fresh split full-lane verification:

```text
core 9/9 + depth 4/4 + programming 6/6 + real-use 6/6 = 25/25
```

The support-pattern import/list/detail/review API exists, accepted support
patterns now feed governed Context Bridge/prompt behavior, and Workbench now has
a Support review drawer for filtering and accepting/deferring/rejecting
candidates. Phase 1.8 has started: conflicted trace packets now carry
first-pass contradiction disposition labels and Workbench shows them in the
Trace drawer. Prompt contracts, memory review affordances, deterministic
conflicted direct answers, opt-in eval cases for all six first-pass
dispositions, and the isolated temporary-sidecar fixture runner are now
implemented; the fixture runner also caught and repaired an `old_employer`
planner ambiguity. The isolated support-pattern fixture lane is also
implemented and verifies accepted guidance is released while rejected guidance
is excluded. The Phase 2 background consolidation / governed Mirus learner plan
now has a first safe implementation slice: a pure review-only candidate planner
that proposes contradiction review, support-style, project-context, and Aether
self-improvement candidates from supplied turns/traces without persisting
anything. A preview-only sidecar endpoint now reads recent traces and returns
those candidates without writes. Preview candidates now include `review_route`
metadata for existing Memory/Support/Reflection review surfaces. The next
concrete task is Workbench UI affordances for reviewing those previewed
candidates without applying them directly.

Why this first:

- It directly improves Nick's real use style.
- It turns measured/blocked contradiction into visible governed state.
- It is smaller than memory-state compression replay and sets up that work.
- It gives the automation a clean continuation target.

## Automation Instruction

When the heartbeat resumes, it should:

1. read this integration audit;
2. avoid more broad artifact diving unless a missing concept requires a specific file;
3. continue the main roadmap from Phase 1.8 contradiction disposition
   governance;
4. update continuity docs when a concept moves from "missing/weak" to implemented/tested.

## Bottom Line

The recovered artifacts are useful if they become robustness mechanisms.

The path forward is:

```text
translate concepts -> map to current Aether -> implement/evaluate small pieces
-> keep what improves robustness -> retire what does not
```

The main roadmap can resume now.
