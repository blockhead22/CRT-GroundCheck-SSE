# Aether Lab Pause Checkpoint - 2026-07-07

## Why This Exists

This checkpoint freezes the current lab state before opening another side lane.
The project has several adjacent threads now:

- governed synthesis / tension packets;
- J-space / global workspace packet repair;
- Mirus belief-map substrate;
- local reasoning-model preference and public reasoning trace exploration.
- dueling rollercoaster model/governance comparison.

The important boundary is that these are related, but not the same task.

## Current Main Lab Lane

```text
Aether should be deterministic about truth boundaries and generative about
human-facing synthesis.
```

Current proof points:

- governed synthesis lab passed with answer spines and repair;
- tension packet / workspace spine v0 exists;
- qwen2.5:7b-instruct can preserve held tension when the public packet is
  explicit enough;
- Workbench can render tension packet preview in Thinking / Trace surfaces;
- narrow runtime route exists for reflective governance prompts.

Primary doc:

```text
docs\plans\AETHER_GOVERNED_SYNTHESIS_SIDEROADMAP_2026-07-07.md
```

## Current Mirus Lane

The Mirus belief-map lab is started and should be treated as the next substrate
bridge, not as live Workbench behavior.

Current result:

```text
labs\mirus_belief_map_lab\results\mirus_belief_map_1783467086.json

events: 10
passed: 10
safety_passed: 10
nodes: 15
edges: 12
proposals: 12
```

It models:

- weighted meaning nodes;
- evidence receipts;
- support/refinement/contradiction/stale/route-performance edges;
- stability and tension scores;
- preview-only "why Aether thinks this" objects;
- review-only promote, hold-tension, ask-user, freeze-route, prune-pattern,
  and keep-archive-bounded proposals.

Safety boundary:

```text
review_required=true
auto_apply=false
memory_write_allowed=false
support_write_allowed=false
reflection_write_allowed=false
```

Primary doc:

```text
docs\plans\AETHER_MIRUS_BELIEF_MAP_LAB_2026-07-07.md
```

## Reasoning-Model Aside

This aside is useful if it remains a comparison lab.

Local model preference was updated:

- default: `qwen3:14b`;
- reasoning-preferred: `qwen3:14b`, `deepseek-r1:latest`,
  `deepseek-r1:8b`;
- fast standard fallback: `qwen2.5:7b-instruct`;
- code model: `qwen2.5-coder:14b`.

This does **not** mean the project is now model-shopping. The useful question is:

```text
Can a governed workspace hold attention well enough that a smaller standard
model can reason over denser context, and where does coherence break compared
to a reasoning model?
```

Primary doc:

```text
docs\plans\AETHER_LOCAL_REASONING_MODEL_POLICY_2026-07-07.md
```

The concrete harness for that comparison is:

```text
docs\plans\AETHER_DUELING_ROLLERCOASTER_LAB_2026-07-07.md
labs\dueling_rollercoaster_lab\dueling_rollercoaster_lab.py
```

Current scripted result:

```text
case_count: 4
matrix_row_count: 76
public_reasoning_trace_only: true
raw_hidden_chain_of_thought_stored: false
writes_performed: false
```

Current live Ollama result:

```text
artifact:
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783469470_rescored.json

raw_model and standard_rag: no pass across the dense cases
scaffolded_public_reasoning: improves shape but does not pass
governed_scaffolded_repair: reasoning models 4/8 avg 0.8135
qwen3:14b governed repair: 3/4 avg 0.9187
qwen2.5:7b-instruct governed repair: 0/4 avg 0.7031
deepseek-r1:8b governed repair: 1/4 avg 0.7084
deterministic ceiling: 4/4 avg 0.9750
```

Decision:

```text
The aside is useful and no longer purely theoretical. It shows governance and
repair materially improve local model behavior, but it also shows that dense
held-tension/source-boundary answers still need either qwen3-level local
rendering, deterministic external rendering, or a better compressed packet +
repair contract.
```

Latest harness update:

```text
compressed_governed_repair mode exists
semantic_passed is separated from trace_marker_passed
scripted matrix passes 76 rows
focused live compressed packet run completed
artifact:
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783480697_rescored.json
qwen2.5 compressed governed repair: 0/4 pass, 1/4 semantic pass
qwen3 compressed governed repair: 0/4 pass, 1/4 semantic pass
focused live hybrid packet run completed
artifact:
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783481422_rescored.json
qwen2.5 hybrid governed repair: 0/4 pass, 0/4 semantic pass
qwen3 hybrid governed repair: 4/4 pass, 4/4 semantic pass
```

Decision:

```text
Compression alone is too lossy. Do not replace full governed packets with the
compact packet. The next variant should be a hybrid packet: compact evidence
plus explicit held-tension and public-trace skeleton.

The hybrid packet worked for qwen3:14b and did not work for qwen2.5:7b-instruct.
Use that as the current routing lesson: qwen3 is the local dense-synthesis
renderer; qwen2.5 remains a fast/simple/direct-route model.
```

## One-More-Round Result - Side-Roadmap Convergence

The hybrid-packet lesson was pulled back into the governed synthesis side
roadmap as a focused local-model render test.

Artifact:

```text
labs\meaning_compression_lab\results\governed_synthesis_lab_qwen3_hybrid_tension_v1.json
```

Result:

```text
qwen3:14b hybrid governed-spine render + repair: 5/5
held_tension_score: 1.0 on all focused cases
memory/support/reflection writes: false
raw hidden chain-of-thought stored: false
```

Decision:

```text
The useful Workbench-facing pattern is not longer prompts. It is compact
evidence, an explicit public held-tension skeleton, and verifier-delta repair.
This should graduate only into routes that already have a tension_packet or
governed answer spine. Broad conceptual routing still waits for dogfood.
```

## Is The Aside Helpful?

Yes, with limits.

Helpful:

- It tests the same thesis from another angle: model reasoning improves when
  governance holds the workspace, evidence boundaries, and repair loop.
- It gives a clean comparison between standard local models, reasoning local
  models, and deterministic external workspace ceilings.
- It can expose whether public reasoning traces help or hurt coherence.

Not helpful if:

- it becomes broad model shopping;
- it replaces Mirus map work;
- it stores raw hidden chain-of-thought as truth;
- it treats reasoning-model output as authority instead of evidence to verify.

## Recommended Pickup Order

1. Finish the current pause/checkpoint.
2. If returning to main roadmap: add a fixture-backed Workbench preview for the
   Mirus belief-map `render_belief_preview(...)` output.
3. If pursuing the aside: promote the hybrid packet shape into the governed
   synthesis side-roadmap and keep qwen3 as the main local renderer for dense
   synthesis. This is now done for the focused lab path; next step is a narrow
   Workbench route only if live dogfood needs it.
4. Do not wire reasoning traces into runtime until the lab shows whether they
   improve or destabilize answers.

## Verification At Pause

Latest verification from this session:

```powershell
python -m pytest aether-core\tests\test_sidecar_route_policy.py aether-core\tests\test_sidecar_app.py -q
# 75 passed

npm test -- --run App.test.tsx
# 54 frontend/electron tests passed

python -m pytest tests\test_mirus_belief_map_lab.py tests\test_learned_mirus_scorer_lab.py -q
# 16 passed
```

Sidecar was restarted and `/v1/models` reported:

```text
default: qwen3:14b
model_count: 14
```
