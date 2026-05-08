# Aether — one-page summary

*If you have 60 seconds.*

## What it is

A **belief substrate** for LLM agents. Not a memory layer — a layer that stores trust scores, contradiction state, and a dependency graph of which beliefs rest on which others. Built so the persistent self of an agent survives swapping the underlying model.

The model is the mouth. The substrate is the self.

## What's measurably true

- **Geometry-aware grounding beats cosine.** Fisher–Rao distance over diagonal-Gaussian belief loci hits AUC 0.699 vs cosine 0.626 (Δ +0.073) at separating grounded from ungrounded responses on N=200 real conversation samples. +33% relative correlation gain with stored ground-truth labels. *Measured 2026-05-07. Code: [`labs/fidelity_bench/run_bench_metric_ab.py`](../labs/fidelity_bench/run_bench_metric_ab.py).*
- **Belief/speech gap, quantified.** 30 percentage-point divergence between two grounding signals on the same response set. *Code: [`personal_agent/fidelity_mirror.py`](../personal_agent/fidelity_mirror.py), [`labs/fidelity_bench/run_bench.py`](../labs/fidelity_bench/run_bench.py).*
- **Belief backpropagation, validated.** 30/30 experiments. Trust signals propagate through a dependency graph; wrong beliefs self-prune from accumulated error. *Paper: [`papers/belief_backpropagation/`](../papers/belief_backpropagation/).*
- **Cascade complexity, formalized.** 5 theorems on bounded belief-update cascades — depth bounds, damping convergence, NP-hardness conjecture. *Paper: [`papers/cascade_complexity/`](../papers/cascade_complexity/).*
- **Substrate as capacity amplifier.** Phase D: 5 models × 2 difficulty levels × 2 modes × 2 trials = 40-cell grid. Cross-model stdev collapses 4.4× when the substrate is wired in (0.260 → 0.059). The persistent state evens out brain-size differences.

## Why it's interesting now

In **May 2026**, two activation-layer interpretability papers landed that map directly onto pieces this substrate had already built:

| Paper (May 2026) | Their layer | Substrate analog | Substrate built |
|---|---|---|---|
| Goodfire — *The world inside neural networks* | activations | Splats with sigma + Fisher-Rao metric | March 2026 |
| Anthropic — *Natural Language Autoencoders* | activations | `fidelity_mirror` + belief/speech gap | March 2026 |

Independent arrival, dated, with code in the repo. The convergence is the validation.

## What I built (technical scope)

- **Python library** — substrate primitives (splats, dependency graph, trust math, contradiction taxonomy)
- **CLI + MCP server** — `pip install aether-core`, plugs into Claude Code, ChatGPT, any MCP host
- **FastAPI backend + React/TypeScript frontend** — the personal agent that runs on top
- **SQLite persistence** — single-file substrate, no external services, runs offline
- **Two papers** — cascade complexity, belief backpropagation
- **17 lab HTMLs** — every claim has a reproducible experiment
- **539+ tests passing** — the substrate's own tools find bugs in the substrate

Stack: Python 3.10+, FastAPI, SQLite, NumPy, sentence-transformers (MiniLM), React/TypeScript/Vite frontend, Ollama for local LLM, OpenAI/Anthropic SDKs for cloud, Playwright for browser, MCP for agent integration.

## Velocity

- **2026-03 → 2026-05:** v0.1 → v0.15 in two months. 15+ tagged releases.
- **2026-04-17:** Phase D substrate-as-capacity-amplifier result (40-cell grid).
- **2026-05-01:** v0.13.2 cross-platform CI loop closed. 5 versions shipped that day.
- **2026-05-07:** Cosine vs Fisher-Rao A/B measured the same day external papers landed.

Every release is a tag with a CHANGELOG entry. Every paper has experiments with data files. Every lab has a dated HTML.

## How to verify in one command

```bash
git clone <repo>
cd aether-core && pip install -e . && pytest tests/  # 539 pass
# or, the recent measurement:
cd .. && python labs/fidelity_bench/run_bench_metric_ab.py
```

## Who built it

Solo. One person, one year, no team. Comfortable across math, infra, and product. Strongest at: shaping a research result into a shipped tool, measuring instead of arguing, and writing the loops that turn data into decisions.

## What I'm looking for

Engineering or research role where the work is end-to-end — model behavior, evaluation, agent infra, interpretability tooling, or anything epistemic-governance-shaped. Strong preference for places that ship and measure.

Contact: see GitHub profile.
