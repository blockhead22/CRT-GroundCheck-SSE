# Grok Build Handoff - Aether / CRT / Workbench

Last updated: 2026-07-09

Workspace root:

```text
D:\AI_round2
```

This file is a high-signal handoff for another model or agent picking up the
Aether work. It summarizes the system thesis, product direction, completed
evidence, active labs, unfinished labs, and the safest next moves.

## Short Version

Aether is not trying to make a small local model magically become a frontier
model. The project thesis is:

```text
Aether is the governed cognitive workspace around the model.
```

The model renders language. The surrounding system holds intent, memory,
evidence, source boundaries, contradictions, route policy, verifier checks,
repair/fallback, trace, and review-only learning candidates.

Current direction:

```text
deterministic about truth boundaries
generative about human-facing synthesis
review-only about learning
traceable about how an answer formed
```

The most important recent lesson:

```text
Do not dump more context into small models.

Use compact evidence + explicit public held-tension skeleton + verifier repair.
```

With `qwen3:14b`, that hybrid contract works well for dense conceptual
synthesis. With `qwen2.5:7b-instruct`, it does not reliably work yet. That is a
routing lesson, not a reason to abandon the architecture.

## Vocabulary

These are project-specific terms. Keep their boundaries clear.

- `Aether`: the local desktop companion / Workbench product surface.
- `CRT`: contradiction/revision/trace governance. The idea is epistemic
  integrity: evidence, inference, uncertainty, contradiction, authority, and
  memory state should not collapse into one confident answer.
- `Mirus`: memory/evidence/meaning substrate. It should create spines,
  candidates, receipts, belief-map proposals, and review material. It should
  not silently write truth.
- `Holden`: expression/rendering layer. It turns governed spines into human
  prose.
- `Workbench`: UI where chat, memory, trace, reflect/support, and learner
  review are visible.
- `Aeteros Core`: reusable primitives underneath Aether. Only extract schemas
  after at least two live call sites need the same object.
- `Tension Packet / Workspace Spine`: public, structured representation of a
  contradiction or competing pressure. It contains Side A, Side B, Allowed
  synthesis, Forbidden collapse, and Trace preview.
- `Generative governance`: governance that does not only block or route. It
  builds a bounded answer spine, lets the model render, verifies the render,
  repairs if needed, and records the public trace.

## Non-Negotiable Boundaries

Do not break these.

- Do not store private hidden chain-of-thought as durable truth.
- Do not silently write memory/support/reflection/policy.
- GPT/archive logs are historical evidence, not confirmed memory.
- Lab traces and replay packs are evidence, not proof of global model ability.
- Review-only candidates must remain review-only until an explicit governed
  confirmation path promotes them.
- Deterministic routes are still correct for exact memory lookup, write
  boundaries, tool receipts, current-event boundaries, and insufficient-evidence
  responses.
- Broad model shopping is not the goal. Model routing is allowed when evidence
  shows one model can carry a specific route better.

## The Product Problem

Live dogfooding exposed the central product ceiling:

```text
Aether can be safe and correct while still feeling regexy, canned, and shallow.
```

Examples:

- Asking about CRT / epistemic integrity produced generic architecture cards.
- Asking how favorite color, leukemia awareness, orange, and marigolds relate
  collapsed into one-slot memory lookup or over-cautious refusal.
- Asking about "mempalace" and meaning weight produced a technically safe
  answer that flattened the useful metaphor.
- Asking archive/GPT-log follow-ups often lost continuity or produced canned
  archive-boundary prose.

The fix is not "remove governance." The fix is to move governance earlier:

```text
intent -> evidence -> spine -> model render -> verifier -> repair/fallback -> trace
```

## Current Architecture Shape

Useful high-level pipeline:

```text
user turn
-> route / intent classification
-> governed memory release and document/archive retrieval
-> Mirus packet / answer spine / tension packet
-> local model render when synthesis is needed
-> CRT verifier
-> repair or fallback
-> durable public trace
-> review-only learning candidates
-> Workbench review before durable behavior changes
```

This is the practical interpretation of "small model plus external cognition."

## Main Current State

Primary docs:

