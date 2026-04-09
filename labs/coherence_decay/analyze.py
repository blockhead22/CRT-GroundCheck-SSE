"""Coherence Decay Experiment — Analysis & Charts

Reads scored results and produces:
  1. Decay curves (fidelity/drift over token position)
  2. Model × Strategy heatmap
  3. Crossover chart (where does scaffolded-small beat unscaffolded-large?)
  4. Domain comparison
  5. Entropy-leads-drift analysis
"""

import json
import sys
from pathlib import Path

import numpy as np

from config import CHARTS_DIR, RESULTS_DIR

# ---------------------------------------------------------------------------
# Try to import matplotlib, fall back gracefully
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    HAS_PLT = True
except ImportError:
    HAS_PLT = False
    print("[WARN] matplotlib not installed. Charts disabled.")
    print("       pip install matplotlib")


def load_scored(path: str | Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return [d for d in data if d.get("scored")]


# ---------------------------------------------------------------------------
# Chart 1: Model × Strategy Heatmap
# ---------------------------------------------------------------------------
def chart_heatmap(scored: list[dict], metric: str = "composite"):
    """Heatmap: models (rows) × strategies (cols), colored by metric."""
    if not HAS_PLT:
        return

    models = sorted(set(s["model_tier"] for s in scored))
    strategies = sorted(set(s["strategy"] for s in scored))

    grid = np.zeros((len(models), len(strategies)))
    counts = np.zeros_like(grid)

    for s in scored:
        mi = models.index(s["model_tier"])
        si = strategies.index(s["strategy"])
        grid[mi, si] += s.get(metric, 0)
        counts[mi, si] += 1

    # Average
    grid = np.divide(grid, counts, where=counts > 0)

    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(grid, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels([s.replace("_", "\n") for s in strategies], fontsize=9)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models, fontsize=10)

    # Annotate cells
    for i in range(len(models)):
        for j in range(len(strategies)):
            val = grid[i, j]
            ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="white" if val < 0.5 else "black")

    ax.set_title(f"Coherence Decay: {metric.title()} Score\n(Model × Strategy)", fontsize=14)
    plt.colorbar(im, ax=ax, label=metric.title())
    plt.tight_layout()

    out = CHARTS_DIR / f"heatmap_{metric}.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Chart saved: {out}")


# ---------------------------------------------------------------------------
# Chart 2: Fidelity by Domain × Strategy
# ---------------------------------------------------------------------------
def chart_fidelity_by_domain(scored: list[dict]):
    if not HAS_PLT:
        return

    domains = sorted(set(s["domain"] for s in scored))
    strategies = sorted(set(s["strategy"] for s in scored))

    fig, axes = plt.subplots(1, len(domains), figsize=(6 * len(domains), 5), sharey=True)
    if len(domains) == 1:
        axes = [axes]

    for ax, domain in zip(axes, domains):
        domain_data = [s for s in scored if s["domain"] == domain]

        for strat in strategies:
            strat_data = [s for s in domain_data if s["strategy"] == strat]
            if not strat_data:
                continue

            models = sorted(set(s["model_tier"] for s in strat_data))
            fidelities = []
            for m in models:
                model_data = [s for s in strat_data if s["model_tier"] == m]
                avg = np.mean([s["fidelity"]["fidelity_score"] for s in model_data])
                fidelities.append(avg)

            ax.plot(models, fidelities, marker="o", label=strat.replace("_", " "))

        ax.set_title(f"{domain.title()}", fontsize=12)
        ax.set_xlabel("Model Tier")
        ax.set_ylabel("Fidelity Score")
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=7, loc="lower right")
        ax.grid(True, alpha=0.3)

    plt.suptitle("Fidelity by Domain × Strategy × Model", fontsize=14)
    plt.tight_layout()

    out = CHARTS_DIR / "fidelity_by_domain.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Chart saved: {out}")


# ---------------------------------------------------------------------------
# Chart 3: Drift over Spans (the decay curve)
# ---------------------------------------------------------------------------
def chart_drift_decay(scored: list[dict]):
    """Plot semantic drift over span index — this is THE core chart."""
    if not HAS_PLT:
        return

    # Only include results with multiple spans (burst strategies)
    multi_span = [s for s in scored if len(s["drift"].get("drift_scores", [])) > 1]
    if not multi_span:
        print("  [SKIP] No multi-span results for drift decay chart")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    # Group by model_tier × strategy
    groups = {}
    for s in multi_span:
        key = f"{s['model_tier']} / {s['strategy']}"
        groups.setdefault(key, []).append(s["drift"]["drift_scores"])

    for label, drift_lists in sorted(groups.items()):
        # Average drift at each span position
        max_spans = max(len(d) for d in drift_lists)
        avg_drift = []
        for i in range(max_spans):
            vals = [d[i] for d in drift_lists if i < len(d)]
            avg_drift.append(np.mean(vals))

        ax.plot(range(len(avg_drift)), avg_drift, marker="o", label=label, alpha=0.8)

    ax.set_xlabel("Span Index", fontsize=12)
    ax.set_ylabel("Semantic Drift (1 - cosine similarity)", fontsize=12)
    ax.set_title("Semantic Drift Over Generation Spans", fontsize=14)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.02, 1))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    out = CHARTS_DIR / "drift_decay.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {out}")


