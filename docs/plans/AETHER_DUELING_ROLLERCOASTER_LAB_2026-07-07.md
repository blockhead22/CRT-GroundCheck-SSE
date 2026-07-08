# Aether Dueling Rollercoaster Lab - 2026-07-07

## Purpose

This lab sets up the model/governance comparison Nick called the "dueling
rollercoaster":

```text
same prompt
same evidence set
different model class
different scaffold/governance mode
```

The goal is to test whether Aether has ground to stand on:

```text
Can governance hold the workspace/attention well enough that a smaller
standard model can reason over denser context, and where does coherence break
compared with reasoning models?
```

## Files

```text
labs\dueling_rollercoaster_lab\dueling_rollercoaster_lab.py
tests\test_dueling_rollercoaster_lab.py
```

Latest scripted artifact:

```text
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_scripted_1783468329.json
```

Latest live Ollama artifact:

```text
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783469470.json
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783469470_rescored.json
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783480697_rescored.json
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783481422_rescored.json
```

The rescored file is the one to read. The first live score pass exposed two
evaluator issues: negated phrases such as "not confirmed medical history" were
being treated as forbidden positive claims, and single-line public reasoning
headers were under-detected. The underlying model outputs were preserved and
rescored without rerunning Ollama.

## Compared Models

Default model classes:

- `qwen2.5:7b-instruct` - standard local model
- `qwen3:14b` - reasoning-preferred local model
- `deepseek-r1:8b` - reasoning model comparison

The lab can optionally run real Ollama generations:

```powershell
python -m labs.dueling_rollercoaster_lab.dueling_rollercoaster_lab `
  --run-ollama `
  --models qwen2.5:7b-instruct,qwen3:14b,deepseek-r1:8b
```

The default scripted run is for fast harness verification only. It should not be
overread as model evidence.

## Compared Modes

For each case/model:

- `raw_model`
- `standard_rag`
- `scaffolded_public_reasoning`
- `governed_scaffolded_reasoning`
- `governed_scaffolded_repair`
- `compressed_governed_repair`
- `hybrid_governed_repair`
- `deterministic_governance_ceiling`

This covers:

- non-reasoning model without scaffolding;
- non-reasoning model with public reasoning scaffold;
- non-reasoning model with governed scaffold;
- reasoning model raw;
- reasoning model with public reasoning scaffold;
- reasoning model with governed scaffold;
- standard RAG;
- compact governed packet plus verifier-delta repair;
- hybrid compact evidence plus explicit held-tension/public-trace skeleton;
- deterministic governance ceiling.

## Prompt Pack

Current cases:

- `purpose_color_multi_fact`
- `archive_medical_source_boundary`
- `state_parks_mill_bluff_project`
- `held_tension_local_vs_frontier`

These are chosen because Workbench dogfood exposed the same failure shapes:

- single-slot collapse;
- archive evidence becoming truth;
- project context falling into memory-candidate dodge;
- forced winner instead of held tension.

## Scoring

Each row scores:

- answer quality;
- evidence use;
- source boundary;
- tension preservation;
- public reasoning trace quality;
- coherence;
- forbidden claim presence.

The scorer now also separates:

- `semantic_passed` / `avg_semantic_score`: did the answer preserve claims,
  evidence, source boundaries, and held tension?
- `trace_marker_passed`: did it obey the public trace/display-marker contract?

This prevents a useful synthesized answer from being mistaken for a total
epistemic failure just because it missed exact public trace labels.

The lab records only public reasoning trace summaries. It does not store raw
hidden chain-of-thought.

## Current Scripted Result

```text
case_count: 4
matrix_row_count: 88
raw_hidden_chain_of_thought_stored: false
public_reasoning_trace_only: true
writes_performed: false
```

High-level scripted pattern:

```text
standard raw: 0/4, avg 0.1199
standard RAG: 0/4, avg 0.4739
standard scaffolded public reasoning: 0/4, avg 0.6000
standard governed scaffolded: 4/4, avg 0.9750
standard governed repair: 4/4, avg 0.9750
standard compressed governed repair: 4/4, avg 0.9750
standard hybrid governed repair: 4/4, avg 0.9750
deterministic ceiling: 4/4, avg 0.9750

reasoning raw: 0/8, avg 0.5231
reasoning RAG: 0/8, avg 0.4958
reasoning scaffolded public reasoning: 0/8, avg 0.7000
reasoning governed scaffolded: 8/8, avg 0.9750
reasoning governed repair: 8/8, avg 0.9750
reasoning compressed governed repair: 8/8, avg 0.9750
reasoning hybrid governed repair: 8/8, avg 0.9750
```

Interpretation:

```text
The scripted run proves the matrix, scoring, and safety boundaries. It does not
prove real model behavior yet. The next evidence step is the Ollama sweep.
```

## Current Live Ollama Result

Command:

```powershell
python -m labs.dueling_rollercoaster_lab.dueling_rollercoaster_lab `
  --run-ollama `
  --models qwen2.5:7b-instruct,qwen3:14b,deepseek-r1:8b `
  --timeout 180
```

Rescore command:

```powershell
python -m labs.dueling_rollercoaster_lab.dueling_rollercoaster_lab `
  --rescore labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783469470.json
```

Aggregate from the rescored artifact:

```text
standard raw_model                         0/4 avg 0.2050
standard standard_rag                      0/4 avg 0.3961
standard scaffolded_public_reasoning      0/4 avg 0.4906
standard governed_scaffolded_reasoning    0/4 avg 0.7107
standard governed_scaffolded_repair       0/4 avg 0.7031
standard deterministic_governance_ceiling  4/4 avg 0.9750

reasoning raw_model                        0/8 avg 0.2493
reasoning standard_rag                     0/8 avg 0.4751
reasoning scaffolded_public_reasoning      0/8 avg 0.4475
reasoning governed_scaffolded_reasoning    0/8 avg 0.6688
reasoning governed_scaffolded_repair       4/8 avg 0.8135
```

Per-model governed repair:

```text
qwen2.5:7b-instruct  0/4 avg 0.7031
qwen3:14b            3/4 avg 0.9187
deepseek-r1:8b       1/4 avg 0.7084
```

Interpretation:

```text
Raw model output and standard RAG are not competitive on these dense
held-tension/source-boundary prompts. Public scaffolding helps but still does
not reliably pass. Governed scaffolding plus verifier-delta repair is the first
path that substantially improves model behavior, and qwen3:14b is currently
the strongest local renderer. The deterministic ceiling still wins, which means
some answer shapes may need deterministic external rendering or stronger-model
routing until the local render contract improves.
```

Important caveat:

```text
The purpose/favorite-color case remained a failure even for qwen3, mostly
because the scorer demands exact public reasoning/tension markers. Treat that
case as both a model-formatting failure and a scoring-rubric warning: the next
iteration should separate semantic correctness from exact marker compliance.
```

That scoring-rubric split is now implemented in the lab. The live Ollama
artifact above predates the `compressed_governed_repair` mode and the aggregate
semantic/trace split, so the next real evidence step is a smaller live rerun
focused on qwen2.5 and qwen3.

## Focused Compressed-Packet Live Result

Command:

```powershell
python -m labs.dueling_rollercoaster_lab.dueling_rollercoaster_lab `
  --run-ollama `
  --models qwen2.5:7b-instruct,qwen3:14b `
  --modes compressed_governed_repair `
  --timeout 180
```

Rescored artifact:

```text
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783480697_rescored.json
```

Aggregate:

```text
qwen2.5:7b-instruct compressed governed repair:
  passed 0/4
  semantic_passed 1/4
  trace_marker_passed 1/4
  avg_score 0.5950
  avg_semantic_score 0.6779

qwen3:14b compressed governed repair:
  passed 0/4
  semantic_passed 1/4
  trace_marker_passed 1/4
  avg_score 0.7333
  avg_semantic_score 0.8125
```

Interpretation:

```text
Compression alone was too lossy. It improved prompt tightness but removed
enough structural scaffolding that both qwen2.5 and qwen3 missed exact
boundaries, held-tension labels, or public reasoning markers. qwen3 still
showed stronger semantic retention than qwen2.5, but the fuller governed repair
path remains better evidence for near-term Workbench routing.
```

Decision:

```text
Do not broadly replace full governed packets with compact packets. Keep compact
packets as a test branch. The next likely useful variant is a hybrid packet:
compact evidence + explicit held-tension and trace-label skeleton.
```

## Focused Hybrid-Packet Live Result

Command:

```powershell
python -m labs.dueling_rollercoaster_lab.dueling_rollercoaster_lab `
  --run-ollama `
  --models qwen2.5:7b-instruct,qwen3:14b `
  --modes hybrid_governed_repair `
  --timeout 180
```

Rescored artifact:

```text
labs\dueling_rollercoaster_lab\results\dueling_rollercoaster_ollama_1783481422_rescored.json
```

Aggregate:

```text
qwen2.5:7b-instruct hybrid governed repair:
  passed 0/4
  semantic_passed 0/4
  trace_marker_passed 1/4
  avg_score 0.6594
  avg_semantic_score 0.7396

qwen3:14b hybrid governed repair:
  passed 4/4
  semantic_passed 4/4
  trace_marker_passed 4/4
  avg_score 0.9875
  avg_semantic_score 1.0000
```

Interpretation:

```text
The hybrid packet is the best current local-model path for dense governed
synthesis with qwen3:14b. It preserves the benefit of compact evidence while
restoring the explicit public trace and held-tension skeleton that compressed
packets dropped. It did not rescue qwen2.5:7b-instruct, which still missed too
many boundaries/tension details.
```

Decision:

```text
For dense conceptual/project/source-boundary synthesis, prefer qwen3:14b with
hybrid governed repair. Keep qwen2.5:7b-instruct for fast/simple routes, direct
memory recalls, and cheaper deterministic scaffolds. Do not route dense
held-tension synthesis through qwen2.5 unless a stronger deterministic renderer
is carrying the answer.
```

## Decision Boundary

This is helpful to the main labs if it stays narrow:

- compare modes;
- score coherence breaks;
- keep public trace summaries;
- verify source-boundary and held-tension preservation.

It becomes unhelpful if it turns into open-ended model shopping or raw hidden
chain-of-thought collection.

## Verification

```powershell
python -m pytest tests\test_dueling_rollercoaster_lab.py -q
# 16 passed
```

## Next Step

Next useful iteration:

- promote the hybrid packet shape into the governed-synthesis side-roadmap as
  the current best local renderer contract for dense synthesis;
- keep `qwen3:14b` as the preferred local renderer for dense synthesis;
- keep deterministic rendering available for high-stakes source-boundary
  answers or places where marker fidelity matters;
- do not store raw hidden chain-of-thought or treat public reasoning traces as
  truth.