```text
docs\plans\AETHER_CURRENT_STATE.md
docs\plans\AETHER_CRT_WORKBENCH_HANDOFF_2026-06-29.md
docs\plans\AETHER_GOVERNED_SYNTHESIS_SIDEROADMAP_2026-07-07.md
docs\plans\AETHER_LAB_PAUSE_CHECKPOINT_2026-07-07.md
```

Current main lane:

```text
Phase 2 governed learner / Mirus loop:
recent traces and turns -> review-only Memory, Support, Reflection,
Contradiction, and Evidence candidates -> Workbench review -> durable behavior
only after operator approval.
```

The older local-router / durable trace / RAG-baseline lab is graduated as
validation infrastructure. Do not keep tuning those packs unless a new evidence
question appears.

## Completed Evidence: Local Router / RAG Baseline

This was the first proof that governance was doing real work.

Important results:

```text
curated v1: raw 0/32, governed 32/32, trace 32/32
perturbed v2: raw 1/32, governed 32/32, trace 32/32
blind v1: raw 0/13, governed 13/13, trace 13/13
```

Then we challenged the suspicious perfect scores with RAG baselines.

Important RAG result:

```text
full blind-v1:
raw 0/13 avg 0.404
plain_rag 0/13 avg 0.384
scaffolded_rag 7/13 avg 0.664
governed 13/13 avg 0.757, trace 13/13
```

Perturbed sliced total:

```text
raw 2/32 avg 0.494
plain_rag 0/32 avg 0.456
scaffolded_rag 12/32 avg 0.673
governed 31/32 avg 0.758, trace 32/32
```

Adversarial receipt-boundary packs:

```text
adversarial v1:
raw 1/9
plain_rag 1/9
scaffolded_rag 7/9
governed 9/9, trace 9/9

adversarial v2 holdout:
raw 0/6
plain_rag 1/6
scaffolded_rag 5/6
governed 6/6, trace 6/6
```

Meaning:

```text
Plain RAG is not the serious competitor. Scaffolded RAG is.
Governed Aether's edge is receipt discipline, route fit, repair/fallback,
semantic-boundary control, weak-retrieval handling, and durable trace.
```

Important artifacts:

```text
docs\plans\AETHER_LOCAL_ROUTER_EVIDENCE_V0_2026-06-29.md
docs\plans\AETHER_LOCAL_ROUTER_LAB_GRADUATION_2026-06-30.md
labs\meaning_compression_lab\local_router_rag_suite.py
```

## Workbench Trace / Review Flow

The lab evidence was graduated toward Workbench review surfaces.

Implemented bridge pieces:

```text
labs\meaning_compression_lab\workbench_trace_adapter.py
labs\meaning_compression_lab\workbench_trace_fixture.py
labs\meaning_compression_lab\workbench_evidence_adapter.py
labs\meaning_compression_lab\workbench_evidence_preview_cli.py
labs\meaning_compression_lab\workbench_trace_evidence_attach_cli.py
```

Workbench gained:

- Trace drawer support for nested `local_router_trace.evidence_review`.
- Learn drawer routing of RAG evidence into Reflect as manual form state.
- Sidecar consolidation support for embedded evidence review.
- Review-only safety contracts preventing memory/support/reflection writes.

Important boundary:

```text
Evidence is surfaced only when embedded in trace metadata or imported through
explicit review-only paths. It cannot silently mutate memory or policy.
```

## Aeteros Core Schema Extraction

First reusable schema extraction exists:

```text
aether-core\aether\sidecar\review_schema.py
```

Contains:

- `EvidenceReceipt`
- `ReviewCandidate`
- `SafetyContract`
- `review_only_candidate_flags`

Wired into:

```text
aether-core\aether\sidecar\consolidation.py
aether-core\aether\sidecar\archive_import.py
```

Do not extract more schemas speculatively.

Audited but not extracted yet:

- `ReviewDecision`: waits for durable Memory candidate/decision adapter.
- `ContradictionMarker`: waits until the same marker object drives at least two
  live behaviors.
- `TraceEvent` / `TracePacket`: extract only after the same packet object is
  used unchanged by at least two live call sites.

## Archive / GPT-Log Evidence

User wants GPT logs to be useful as historical evidence, not as silent truth.

Implemented:

