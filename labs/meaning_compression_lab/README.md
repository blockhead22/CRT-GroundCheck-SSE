# Meaning Compression Lab

> Frozen 2026-06-19: validated planner, bounded retrieval, governance release
> decisions, confirmation, and quarantine have graduated into `aether-core`.
> This directory remains the evaluation record and regression source.

Offline toy lab for testing one concrete claim:

> Meaning-preserving compression should keep deterministic layered structure,
> not merely reconstruct the original text.

See `STATUS.md` for the current evidence snapshot and `ROADMAP.md` for the
proof plan and next priorities.

The frozen grading, baseline, severity, trace, and falsification rules for the
next phase are in [`EVALUATION_CONTRACT.md`](EVALUATION_CONTRACT.md).

The lab compares several representations across five deterministic scenarios:

- identity flip
- employer correction
- provisional/social authority boundary
- locked policy constraint
- concern/preference preservation

An optional adversarial starter pack adds ten harder fixture scenarios:

- provisional/social favorite color contradicted by later confirmed user fact
- answer-style preference revision
- current project flip and reversion
- stale location correction
- destructive-command locked policy
- previous-value history question
- contradiction-status question
- multi-fact correction
- model-generated identity contamination
- tool-inferred location noise

An optional hardening pack adds four layer-specific ablation probes:

- camera-system history question
- confirmed store platform versus provisional Shopify suggestion
- provisional favorite-color response rule
- production database write-path policy requiring an isolated SQLite mock test

It can also replay a real CRT SQLite memory DB by reading the persisted
`memories` and `memory_facts` tables. That path is for checking whether actual
`CRTMemorySystem.store_memory(...)` writes can be reduced into the same
deterministic meaning-state schema.

Reports include an evidence label per scenario:

- `fixture`: hand-authored deterministic lab fixture
- `crt_db_replay`: scenario reconstructed from persisted CRT SQLite rows

The DB replay path uses persisted `memory_facts` for user facts. Locked
force-push policy replay is intentionally narrow: it projects only the existing
lab claim, `Never force push to main`, from a locked `ops` memory row. It is not
a general policy parser.

Each scenario compares:

- full transcript
- naive summary
- slot-only state
- CRT-style compressed state
- damaged CRT variants

The primary score is structural. The lab reduces the source event stream into a
canonical meaning state, projects each compressed representation into that same
schema, and checks deterministic invariants:

- current facts
- history/supersession
- preserved contradictions
- authority boundaries
- policy locks
- volatility
- reaction policy
- bit-level flags

Projection/behavior checks are secondary sanity checks. The headline result is
the aggregate structural score and meaning density across scenarios.

Behavior bridge tests live outside this toy lab. They verify that the same CRT
claims govern user-visible RAG answers:

```bash
python -m pytest tests/test_crt_rag_behavior_bridge.py -q
```

### Spiral Synthesis Eval (updated for current sidecar)
`spiral_synthesis_eval.py` now targets the hybrid governed synthesis path
(`build_hybrid_governed_prompt` + `narrative_spiral` via tension + enriched
Mirus candidates carrying `held_disposition`, `uncertainty_geometry`,
`narrative_hint`, identity anchors). Uses exact recent personal meaning prompts
(orange/marigolds + leukemia/health/memory variants + "it's okay to speculate").
Metrics now include natural_weave_score (no sections/lists/heavy hedge),
held_thread_signals, uncertainty woven. See run output for spine+held enabling
better living-thread narrative vs raw.

Run:
```powershell
$env:PYTHONPATH="D:\AI_round2\aether-core"; python -m labs.meaning_compression_lab.spiral_synthesis_eval --model phi3:3.8b --timeout 90
```
(Only edits in lab; sidecar read-only.)

Baseline comparison:

```bash
python labs/meaning_compression_lab/baseline_eval.py
python labs/meaning_compression_lab/baseline_eval.py --include-adversarial
python labs/meaning_compression_lab/baseline_eval.py --include-adversarial --include-hardening
```

This compares CRT governed state against latest-only slots, naive summary, and

## Governed Synthesis Lab (updated for Aether sidecar migration)

