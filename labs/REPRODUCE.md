# Reproducibility guide

Every lab and paper experiment in the repo, with the exact command to run it, what it touches, and what it writes. The goal is that a stranger who has never seen this codebase can land on this page, install once, and reproduce any result.

---

## One-time setup

```bash
git clone https://github.com/blockhead22/CRT-GroundCheck-SSE.git
cd CRT-GroundCheck-SSE
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt   # if present
pip install numpy scipy matplotlib sentence-transformers networkx sqlite3
```

Most labs are **standalone** — pure NumPy / SQLite math, no LLM calls, no network, no GPU. The exceptions are the LLM-calling labs (Phi-3 fine-tune, brain-swap benches, pollution sweeps); those are flagged explicitly below with their extra setup.

The substrate's own data files are committed under `data/` (chatgpt_corpus.db, chatgpt_consistency.db, chatgpt_drift.db) and `personal_agent/*.db`. No external download required for any of the headline results.

---

## Headline results

These are the experiments cited on the public docs and the README. Each is a single command, runs offline, finishes in seconds-to-minutes, and prints a self-contained verdict.

### 1. Belief backpropagation — 30/30 validation

**What it shows:** Trust signals propagate backward through a belief dependency graph. Wrong beliefs self-prune; domain volatility becomes measurable; self-model edges respond to per-domain correction history.

```bash
python papers/belief_backpropagation/experiments.py
```

- **Runtime:** ~3 seconds.
- **Output:** stdout — six labs, ends with `RESULTS: 30 passed, 0 failed, 30 total`.
- **No state written.**
- **Re-verified 2026-05-07.** All green.

### 2. Cascade complexity — damping convergence + production BDG

**What it shows:** Belief revision cascades terminate at a depth bounded by `log(δ₀/τ) / log(1/ρ)`. Empirical fit on a 599-node production BDG.

```bash
python papers/cascade_complexity/experiments.py
python papers/cascade_complexity/damping_analysis.py
```

- **Runtime:** ~2 seconds each.
- **Output:** stdout numbers + matplotlib charts under `papers/cascade_complexity/`.
- **Reads** `personal_agent/crt_memory_shared.db` (599 nodes baseline) — already committed.

### 3. Fidelity benchmark — belief/speech gap (Anthropic NLA analog)

**What it shows:** What fraction of real responses are actually grounded in the substrate's stored memories.

```bash
python labs/fidelity_bench/run_bench.py
```

- **Runtime:** ~30 seconds.
- **Output:** `labs/fidelity_bench/results/fidelity_bench_<timestamp>.{json,png}`.
- **N=30** by default; bump `SAMPLE_SIZE` in the script for more.
- **Reads** `personal_agent/crt_memory_shared.db` (`belief_speech` table — 1,073 rows).

### 4. Geometry-aware grounding A/B — cosine vs Fisher–Rao (Goodfire analog)

**What it shows:** A curvature-aware metric (Fisher–Rao on diagonal Gaussian belief loci) discriminates grounded responses better than cosine. Substrate-layer analog of Goodfire's curved-manifold result for activations.

```bash
python labs/fidelity_bench/run_bench_metric_ab.py
```

- **Runtime:** ~60 seconds at N=200.
- **Output:** `labs/fidelity_bench/results/fidelity_bench_metric_ab_<timestamp>.{json,png}`.
- **Headline result (2026-05-07):** Fisher AUC 0.699 vs cosine 0.626 (Δ +0.073); Pearson r 0.235 → 0.312 (+33% relative). 107/200 samples flip across metrics.
- **See** [`fidelity_bench/README.md`](fidelity_bench/README.md) for full method, limitations, follow-ups.

### 5. Aether bench — cold vs warm paired trials

**What it shows:** Substrate-as-capacity-amplifier. Same model answers task with vs without the substrate.

```bash
python -m labs.aether_bench.harness --smoke
python -m labs.aether_bench.harness --brain stub --arm both --tasks all
```

- **Runtime:** smoke is seconds; full sweep depends on brain. Stub brain is offline.
- **Output:** `labs/aether_bench/trials.sqlite` (152 trials at last run).
- **Real-brain runs** require an OpenAI/Anthropic API key or local Ollama; see `labs/aether_bench/aether_client.py`.
- **Pre-seed:** `python -m labs.aether_bench.seed` writes task-reference facts into the substrate before the warm arm.

---

## Mempalace labs — standalone prototypes

Each script is self-contained, no DB, no network. Pure-Python belief-graph + tension dynamics.

```bash
python labs/mempalace_lab/gravity_lab.py
python labs/mempalace_lab/goal_formation_lab.py
python labs/mempalace_lab/autonomous_exploration_lab.py
python labs/mempalace_lab/contradiction_test.py
python labs/mempalace_lab/crt_contradiction_test.py
```

Each prints its own verdict. Goal-formation lab is 15/15 on the contradiction-as-tension cases; gravity lab demonstrates the mass/tension/splitting model.

---

## Coherence-decay labs

