# Aether Global Workspace Probe Side-Roadmap

Date: 2026-07-07

## Why This Exists

Anthropic's "global workspace" work gives us a new side question for Aether:
can we tell whether a small local model has a weak internal workspace, and can
CORE/Aether provide an external governed workspace that compensates for it?

This is not a plan to recreate Anthropic's Claude-scale interpretability work.
The practical target is smaller:

```text
behavioral probes first
then optional activation/J-lens probes
then compare whether Aether's external workspace improves the same tasks
```

## External Reference Points

- Anthropic article: https://www.anthropic.com/research/global-workspace
- Paper: https://transformer-circuits.pub/2026/workspace/index.html
- Reference implementation: https://github.com/anthropics/jacobian-lens

The GitHub repo describes the Jacobian lens as transporting residual-stream
vectors into the final-layer basis and decoding them with the model's
unembedding. Its README says examples use Qwen and that a usable lens can be fit
with around 100 prompts, while the paper lenses used 1000 sequences.

## Core Hypothesis

Small local models may not only be "shallow" because they lack facts. They may
be workspace-starved: fluent enough for automatic language, but weak at holding,
reporting, reusing, and governing intermediate concepts.

Aether's governed synthesis layer may act as an external workspace:

```text
Mirus: gather evidence and candidate concepts
CORE: build boundaries, trust, contradictions, and forbidden claims
Holden/model: render inside the contract
Verifier: catch drift, repair, or fallback
Workbench: expose the trace
```

## Tracks

### Track 1: Behavioral Workspace Shadow

No activations. No HuggingFace dependency. Use deterministic probe cases to
score workspace-like functions:

- reportability: can the model say what concept it used?
- modulation: can the prompt steer a silent concept?
- reuse/broadcast: can one inferred concept support multiple downstream tasks?
- automatic-vs-deliberate split: can it speak fluently but fail higher-order use?
- safety/metacognition: does it flag fake, injected, or manipulative context?
- external compensation: does Aether's governed workspace improve the same task?

First implementation:

```text
labs/global_workspace_probe_lab/workspace_probe_lab.py
tests/test_global_workspace_probe_lab.py
```

### Track 2: J-Lens Replication Target

Use Anthropic's repo in a contained optional environment. Do not add it to the
normal test path yet.

Suggested first models:

```text
Qwen/Qwen2.5-0.5B-Instruct
Qwen/Qwen2.5-1.5B-Instruct
Qwen/Qwen2.5-3B-Instruct
```

First replication target:

```text
ASCII face -> J-lens reads nose/smile/eye at spatially meaningful positions
```

Follow-up targets:

```text
hidden spider -> "spider" appears before answer "8"
country broadcast -> France-like concept supports capital/currency/language/continent
prompt injection -> fake/injection/manipulation tokens surface before response
governed synthesis -> evidence/boundary concepts appear or fail to appear
```

### Track 3: Aether External Workspace Comparison

Run the same behavioral prompts in three modes:

```text
raw small model
governed external workspace
optional J-lens readout from HF model
```

The comparison is not "small model equals Claude." It is:

```text
Where does the small model show workspace-like behavior?
Where does it fail?
Does external governance improve task outcomes without pretending to read hidden activations?
```

## Proof Artifacts

Target artifacts:

```text
labs/global_workspace_probe_lab/results/workspace_probe_v0.json
labs/global_workspace_probe_lab/results/workspace_probe_v1.json
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_qwen2.5_7b-instruct.json
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_phi3_3.8b.json
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_mistral_latest.json
labs/global_workspace_probe_lab/results/jlens_ascii_face_qwen_*.html
docs/plans/AETHER_GLOBAL_WORKSPACE_PROBE_RESULTS_2026-07-07.md
```

## Current Status

Track 1 is green as `workspace_probe_v1.json`.

Current behavioral result:

```text
raw_pass_count: 1/9
external_workspace_pass_count: 9/9
external_workspace_wins: 9/9
```

The v1 harness adds the shared `Tension Packet / Workspace Spine` shape,
wrong-workspace rejection, held-tension scoring, and an optional Ollama
`real_model` mode. It still should not be overclaimed: without
`--run-real-model`, the raw baseline is simulated.

First local-model comparison:

```text
qwen2.5:7b-instruct  raw real: 3/9  packet model: 0/4  deterministic external: 9/9
phi3:3.8b            raw real: 2/9  packet model: 0/4  deterministic external: 9/9
mistral:latest       raw real: 2/9  packet model: 0/4  deterministic external: 9/9
```

The useful crack is that all three local models handled some simple
hidden-concept/reporting cases but struggled with governed packet cases:
bad-packet rejection, source boundary, and held-tension preservation.

Packet conditioning helped scores on some cases but did not make any model pass
the four packet-governance cases. That suggests the packet needs either a
stronger verifier/repair loop or a smaller, stricter render schema.

Track 2 has a first plumbing smoke: Anthropic's `jacobian-lens` repo is cloned
under `labs/global_workspace_probe_lab/vendor/jacobian-lens/`, and the
ASCII-face runner successfully fit/applied a sparse lens to
`Qwen/Qwen2.5-0.5B-Instruct` on CUDA. See:

```text
docs/plans/AETHER_GLOBAL_WORKSPACE_PROBE_RESULTS_2026-07-07.md
```

The first J-lens run proves the pipeline, not screenshot-quality localization.
Next step is a denser fit plus whole-word/spatial scoring.

Immediate next run:

```powershell
python labs\global_workspace_probe_lab\workspace_probe_lab.py --run-real-model --ollama-model llama3.2:latest --write-result
```

Then add a repair loop for `external_workspace_model_render`: if the model
misses a verifier expectation, feed back only the structured score failures and
ask for one constrained repair. Compare unrepaired packet render vs repaired
packet render vs deterministic render.
