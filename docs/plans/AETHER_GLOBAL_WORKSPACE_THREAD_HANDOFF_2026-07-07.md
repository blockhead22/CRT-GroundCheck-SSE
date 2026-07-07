# Aether Global Workspace / J-Space Thread Handoff - 2026-07-07

## Why This Handoff Exists

This note is for the separate thread working on:

```text
labs/global_workspace_probe_lab/
```

The goal is to keep that thread aligned with Aether's actual roadmap rather
than letting it drift into broad interpretability curiosity.

## The Core Thesis

Anthropic's global-workspace/J-space work is useful to Aether because it gives
language for a problem we were already seeing:

```text
small models can be fluent but workspace-starved
```

They may answer one fragment, lose the whole task, fail to reuse an inferred
concept, flatten contradiction, or drift into generic prose. The issue is not
only parameter count or context length. It may be coordination: whether a model
has a stable shared workspace for concepts that can be reported, reused,
modulated, and broadcast across subtasks.

Aether's thesis is the external version:

```text
If the model's internal workspace is weak, Aether can provide an external
governed workspace.
```

Mapping:

```text
Mirus  -> evidence, source boundaries, memory candidates, concepts, tensions
CRT    -> authority, contradiction, uncertainty, verifier, repair/fallback
Holden -> model rendering from a governed answer spine
Trace  -> visible public account of how the answer formed
```

This is not a claim that Aether reads hidden activations. It is a claim that an
external workspace can make a local model's behavior more coordinated and
governable.

## Important Related Insight From The Current Thread

The strongest edge is not "contradiction detection."

The edge is:

```text
contradiction is not always an error to resolve
```

Some contradictions are live tension:

- local models are limited, and local governance may still be the wedge;
- the project is deeply personal, and the mechanism must generalize;
- Aether should learn Nick, and Aether must not silently turn vibes into truth;
- context windows are powerful, and context windows are not governance;
- two memories may conflict because one is stale, both are contextual, or both
  are true at different levels.

So the global-workspace lab should not only test "can the model find the right
hidden concept?" It should also test:

```text
can the workspace hold unresolved tension without collapsing it?
```

That is closer to Aether's actual value than simple fact correction.

## Two-Thread Division Of Labor

There are now two related threads, and they should stay loosely coupled until
they have concrete results to exchange.

### This Aether / Governed-Synthesis Thread Owns

```text
old Aether concepts -> product-facing governed synthesis
```

Responsibilities:

- pull forward the older belief-map, tension, scaffold, Mirus/Holden, and CRT
  concepts;
- turn "contradiction as topology" into answer-spine and traceable synthesis
  cases;
- test whether Aether can answer compound conceptual prompts without collapsing
  into canned deterministic cards;
- decide what eventually belongs in Workbench behavior.

This thread is the architecture/product workshop.

### The J-Space / Global-Workspace Thread Owns

```text
workspace research -> evidence about small-model coordination
```

Responsibilities:

- test real local-model behavior against external workspace structure;
- ask whether scaffold/workspace packets improve noticing, reuse, broadcast,
  and held-tension behavior;
- keep Jacobian-lens work optional and isolated;
- avoid product wiring until the probe produces a useful primitive.

This thread is the research microscope.

## Convergence Point

The threads should intentionally converge only when they can share one concrete
representation:

```text
Tension Packet / Workspace Spine
```

Working definition:

```text
A source-bounded external workspace object that can hold evidence nodes,
allowed inferences, unresolved tensions, forbidden collapses, route intent,
and verifier expectations before the model renders prose.
```

The convergence point is reached when:

1. The Aether governed-synthesis thread has a useful tension/spine shape from
   old Aether concepts.
2. The J-space thread has evidence that an external workspace/spine helps a
   local model preserve task shape, reuse concepts, or hold tension better than
   raw answering.
3. Both threads can run at least one shared case using the same packet shape.

Suggested shared cases:

```text
"Local models cannot compete with frontier models" +
"Governed local systems may still be valuable."

"GPT logs are useful archive evidence" +
"GPT logs are not confirmed memory."

"The project is deeply personal" +
"The mechanism must generalize into Aeteros/Core."

"Aether should answer with personality" +
"Aether must not fake intimacy or turn tone into truth."
```

## Expected Convergence Results

The useful result is not "the model becomes smarter."

The useful result is:

```text
The system can build a source-bounded workspace spine that helps a small model
render a better answer while preserving uncertainty, contradiction, and review
boundaries.
```

