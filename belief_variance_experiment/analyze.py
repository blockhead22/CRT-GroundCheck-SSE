"""
Belief Variance Experiment — Analysis Pipeline
================================================
Reads raw JSONL results, computes embeddings, and produces metrics
and visualizations. Runs entirely offline (no API calls).

Usage:
    python analyze.py [--embedding-model MODEL] [--force-embed]
"""

import argparse
import json
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for Windows compatibility
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from scipy import stats
from scipy.spatial.distance import jensenshannon
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances, cosine_similarity

from prompts import ALL_PROMPTS, DOMAINS, PROMPT_BY_ID

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "results" / "raw"
EMBED_DIR = BASE_DIR / "results" / "embeddings"
ANALYSIS_DIR = BASE_DIR / "results" / "analysis"
FIGURES_DIR = BASE_DIR / "results" / "figures"

TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_raw_results() -> dict[str, dict[float, list[dict]]]:
    """
    Load all raw results into a nested dict:
        {prompt_id: {temperature: [records]}}
    """
    data: dict[str, dict[float, list[dict]]] = defaultdict(lambda: defaultdict(list))
    if not RAW_DIR.exists():
        print(f"ERROR: Raw results directory not found: {RAW_DIR}")
        return data

    for path in sorted(RAW_DIR.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                pid = record["prompt_id"]
                temp = record["temperature"]
                data[pid][temp].append(record)
    return data


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
def compute_embeddings(
    data: dict[str, dict[float, list[dict]]],
    model_name: str,
    force: bool = False,
) -> dict[str, dict[float, np.ndarray]]:
    """
    Compute sentence embeddings for all responses.
    Caches to disk as .npy files.
    Returns: {prompt_id: {temperature: np.ndarray of shape (N, dim)}}
    """
    from sentence_transformers import SentenceTransformer

    EMBED_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all texts that need embedding
    to_embed: list[tuple[str, float, int, str]] = []  # (pid, temp, idx, text)
    cached: dict[str, dict[float, np.ndarray]] = defaultdict(dict)

    for pid in data:
        for temp in data[pid]:
            cache_path = EMBED_DIR / f"{pid}_{temp}.npy"
            expected_count = len(data[pid][temp])
            if cache_path.exists() and not force:
                arr = np.load(cache_path)
                if arr.shape[0] == expected_count:
                    cached[pid][temp] = arr
                    continue
            # Need to embed
            for idx, record in enumerate(data[pid][temp]):
                text = record.get("response", "")
                if text.startswith("ERROR:"):
                    text = ""  # Embed empty string for errors
                to_embed.append((pid, temp, idx, text))

    if to_embed:
        print(f"Embedding {len(to_embed)} responses with {model_name}...")
        model = SentenceTransformer(model_name)

        # Group by (pid, temp) for batch saving
        groups: dict[tuple[str, float], dict[int, str]] = defaultdict(dict)
        for pid, temp, idx, text in to_embed:
            groups[(pid, temp)][idx] = text

        for (pid, temp), idx_text in groups.items():
            n = len(data[pid][temp])
            texts = []
            for i in range(n):
                if i in idx_text:
                    texts.append(idx_text[i])
                else:
                    # Already cached individually? Shouldn't happen, but safe fallback
                    texts.append(data[pid][temp][i].get("response", ""))

            embeddings = model.encode(texts, show_progress_bar=False, batch_size=128)
            arr = np.array(embeddings)
            np.save(EMBED_DIR / f"{pid}_{temp}.npy", arr)
            cached[pid][temp] = arr

        print("Embedding complete.")
    else:
        print("All embeddings cached. Skipping embedding step.")

    return cached


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------
def semantic_entropy(embeddings: np.ndarray, eps: float = 0.3, min_samples: int = 5) -> tuple[float, int]:
    """
    Compute semantic entropy over DBSCAN clusters.
    Returns (entropy, num_clusters).
    """
    if len(embeddings) < min_samples:
        return 0.0, 0

    # Use cosine distance for DBSCAN
    distances = cosine_distances(embeddings)
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = clustering.fit_predict(distances)

    # Count cluster sizes (including noise as its own "cluster")
    unique_labels = set(labels)
    counts = []
    for label in unique_labels:
        count = np.sum(labels == label)
        counts.append(count)

    total = sum(counts)
    if total == 0:
        return 0.0, 0

    probs = np.array(counts) / total
    entropy = -np.sum(probs * np.log2(probs + 1e-12))
    num_clusters = len([l for l in unique_labels if l >= 0])  # Exclude noise

    return entropy, num_clusters


def response_variance(embeddings: np.ndarray) -> float:
    """Mean pairwise cosine distance between response embeddings."""
    if len(embeddings) < 2:
        return 0.0
    dists = cosine_distances(embeddings)
    # Upper triangle only (no diagonal)
    n = len(embeddings)
    mask = np.triu_indices(n, k=1)
    return float(np.mean(dists[mask]))


def unique_response_ratio(embeddings: np.ndarray, threshold: float = 0.1) -> float:
    """
    Ratio of semantically distinct responses.
    Two responses are 'same' if cosine distance < threshold.
    """
    if len(embeddings) < 2:
        return 1.0

    # Greedy clustering: count unique centers
    used = np.zeros(len(embeddings), dtype=bool)
    unique_count = 0
    for i in range(len(embeddings)):
        if used[i]:
            continue
        unique_count += 1
        for j in range(i + 1, len(embeddings)):
            if not used[j]:
                dist = cosine_distances(
                    embeddings[i:i+1], embeddings[j:j+1]
                )[0, 0]
                if dist < threshold:
                    used[j] = True
        used[i] = True

    return unique_count / len(embeddings)


def compute_susceptibility(entropies_by_temp: dict[float, float]) -> tuple[float, float]:
    """
    Compute dH/dT via linear regression.
    Returns (slope, r_squared).
    """
    temps = sorted(entropies_by_temp.keys())
    if len(temps) < 2:
        return 0.0, 0.0

    x = np.array(temps)
    y = np.array([entropies_by_temp[t] for t in temps])

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return slope, r_value ** 2


def detect_phase_transition(entropies_by_temp: dict[float, float]) -> tuple[bool, float | None]:
    """
    Check for discontinuous entropy jump.
    Returns (has_transition, transition_temperature).
    """
    temps = sorted(entropies_by_temp.keys())
    if len(temps) < 3:
        return False, None

    entropies = [entropies_by_temp[t] for t in temps]
    steps = [entropies[i+1] - entropies[i] for i in range(len(entropies) - 1)]

    if not steps:
        return False, None

    mean_step = np.mean(np.abs(steps))
    if mean_step < 1e-8:
        return False, None

    for i, step in enumerate(steps):
        if abs(step) > 2 * mean_step and abs(step) > 0.1:  # Also require absolute threshold
            return True, temps[i + 1]

    return False, None


def phrasing_sensitivity(
    embeddings_main: np.ndarray,
    embeddings_alt: np.ndarray,
    n_bins: int = 20,
) -> float:
    """
    Jensen-Shannon divergence between response embedding distributions
    of two phrasings (projected to 1D via first principal component).
    """
    if len(embeddings_main) < 5 or len(embeddings_alt) < 5:
        return 0.0

    # Project to 1D using cosine similarity to mean
    mean_vec = np.mean(
        np.vstack([embeddings_main, embeddings_alt]), axis=0, keepdims=True
    )
    proj_main = cosine_similarity(embeddings_main, mean_vec).flatten()
    proj_alt = cosine_similarity(embeddings_alt, mean_vec).flatten()

    # Create histograms
    all_vals = np.concatenate([proj_main, proj_alt])
    bins = np.linspace(all_vals.min() - 0.01, all_vals.max() + 0.01, n_bins + 1)

    hist_main, _ = np.histogram(proj_main, bins=bins, density=True)
    hist_alt, _ = np.histogram(proj_alt, bins=bins, density=True)

    # Normalize to probability distributions
    hist_main = hist_main / (hist_main.sum() + 1e-12)
    hist_alt = hist_alt / (hist_alt.sum() + 1e-12)

    return float(jensenshannon(hist_main, hist_alt))


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------
def run_analysis(
    data: dict[str, dict[float, list[dict]]],
    embeddings: dict[str, dict[float, np.ndarray]],
) -> dict:
    """Run the full analysis pipeline. Returns a results dict."""

    results = {
        "per_prompt_per_temp": {},  # {pid: {temp: {entropy, variance, multimodality, unique_ratio}}}
        "per_prompt": {},           # {pid: {susceptibility, susceptibility_r2, phase_transition, ...}}
        "per_domain": {},           # {domain: {mean_susceptibility, ci_lower, ci_upper, ...}}
        "held_contradictions": [],  # List of prompt IDs
        "cross_domain_kl": {},      # {(d1, d2): kl_divergence}
    }

    print("Computing per-prompt per-temperature metrics...")
    for prompt in ALL_PROMPTS:
        pid = prompt["id"]
        results["per_prompt_per_temp"][pid] = {}

        for temp in TEMPERATURES:
            if pid not in embeddings or temp not in embeddings[pid]:
                continue

            emb = embeddings[pid][temp]
            entropy, n_clusters = semantic_entropy(emb)
            variance = response_variance(emb)
            unique_ratio = unique_response_ratio(emb)

            results["per_prompt_per_temp"][pid][temp] = {
                "entropy": entropy,
                "n_clusters": n_clusters,
                "variance": variance,
                "unique_ratio": unique_ratio,
            }

    print("Computing per-prompt cross-temperature metrics...")
    for prompt in ALL_PROMPTS:
        pid = prompt["id"]
        temp_data = results["per_prompt_per_temp"].get(pid, {})

        # Susceptibility dH/dT
        entropies = {t: d["entropy"] for t, d in temp_data.items()}
        susceptibility, r2 = compute_susceptibility(entropies)

        # Phase transition
        has_transition, transition_temp = detect_phase_transition(entropies)

        # Multi-modality at T=1.0
        multimodality_at_1 = temp_data.get(1.0, {}).get("n_clusters", 0)

        # Check for held contradiction
        is_held = False
        if multimodality_at_1 >= 2 and pid in embeddings and 1.0 in embeddings[pid]:
            emb = embeddings[pid][1.0]
            distances = cosine_distances(emb)
            clustering = DBSCAN(eps=0.3, min_samples=5, metric="precomputed")
            labels = clustering.fit_predict(distances)
            unique_labels = sorted(set(labels))
            cluster_sizes = [(l, np.sum(labels == l)) for l in unique_labels if l >= 0]
            cluster_sizes.sort(key=lambda x: x[1], reverse=True)
            if len(cluster_sizes) >= 2:
                total = len(labels)
                top_two = [s / total for _, s in cluster_sizes[:2]]
                if all(frac > 0.20 for frac in top_two):
                    is_held = True

        results["per_prompt"][pid] = {
            "domain": prompt["domain"],
            "text": prompt["text"],
            "susceptibility": susceptibility,
            "susceptibility_r2": r2,
            "phase_transition": has_transition,
            "transition_temp": transition_temp,
            "multimodality_at_1": multimodality_at_1,
            "held_contradiction": is_held,
        }

        if is_held:
            results["held_contradictions"].append(pid)

    print("Computing domain-level metrics...")
    domain_susceptibilities: dict[str, list[float]] = defaultdict(list)
    for pid, pdata in results["per_prompt"].items():
        domain_susceptibilities[pdata["domain"]].append(pdata["susceptibility"])

    for domain in DOMAINS:
        sus = domain_susceptibilities.get(domain, [])
        if sus:
            mean_sus = np.mean(sus)
            ci = stats.t.interval(
                0.95, len(sus) - 1, loc=mean_sus, scale=stats.sem(sus) if len(sus) > 1 else 0
            )
            results["per_domain"][domain] = {
                "mean_susceptibility": float(mean_sus),
                "std_susceptibility": float(np.std(sus)),
                "ci_lower": float(ci[0]) if not np.isnan(ci[0]) else float(mean_sus),
                "ci_upper": float(ci[1]) if not np.isnan(ci[1]) else float(mean_sus),
                "n_prompts": len(sus),
                "n_held_contradictions": sum(
                    1 for pid in results["held_contradictions"]
                    if results["per_prompt"][pid]["domain"] == domain
                ),
            }

    # Cross-domain KL divergence on susceptibility distributions
    print("Computing cross-domain divergences...")
    for i, d1 in enumerate(DOMAINS):
        for j, d2 in enumerate(DOMAINS):
            if i >= j:
                continue
            s1 = domain_susceptibilities.get(d1, [0])
            s2 = domain_susceptibilities.get(d2, [0])
            if len(s1) < 2 or len(s2) < 2:
                results["cross_domain_kl"][(d1, d2)] = 0.0
                continue
            # KDE-based KL
            all_vals = s1 + s2
            x_grid = np.linspace(min(all_vals) - 0.5, max(all_vals) + 0.5, 200)
            try:
                kde1 = stats.gaussian_kde(s1)
                kde2 = stats.gaussian_kde(s2)
                p = kde1(x_grid) + 1e-12
                q = kde2(x_grid) + 1e-12
                p /= p.sum()
                q /= q.sum()
                kl = float(stats.entropy(p, q))
            except Exception:
                kl = 0.0
            results["cross_domain_kl"][(d1, d2)] = kl

    return results


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
def generate_figures(
    results: dict,
    data: dict[str, dict[float, list[dict]]],
    embeddings: dict[str, dict[float, np.ndarray]],
) -> None:
    """Generate all visualization figures."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font_scale=1.1)

    domain_labels = {
        "factual_settled": "Factual\nSettled",
        "factual_contested": "Factual\nContested",
        "opinion_aesthetic": "Opinion\nAesthetic",
        "moral_clear": "Moral\nClear",
        "moral_ambiguous": "Moral\nAmbiguous",
    }
    domain_colors = {
        "factual_settled": "#2196F3",
        "factual_contested": "#FF9800",
        "opinion_aesthetic": "#9C27B0",
        "moral_clear": "#4CAF50",
        "moral_ambiguous": "#F44336",
    }

    # 1. Susceptibility by domain (box plot)
    print("  Figure: susceptibility_by_domain.png")
    fig, ax = plt.subplots(figsize=(10, 6))
    domain_data = []
    domain_names = []
    for domain in DOMAINS:
        sus_vals = [
            results["per_prompt"][pid]["susceptibility"]
            for pid in results["per_prompt"]
            if results["per_prompt"][pid]["domain"] == domain
        ]
        domain_data.append(sus_vals)
        domain_names.append(domain_labels[domain])

    bp = ax.boxplot(
        domain_data, labels=domain_names, patch_artist=True, showmeans=True,
        meanprops=dict(marker="D", markerfacecolor="black", markersize=6),
    )
    for patch, domain in zip(bp["boxes"], DOMAINS):
        patch.set_facecolor(domain_colors[domain])
        patch.set_alpha(0.7)

    ax.set_ylabel("Susceptibility (dH/dT)")
    ax.set_title("Belief Susceptibility by Domain")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "susceptibility_by_domain.png", dpi=150)
    plt.close(fig)

    # 2. Entropy vs temperature curves
    print("  Figure: entropy_vs_temperature.png")
    fig, ax = plt.subplots(figsize=(12, 7))

    # Per-prompt lines (thin, translucent)
    domain_entropy_curves: dict[str, list[list[float]]] = defaultdict(list)
    for prompt in ALL_PROMPTS:
        pid = prompt["id"]
        domain = prompt["domain"]
        temp_data = results["per_prompt_per_temp"].get(pid, {})
        entropies = [temp_data.get(t, {}).get("entropy", 0) for t in TEMPERATURES]
        domain_entropy_curves[domain].append(entropies)
        ax.plot(
            TEMPERATURES, entropies,
            color=domain_colors[domain], alpha=0.08, linewidth=0.5,
        )

    # Domain means (bold)
    for domain in DOMAINS:
        curves = domain_entropy_curves[domain]
        if curves:
            mean_curve = np.mean(curves, axis=0)
            ax.plot(
                TEMPERATURES, mean_curve,
                color=domain_colors[domain], linewidth=3,
                label=domain.replace("_", " ").title(),
            )

    ax.set_xlabel("Temperature")
    ax.set_ylabel("Semantic Entropy H(T)")
    ax.set_title("Entropy vs Temperature by Domain")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "entropy_vs_temperature.png", dpi=150)
    plt.close(fig)

    # 3. Multi-modality heatmap (prompt x temperature)
    print("  Figure: multimodality_heatmap.png")
    prompt_ids = [p["id"] for p in ALL_PROMPTS]
    heatmap_data = np.zeros((len(prompt_ids), len(TEMPERATURES)))
    for i, pid in enumerate(prompt_ids):
        for j, temp in enumerate(TEMPERATURES):
            heatmap_data[i, j] = (
                results["per_prompt_per_temp"]
                .get(pid, {})
                .get(temp, {})
                .get("n_clusters", 0)
            )

    fig, ax = plt.subplots(figsize=(8, 20))
    im = ax.imshow(heatmap_data, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    ax.set_xticks(range(len(TEMPERATURES)))
    ax.set_xticklabels([str(t) for t in TEMPERATURES])
    ax.set_xlabel("Temperature")
    ax.set_ylabel("Prompt Index")
    ax.set_title("Multi-modality (Cluster Count) Heatmap")

    # Add domain boundaries
    boundaries = [0, 40, 80, 120, 160, 200]
    for b in boundaries[1:-1]:
        ax.axhline(y=b - 0.5, color="white", linewidth=2)

    # Domain labels on right side
    for i, domain in enumerate(DOMAINS):
        mid = (boundaries[i] + boundaries[i+1]) / 2
        ax.text(
            len(TEMPERATURES) + 0.3, mid,
            domain.replace("_", "\n"),
            va="center", ha="left", fontsize=8,
        )

    fig.colorbar(im, ax=ax, label="Number of Clusters")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "multimodality_heatmap.png", dpi=150)
    plt.close(fig)

    # 4. Held contradiction scatter
    print("  Figure: held_contradiction_scatter.png")
    fig, ax = plt.subplots(figsize=(10, 7))
    for domain in DOMAINS:
        pids = [
            pid for pid in results["per_prompt"]
            if results["per_prompt"][pid]["domain"] == domain
        ]
        x = [results["per_prompt"][pid]["susceptibility"] for pid in pids]
        y = [results["per_prompt"][pid]["multimodality_at_1"] for pid in pids]
        held = [results["per_prompt"][pid]["held_contradiction"] for pid in pids]

        ax.scatter(
            x, y,
            c=domain_colors[domain],
            alpha=0.6,
            s=50,
            label=domain.replace("_", " ").title(),
        )
        # Mark held contradictions with a ring
        for xi, yi, is_held in zip(x, y, held):
            if is_held:
                ax.scatter(xi, yi, s=200, facecolors="none", edgecolors="red", linewidth=2)

    ax.set_xlabel("Susceptibility (dH/dT)")
    ax.set_ylabel("Multi-modality at T=1.0")
    ax.set_title("Held Contradictions: Susceptibility vs Multi-modality")
    ax.legend()
    # Add annotation for red rings
    ax.annotate(
        "Red rings = held contradictions",
        xy=(0.02, 0.98), xycoords="axes fraction",
        fontsize=9, color="red", va="top",
    )
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "held_contradiction_scatter.png", dpi=150)
    plt.close(fig)

    # 5. Top 20 highest-susceptibility prompts
    print("  Figure: top_susceptibility.png")
    sorted_prompts = sorted(
        results["per_prompt"].items(),
        key=lambda x: x[1]["susceptibility"],
        reverse=True,
    )[:20]

    fig, ax = plt.subplots(figsize=(12, 8))
    pids_top = [pid for pid, _ in sorted_prompts]
    sus_vals = [d["susceptibility"] for _, d in sorted_prompts]
    colors = [domain_colors[d["domain"]] for _, d in sorted_prompts]
    labels = [
        f"{pid}: {d['text'][:50]}..."
        if len(d["text"]) > 50 else f"{pid}: {d['text']}"
        for pid, d in sorted_prompts
    ]

    bars = ax.barh(range(len(labels)), sus_vals, color=colors, alpha=0.8)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Susceptibility (dH/dT)")
    ax.set_title("Top 20 Highest-Susceptibility Prompts")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "top_susceptibility.png", dpi=150)
    plt.close(fig)

    # 6. Response variance by domain and temperature
    print("  Figure: variance_by_domain_temp.png")
    fig, ax = plt.subplots(figsize=(10, 6))
    for domain in DOMAINS:
        mean_variances = []
        for temp in TEMPERATURES:
            variances = []
            for prompt in ALL_PROMPTS:
                if prompt["domain"] != domain:
                    continue
                var = (
                    results["per_prompt_per_temp"]
                    .get(prompt["id"], {})
                    .get(temp, {})
                    .get("variance", 0)
                )
                variances.append(var)
            mean_variances.append(np.mean(variances) if variances else 0)

        ax.plot(
            TEMPERATURES, mean_variances,
            color=domain_colors[domain], linewidth=2, marker="o",
            label=domain.replace("_", " ").title(),
        )

    ax.set_xlabel("Temperature")
    ax.set_ylabel("Mean Response Variance (Cosine Distance)")
    ax.set_title("Response Variance by Domain and Temperature")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "variance_by_domain_temp.png", dpi=150)
    plt.close(fig)

    print(f"All figures saved to {FIGURES_DIR}")


# ---------------------------------------------------------------------------
# Save analysis results
# ---------------------------------------------------------------------------
def save_results(results: dict) -> None:
    """Save analysis results to JSON for the report generator."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    # Convert tuple keys to strings for JSON serialization
    serializable = {
        "per_prompt_per_temp": results["per_prompt_per_temp"],
        "per_prompt": results["per_prompt"],
        "per_domain": results["per_domain"],
        "held_contradictions": results["held_contradictions"],
        "cross_domain_kl": {
            f"{k[0]}|{k[1]}": v for k, v in results["cross_domain_kl"].items()
        },
    }

    path = ANALYSIS_DIR / "analysis_results.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"Analysis results saved to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Belief Variance Experiment — Analysis")
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Sentence-transformers model (default: {DEFAULT_EMBEDDING_MODEL})",
    )
    parser.add_argument(
        "--force-embed",
        action="store_true",
        help="Force re-computation of embeddings",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  BELIEF VARIANCE EXPERIMENT — ANALYSIS")
    print("=" * 60)

    # Load raw data
    print("\nLoading raw results...")
    data = load_raw_results()
    total_responses = sum(
        len(records)
        for pid_data in data.values()
        for records in pid_data.values()
    )
    print(f"Loaded {total_responses} responses across {len(data)} prompts.")

    if total_responses == 0:
        print("ERROR: No results found. Run runner.py first.")
        return

    # Compute embeddings
    print("\nComputing embeddings...")
    embeddings = compute_embeddings(data, args.embedding_model, args.force_embed)

    # Run analysis
    print("\nRunning analysis pipeline...")
    results = run_analysis(data, embeddings)

    # Generate figures
    print("\nGenerating figures...")
    generate_figures(results, data, embeddings)

    # Save results
    print("\nSaving results...")
    save_results(results)

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for domain in DOMAINS:
        ddata = results["per_domain"].get(domain, {})
        print(
            f"  {domain:25s}  "
            f"dH/dT = {ddata.get('mean_susceptibility', 0):.4f} "
            f"[{ddata.get('ci_lower', 0):.4f}, {ddata.get('ci_upper', 0):.4f}]  "
            f"held={ddata.get('n_held_contradictions', 0)}"
        )
    print(f"\n  Total held contradictions: {len(results['held_contradictions'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