`labs/coherence_decay/` contains the largest set of experiment scripts in the repo (50+ files). Most are independent investigations from the 2026-04-09 sweep (~360 runs, entropy stabilization, sandbox escapes). Common entry points:

```bash
python labs/coherence_decay/analyze.py          # summary across runs
python labs/coherence_decay/analyze_phase_c.py  # paraphrase corpus (Phase C)
python labs/coherence_decay/analyze_phase_d.py  # 40-cell brain × difficulty grid
python labs/coherence_decay/atomic_verify.py    # atomic-claim verification (94%)
python labs/coherence_decay/audit_crt.py        # production audit ceiling
python labs/coherence_decay/bdg_belief_hybrid.py
python labs/coherence_decay/bdg_belief_structural.py
python labs/coherence_decay/bdg_intent_router.py
python labs/coherence_decay/docker_escape.py    # 5-level sandbox escape
python labs/coherence_decay/exploration_tree.py # MCTS-inspired exploration
python labs/coherence_decay/lan_discovery.py    # LAN scan + Ollama discovery
```

Most write a `results/` directory or stdout-only. The full sweep was 360+ runs over ~24h on consumer hardware. **Some scripts call out to LLMs** (Ollama or cloud) — those will fail without configured keys; check the file header for the dependency.

---

## Belief-backprop supporting labs

```bash
python papers/belief_backpropagation/wobble_lab.py
python papers/belief_backpropagation/contradiction_drive_lab.py
python papers/belief_backpropagation/compressed_epistemic_lab.py
python papers/belief_backpropagation/context_pollution_lab.py
python papers/belief_backpropagation/claude_pollution_lab.py        # needs ANTHROPIC_API_KEY
python papers/belief_backpropagation/claude_variance_pollution_lab.py # needs ANTHROPIC_API_KEY
python papers/belief_backpropagation/sse_production_lab.py
```

Wobble, contradiction-drive, compressed-epistemic, and context-pollution are offline. The `claude_*` labs need `ANTHROPIC_API_KEY` and will spend tokens (~$0.05–$0.20 per run depending on sweep size).

The Phi-3 fine-tune chain (`crt_phi3_finetune.py`, `crt_phi3_finetune_v2.py`, `modal_train.py`) requires a Modal account and GPU — out of scope for casual reproduction; runs are documented in the paper.

---

## Other labs

| Path | What it is | Runtime | Notes |
|---|---|---|---|
| `labs/meaning_compression_lab/run_lab.py` | deterministic meaning-compression toy benchmark | seconds | offline, writes JSON results |
| `labs/meaning_compression_lab/baseline_eval.py` | structural baseline comparison for CRT meaning state | seconds | offline, writes JSON results |
| `labs/meaning_compression_lab/plain_rag_eval.py` | simulated/Ollama plain-RAG answer comparison | seconds-minutes | simulated is offline; Ollama mode needs local model |
| `labs/meaning_compression_lab/scaffold_eval.py` | compressed meaning scaffold vs raw transcript fragments | seconds-minutes | deterministic is offline; Ollama mode needs local model |
| `tests/test_crt_rag_behavior_bridge.py` | RAG behavior bridge for CRT meaning claims | ~1 minute | pytest; writes temp SQLite DBs only |
| `labs/scaffold_conversation_lab/scaffold_conversation_lab.py` | scaffold-vs-direct conversation comparison | ~minutes | results.json committed |
| `labs/case_study/adnan_syed/` | case-study reasoning trace | reading | not a runnable lab |
| `labs/gravity/gravity_belief_store.py` | belief-store gravity bridge | n/a | library, not a runner |

---

## Quick "does my install work" check

```bash
# Should print "30 passed, 0 failed" in 3 seconds
python papers/belief_backpropagation/experiments.py | tail -3

# Should print a fidelity composite around 0.28 on N=30 in ~30 seconds
python labs/fidelity_bench/run_bench.py | tail -10
```

If both green, the substrate side is up. If you want the full agent loop (FastAPI + SQLite + frontend), see the top-level README.

---

## Lab HTML write-ups (pre-rendered)

`docs/labs/` contains 17 dated HTML write-ups of completed lab runs. Each is a snapshot, not a runner. Highlights:

- `continuity-blind-v2-latest.html` — continuity-blind contradiction phenomenon, 9 dated runs over one afternoon
- `contradiction-pipeline-lab-latest.html` — contradiction pipeline results
- `slot-coverage-gpt-corpus.html`, `slot-drift-gpt-corpus.html` — slot extractor coverage on the GPT corpus
- `v2-pair-audit.html` — v2 pair-filter validation

These are the receipts. They don't re-run themselves; they document what *did* run.

---

## Known gaps

The following claims need a runner that doesn't yet exist as a single command:

- **"sub-2ms fidelity verification"** — needs a timing harness (planned).
- **"18/18 disposition test suite"** — test file location not currently mapped.
- **"22,702 variance probes"** — historical claim; current count from the substrate is much smaller. See [`docs/CLAIMS_AUDIT.md`](../docs/CLAIMS_AUDIT.md).

Contributions that close these gaps are explicitly welcome.
