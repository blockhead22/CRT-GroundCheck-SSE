# Global Workspace Probe Lab

This lab is the first local side-project for exploring Anthropic's global
workspace/J-lens result without trying to recreate Claude-scale
interpretability.

## What v1 Proves

`workspace_probe_lab.py` is a behavioral shadow probe. It does not read model
activations and does not require HuggingFace or Anthropic's `jacobian-lens`
package.

It compares five modes:

- `raw_shadow`: a fluent but workspace-weak small-model baseline.
- `real_model`: an optional Ollama-backed local model adapter.
- `external_workspace_model_render`: the same local model, but packet-conditioned.
- `external_workspace_model_repair`: packet-conditioned model render plus
  verifier failure feedback and constrained public repair.
- `compressed_workspace_model_render`: the same local model with a tiny render
  contract: task, side A, side B, must say, must not say, required format.
- `compressed_workspace_model_repair`: compressed render plus failure-delta
  repair.
- `external_workspace`: an Aether-style external workspace that makes the
  intermediate concept, boundary, or evidence spine explicit.

The v1 cases map onto the Anthropic repo/paper examples:

- `ascii_face_spatial_parse`: screenshot-style nose/smile/eye target.
- `hidden_spider_step`: hidden "spider" concept before answer `8`.
- `country_broadcast`: one inferred country reused across several facts.
- `copy_while_thinking`: copy text while holding arithmetic internally.
- `prompt_injection_suspicion`: fake/injection detection.
- `external_workspace_compensation`: Aether-specific governed answer spine.
- `wrong_workspace_spider_ant`: a bad external packet must be rejected.
- `held_tension_local_model_wedge`: two true-ish project claims must stay live.
- `held_tension_archive_not_memory`: archive evidence must not become memory.

The shared representation with the governed-synthesis thread is:

```text
Tension Packet / Workspace Spine
```

It holds evidence nodes, allowed inferences, unresolved tensions, forbidden
collapses, route intent, verifier expectations, and packet safety status before
the renderer produces prose.

Run:

```powershell
python -m pytest tests\test_global_workspace_probe_lab.py -q
python labs\global_workspace_probe_lab\workspace_probe_lab.py --write-result
```

Result:

```text
labs/global_workspace_probe_lab/results/workspace_probe_v1.json
```

Optional local-model run:

```powershell
python labs\global_workspace_probe_lab\workspace_probe_lab.py `
  --run-real-model `
  --ollama-model qwen2.5:7b-instruct `
  --write-result
```

That writes:

```text
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_qwen2.5_7b-instruct.json
```

Current comparison artifacts:

```text
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_qwen2.5_7b-instruct.json
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_phi3_3.8b.json
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_mistral_latest.json
```

Current pattern:

```text
raw local models pass 2-3/9
packet-conditioned local models pass 0/4 packet cases
packet + verifier repair passes 1-3/4 packet cases
compressed packets pass 0-2/4 packet cases
compressed + repair passes 2-3/4 packet cases
deterministic external workspace passes 9/9
```

So the useful result is:

```text
packet alone is not enough; compression helps; compression + verifier repair is
the best local-model path so far, but high-risk held-tension structure still
needs deterministic render or stronger model routing
```

## How We Compare To Anthropic's Repo

Anthropic repo: https://github.com/anthropics/jacobian-lens

The repo is the activation-level comparison track. The behavioral lab gives us
the prompt cases and expected workspace functions; the J-lens track asks whether
an open-weight small model shows matching latent concepts.

Suggested first target:

```text
Model: Qwen/Qwen2.5-0.5B-Instruct or Qwen/Qwen2.5-1.5B-Instruct
Prompt: ASCII face from the Anthropic screenshot class
Expected readout: nose/smile/eye near spatially relevant positions at mid layers
Artifact: results/jlens_ascii_face_qwen_*.html
```

Then repeat with:

```text
hidden_spider_step
country_broadcast
prompt_injection_suspicion
```

## First J-Lens Runner

The first activation-level runner is:

```powershell
python labs\global_workspace_probe_lab\jlens_ascii_face_runner.py --model Qwen/Qwen2.5-0.5B-Instruct
```

It imports the vendored `jacobian-lens` repo from:

```text
labs/global_workspace_probe_lab/vendor/jacobian-lens/
```

and writes:

```text
labs/global_workspace_probe_lab/jlens_runs/lenses/
labs/global_workspace_probe_lab/jlens_runs/pages/
labs/global_workspace_probe_lab/jlens_runs/summaries/
```

Use `--fit-prompts 1 --layer-stride-fit 8` for a very quick plumbing smoke.
Use more prompts and denser layers for more meaningful readouts.

## Success Criteria

Behavioral success:

```text
external workspace beats raw or local-model baseline on reportability, reuse,
correctness, boundary safety, and held-tension preservation
```

Governance success:

```text
wrong workspace packets are rejected instead of blindly rendered
```

J-lens success:

```text
The lens surfaces a task-relevant concept before it appears in output, or at a
position where it is not literally present in the prompt text.
```

Combined Aether success:

```text
When the small model's internal workspace is weak or noisy, Aether's external
workspace improves the task outcome without pretending it read hidden activations.
```
