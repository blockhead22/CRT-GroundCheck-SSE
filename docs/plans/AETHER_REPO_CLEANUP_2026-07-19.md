# Aether Repo Cleanup - 2026-07-19

Branch:

```text
codex/repo-cleanup-archive
```

## Goal

Clean the root repo without destroying high-leverage experimental work:

- keep live source and current Aether/Workbench docs visible
- archive dated handoffs, model-synthesis notes, and historical result logs
- stop tracking generated/runtime payloads
- preserve useful generated artifacts locally when they may still help
- remove private database backup files from the working tree

## Commit Checkpoints

```text
71550224e chore: ignore nested external worktrees
d8d10817f chore: untrack ignored generated artifacts
46b0c8438 chore: clean root scratch artifacts
04595ea1f docs: archive dated root notes
1b5fed979 docs: archive runtime logs and benchmark outputs
a77340c3a chore: untrack paper experiment outputs
3585f814b chore: remove tracked generated payloads
```

## What Changed

Root-level clutter was reduced to current entry points:

```text
README.md
ROADMAP.md
CHANGELOG.md
ACTION_EXECUTION.md
requirements.txt
```

Historical notes were moved into tracked archive folders:

```text
docs/archive/local-router-lab-2026-06/
docs/archive/grok-research-2026-07/
docs/archive/legacy-prompts-2026-03/
docs/archive/personal-handoff-2026-05/
docs/archive/root-notes-2026/
docs/archive/adapter-judgment-logs-2026/
docs/archive/vilt-benchmark-results-2026-02/
```

Old root diagnostic helpers were moved to:

```text
tools/archive/legacy-root-scratch/
```

Generated/runtime payloads were removed from Git tracking and ignored:

```text
aether-core/
labs/mempalace_lab/mempalace/
labs/global_workspace_probe_lab/vendor/
labs/global_workspace_probe_lab/jlens_runs/
labs/**/results/
papers/**/output/
adapter_logs/
benchmark_results/
workspace/uploads/
compression_lab/*.pkl
compression_lab/vectors*.npy
compression_lab/vectors*_meta.json
```

Private database wipe backups were removed from the working tree and ignored:

```text
*.db.wipe_backup*
```

## Preserved Locally But No Longer Tracked

These generated artifacts were intentionally kept on disk where applicable but
removed from Git:

- compression lab response/vector payloads
- global workspace probe `jlens_runs`
- paper experiment `output`
- workspace upload images
- local-router/lab result JSON under ignored result folders

## Boundaries

Do not treat this cleanup as a decision to delete experimental source.
The following remain tracked because they are still useful research/source
areas, even if not all are live product code:

- `labs/meaning_compression_lab/`
- `labs/global_workspace_probe_lab/` source files
- `belief_variance_experiment/` source and findings
- `compression_lab/` source and summary docs
- `papers/compression_experiment/` source files
- Workbench and sidecar integration code

Do not run Git object pruning or destructive history rewrite without a separate
explicit decision. The working tree is cleaner now, but the existing Git object
store may still be large until normal maintenance or a deliberate history
cleanup is chosen.

## Verification

Focused Aether tests:

```text
python -m pytest tests\test_generative_governance_spike.py tests\test_generative_governance_render_compare.py tests\test_generative_governance_trace_memory.py tests\test_generative_governance_live_renderer.py tests\test_generative_governance_lab.py tests\test_local_router_cli.py -q
```

Result:

```text
50 passed
```

Compile checks passed for:

```text
papers\compression_experiment\*.py
compression_lab\sensitivity_experiment.py
compression_lab\sensitivity_experiment_scale.py
labs\global_workspace_probe_lab\jlens_ascii_face_runner.py
```

Tracked-ignored check:

```text
git ls-files -ci --exclude-standard
```

Result:

```text
0 tracked ignored files
```
