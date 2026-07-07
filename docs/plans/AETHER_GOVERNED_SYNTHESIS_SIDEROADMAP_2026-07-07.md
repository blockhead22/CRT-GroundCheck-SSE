# Aether Governed Synthesis Side-Roadmap - 2026-07-07

## Purpose

This is the side-roadmap for the issue exposed by live Workbench dogfooding:

```text
Aether can prevent some local-model hallucinations with deterministic final
answers, but too many deterministic final answers make the system feel canned,
regexy, and conceptually shallow.
```

The goal is not to remove deterministic governance. The goal is to put it in
the right position:

```text
deterministic governance builds the contract
model/Holden renders inside the contract
CRT verifies the rendered answer
Workbench shows the trace
```

Operating thesis:

```text
Aether should be deterministic about truth boundaries and generative about
human-facing synthesis.
```

That is the practical distinction between deterministic governance and
epistemic governance. Deterministic governance can keep the same input on the
same rule path. Epistemic governance must also preserve what evidence was used,
what uncertainty remains, what synthesis was allowed, what the model rendered,
what drifted, and why the final answer survived verification.

## Problem Statement

Deterministic governance is a mechanism. Epistemic governance is the goal.

Current failure mode:

```text
prompt shape -> route match -> fixed final answer
```

That can be correct and safe, but it often proves only that the harness can
return a policy card. It does not prove that Aether can synthesize across
memory, archive evidence, project documents, uncertainty, and user intent.

Desired mode:

```text
intent classification
-> evidence retrieval
-> Mirus answer spine
-> Holden/model render
-> CRT verifier / repair / fallback
-> Thinking trace
```

## What Must Stay Deterministic

These are still good deterministic-final lanes:

- exact confirmed-memory lookup;
- unresolved memory boundary;
- explicit memory-write acknowledgement;
- source/tool receipt;
- current-event/no-live-data boundary;
- sensitive insufficient-evidence boundary;
- verifier failure / fallback explanation.

These should stay crisp and boring.

## What Should Become Governed Synthesis

These should not remain fixed prose cards:

- CRT / CORE / epistemic integrity explanations;
- Aether purpose and why the system matters;
- deterministic governance vs epistemic governance;
- personal color/flower/health-symbolism relationship prompts;
- state-parks project and Mill Bluff significance;
- GPT/archive theme analysis and follow-ups;
- business/grant/project synthesis;
- personality/voice questions;
- any multi-fact prompt where the user asks how ideas relate.

## Proof Before Product Wiring

Build a small lab before changing Workbench behavior:

```text
labs/meaning_compression_lab/governed_synthesis_lab.py
```

It should compare:

```text
canned deterministic answer
raw local-model style answer
governed spine + rendered answer + verifier
```

The lab should score:

- correctness;
- governance boundary;
- synthesis across multiple evidence nodes;
- cannedness / repeated-card feel;
- unsupported claim avoidance;
- formatting readability;
- Aether voice.

The lab should prove the oldest useful methodology in the system:

```text
Mirus does not produce prose. Mirus produces a spine.
Holden/model does not decide what is true. Holden renders from the spine.
CRT does not only block scary outputs. CRT verifies rendered language against
the spine.
The trace does not only say "tool used." It shows evidence, allowed synthesis,
forbidden claims, render mode, verifier result, and repair/fallback.
```

## Initial Prompt Pack

Start with 6-8 cases:

1. `Is deterministic governance the same as epistemic governance?`
2. `Aether, describe epistemic integrity and what CRT tries to solve.`
3. `Aether, what is your purpose in relation to my favorite color, and why does that matter to AI?`
4. `What is my favorite flower and why?`
5. `Why does Mill Bluff matter to my state parks project?`
6. `Using GPT logs, what do you think holds me back?`
7. `Search this project for where memory candidates are created. Name exact files only.`
8. `Search the GPT logs for my medical history. Source-bound archive hits only.`

## Success Criteria

Governed synthesis is worth product wiring when:

- it beats canned and raw baselines on total score;
- it does not invent acronym expansions or unsupported facts;
- it preserves archive/project/memory authority boundaries;
- it connects at least two relevant evidence nodes for synthesis prompts;
- it does not collapse compound prompts into one-slot lookup;
- it produces readable sections or bullets where helpful;
- verifier flags can catch raw-model drift and overclaiming;
- no memory/support/reflection writes happen from the lab.

## First Product Slice After Lab

If the lab passes, wire one narrow route:

```text
CRT / deterministic governance / epistemic governance explanation prompts
```