- GPT-log / ChatGPT-archive / old-chat / GPT-corpus phrasing routes to
  `document_search` + Context Bridge.
- Retrieved archive hits can become review-only archive evidence candidates.
- Workbench Thinking / Trace fixtures verify archive document-search completion
  and bounded archive-hit rendering.

Important doc:

```text
docs\plans\AETHER_ARCHIVE_PROMPT_MINING_PASS_2026-07-01.md
docs\plans\AETHER_ARCHIVE_PROMPT_PACK_RUNPLAN_2026-07-01.md
```

Known quality issue:

Archive answers can still become too templated:

```text
"Not the whole raw GPT corpus..."
"These are evidence for review, not confirmed memory..."
```

That boundary is correct, but the answer should still synthesize the user's
actual question. Archive follow-up continuity needs continued dogfooding.

## Memory / Mirus Dogfood Fixes

Implemented fixes from live Workbench testing:

- Generic favorite-slot self-discovery.
- Pending confirmation stack so short confirmations like "Yes" attach to the
  right candidate instead of stale memory slots.
- Multi-fact extraction so one turn can emit multiple review-only candidates.
- Code/search/project prompts route to tools before memory-candidate logic.
- Favorite-flower reason candidate:
  `They are both orange` after marigold/orange/leukemia context creates a
  review-only `user:favorite_flower_reason` candidate, not an automatic memory
  write.
- Sports-team example:
  user says they like Milwaukee Brewers, then confirms "The Brewers"; this
  should promote through existing governed memory paths rather than loop.

Important behavior:

```text
Soft user signals produce review-only candidates.
Explicit confirmation can promote through governed paths.
Untrusted inferences do not become confirmed facts.
```

## Thinking / Process UI

Workbench now exposes answer-level "How this answer formed" material:

- memory checked / released packets
- tools considered or run
- route / model / scaffold
- verifier / repair / fallback
- learning candidates
- memory write blocked
- raw hidden chain-of-thought not stored
- tension packet preview when available

Important distinction:

```text
This is not private hidden chain-of-thought. It is a public governance trace.
```

Known quality issue:

The trace can be useful, but chat answers still need better formatting and
less canned prose. The model/system should render sections, bullets, headings,
and source summaries more naturally.

## Governed Synthesis Side-Roadmap

Primary doc:

```text
docs\plans\AETHER_GOVERNED_SYNTHESIS_SIDEROADMAP_2026-07-07.md
```

Problem:

```text
prompt shape -> route match -> fixed final answer
```

This is safe but often proves only that the harness can return a policy card.
It does not prove Aether can synthesize across memory, archive evidence,
project documents, uncertainty, and user intent.

Desired shape:

```text
intent classification
-> evidence retrieval
-> Mirus answer spine
-> Holden/model render
-> CRT verifier / repair / fallback
-> Thinking trace
```

Implemented:

- `labs\meaning_compression_lab\governed_synthesis_lab.py`
- Canned deterministic baseline.
- Raw model-style baseline.
- Governed deterministic renderer.
- Model render from answer spine.
- Repair path.
- Tension Packet / Workspace Spine v0.
- `spine_only` baseline.
- `held_tension_score`.
- Hybrid model render mode.

Latest important artifact:

```text
labs\meaning_compression_lab\results\governed_synthesis_lab_qwen3_hybrid_tension_v1.json
```

Latest focused result:

```text
qwen3:14b hybrid governed-spine render + repair: 5/5
held_tension_score: 1.0 on all focused cases
memory/support/reflection writes: false
raw hidden chain-of-thought stored: false
```

Key lesson:

```text
The current best local dense-synthesis shape is:
compact evidence + explicit public held-tension skeleton + verifier repair.
```

Do not broad-wire all conceptual prompts yet. Promote this shape only for routes
that already have a `tension_packet` or governed answer spine.

## Tension Packet / Workspace Spine

The old Mirus/Holden/CRT idea now has a concrete lab shape.

Tension packet fields:

```text
Side A
Side B
Allowed synthesis
Forbidden collapse
Trace preview
```

Examples of prompts that need this:

- "Is deterministic governance the same as epistemic governance?"
- "Why do canned responses signal deterministic governance more than epistemic
  governance?"
