"""
Belief Variance Experiment — Density & Advanced Metrics Analysis
================================================================
Computes cluster compactness, mass distribution, density ratios,
peak persistence, silhouette scores, within-cluster cosine similarity,
template similarity, cross-model centroid distance, regime transition
curves, and Bhattacharyya overlap across model-specific subdirectories.

Usage:
    python analyze_density.py --all
    python analyze_density.py --data-dir results/raw/qwen3_14b
"""

import argparse
import json
import warnings
from collections import defaultdict
from pathlib import Path
from itertools import combinations

import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from scipy.spatial.distance import cdist
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.metrics.pairwise import cosine_distances, cosine_similarity

from prompts import ALL_PROMPTS, DOMAINS, PROMPT_BY_ID

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "results" / "raw"
EMBED_DIR = BASE_DIR / "results" / "embeddings"
OUTPUT_DIR = BASE_DIR / "results" / "density_analysis"
TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DBSCAN_EPS = 0.3
DBSCAN_MIN_SAMPLES = 3
MIN_RESPONSES = 5  # skip prompts with fewer responses

MODEL_DIRS = {
    "qwen3_14b": RAW_DIR / "qwen3_14b",
    "mistral_latest": RAW_DIR / "mistral_latest",
    "deepseek-r1_8b": RAW_DIR / "deepseek-r1_8b",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_model_data(data_dir: Path) -> dict[str, dict[float, list[dict]]]:
    """Load JSONL files from a model-specific directory."""
    data: dict[str, dict[float, list[dict]]] = defaultdict(lambda: defaultdict(list))
    if not data_dir.exists():
        print(f"  WARNING: directory not found: {data_dir}")
        return data
    for path in sorted(data_dir.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    data[record["prompt_id"]][record["temperature"]].append(record)
                except (json.JSONDecodeError, KeyError):
                    continue
    return data


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def compute_embeddings(
    data: dict[str, dict[float, list[dict]]],
    model_name: str,
    cache_prefix: str = "",
) -> dict[str, dict[float, np.ndarray]]:
    """Compute or load cached sentence embeddings."""
    from sentence_transformers import SentenceTransformer

    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    cached: dict[str, dict[float, np.ndarray]] = defaultdict(dict)
    to_embed: list[tuple[str, float, int, str]] = []

    for pid in data:
        for temp in data[pid]:
            cache_path = EMBED_DIR / f"{cache_prefix}{pid}_{temp}.npy"
            expected = len(data[pid][temp])
            if cache_path.exists():
                arr = np.load(cache_path)
                if arr.shape[0] == expected:
                    cached[pid][temp] = arr
                    continue
            for idx, rec in enumerate(data[pid][temp]):
                text = rec.get("response", "")
                if text.startswith("ERROR:"):
                    text = ""
                to_embed.append((pid, temp, idx, text))

    if to_embed:
        print(f"  Embedding {len(to_embed)} responses with {model_name}...")
        model = SentenceTransformer(model_name)
        groups: dict[tuple[str, float], dict[int, str]] = defaultdict(dict)
        for pid, temp, idx, text in to_embed:
            groups[(pid, temp)][idx] = text

        for (pid, temp), idx_text in groups.items():
            n = len(data[pid][temp])
            texts = [idx_text.get(i, data[pid][temp][i].get("response", "")) for i in range(n)]
            embeddings = model.encode(texts, show_progress_bar=False, batch_size=128)
            arr = np.array(embeddings)
            np.save(EMBED_DIR / f"{cache_prefix}{pid}_{temp}.npy", arr)
            cached[pid][temp] = arr
    else:
        print("  All embeddings cached.")

    return cached


# ---------------------------------------------------------------------------
# DBSCAN helper
# ---------------------------------------------------------------------------
def run_dbscan(emb: np.ndarray, eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES):
    """Run DBSCAN on cosine distance matrix. Returns labels."""
    distances = cosine_distances(emb)
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    return clustering.fit_predict(distances)


# ---------------------------------------------------------------------------
# Metric 1: Cluster compactness
# ---------------------------------------------------------------------------
def cluster_compactness(emb: np.ndarray) -> float:
    """Average cosine distance from each point to the centroid."""
    if len(emb) < 2:
        return 0.0
    centroid = emb.mean(axis=0, keepdims=True)
    dists = cosine_distances(emb, centroid).flatten()
    return float(np.mean(dists))


# ---------------------------------------------------------------------------
# Metric 2: Cluster mass distribution
# ---------------------------------------------------------------------------
def cluster_mass_distribution(labels: np.ndarray) -> dict:
    """Returns {label: fraction} including noise (-1)."""
    total = len(labels)
    if total == 0:
        return {}
    unique, counts = np.unique(labels, return_counts=True)
    return {int(l): float(c / total) for l, c in zip(unique, counts)}


# ---------------------------------------------------------------------------
# Metric 3: Density ratio (intra/inter cluster distance)
# ---------------------------------------------------------------------------
def density_ratio(emb: np.ndarray, labels: np.ndarray) -> float | None:
    """Ratio of mean intra-cluster to mean inter-cluster distance."""
    cluster_ids = [l for l in set(labels) if l >= 0]
    if len(cluster_ids) < 2:
        return None

    # Intra-cluster: mean pairwise distance within each cluster
    intra_dists = []
    centroids = []
    for cid in cluster_ids:
        mask = labels == cid
        cluster_emb = emb[mask]
        centroids.append(cluster_emb.mean(axis=0))
        if len(cluster_emb) < 2:
            continue
        d = cosine_distances(cluster_emb)
        iu = np.triu_indices(len(cluster_emb), k=1)
        intra_dists.extend(d[iu].tolist())

    if not intra_dists:
        return None

    # Inter-cluster: pairwise distances between centroids
    centroid_arr = np.array(centroids)
    inter_d = cosine_distances(centroid_arr)
    iu = np.triu_indices(len(centroid_arr), k=1)
    inter_dists = inter_d[iu]

    mean_inter = float(np.mean(inter_dists))
    if mean_inter < 1e-12:
        return None

    return float(np.mean(intra_dists) / mean_inter)


# ---------------------------------------------------------------------------
# Metric 4: Peak persistence
# ---------------------------------------------------------------------------
def peak_persistence(
    embeddings_by_temp: dict[float, np.ndarray],
    eps=DBSCAN_EPS,
    min_samples=DBSCAN_MIN_SAMPLES,
) -> dict:
    """Track which cluster centroid signatures persist across temperatures."""
    # For each temperature, get cluster centroids
    temp_centroids: dict[float, list[np.ndarray]] = {}
    for temp in sorted(embeddings_by_temp.keys()):
        emb = embeddings_by_temp[temp]
        if len(emb) < min_samples:
            continue
        labels = run_dbscan(emb, eps, min_samples)
        cluster_ids = [l for l in set(labels) if l >= 0]
        centroids = []
        for cid in cluster_ids:
            centroids.append(emb[labels == cid].mean(axis=0))
        temp_centroids[temp] = centroids

    if not temp_centroids:
        return {"persistent": 0, "transient": 0, "total_unique": 0}

    # Track unique cluster centers across temperatures by matching nearest centroids
    all_centroids = []
    centroid_temp_presence: list[set[float]] = []

    for temp, centroids in sorted(temp_centroids.items()):
        for c in centroids:
            matched = False
            for i, existing in enumerate(all_centroids):
                dist = float(cosine_distances(c.reshape(1, -1), existing.reshape(1, -1))[0, 0])
                if dist < DBSCAN_EPS:  # Same cluster if within eps
                    centroid_temp_presence[i].add(temp)
                    # Update centroid as running mean
                    all_centroids[i] = (all_centroids[i] + c) / 2
                    matched = True
                    break
            if not matched:
                all_centroids.append(c.copy())
                centroid_temp_presence.append({temp})

    persistent = sum(1 for s in centroid_temp_presence if len(s) >= 3)
    transient = sum(1 for s in centroid_temp_presence if len(s) == 1)
    return {
        "persistent": persistent,
        "transient": transient,
        "total_unique": len(all_centroids),
    }


# ---------------------------------------------------------------------------
# Metric 5: Silhouette scores
# ---------------------------------------------------------------------------
def compute_silhouette(emb: np.ndarray, labels: np.ndarray) -> float | None:
    """Silhouette score in full 384D space using cosine metric."""
    n_clusters = len(set(labels) - {-1})
    if n_clusters < 2 or len(emb) < 3:
        return None
    # Only score non-noise points
    mask = labels >= 0
    if mask.sum() < 3:
        return None
    try:
        return float(silhouette_score(emb[mask], labels[mask], metric="cosine"))
    except ValueError:
        return None


def domain_silhouette(
    all_emb: list[np.ndarray],
    all_domains: list[str],
) -> float | None:
    """Silhouette score treating domain as the cluster label."""
    if len(all_emb) < 10:
        return None
    emb = np.vstack(all_emb)
    # Map domain strings to ints
    unique_domains = sorted(set(all_domains))
    if len(unique_domains) < 2:
        return None
    domain_map = {d: i for i, d in enumerate(unique_domains)}
    labels = np.array([domain_map[d] for d in all_domains])
    try:
        return float(silhouette_score(emb, labels, metric="cosine"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Metric 6 & 7: Within-cluster cosine similarity / Template similarity
# ---------------------------------------------------------------------------
def within_cluster_cosine_sim(emb: np.ndarray, labels: np.ndarray) -> dict:
    """Per-cluster average pairwise cosine similarity."""
    result = {}
    for cid in set(labels):
        mask = labels == cid
        cluster_emb = emb[mask]
        if len(cluster_emb) < 2:
            result[int(cid)] = 1.0
            continue
        sim = cosine_similarity(cluster_emb)
        iu = np.triu_indices(len(cluster_emb), k=1)
        result[int(cid)] = float(np.mean(sim[iu]))
    return result


def template_similarity(cluster_sims: dict) -> float:
    """Average within-cluster cosine similarity across all clusters (excl noise)."""
    valid = [v for k, v in cluster_sims.items() if k >= 0]
    if not valid:
        # Fall back to noise cluster
        return cluster_sims.get(-1, 0.0)
    return float(np.mean(valid))


# ---------------------------------------------------------------------------
# Metric 8: Cross-model centroid distance
# ---------------------------------------------------------------------------
def cross_model_centroid_distances(
    model_embeddings: dict[str, dict[str, dict[float, np.ndarray]]],
) -> dict:
    """For each (prompt, temp), distance between centroids from different models."""
    results = {}
    model_names = sorted(model_embeddings.keys())
    for pid in PROMPT_BY_ID:
        results[pid] = {}
        for temp in TEMPERATURES:
            centroids = {}
            for mname in model_names:
                emb_dict = model_embeddings.get(mname, {})
                if pid in emb_dict and temp in emb_dict[pid]:
                    emb = emb_dict[pid][temp]
                    if len(emb) >= MIN_RESPONSES:
                        centroids[mname] = emb.mean(axis=0)
            # Pairwise distances
            pairs = {}
            for m1, m2 in combinations(sorted(centroids.keys()), 2):
                d = float(cosine_distances(
                    centroids[m1].reshape(1, -1),
                    centroids[m2].reshape(1, -1),
                )[0, 0])
                pairs[f"{m1}_vs_{m2}"] = d
            if pairs:
                results[pid][temp] = pairs
    return results


# ---------------------------------------------------------------------------
# Metric 9: Regime transition curve classification
# ---------------------------------------------------------------------------
def classify_regime(spreads_by_temp: dict[float, float]) -> dict:
    """
    Fit spread-vs-temperature and classify:
      - crack: sharp elbow (large second derivative)
      - gradient: linear growth
      - fog: gentle curve (sublinear)
      - compressed: flat (near-zero slope)
    """
    temps = sorted(spreads_by_temp.keys())
    if len(temps) < 3:
        return {"regime": "unknown", "slope": 0.0, "r2": 0.0}

    x = np.array(temps)
    y = np.array([spreads_by_temp[t] for t in temps])

    # Linear fit
    slope, intercept, r_value, _, _ = stats.linregress(x, y)
    r2 = r_value ** 2

    # Range of y
    y_range = y.max() - y.min()

    # Second derivative approximation
    if len(temps) >= 3:
        dy = np.diff(y)
        d2y = np.diff(dy)
        max_d2y = float(np.max(np.abs(d2y))) if len(d2y) > 0 else 0.0
    else:
        max_d2y = 0.0

    # Classification
    if y_range < 0.02:
        regime = "compressed"
    elif max_d2y > 0.1 and y_range > 0.05:
        regime = "crack"
    elif r2 > 0.85 and abs(slope) > 0.02:
        regime = "gradient"
    elif abs(slope) > 0.01:
        regime = "fog"
    else:
        regime = "compressed"

    return {
        "regime": regime,
        "slope": float(slope),
        "r2": float(r2),
        "y_range": float(y_range),
        "max_d2y": float(max_d2y),
    }


# ---------------------------------------------------------------------------
# Metric 10: Bhattacharyya overlap between domains
# ---------------------------------------------------------------------------
def bhattacharyya_coefficient(emb1: np.ndarray, emb2: np.ndarray, n_dims: int = 20) -> float:
    """
    Estimate Bhattacharyya coefficient between two embedding distributions.
    Projects to n_dims principal components for tractability.
    """
    if len(emb1) < 5 or len(emb2) < 5:
        return 0.0

    from sklearn.decomposition import PCA

    combined = np.vstack([emb1, emb2])
    n_components = min(n_dims, combined.shape[0] - 1, combined.shape[1])
    if n_components < 1:
        return 0.0

    pca = PCA(n_components=n_components)
    projected = pca.fit_transform(combined)
    p1 = projected[:len(emb1)]
    p2 = projected[len(emb1):]

    # Compute means and covariances
    mu1, mu2 = p1.mean(axis=0), p2.mean(axis=0)
    cov1 = np.cov(p1, rowvar=False) + np.eye(n_components) * 1e-6
    cov2 = np.cov(p2, rowvar=False) + np.eye(n_components) * 1e-6
    cov_avg = (cov1 + cov2) / 2

    # Bhattacharyya distance
    diff = mu1 - mu2
    try:
        inv_cov = np.linalg.inv(cov_avg)
        term1 = 0.125 * diff @ inv_cov @ diff
        sign, logdet_avg = np.linalg.slogdet(cov_avg)
        _, logdet1 = np.linalg.slogdet(cov1)
        _, logdet2 = np.linalg.slogdet(cov2)
        term2 = 0.5 * (logdet_avg - 0.5 * (logdet1 + logdet2))
        bd = term1 + term2
        # Coefficient = exp(-distance)
        return float(np.exp(-bd))
    except np.linalg.LinAlgError:
        return 0.0


def bhattacharyya_domain_overlap(
    data: dict[str, dict[float, list[dict]]],
    embeddings: dict[str, dict[float, np.ndarray]],
) -> dict:
    """Bhattacharyya coefficient between all domain pairs at each temperature."""
    # Collect embeddings by domain and temperature
    domain_embs: dict[str, dict[float, list[np.ndarray]]] = defaultdict(lambda: defaultdict(list))
    for pid in data:
        prompt_info = PROMPT_BY_ID.get(pid)
        if not prompt_info:
            continue
        domain = prompt_info["domain"]
        for temp in data[pid]:
            if pid in embeddings and temp in embeddings[pid]:
                domain_embs[domain][temp].append(embeddings[pid][temp])

    results = {}
    for d1, d2 in combinations(sorted(DOMAINS), 2):
        key = f"{d1}_vs_{d2}"
        results[key] = {}
        for temp in TEMPERATURES:
            e1_list = domain_embs.get(d1, {}).get(temp, [])
            e2_list = domain_embs.get(d2, {}).get(temp, [])
            if not e1_list or not e2_list:
                continue
            e1 = np.vstack(e1_list)
            e2 = np.vstack(e2_list)
            results[key][temp] = bhattacharyya_coefficient(e1, e2)
    return results


# ---------------------------------------------------------------------------
# Full per-model analysis
# ---------------------------------------------------------------------------
def analyze_model(
    model_name: str,
    data: dict[str, dict[float, list[dict]]],
    embeddings: dict[str, dict[float, np.ndarray]],
) -> dict:
    """Run all density metrics for a single model."""
    results = {
        "model": model_name,
        "per_prompt_temp": {},
        "per_prompt": {},
        "per_domain": {},
        "domain_silhouette": {},
        "bhattacharyya_overlap": {},
        "regime_summary": {},
        "three_metric_table": {},
    }

    # --- Per-prompt per-temperature metrics ---
    print(f"  [{model_name}] Computing per-prompt per-temperature metrics...")
    for pid in sorted(data.keys()):
        results["per_prompt_temp"][pid] = {}
        for temp in TEMPERATURES:
            if pid not in embeddings or temp not in embeddings[pid]:
                continue
            emb = embeddings[pid][temp]
            if len(emb) < MIN_RESPONSES:
                continue

            labels = run_dbscan(emb)
            compactness = cluster_compactness(emb)
            mass = cluster_mass_distribution(labels)
            dr = density_ratio(emb, labels)
            sil = compute_silhouette(emb, labels)
            wc_sim = within_cluster_cosine_sim(emb, labels)
            tmpl_sim = template_similarity(wc_sim)

            # Spread = mean pairwise cosine distance
            if len(emb) >= 2:
                d = cosine_distances(emb)
                iu = np.triu_indices(len(emb), k=1)
                spread = float(np.mean(d[iu]))
            else:
                spread = 0.0

            n_clusters = len([l for l in set(labels) if l >= 0])

            results["per_prompt_temp"][pid][str(temp)] = {
                "compactness": compactness,
                "cluster_mass": mass,
                "density_ratio": dr,
                "silhouette": sil,
                "within_cluster_sim": wc_sim,
                "template_similarity": tmpl_sim,
                "spread": spread,
                "n_clusters": n_clusters,
                "n_responses": len(emb),
            }

    # --- Per-prompt cross-temperature metrics ---
    print(f"  [{model_name}] Computing peak persistence and regime classification...")
    for pid in sorted(data.keys()):
        emb_by_temp = {}
        spread_by_temp = {}
        mode_by_temp = {}
        for temp in TEMPERATURES:
            if pid in embeddings and temp in embeddings[pid]:
                emb_by_temp[temp] = embeddings[pid][temp]
            pt = results["per_prompt_temp"].get(pid, {}).get(str(temp), {})
            if pt:
                spread_by_temp[temp] = pt["spread"]
                mode_by_temp[temp] = pt["n_clusters"]

        persistence = peak_persistence(emb_by_temp)
        regime = classify_regime(spread_by_temp) if len(spread_by_temp) >= 3 else {"regime": "unknown"}

        prompt_info = PROMPT_BY_ID.get(pid, {})
        results["per_prompt"][pid] = {
            "domain": prompt_info.get("domain", "unknown"),
            "persistence": persistence,
            "regime": regime,
        }

    # --- Domain-level silhouette ---
    print(f"  [{model_name}] Computing domain-level silhouette scores...")
    for temp in TEMPERATURES:
        all_emb = []
        all_domains = []
        for pid in data:
            prompt_info = PROMPT_BY_ID.get(pid)
            if not prompt_info:
                continue
            if pid in embeddings and temp in embeddings[pid]:
                emb = embeddings[pid][temp]
                if len(emb) >= MIN_RESPONSES:
                    all_emb.append(emb)
                    all_domains.extend([prompt_info["domain"]] * len(emb))
        sil = domain_silhouette(all_emb, all_domains)
        results["domain_silhouette"][str(temp)] = sil

    # --- Bhattacharyya overlap ---
    print(f"  [{model_name}] Computing Bhattacharyya domain overlap...")
    results["bhattacharyya_overlap"] = bhattacharyya_domain_overlap(data, embeddings)

    # --- Regime summary ---
    regime_counts = defaultdict(int)
    for pid, pdata in results["per_prompt"].items():
        r = pdata.get("regime", {}).get("regime", "unknown")
        regime_counts[r] += 1
    results["regime_summary"] = dict(regime_counts)

    # --- Three-metric table: spread growth + mode count + template similarity per domain ---
    print(f"  [{model_name}] Building three-metric table...")
    for domain in DOMAINS:
        domain_pids = [pid for pid in data if PROMPT_BY_ID.get(pid, {}).get("domain") == domain]
        if not domain_pids:
            continue

        # Spread growth: slope of spread vs temperature across domain prompts
        spread_slopes = []
        mode_counts_at_1 = []
        template_sims = []

        for pid in domain_pids:
            spreads = {}
            for temp in TEMPERATURES:
                pt = results["per_prompt_temp"].get(pid, {}).get(str(temp), {})
                if pt:
                    spreads[temp] = pt["spread"]
            if len(spreads) >= 2:
                x = np.array(sorted(spreads.keys()))
                y = np.array([spreads[t] for t in x])
                slope, _, _, _, _ = stats.linregress(x, y)
                spread_slopes.append(slope)

            # Mode count at T=1.0
            pt_1 = results["per_prompt_temp"].get(pid, {}).get("1.0", {})
            if pt_1:
                mode_counts_at_1.append(pt_1["n_clusters"])

            # Template similarity at T=1.0
            if pt_1 and "template_similarity" in pt_1:
                template_sims.append(pt_1["template_similarity"])

        results["three_metric_table"][domain] = {
            "mean_spread_growth": float(np.mean(spread_slopes)) if spread_slopes else 0.0,
            "std_spread_growth": float(np.std(spread_slopes)) if spread_slopes else 0.0,
            "mean_mode_count": float(np.mean(mode_counts_at_1)) if mode_counts_at_1 else 0.0,
            "mean_template_similarity": float(np.mean(template_sims)) if template_sims else 0.0,
            "n_prompts": len(domain_pids),
        }

    return results


# ---------------------------------------------------------------------------
# Summary printing
# ---------------------------------------------------------------------------
def print_summary(all_results: dict[str, dict], cross_model: dict | None = None) -> None:
    """Print formatted summary tables to stdout."""
    sep = "=" * 90

    for model_name, res in sorted(all_results.items()):
        print(f"\n{sep}")
        print(f"  MODEL: {model_name}")
        print(sep)

        # Three-metric table
        print(f"\n  THREE-METRIC TABLE (spread growth / mode count / template similarity)")
        print(f"  {'Domain':<25s} {'Spread dS/dT':>12s} {'Modes@T=1':>10s} {'Template Sim':>13s} {'N':>5s}")
        print(f"  {'-'*25} {'-'*12} {'-'*10} {'-'*13} {'-'*5}")
        for domain in DOMAINS:
            d = res["three_metric_table"].get(domain, {})
            if d:
                print(
                    f"  {domain:<25s} "
                    f"{d['mean_spread_growth']:>12.4f} "
                    f"{d['mean_mode_count']:>10.2f} "
                    f"{d['mean_template_similarity']:>13.4f} "
                    f"{d['n_prompts']:>5d}"
                )

        # Domain silhouette scores
        print(f"\n  DOMAIN SILHOUETTE SCORES (do domains separate in 384D?)")
        print(f"  {'Temp':<8s} {'Silhouette':>12s}")
        print(f"  {'-'*8} {'-'*12}")
        for temp in TEMPERATURES:
            sil = res["domain_silhouette"].get(str(temp))
            sil_str = f"{sil:.4f}" if sil is not None else "N/A"
            print(f"  {temp:<8.1f} {sil_str:>12s}")

        # Regime transition summary
        print(f"\n  REGIME CLASSIFICATION")
        for regime, count in sorted(res.get("regime_summary", {}).items()):
            print(f"    {regime:<15s}: {count}")

        # Bhattacharyya top overlaps
        print(f"\n  BHATTACHARYYA OVERLAP (top domain pairs at T=1.0)")
        bhat = res.get("bhattacharyya_overlap", {})
        pairs_at_1 = []
        for pair_key, temp_dict in bhat.items():
            val = temp_dict.get(1.0)
            if val is not None:
                pairs_at_1.append((pair_key, val))
        pairs_at_1.sort(key=lambda x: x[1], reverse=True)
        for pair_key, val in pairs_at_1[:5]:
            print(f"    {pair_key:<45s}: {val:.4f}")

    # Cross-model centroid distances
    if cross_model:
        print(f"\n{sep}")
        print("  CROSS-MODEL CENTROID DISTANCES (mean across prompts at T=1.0)")
        print(sep)
        pair_dists: dict[str, list[float]] = defaultdict(list)
        for pid, temp_dict in cross_model.items():
            if 1.0 in temp_dict:
                for pair, dist in temp_dict[1.0].items():
                    pair_dists[pair].append(dist)
        for pair, dists in sorted(pair_dists.items()):
            print(f"  {pair:<40s}: mean={np.mean(dists):.4f}  std={np.std(dists):.4f}  n={len(dists)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Density & Advanced Metrics Analysis")
    parser.add_argument("--all", action="store_true", help="Analyze all models")
    parser.add_argument("--data-dir", type=str, help="Path to a single model's raw data directory")
    parser.add_argument("--embedding-model", default=EMBEDDING_MODEL, help="Embedding model name")
    args = parser.parse_args()

    if not args.all and not args.data_dir:
        parser.error("Specify --all or --data-dir")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  DENSITY & ADVANCED METRICS ANALYSIS")
    print("=" * 60)

    # Determine which models to analyze
    if args.all:
        targets = {}
        for mname, mdir in MODEL_DIRS.items():
            if mdir.exists():
                targets[mname] = mdir
            else:
                print(f"  Skipping {mname}: directory not found ({mdir})")
    else:
        ddir = Path(args.data_dir)
        if not ddir.is_absolute():
            ddir = BASE_DIR / ddir
        mname = ddir.name
        targets = {mname: ddir}

    all_results: dict[str, dict] = {}
    model_embeddings: dict[str, dict[str, dict[float, np.ndarray]]] = {}

    for model_name, model_dir in targets.items():
        print(f"\n{'-'*60}")
        print(f"  Loading {model_name} from {model_dir}")
        print(f"{'-'*60}")

        data = load_model_data(model_dir)
        total = sum(len(recs) for pt in data.values() for recs in pt.values())
        print(f"  Loaded {total} responses across {len(data)} prompts")

        if total == 0:
            print(f"  Skipping {model_name}: no data")
            continue

        # Cache prefix keeps model embeddings separate
        prefix = f"{model_name}_" if model_name != "" else ""
        embeddings = compute_embeddings(data, args.embedding_model, cache_prefix=prefix)

        res = analyze_model(model_name, data, embeddings)
        all_results[model_name] = res
        model_embeddings[model_name] = embeddings

        # Save per-model results
        out_path = OUTPUT_DIR / f"{model_name}_density.json"
        # Convert numpy types for JSON serialization
        def make_serializable(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {str(k): make_serializable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [make_serializable(x) for x in obj]
            return obj

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(make_serializable(res), f, indent=2, ensure_ascii=False)
        print(f"  Saved: {out_path}")

    # Cross-model analysis
    cross_model = None
    if len(model_embeddings) >= 2:
        print(f"\n{'-'*60}")
        print("  Computing cross-model centroid distances...")
        print(f"{'-'*60}")
        cross_model = cross_model_centroid_distances(model_embeddings)
        out_path = OUTPUT_DIR / "cross_model_distances.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {pid: {str(t): v for t, v in tdata.items()} for pid, tdata in cross_model.items() if tdata},
                f, indent=2, ensure_ascii=False,
            )
        print(f"  Saved: {out_path}")

    # Print summary
    print_summary(all_results, cross_model)

    print(f"\n{'='*60}")
    print(f"  All results saved to {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