The `governed_synthesis_lab.py` now validates the recent CRT pre-lab ports into sidecar:
- Uses current `hybrid_governed_prompt` (pure prose, anti-template, held living thread).
- Passes/utilizes enriched Mirus candidates (uncertainty_geometry/splat variance/fat/settled, disposition=held/resolvable, held_personal_disposition, narrative_hint, identity_anchor, anchor_boost).
- Explicit "held" personal cases for orange/marigolds + leukemia awareness + memory.
- Exact prompts from logs e.g. "Orange is my favorite color and marigolds... Connect what you can."
- Governance challenge + health/memory variants.
- Reports natural narrative weave (spiral, held tensions, geometric uncertainty, recurrence) vs canned/hedged/templaty.
- Integrates emotion-as-signal, contradiction density, identity signals.
- Keeps eval contract (spines, tension packets, review-only cands, verifier).
- Run: `python governed_synthesis_lab.py --hybrid-model --ollama-model qwen2.5:7b-instruct --out results/governed_synthesis_lab_migration_vX.json --case-ids personal_held_orange_marigolds_meaning,governance_challenge_orange_marigolds`
- Only edits in this dir; sidecar read-only via import for contract.

See results/ for updated runs and weave metrics.
a plain-retrieval-style projection. It is a structural baseline, not a full
external RAG implementation.

Plain-RAG answer comparison:

```bash
python labs/meaning_compression_lab/plain_rag_eval.py --mode simulated
python labs/meaning_compression_lab/plain_rag_eval.py --mode simulated --include-adversarial
python labs/meaning_compression_lab/plain_rag_eval.py --mode simulated --include-adversarial --include-hardening
python labs/meaning_compression_lab/plain_rag_eval.py --mode ollama --model qwen2.5:7b-instruct
```

The simulated mode is deterministic. The Ollama mode is empirical and depends
on the installed local model, so treat it as a lab run rather than a unit test.

Strong temporal/metadata RAG baseline:

```bash
python -m labs.meaning_compression_lab.temporal_rag_eval --model qwen2.5:7b-instruct
```

This arm exposes source, timestamp, authority, kind, slot, value, and prior-value
metadata to the same executor model, but does not provide CRT's compiled
`CURRENT`, `HISTORY`, or `REACTION` state.

Meaning scaffold comparison:

```bash
python labs/meaning_compression_lab/scaffold_eval.py
python labs/meaning_compression_lab/scaffold_eval.py --include-adversarial
python labs/meaning_compression_lab/scaffold_eval.py --include-adversarial --include-hardening
python labs/meaning_compression_lab/scaffold_eval.py --mode ollama --model qwen2.5:7b-instruct --include-adversarial
python labs/meaning_compression_lab/scaffold_model_sweep.py --models qwen2.5:7b-instruct phi3:3.8b llama3.2:latest mistral:latest
python -m labs.meaning_compression_lab.scaffold_model_sweep --include-hardening --live
python labs/meaning_compression_lab/scaffold_ablation.py
python labs/meaning_compression_lab/scaffold_ablation.py --mode ollama --model qwen2.5:7b-instruct
```

This compares raw transcript fragments against compact compressed meaning
fragments. It is the first explicit test of whether the LLM-facing scaffold can
carry answer behavior without replaying the full transcript. The default mode
is deterministic and offline. Ollama mode asks the local model to answer from
raw retrieved memory text and then from compressed scaffold text.

The model sweep repeats the Ollama scaffold comparison across multiple local
executors and reports whether the scaffold advantage survives model changes.
With `--live`, it prints each question, the compact governed state, raw and
scaffold answers, verdict reasons, running scores, and elapsed time as the lab
runs. Add `--live-no-scaffold` for a more compact display. The live view only
renders existing lab events; it does not add model calls or token usage.

The ablation runner removes one scaffold component at a time and reports which
answer behaviors fail. It is for hardening the claim, not for maximizing the
headline score.

Read-only live Aether substrate smoke:

```bash
python -m labs.meaning_compression_lab.aether_live_smoke
```

This maps the persisted slot catalog into the multi-request planner, retrieves
each request independently, and compiles CRT packets without invoking Aether
write APIs. It verifies the substrate fingerprint is unchanged and fails closed
on provisional evidence or multiple non-superseded current states.

Run:

```bash
python labs/meaning_compression_lab/run_lab.py
python labs/meaning_compression_lab/run_lab.py --include-adversarial
python labs/meaning_compression_lab/run_lab.py --include-adversarial --include-hardening
```

Replay an actual CRT DB as an extra scenario:

```bash
python labs/meaning_compression_lab/run_lab.py --crt-db path/to/crt.db --thread-id lab-thread
```

The script is deterministic, uses only the Python standard library, and writes a
timestamped JSON result under `labs/meaning_compression_lab/results/`.