# ---------------------------------------------------------------------------
# Chart 4: Crossover Point
# ---------------------------------------------------------------------------
def chart_crossover(scored: list[dict]):
    """The money shot: where does small+scaffold beat large+free?"""
    if not HAS_PLT:
        return

    models = sorted(set(s["model_tier"] for s in scored))
    strategies = sorted(set(s["strategy"] for s in scored))

    if len(models) < 2:
        print("  [SKIP] Need 2+ model tiers for crossover chart")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    for model in models:
        composites = []
        for strat in strategies:
            data = [s for s in scored if s["model_tier"] == model and s["strategy"] == strat]
            if data:
                composites.append(np.mean([s["composite"] for s in data]))
            else:
                composites.append(0)

        ax.plot(strategies, composites, marker="s", linewidth=2, markersize=8, label=model)

    ax.set_xlabel("Strategy Level", fontsize=12)
    ax.set_ylabel("Composite Score", fontsize=12)
    ax.set_title("Crossover Analysis: Can Scaffolded Small Beat Unscaffolded Large?", fontsize=13)
    ax.legend(fontsize=10)
    ax.set_xticklabels([s.replace("_", "\n") for s in strategies], fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)
    plt.tight_layout()

    out = CHARTS_DIR / "crossover.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Chart saved: {out}")


# ---------------------------------------------------------------------------
# Chart 5: Contradiction rate by strategy
# ---------------------------------------------------------------------------
def chart_contradiction_rate(scored: list[dict]):
    if not HAS_PLT:
        return

    strategies = sorted(set(s["strategy"] for s in scored))
    models = sorted(set(s["model_tier"] for s in scored))

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(strategies))
    width = 0.8 / len(models)

    for i, model in enumerate(models):
        rates = []
        for strat in strategies:
            data = [s for s in scored if s["model_tier"] == model and s["strategy"] == strat]
            if data:
                rate = sum(1 for s in data if not s["self_contradiction"]["self_consistent"]) / len(data)
                rates.append(rate)
            else:
                rates.append(0)

        offset = (i - len(models) / 2 + 0.5) * width
        ax.bar(x + offset, rates, width, label=model, alpha=0.8)

    ax.set_xlabel("Strategy", fontsize=12)
    ax.set_ylabel("Self-Contradiction Rate", fontsize=12)
    ax.set_title("Self-Contradiction Rate by Model × Strategy", fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([s.replace("_", "\n") for s in strategies], fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    out = CHARTS_DIR / "contradiction_rate.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Chart saved: {out}")


# ---------------------------------------------------------------------------
# Summary table (text)
# ---------------------------------------------------------------------------
def print_full_summary(scored: list[dict]):
    """Detailed text summary."""
    print(f"\n{'='*80}")
    print(f"COHERENCE DECAY EXPERIMENT — FULL ANALYSIS")
    print(f"{'='*80}")

    models = sorted(set(s["model_tier"] for s in scored))
    strategies = sorted(set(s["strategy"] for s in scored))
    domains = sorted(set(s["domain"] for s in scored))

    print(f"\nModels tested:     {models}")
    print(f"Strategies tested: {strategies}")
    print(f"Domains tested:    {domains}")
    print(f"Total scored runs: {len(scored)}")

    # Per-domain breakdown
    for domain in domains:
        print(f"\n--- {domain.upper()} ---")
        domain_data = [s for s in scored if s["domain"] == domain]

        print(f"\n{'Model':<18} {'Strategy':<22} {'Fidelity':>8} {'Drift':>8} {'Contradict':>10} {'Composite':>9}")
        print("-" * 80)

        for model in models:
            for strat in strategies:
                data = [s for s in domain_data if s["model_tier"] == model and s["strategy"] == strat]
                if not data:
                    continue
                fid = np.mean([s["fidelity"]["fidelity_score"] for s in data])
                dft = np.mean([s["drift"].get("drift_mean", 0) for s in data])
                con = sum(1 for s in data if not s["self_contradiction"]["self_consistent"]) / len(data)
                comp = np.mean([s["composite"] for s in data])
                print(f"{model:<18} {strat:<22} {fid:>8.3f} {dft:>8.3f} {con:>10.3f} {comp:>9.3f}")

    # Key findings
    print(f"\n{'='*80}")
    print("KEY FINDINGS")
    print(f"{'='*80}")

    # Best composite per model
    for model in models:
        model_data = [s for s in scored if s["model_tier"] == model]
        if model_data:
            best = max(model_data, key=lambda s: s["composite"])
            print(f"  {model} best: {best['strategy']} (composite={best['composite']:.3f})")

    # Crossover detection
    if len(models) >= 2:
        smallest = models[0]
        largest = models[-1]
        small_l4 = [s for s in scored if s["model_tier"] == smallest and s["strategy"] == "L4_full_scaffold"]
        large_l0 = [s for s in scored if s["model_tier"] == largest and s["strategy"] == "L0_free_500"]

        if small_l4 and large_l0:
            small_comp = np.mean([s["composite"] for s in small_l4])
            large_comp = np.mean([s["composite"] for s in large_l0])
            print(f"\n  CROSSOVER TEST:")
            print(f"    {smallest} + L4_full_scaffold = {small_comp:.3f}")
            print(f"    {largest} + L0_free_500       = {large_comp:.3f}")
            if small_comp > large_comp:
                print(f"    >>> CROSSOVER DETECTED: Scaffolded small beats unscaffolded large!")
            else:
                gap = large_comp - small_comp
                print(f"    >>> No crossover (gap = {gap:.3f})")

    print(f"\n{'='*80}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def analyze(scored_file: str | Path):
    """Run full analysis."""
    scored = load_scored(scored_file)
    if not scored:
        print("No scored results to analyze.")
        return

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\nGenerating charts...")
    chart_heatmap(scored, "composite")
    chart_heatmap(scored, "fidelity")
    chart_fidelity_by_domain(scored)
    chart_drift_decay(scored)
    chart_crossover(scored)
    chart_contradiction_rate(scored)

    print_full_summary(scored)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze coherence decay results")
    parser.add_argument("scored_file", help="Path to scored results JSON")
    args = parser.parse_args()
    analyze(args.scored_file)