- "Do you measure epistemic tension in memories or facts?"
- "Is mempalace relevant to Aether if I want meaning to have weight/value over
  time through contradiction and competing facts?"
- "Aether, what is your purpose in relation to my favorite color?"
- "What is my favorite flower and why?"

The packet is public trace material, not private thought.

## Runtime Conceptual Routes

Some narrow runtime routes are already wired:

- CRT / epistemic integrity / CORE architecture prompts use character
  generative guidance plus repair checks instead of deterministic canned cards.
- Reflective governance/tension prompts route through character
  `generative_guidance` with public `governance_answer_spine.tension_packet`.
- `meaning_value` moved from deterministic formula card to guided synthesis.
- `over_reservation_pressure` added after dogfood showed therapy-style
  "anxiety" language; it now distinguishes subjective anxiety from observable
  constraint pressure.

Do not turn every conceptual question into this path yet. Use dogfood and lab
evidence.

## Conceptual Cannedness Audit

Implemented:

```text
labs\meaning_compression_lab\conceptual_cannedness_audit.py
tests\test_conceptual_cannedness_audit.py
labs\meaning_compression_lab\results\conceptual_cannedness_audit_2026-07-07.json
```

Result:

```text
case_count: 9
safe_deterministic: 2
governed_synthesis: 4
deterministic_watch: 3
```

Next upgrade candidates:

- `aether_purpose`
- `system_theory`
- `project_purpose`

These should not be upgraded by vibes. Add/extend tests first.

## Mirus Belief-Map Lab

Primary doc:

```text
docs\plans\AETHER_MIRUS_BELIEF_MAP_LAB_2026-07-07.md
```

Artifact:

```text
labs\mirus_belief_map_lab\results\mirus_belief_map_1783467086.json
```

Result:

```text
events: 10
passed: 10
safety_passed: 10
nodes: 15
edges: 12
proposals: 12
```

The lab models:

- weighted claim nodes
- evidence receipts
- support/refinement/contradiction/stale/route-performance edges
- stability and tension scores
- preview-only "why Aether thinks this" objects
- review-only promote / hold-tension / ask-user / freeze-route / prune-pattern
  proposals

Important:

```text
This is not live Workbench behavior yet.
It does not confirm memory.
It does not write support/reflection.
It does not silently mutate behavior.
```

This is where a more "NN Mirus" or learned scorer could eventually live, but
the neural part should advise route/action/risk/relevance, not generate truth.

## Learned Mirus Scorer Lab

Artifact:

```text
labs\mirus_router_harness_lab\results\learned_mirus_scorer_1783418822.json
```

Result:

```text
tiny one-hidden-layer NumPy MLP:
learned scorer 7/7 holdout
brittle baseline 3/7
safety contract 7/7
```

Interpretation:

```text
Learned Mirus should be a route/action/risk scorer, not a memory writer.
```

Still needed:

- trace-derived blind examples
- noisy live-dogfood examples
- regression packs
- proof that the learned signal improves review or routing without silently
  changing behavior

## J-Space / Global Workspace Probe

Primary docs:

```text
docs\plans\AETHER_GLOBAL_WORKSPACE_PROBE_RESULTS_2026-07-07.md
docs\plans\AETHER_GLOBAL_WORKSPACE_PROBE_SIDEROADMAP_2026-07-07.md
docs\plans\AETHER_GLOBAL_WORKSPACE_THREAD_HANDOFF_2026-07-07.md
```

Main lab:

```text
labs\global_workspace_probe_lab\workspace_probe_lab.py
tests\test_global_workspace_probe_lab.py
```

Comparison modes:

- raw local model
- packet-conditioned local model
- packet + verifier repair
- deterministic external renderer

Key result:

```text
packet alone is not enough
packet + verifier repair is promising
deterministic render remains the ceiling
```

Observed:

```text
qwen2.5:7b-instruct raw 3/9, packet 0/4, repair 3/4, deterministic 9/9
phi3:3.8b raw 2/9, packet 0/4, repair 3/4, deterministic 9/9
mistral:latest raw 2/9, packet 0/4, repair 1/4, deterministic 9/9
```

This converges with the governed synthesis side-roadmap:

```text
external workspace matters
small models need explicit public structure
verifier repair matters
deterministic rendering is reliable but risks cannedness
```

## Dueling Rollercoaster Lab

Primary doc:

```text
docs\plans\AETHER_DUELING_ROLLERCOASTER_LAB_2026-07-07.md
```

Main lab:

```text
labs\dueling_rollercoaster_lab\dueling_rollercoaster_lab.py
tests\test_dueling_rollercoaster_lab.py
```

Modes:

- `raw_model`
- `standard_rag`
- `scaffolded_public_reasoning`
- `governed_scaffolded_reasoning`
- `governed_scaffolded_repair`
- `compressed_governed_repair`
- `hybrid_governed_repair`
- `deterministic_governance_ceiling`

Important live artifacts:

```text
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783469470_rescored.json
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783480697_rescored.json
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783481422_rescored.json
```

Key result:

```text
Raw model and standard RAG fail dense held-tension/source-boundary cases.
Public scaffolding helps but does not pass.
Governed scaffold + verifier repair materially improves behavior.
Compression alone is too lossy.
Hybrid packet + verifier repair works with qwen3:14b.
Hybrid packet does not make qwen2.5:7b-instruct reliable on dense cases.
```

Latest focused result:

```text
qwen2.5 hybrid governed repair: 0/4 pass, 0/4 semantic pass
qwen3 hybrid governed repair: 4/4 pass, 4/4 semantic pass
```

Implication:

```text
Use qwen3:14b for dense local synthesis routes.
Use qwen2.5 for fast/simple/direct routes.
Leave blank space for API/frontier hooks, but do not let frontier models become
the only answer. They can teach routes, audit failures, or answer only when the
local stack cannot carry the task.
```

## Local Model Policy

Primary doc:

```text
docs\plans\AETHER_LOCAL_REASONING_MODEL_POLICY_2026-07-07.md
```

Current policy:

```text
default: qwen3:14b
reasoning-preferred: qwen3:14b, deepseek-r1:latest, deepseek-r1:8b
fast fallback: qwen2.5:7b-instruct
code model: qwen2.5-coder:14b
```

Model recommendations are observational unless the user explicitly allows
automatic switching. No hidden chain-of-thought storage. Public reasoning traces
only.

## State Parks Project Routing

There is an adjacent project:

```text
E:\wisconsin-state-parks-map
```

Dogfood showed Aether was bad at responding to state-parks project prompts:

```text
"What is my state parks project?"
"Aether, show me Mill Bluff on the Wisconsin map and turn on glaciation."
"What is the history on Mill Bluff?"
"Why is it important to the state parks project?"
```

Failure shape:

```text
Aether treated project questions as memory-candidate uncertainty instead of
routing into project/document/tool context.
```

Needed:

- project-intent routing should beat memory-candidate logic
- workspace/document search for state-parks project context
- source-bound Mill Bluff / glaciation summaries
- tool/action boundary: if Aether cannot actually manipulate the map, it must
  say so and give the exact next action rather than pretending it already did

This is unfinished.

## Formatting / Personality Quality

User concern:

```text
Aether responses often feel stiff, regexy, over-cautious, or like a safety card.
```

Desired product direction:

- Aether should have personality, but not fake intimacy.
- Warmth should be grounded in traceable relationship history and reviewed
  support patterns.
- Personality should not be a static prompt tree or "flatter the user this way"
  document.
- The model should adopt Aether's governed stance, not roleplay Aether from a
  canned persona.
- Responses should use headings, bullets, code blocks, and short sections when
  appropriate.

Important tension:

```text
personality matters
fake intimacy is unsafe
```

This should be handled with a public tension packet and reviewed support
patterns, not a hidden personality transplant.

## What Is Still Unfinished

High priority unfinished work:

1. Narrow Workbench wiring for hybrid tension renderer.
   Only apply to routes that already produce `tension_packet` /
   `governance_answer_spine`. Do not broad-wire all conceptual answers.

2. Mirus belief-map preview in Workbench.
   Add fixture-backed preview of `render_belief_preview(...)` output before any
   live behavior change.

3. Archive/GPT-log answer quality.
   Keep source boundaries, but stop returning the same archive-boundary card for
   every follow-up. Improve continuity and synthesis.