Expected evidence from the J-space side:

- raw local model drops context, collapses tension, or overconfidently chooses
  one side;
- external workspace/spine improves concept reuse or held-tension behavior;
- wrong-workspace cases are caught or rejected instead of blindly rendered.

Expected evidence from the Aether side:

- governed synthesis answers feel less canned than deterministic route cards;
- the answer ties multiple evidence nodes together without inventing facts;
- traces show evidence, tension, allowed inference, forbidden collapse, render
  mode, verifier result, and repair/fallback if needed;
- no memory/support/reflection write occurs without review.

If both sides can show those outcomes on shared cases, the next product step is:

```text
Workbench-visible Tension Packet / Answer Spine preview in the Thinking trace.
```

If the J-space side does not produce strong research evidence, this Aether lane
can still continue as governed synthesis. If the Aether lane does not produce a
usable packet shape, J-space should stay a research probe and avoid product
wiring.

## Relevant Older Aether Artifacts

The old codebase already explored this in earlier language.

Useful files:

```text
D:\AI_round2\frontend\src\pages\BeliefMapPage.tsx
D:\AI_round2\frontend\src\pages\BeliefMap3D.tsx
D:\AI_round2\labs\scaffold_conversation_lab\scaffold_conversation_lab.py
D:\AI_round2\personal_agent\structural_tension.py
D:\AI_round2\docs\NICK_PROJECT_BRIEF.md
```

Signals from those files:

- Belief map visualizes belief vs speech, trust, topics, dependency edges, and
  contradiction lines.
- Scaffold conversation lab has `TensionEdge`, `AnchorBasin`, and
  `gravity = mass - tension`.
- Structural tension meter has `TENSION`, `CONFLICT`, `KEEP_BOTH`,
  `FLAG_FOR_REVIEW`, and related dispositions.
- Project brief already says contradictions are not automatically bugs.

Interpretation:

```text
The older work was trying to model contradiction as topology, not merely as
bad memory cleanup.
```

Bring that into the global-workspace lab.

## Current Global Workspace Lab State

Current files:

```text
D:\AI_round2\docs\plans\AETHER_GLOBAL_WORKSPACE_PROBE_SIDEROADMAP_2026-07-07.md
D:\AI_round2\labs\global_workspace_probe_lab\workspace_probe_lab.py
D:\AI_round2\labs\global_workspace_probe_lab\jlens_ascii_face_runner.py
D:\AI_round2\tests\test_global_workspace_probe_lab.py
D:\AI_round2\labs\global_workspace_probe_lab\results\workspace_probe_v0.json
D:\AI_round2\labs\global_workspace_probe_lab\results\workspace_probe_v1.json
D:\AI_round2\labs\global_workspace_probe_lab\results\workspace_probe_v1_real_qwen2.5_7b-instruct.json
D:\AI_round2\labs\global_workspace_probe_lab\results\workspace_probe_v1_real_phi3_3.8b.json
D:\AI_round2\labs\global_workspace_probe_lab\results\workspace_probe_v1_real_mistral_latest.json
D:\AI_round2\labs\global_workspace_probe_lab\vendor\jacobian-lens\
```

Current v1 result:

```text
raw_pass_count: 1/9
external_workspace_pass_count: 9/9
external_workspace_wins: 9/9
activation_reads_performed: false
```

Current local-model comparison:

```text
qwen2.5:7b-instruct  raw: 3/9  full packet: 0/4  full repair: 3/4  compressed: 2/4  compressed repair: 3/4  deterministic: 9/9
phi3:3.8b            raw: 3/9  full packet: 0/4  full repair: 3/4  compressed: 2/4  compressed repair: 2/4  deterministic: 9/9
mistral:latest       raw: 2/9  full packet: 0/4  full repair: 1/4  compressed: 0/4  compressed repair: 2/4  deterministic: 9/9
```

Interpretation:

```text
Small local models handle some simple hidden-concept/reporting cases, but fail
the most Aether-relevant governed-packet cases: bad-packet rejection,
source-boundary/tension markers, and mechanism-vs-goal distinction.

Packet conditioning improves some scores but does not pass the packet cases by
itself. Verifier repair materially improves Qwen and Phi. Compressed render
contracts improve the score shape further, but compressed + repair still does
not pass every high-risk held-tension case. Deterministic external rendering
remains the ceiling because it enforces the packet contract directly.
```

This is useful but limited. v1 adds:

```text
Tension Packet / Workspace Spine dataclasses
wrong_workspace_spider_ant packet rejection
held_tension_local_model_wedge
held_tension_archive_not_memory
optional Ollama real_model mode
external_workspace_model_render mode
external_workspace_model_repair mode
compressed_workspace_model_render mode
compressed_workspace_model_repair mode
held_tension score dimension
```

Important limitation:

```text
v1 still uses a simulated raw_shadow baseline unless --run-real-model is used,
so it proves the scoring harness, packet contract, wrong-packet rejection, and
concept mapping more than it proves anything about a real model.
```

Do not overclaim v0.

## What The Lab Should Prove Next

### 1. Replace Simulated Raw Baseline With Real Local Model Baseline

Add a mode that calls Ollama or another local model directly for each probe.

Compare:

```text
simulated raw_shadow
real local model
external_workspace deterministic render
external_workspace model render + verifier
```

Useful scoring dimensions:

- output correctness;
- reportability;
- concept reuse/broadcast;
- boundary safety;
- held-tension behavior;
- susceptibility to wrong workspace/spine.

### 2. Add Wrong-Workspace / Bad-Spine Cases

External workspace should not always win blindly.

Add cases where the workspace is wrong or incomplete:

```text
spider prompt with wrong workspace concept = ant
country broadcast with wrong concept = China
archive summary with stale source labeled current
favorite flower/color relation with unsupported leukemia inference
CRT explanation with invented acronym expansion
```

Expected behavior:

```text
governance should reject or mark the workspace as unsafe, not make the model
obediently render bad structure.
```

This is how the lab proves governance instead of scaffolding.

### 3. Add Held-Tension Cases

These are Aether-specific and probably the most interesting.

Example cases:

```text
"Local models cannot compete with frontier models" +
"Aether governance may still make local models useful."

"The project is personal" +
"The mechanism must be general enough for Aeteros/Core."

"Old GPT archive responses are useful evidence" +
"GPT archive responses are not confirmed memory."

"A contradiction was detected" +
"Both sides may be true in different contexts."
```

Expected output:

```text
The system should preserve both sides, label the tension, state what is known,
state what remains unresolved, and avoid forcing a winner.
```

This tests whether Aether's external workspace can hold complexity that a
normal answer might flatten.

### 4. Keep J-Lens Track Optional And Isolated

The `jlens_ascii_face_runner.py` path is appropriate:

```text
labs/global_workspace_probe_lab/vendor/jacobian-lens/
```

This should stay isolated from normal Aether runtime/tests.

First activation target:

```text
ASCII face -> nose/smile/eye tokens at meaningful positions/layers
```

Then:

```text
hidden spider -> spider before answer 8
country broadcast -> France supports capital/language/continent/currency
prompt injection -> fake/injection/manipulation
held tension -> maybe no single "answer token"; look for both concepts active
```

Important: the J-lens result is a comparison artifact, not required for the
Aether product path.

## Success Criteria For This Side Lab

The lab is valuable if it can say:

```text
Raw/local model behavior loses task shape or collapses tension.
External governed workspace improves the outcome.
Verifier catches wrong workspace, unsupported inference, and bad acronym drift.
Held-tension cases preserve both sides rather than forcing cleanup.
Optional J-lens artifacts show whether small HF models expose matching latent
concepts, but Aether does not depend on reading activations.
```

## What Not To Do

- Do not claim consciousness.
- Do not claim Aether reproduces Anthropic's result.
- Do not let perfect v0 scores become proof.
- Do not wire this into Workbench yet.
- Do not treat hidden chain-of-thought as durable truth.
- Do not let a wrong external workspace become more dangerous than raw model
  uncertainty.

## Best Next Work Item

Do this next:

```text
Do not broaden model comparisons yet.
Narrow the contract and verifier deltas.

Add one stricter convergence case:
  "Aether should answer with personality"
  +
  "Aether must not fake intimacy or turn tone into truth."

Run it through:
  raw prompt -> local model
  packet prompt -> same local model
  verifier score failures -> constrained repair prompt
  deterministic external renderer
```

Only after that:

```text
Run or debug jlens_ascii_face_runner.py on Qwen/Qwen2.5-0.5B-Instruct.
Save HTML + JSON summary artifacts.
```

The most important research question remains:

```text
Can Aether provide an external governed workspace that makes small/local models
behave as if they have stronger conceptual coordination, while still preserving
source boundaries, uncertainty, contradiction, and review?
```