Implementation target:

```text
build answer spine from code/docs/trace concepts
render with local model
verify forbidden claims
fallback to deterministic boundary only if render fails
show spine + verifier in Thinking drawer
```

## First Product Slice - Implemented

Implemented the first narrow route in the sidecar:

```text
D:\AI_round2\aether-core\aether\sidecar\character_answer.py
```

Change:

```text
CRT / epistemic integrity / CORE architecture questions no longer return a
deterministic final-answer card. They now return character `generative_guidance`.
The local model renders the answer from that guidance, and the existing
character repair check catches generic answers, invented CRT/CORE acronym
expansions, and missing architecture anchors.
```

Guarded required anchors:

```text
evidence / inference
uncertainty / contradiction
authority / confirmed state
governance around the model
governed substrate slots
Context Bridge
Mirus review-only candidates
verifier / repair / fallback
visible trace receipts
no invented CRT or CORE acronym expansion
```

Verification:

```text
python -m pytest aether-core\tests\test_sidecar_character_answer.py aether-core\tests\test_sidecar_quality_dogfood.py -q
38 passed

python -m pytest tests\test_governed_synthesis_lab.py tests\test_generative_governance_lab.py -q
15 passed
```

Boundary:

```text
This only changes the conceptual CRT/epistemic architecture lane. Direct
confirmed-memory lookups, unresolved memory boundaries, tool receipts, current
event boundaries, and other crisp deterministic surfaces stay deterministic.
That keeps governance deterministic where truth boundaries matter while allowing
the model to synthesize where the user is asking for concepts to be related.
```

## Anti-Goals

- Do not remove safety boundaries.
- Do not let local model own truth.
- Do not store hidden chain-of-thought.
- Do not auto-write memory/support/reflection.
- Do not turn GPT archive into confirmed profile truth.
- Do not solve cannedness by adding bigger canned cards.

## Roadmap Relationship

This is adjacent to, and supportive of, the main Aether roadmap.

Main roadmap:

```text
governed memory -> trace/review candidates -> Workbench dogfood -> Aeteros Core
```

Side-roadmap:

```text
governed memory + evidence -> governed synthesis -> verified natural answers
```

This lane is the bridge between "Aether knows things safely" and "Aether can
explain and relate things without sounding like a routed FAQ."

## J-Space / Global Workspace Convergence

The separate J-space/global-workspace thread should keep working independently
until both lanes have something concrete to exchange.

This governed-synthesis lane owns:

```text
old Aether concepts -> tension-aware answer spine -> product-facing behavior
```

The J-space lane owns:

```text
workspace research -> evidence that external structure helps small models
```

The intentional convergence point is:

```text
Tension Packet / Workspace Spine
```

Working definition:

```text
A source-bounded external workspace object that can hold evidence nodes,
allowed inferences, unresolved tensions, forbidden collapses, route intent,
and verifier expectations before the model renders prose.
```

Expected Aether-side result:

- answers are less canned than deterministic cards;
- multiple facts/concepts can be composed without one-slot collapse;
- contradiction can be held as tension when both sides may matter;
- trace shows evidence, allowed synthesis, forbidden collapse, render mode,
  verifier result, and repair/fallback;
- no memory/support/reflection writes occur without review.

Expected J-space-side result:

- raw local model loses task shape, collapses tension, or overclaims;
- external workspace/spine improves concept reuse or held-tension behavior;
- wrong workspace/spine cases are caught instead of blindly obeyed.

If both sides succeed on shared cases, the next Workbench product step is:

```text
Workbench-visible Tension Packet / Answer Spine preview in the Thinking trace.
```

## Lab Checkpoint - v2

Implemented:

```text
D:\AI_round2\labs\meaning_compression_lab\governed_synthesis_lab.py
D:\AI_round2\tests\test_governed_synthesis_lab.py
D:\AI_round2\labs\meaning_compression_lab\results\governed_synthesis_lab_v2.json
```

Current v2 cases:

```text
deterministic_vs_epistemic_governance
crt_epistemic_integrity
purpose_color_ai
archive_personal_blockers
flower_orange_health_boundary
state_parks_mill_bluff
sensitive_archive_medical_summary
code_search_memory_candidates
```

The lab compares:

```text
canned deterministic final
raw model-style answer
governed spine + render + verifier
```

Current result:

```text
governed synthesis wins all 8 cases
no memory writes
no support/reflection writes
no raw chain-of-thought storage
```

Verification:

```text
python -m pytest tests\test_governed_synthesis_lab.py -q
10 passed

python -m pytest tests\test_governed_synthesis_lab.py tests\test_generative_governance_lab.py -q
15 passed
```

Important limitation:

```text
The deterministic governed renderer proves the structure, not the product
experience. The next layer is the model render adapter: Mirus builds a spine,
Holden/model renders from it, CRT verifies the answer, and repair/fallback
only runs when the rendered language drifts.
```

## Lab Checkpoint - qwen2.5 7B Render Adapter

Implemented:

```text
model render prompt builder
model repair prompt builder
Ollama adapter
model and model_initial result tracking
same verifier used for deterministic and model renders
```

Artifact:

```text
D:\AI_round2\labs\meaning_compression_lab\results\governed_synthesis_lab_qwen25_repair_v0.json
```

Result:

```text
model: qwen2.5:7b-instruct
cases: 8
initial model renders passed: 6/8
repair-closed failures: 2/2
final model pass count: 8/8
memory/support/reflection writes: false
raw hidden chain-of-thought stored: false
```

What this proves:

```text
A small local model can render more natural answers from a governed answer
spine when the system owns evidence, required claims, forbidden claims, and
the boundary contract.
```

What this does not prove yet:

```text
This is still a lab pack, not a Workbench route. The pass count should not be
treated as broad product readiness until it survives live prompts, new blind
cases, and UI trace review.
```

## Lab Checkpoint - Tension Packet / Workspace Spine v0

Implemented the first Aether-side convergence shape:

```text
TensionSide
TensionPacket
AnswerSpine.tension_packet
render_spine_only_answer baseline
held_tension_score in the verifier
```

Artifact:

```text
D:\AI_round2\labs\meaning_compression_lab\results\governed_synthesis_lab_tension_packet_v0.json
```

New held-tension cases:

```text
tension_local_models_frontier_wedge
tension_archive_evidence_not_memory
tension_personal_aether_general_core
tension_personality_without_fake_intimacy
```

What changed:

```text
The lab now distinguishes "mentions both facts" from "holds the tension."
Plain governed spine renders can include the evidence, but they only receive
partial held-tension credit unless they explicitly mark the held tension,
allowed synthesis, forbidden collapse, and trace preview.
```

Current result:

```text
case_count: 12
overall passed: true
tension cases: 4/4 packet-aware governed renders passed
spine_only held_tension_score: 0.45 on each held-tension case
packet-aware held_tension_score: 1.0 on each held-tension case
memory/support/reflection writes: false
raw hidden chain-of-thought stored: false
```

Verification:

```text
python -m pytest tests\test_governed_synthesis_lab.py -q
12 passed

python -m pytest tests\test_governed_synthesis_lab.py tests\test_generative_governance_lab.py -q
17 passed
```

Interpretation:

```text
This is the first concrete import of the old Aether belief-map / structural
tension idea into the governed synthesis lane. It does not claim the product is
ready. It proves a narrow lab distinction: an explicit tension/workspace packet
can preserve both sides of a live contradiction better than a normal answer
spine that merely lists the evidence.
```

Next useful bridge:

```text
Run a model-render pass against the tension cases, then decide whether a small
Thinking-trace preview should show the packet as "Held tension" before any
Workbench behavior uses it.
```

## Lab Checkpoint - qwen2.5 Tension Packet Render v1

Artifact:

```text
D:\AI_round2\labs\meaning_compression_lab\results\governed_synthesis_lab_qwen25_tension_packet_v1.json
```

Result:

```text
model: qwen2.5:7b-instruct
cases: 12
model pass count: 12/12
tension packet cases: 4/4
tension packet held_tension_score: 1.0 on all 4
memory/support/reflection writes: false
raw hidden chain-of-thought stored: false
```

Important finding:

```text
The first Qwen pass against tension packets failed the held-tension verifier
because the model preserved the general idea but omitted explicit public trace
labels such as Allowed synthesis and Forbidden collapse. Tightening the render
and repair prompt to require a Held Tension section with exact public labels
closed the issue.
```

Interpretation:

```text
Small-model rendering can preserve old Aether-style held tension when the
external workspace packet is explicit enough. The packet does not need hidden
chain-of-thought; it needs source-bounded sides, allowed synthesis, forbidden
collapse, and trace preview lines that the renderer can carry forward.
```

Next useful product-facing step:

```text
Do not wire broad runtime behavior yet. Add a narrow Workbench Thinking-trace
preview shape for tension/workspace packets, or route one focused conceptual
prompt through this shape behind a test fixture first.
```