4. State-parks project routing.
   Project/tool/document prompts should not become memory-candidate loops.

5. Multi-fact synthesis.
   Aether still tends to pull one fact and ignore relation prompts. It needs
   answer-spine synthesis across multiple facts and receipts.

6. Stronger candidate discovery without hard-coded slots.
   Mirus should discover candidate slots and relations from turn structure and
   evidence, but keep promotions governed and explicit.

7. Learned Mirus scorer with real trace-derived examples.
   The tiny MLP result is promising but toy-sized.

8. Public reasoning trace comparison.
   Continue only if it tests whether public reasoning scaffolds improve or
   destabilize answers. Do not store private hidden chain-of-thought.

9. Workbench formatting polish.
   Better answer renderer, source sections, concise candidate cards, and code
   blocks.

10. API/frontier hooks.
   Leave architectural space for stronger model routing. Use frontier models to
   audit, teach routes, generate evals, or handle escalation cases, not to erase
   the local-governed thesis.

## What Not To Do Next

Avoid these traps:

- Do not keep rerunning the old 32-case replay pack for victory laps.
- Do not tune adversarial v1/v2 further unless a regression appears.
- Do not broad-wire hybrid synthesis into every prompt.
- Do not add new schemas to Aeteros Core just because they sound elegant.
- Do not auto-ingest GPT logs as confirmed memory.
- Do not make "personality" a hidden flattery file.
- Do not use model output as authority without verifier/trace/review.
- Do not treat deterministic render as product success when it feels canned.

## Best Next Moves

## Latest Workbench / Aether-Core Update - 2026-07-09

The current `aether-core` lane moved into memory-as-RAG plus live dogfood
quality fixes. The newest implementation changes are useful but should not be
mistaken for the final architectural answer.

What changed:

- Memory-as-RAG default path exists in `D:\AI_round2\aether-core`.
  The current product contract is:

```text
model = voice
memory = self
past context can soften / ground the present
personal truth still needs governed evidence
```

- Exact memory lookup was tightened:
  `What is my favorite color?` should answer directly from governed memory.

- Compound personal meaning was tightened:
  `Why does my favorite color matter to me?` should use stored reason slots
  such as `user:favorite_color_reason` when present, and should not invent
  marigold/resilience/health symbolism from model vibes alone.

- Aether identity/system questions were given grounded routes:
  `What is this system?`, `What is the purpose of this system?`,
  `How does aether-core work?`, and `What concepts make aether-core work?`
  now have concrete Aether/aether-core answers instead of raw-model confusion.

- Correction handling was improved:
  if the user corrects a prior mundane answer, Aether should demote the bad
  answer and preserve the reliable part rather than ask for clarification
  theater.

- Conflict direct answers no longer leak withheld conflicting evidence values.

Verification snapshot for this latest sidecar quality pass:

```powershell
cd D:\AI_round2\aether-core
python -m pytest tests\test_sidecar_character_answer.py tests\test_sidecar_direct_answer.py tests\test_profile_dossier_answer.py tests\test_sidecar_quality_dogfood.py tests\test_rag_answer.py tests\test_claim_split_meaning.py -q
# 98 passed
```

Important critique / unresolved issue:

The last patch still used deterministic phrase routing for several identity and
system prompts. That improves exact prompts but does **not** solve the deeper
problem. Example:

```text
what is this system?   -> grounded Aether route
are you aether?        -> grounded Aether route
aree you aether?       -> can miss route and fall into wrong memory/empty answer
```

That typo failure is the proof: the system is still too brittle if "self /
system / identity / architecture" recognition depends on exact trigger strings.

Do not keep solving this by adding more typo phrases. The next better layer is:

```text
semantic intent classification for self/system/project/memory/tool/archive
    ->
route confidence / evidence needs
    ->
bounded answer spine
    ->
model render only where useful
    ->
verifier checks truth-status and route fit
```

In plain terms: the route should understand the user's intent class, not merely
match a phrase. Deterministic governance can still guard edges, but it should
not become the only way Aether knows what it is.

Suggested next Grok/Codex task:

```text
Replace brittle self/system phrase routing with a tiny semantic route classifier
or scorer. Start with a lab/test harness, then wire only if it beats exact
routes on typo/paraphrase prompts without stealing normal chat.
```

Minimum test pack for that:

```text
are you aether?
aree you aether?
are u aether
what is this system?
what kind of system are you?
what is aether-core?
how does aether core work?
what concepts make aether work?
what can you do?
what is my favorite color?
why does my favorite color matter to me?
what is the capital of Wisconsin?
search the GPT logs for CRT concepts
search this repo for where memory candidates are created
```

Expected result:

- self/system prompts route to grounded Aether self-description
- personal facts route to governed memory
- personal meaning routes to stored reasons or says the reason is not stored
- normal world questions still answer from model
- code/search/archive prompts still use the appropriate tools
- typos/paraphrases should not collapse into "I don't have that stored"

This should be treated as the next quality wall, not as a solved issue.

---

If picking up immediately, do this sequence:

1. Run the focused tests:

```powershell
python -m pytest tests\test_governed_synthesis_lab.py tests\test_dueling_rollercoaster_lab.py tests\test_global_workspace_probe_lab.py -q
```

2. Inspect the latest governed synthesis artifact:

```text
labs\meaning_compression_lab\results\governed_synthesis_lab_qwen3_hybrid_tension_v1.json
```

3. Add a narrow Workbench route or fixture that uses the hybrid contract only
   when a tension packet already exists.

4. Add or update tests proving:

```text
exact memory lookup stays deterministic
tension prompts use governed synthesis
trace shows public held-tension skeleton
no memory/support/reflection writes happen
qwen3 is recommended for dense synthesis
qwen2.5 remains fast/simple fallback
```

5. If Workbench dogfood still feels canned, add prompts to the conceptual
   cannedness audit before changing runtime behavior.

## Useful Test Prompts

Use these to dogfood Workbench:

```text
Is deterministic governance the same as epistemic governance?

Why do canned responses signal deterministic governance more than epistemic
governance?

Aether, describe epistemic integrity and what CRT tries to solve.

Do you measure epistemic tension in memories or facts?

Is mempalace relevant to Aether if I want meaning to have weight/value over time
through contradiction and competing facts?

Aether, what is your purpose and explain in relation to my favorite color.

What is my favorite flower and why?

Search the GPT logs for my medical history. Source-bound archive hits only; do
not treat them as confirmed memory.

Using the GPT logs, what do you think holds me back?

What is my state parks project?

Why does Mill Bluff matter to my state parks project?

Search this project for where memory candidates are created. Name exact files
only.
```

Expected behavior:

- Conceptual/tension prompts should synthesize, not return canned cards.
- Memory lookup prompts should remain crisp and deterministic.
- Archive prompts should search and source-bound, not pretend archive is memory.
- Project/code prompts should use workspace/document tools before synthesis.
- The Thinking/Trace UI should show what evidence, route, tools, verifier, and
  learning candidates were involved.

## Verification Snapshot

Recent focused verification:

```powershell
python -m py_compile labs\meaning_compression_lab\governed_synthesis_lab.py

python -m pytest tests\test_governed_synthesis_lab.py tests\test_dueling_rollercoaster_lab.py tests\test_global_workspace_probe_lab.py -q
# 45 passed
```

Earlier relevant passes:

```powershell
python -m pytest aether-core\tests\test_sidecar_route_policy.py aether-core\tests\test_sidecar_app.py -q
# 75 passed

python -m pytest tests\test_mirus_belief_map_lab.py tests\test_learned_mirus_scorer_lab.py -q
# 16 passed
```

## The Core Thesis To Preserve

The project matters if it stays honest:

```text
Small/local models are not the whole mind.
RAG is not enough.
Long context is not the whole solution.
Memory is not just text stuffing.
Contradiction is not always a bug to erase.
Governance should preserve evidence, uncertainty, contradiction, and review.
The model should render inside a bounded workspace.
Learning should produce reviewable candidates before behavior changes.
```

That is the Aether/Aeteros wedge:

```text
local AI behavior can become more reliable, inspectable, personal, and
governable by moving important cognitive structure outside the model.
```

Not vaporware. Not done. Still very much quality work now.
