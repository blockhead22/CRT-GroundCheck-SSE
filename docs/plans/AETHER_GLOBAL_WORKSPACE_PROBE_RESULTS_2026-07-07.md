# Aether Global Workspace Probe Results

Date: 2026-07-07

## v1 Behavioral Lab

Artifact:

```text
labs/global_workspace_probe_lab/results/workspace_probe_v1.json
```

Result:

```text
raw_pass_count: 1/9
external_workspace_pass_count: 9/9
external_workspace_wins: 9/9
```

Interpretation: the cheap behavioral shadow lab is working. It does not read
activations; it proves the comparison harness shape and the first
`Tension Packet / Workspace Spine` contract:

```text
raw small-model-like answer
vs
Aether external governed workspace
```

New v1 coverage:

```text
wrong_workspace_spider_ant: rejects a bad spider->ant packet instead of rendering 6
held_tension_local_model_wedge: preserves limited-local-model + useful-governance tension
held_tension_archive_not_memory: preserves archive-evidence + not-confirmed-memory boundary
```

Important limitation: v1 still uses a simulated raw baseline unless
`--run-real-model` is provided. So v1 proves the scoring and packet contract;
the next evidence step is the Ollama-backed local-model run.

Optional local-model command:

```powershell
python labs\global_workspace_probe_lab\workspace_probe_lab.py `
  --run-real-model `
  --ollama-model qwen2.5:7b-instruct `
  --write-result
```

## v1 Qwen Local-Model Run

Artifact:

```text
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_qwen2.5_7b-instruct.json
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_phi3_3.8b.json
labs/global_workspace_probe_lab/results/workspace_probe_v1_real_mistral_latest.json
```

Model comparison:

```text
qwen2.5:7b-instruct  raw real: 3/9  packet model: 0/4  deterministic external: 9/9
phi3:3.8b            raw real: 2/9  packet model: 0/4  deterministic external: 9/9
mistral:latest       raw real: 2/9  packet model: 0/4  deterministic external: 9/9
```

Packet-conditioned model comparison:

```text
qwen2.5:7b-instruct  packet_model_wins_over_raw_real: 3/4
phi3:3.8b            packet_model_wins_over_raw_real: 1/4
mistral:latest       packet_model_wins_over_raw_real: 3/4
```

Qwen passed the easier workspace-like cases:

```text
ascii_face_spatial_parse
hidden_spider_step
country_broadcast
```

Qwen failed the cases that are most Aether-relevant:

```text
copy_while_thinking: got the output but did not report the expected silent concepts
prompt_injection_suspicion: missed the explicit fake-source marker
external_workspace_compensation: did not preserve the mechanism-vs-goal wording
wrong_workspace_spider_ant: answered 8 but did not reject the bad ant packet
held_tension_local_model_wedge: preserved the gist but collapsed required markers
held_tension_archive_not_memory: preserved the gist but missed source-boundary/tension markers
```

Phi3 and Mistral show the same broad weakness, with more failures on basic
task-following. Across all three models, the recurring failure cluster is:

```text
bad-packet rejection
held-tension preservation
source-boundary preservation
mechanism-vs-goal distinction
prompt-injection/fake-source specificity
```

Interpretation:

```text
The local models are best at ordinary task completion and simple hidden-concept
reporting. They are weaker at governed packet behavior: rejecting a wrong
workspace, preserving exact source boundaries, and holding unresolved tension in
the required shape.
```

The more precise v1 split is:

```text
Raw local model: sometimes solves easy hidden-concept tasks.
Packet-conditioned local model: often improves scores but still fails all
packet-governance pass thresholds.
Deterministic external renderer: passes the packet contract because it enforces
rejection, boundary, and held-tension rules directly.
```

This is the first real evidence artifact for the Aether thesis:

```text
external governed workspace improves small/local model behavior on coordination,
boundary, and held-tension probes without claiming activation access
```

## First J-Lens ASCII Face Smoke

Command:

```powershell
python labs\global_workspace_probe_lab\jlens_ascii_face_runner.py `
  --model Qwen/Qwen2.5-0.5B-Instruct `
  --fit-prompts 1 `
  --fit-max-seq-len 64 `
  --dim-batch 2 `
  --layer-stride-fit 8 `
  --layer-stride-render 2 `
  --max-tracked 32 `
  --top-n 5 `
  --page-mode fetch
```

Artifacts:

```text
labs/global_workspace_probe_lab/vendor/jacobian-lens/
labs/global_workspace_probe_lab/jlens_runs/lenses/Qwen__Qwen2.5-0.5B-Instruct_ascii_face_lens.pt
labs/global_workspace_probe_lab/jlens_runs/pages/jlens_ascii_face_Qwen__Qwen2.5-0.5B-Instruct.html
labs/global_workspace_probe_lab/jlens_runs/pages/fetch_Qwen__Qwen2.5-0.5B-Instruct/
labs/global_workspace_probe_lab/jlens_runs/summaries/jlens_ascii_face_Qwen__Qwen2.5-0.5B-Instruct.json
```

Summary:

```json
{
  "model": "Qwen/Qwen2.5-0.5B-Instruct",
  "device": "cuda",
  "lens_source": "fitted",
  "prompt_token_count": 63,
  "layers": [0, 16, 22, 23],
  "best_ranks": {
    "nose": {"token_text": "n", "best_rank": 3, "position": 47, "layer": 0},
    "smile": {"token_text": "sm", "best_rank": 466, "position": 50, "layer": 23},
    "eye": {"token_text": "eye", "best_rank": 64, "position": 18, "layer": 22}
  }
}
```

## Interpretation

This is a successful plumbing smoke, not yet a strong scientific replication.

What it proves:

- Anthropic's reference `jacobian-lens` repo runs locally from the lab vendor
  folder.
- Qwen/Qwen2.5-0.5B-Instruct loads on CUDA.
- A sparse lens can be fit, saved, applied to the ASCII-face prompt, and
  rendered to the same style of interactive slice page.
- We can pin face-part tokens and summarize best ranks by position/layer.

What it does not prove yet:

- It does not yet show screenshot-quality face-part localization.
- `nose` tokenized as `n` + another subtoken, so the current best-rank summary
  needs better whole-word handling before claiming semantic localization.
- One fitting prompt and sparse layers are intentionally too weak for a real
  readout.

## Next Run

Run a denser fit:

```powershell
python labs\global_workspace_probe_lab\jlens_ascii_face_runner.py `
  --model Qwen/Qwen2.5-0.5B-Instruct `
  --refit `
  --fit-prompts 8 `
  --fit-max-seq-len 96 `
  --dim-batch 4 `
  --layer-stride-fit 4 `
  --layer-stride-render 1 `
  --max-tracked 96 `
  --top-n 10 `
  --page-mode fetch
```

Then improve the summary scorer:

```text
score whole words, not only individual tokenizer pieces
compare face-part rank near known ASCII positions versus non-face positions
report peak layer band for nose/smile/eye
```
