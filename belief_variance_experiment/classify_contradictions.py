"""
Contradiction Cluster Classifier
=================================
For each prompt flagged as a "held contradiction" (DBSCAN found 2+ clusters
at T=1.0), classify whether the clusters represent:

  GENUINE_SPLIT    — model holds two meaningfully distinct positions
  HEDGE_VARIANT    — model says the same hedged nothing in different ways
  STYLISTIC_DRIFT  — differences are framing/style, not substance

Uses the same DBSCAN parameters and embedding model as analyze.py.

Usage:
    python classify_contradictions.py [--force-embed]
"""

import argparse
import json
import textwrap
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.metrics.pairwise import cosine_distances

from prompts import PROMPT_BY_ID

# ---------------------------------------------------------------------------
# Paths & constants — match analyze.py exactly
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "results" / "raw"
EMBED_DIR = BASE_DIR / "results" / "embeddings"
ANALYSIS_DIR = BASE_DIR / "results" / "analysis"

DBSCAN_EPS = 0.3
DBSCAN_MIN_SAMPLES = 2  # Lowered from 5 — data has ~30 responses per prompt (not 50)

CLASSIFICATION_LABELS = [
    "GENUINE_SPLIT",
    "HEDGE_VARIANT",
    "STYLISTIC_DRIFT",
    "INSUFFICIENT_DATA",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_held_contradictions() -> list[str]:
    """Load the list of held-contradiction prompt IDs from analysis results."""
    path = ANALYSIS_DIR / "analysis_results.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["held_contradictions"]


def find_raw_file(prompt_id: str, temperature: float) -> Path:
    """Find raw JSONL file, checking both flat and model-subdirectory layouts."""
    filename = f"{prompt_id}_{temperature}.jsonl"
    # Flat layout
    flat = RAW_DIR / filename
    if flat.exists():
        return flat
    # Model subdirectory layout
    for subdir in sorted(RAW_DIR.iterdir()):
        if subdir.is_dir():
            candidate = subdir / filename
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"Cannot find {filename} in {RAW_DIR} or its subdirectories")


def load_responses(prompt_id: str, temperature: float = 1.0) -> list[str]:
    """
    Load raw response texts for a prompt at a given temperature.
    Aggregates across all model subdirectories to maximize sample size.
    """
    filename = f"{prompt_id}_{temperature}.jsonl"
    responses = []

    # Collect from all sources: flat files and model subdirs
    candidates = [RAW_DIR / filename]
    for subdir in sorted(RAW_DIR.iterdir()):
        if subdir.is_dir():
            candidates.append(subdir / filename)

    for path in candidates:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                text = record.get("response", "")
                if text.startswith("ERROR:"):
                    text = ""
                responses.append(text)

    if not responses:
        raise FileNotFoundError(f"No raw data found for {prompt_id} T={temperature}")
    return responses


def load_embeddings(
    prompt_id: str, temperature: float, responses: list[str],
    model=None,
) -> tuple[np.ndarray, object]:
    """
    Load cached embeddings if they match the response count, otherwise recompute.
    Returns (embeddings_array, model) — model is loaded lazily on first recompute.
    """
    path = EMBED_DIR / f"{prompt_id}_{temperature}.npy"
    if path.exists():
        arr = np.load(path)
        if arr.shape[0] == len(responses):
            return arr, model

    # Recompute — embedding count doesn't match response count
    if model is None:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(responses, show_progress_bar=False, batch_size=128)
    arr = np.array(embeddings)
    return arr, model


# ---------------------------------------------------------------------------
# Cluster analysis
# ---------------------------------------------------------------------------
def run_dbscan(embeddings: np.ndarray) -> np.ndarray:
    """Run DBSCAN with the same parameters as analyze.py. Returns labels."""
    distances = cosine_distances(embeddings)
    clustering = DBSCAN(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES, metric="precomputed")
    return clustering.fit_predict(distances)


def cluster_metrics(embeddings: np.ndarray, labels: np.ndarray) -> dict:
    """
    Compute per-cluster and inter-cluster metrics.
    Returns dict with cluster info, distances, silhouette, representatives.
    """
    unique_labels = sorted(set(labels))
    cluster_ids = [l for l in unique_labels if l >= 0]

    if len(cluster_ids) < 2:
        return None

    dist_matrix = cosine_distances(embeddings)

    # Per-cluster: centroid, intra-cluster distance, member indices
    clusters = {}
    for cid in cluster_ids:
        mask = labels == cid
        indices = np.where(mask)[0]
        cluster_emb = embeddings[indices]
        centroid = cluster_emb.mean(axis=0)

        # Intra-cluster: mean pairwise cosine distance within cluster
        if len(indices) > 1:
            sub_dist = dist_matrix[np.ix_(indices, indices)]
            triu = np.triu_indices(len(indices), k=1)
            intra_dist = float(np.mean(sub_dist[triu]))
        else:
            intra_dist = 0.0

        # Representative: point closest to centroid
        centroid_dists = cosine_distances(cluster_emb, centroid.reshape(1, -1)).flatten()
        rep_order = np.argsort(centroid_dists)
        rep_indices = [int(indices[i]) for i in rep_order[:2]]  # top 2 closest to centroid

        clusters[cid] = {
            "indices": indices.tolist(),
            "size": int(len(indices)),
            "centroid": centroid,
            "intra_dist": intra_dist,
            "rep_indices": rep_indices,
        }

    # Inter-cluster distances (between centroids and between all member pairs)
    cluster_pairs = []
    for i, c1 in enumerate(cluster_ids):
        for c2 in cluster_ids[i + 1:]:
            # Centroid-to-centroid distance
            centroid_dist = float(cosine_distances(
                clusters[c1]["centroid"].reshape(1, -1),
                clusters[c2]["centroid"].reshape(1, -1),
            )[0, 0])

            # Mean distance between all cross-cluster pairs
            idx1 = clusters[c1]["indices"]
            idx2 = clusters[c2]["indices"]
            cross_dists = dist_matrix[np.ix_(idx1, idx2)]
            mean_cross_dist = float(np.mean(cross_dists))

            cluster_pairs.append({
                "clusters": (c1, c2),
                "centroid_distance": centroid_dist,
                "mean_cross_distance": mean_cross_dist,
            })

    # Silhouette score (excluding noise points)
    valid_mask = labels >= 0
    if valid_mask.sum() > 1 and len(set(labels[valid_mask])) >= 2:
        sil = float(silhouette_score(
            dist_matrix[np.ix_(valid_mask, valid_mask)],
            labels[valid_mask],
            metric="precomputed",
        ))
    else:
        sil = 0.0

    # Noise stats
    noise_count = int(np.sum(labels == -1))

    return {
        "clusters": clusters,
        "cluster_pairs": cluster_pairs,
        "silhouette": sil,
        "noise_count": noise_count,
        "n_clusters": len(cluster_ids),
    }


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------
def compute_thresholds(all_metrics: list[dict]) -> dict:
    """
    Compute classification thresholds from the data distribution.
    Uses percentiles of inter-cluster centroid distance and intra-cluster distance.
    """
    inter_dists = []
    intra_dists = []
    silhouettes = []
    separation_ratios = []

    for m in all_metrics:
        if m is None:
            continue
        for pair in m["cluster_pairs"]:
            inter_dists.append(pair["centroid_distance"])
        for cid, cdata in m["clusters"].items():
            intra_dists.append(cdata["intra_dist"])
        silhouettes.append(m["silhouette"])

        # Separation ratio: inter / max(intra) — higher = more genuine
        max_intra = max(c["intra_dist"] for c in m["clusters"].values()) or 1e-6
        best_inter = max(p["centroid_distance"] for p in m["cluster_pairs"])
        separation_ratios.append(best_inter / max_intra)

    inter_dists = np.array(inter_dists)
    separation_ratios = np.array(separation_ratios)
    silhouettes = np.array(silhouettes)

    return {
        "inter_p25": float(np.percentile(inter_dists, 25)),
        "inter_p50": float(np.percentile(inter_dists, 50)),
        "inter_p75": float(np.percentile(inter_dists, 75)),
        "separation_p33": float(np.percentile(separation_ratios, 33)),
        "separation_p66": float(np.percentile(separation_ratios, 66)),
        "silhouette_p33": float(np.percentile(silhouettes, 33)),
        "silhouette_p66": float(np.percentile(silhouettes, 66)),
    }


def classify_one(metrics: dict, thresholds: dict) -> str:
    """
    Classify a single held contradiction based on cluster geometry.

    GENUINE_SPLIT:    high separation ratio + high silhouette
    HEDGE_VARIANT:    low separation ratio (clusters overlap heavily)
    STYLISTIC_DRIFT:  moderate separation, not clearly genuine or hedge
    """
    if metrics is None:
        return "INSUFFICIENT_DATA"

    max_intra = max(c["intra_dist"] for c in metrics["clusters"].values()) or 1e-6
    best_inter = max(p["centroid_distance"] for p in metrics["cluster_pairs"])
    sep_ratio = best_inter / max_intra
    sil = metrics["silhouette"]

    # Primary signal: separation ratio
    # Secondary signal: silhouette score
    if sep_ratio >= thresholds["separation_p66"] and sil >= thresholds["silhouette_p33"]:
        return "GENUINE_SPLIT"
    elif sep_ratio <= thresholds["separation_p33"] or sil <= thresholds["silhouette_p33"]:
        return "HEDGE_VARIANT"
    else:
        return "STYLISTIC_DRIFT"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def build_report(
    held_ids: list[str],
    all_metrics: list[dict],
    classifications: list[str],
    responses_map: dict[str, list[str]],
    thresholds: dict,
) -> dict:
    """Build the full JSON report."""
    per_prompt = {}
    for pid, metrics, classification in zip(held_ids, all_metrics, classifications):
        responses = responses_map[pid]

        entry = {
            "prompt_id": pid,
            "domain": PROMPT_BY_ID[pid]["domain"],
            "prompt_text": PROMPT_BY_ID[pid]["text"],
            "classification": classification,
        }

        if metrics is not None:
            entry["silhouette"] = metrics["silhouette"]
            entry["n_clusters"] = metrics["n_clusters"]
            entry["noise_count"] = metrics["noise_count"]

            # Cluster details with representative responses
            cluster_details = []
            for cid, cdata in sorted(metrics["clusters"].items()):
                reps = [responses[i] for i in cdata["rep_indices"]]
                cluster_details.append({
                    "cluster_id": cid,
                    "size": cdata["size"],
                    "intra_cluster_distance": round(cdata["intra_dist"], 6),
                    "representative_responses": reps,
                })
            entry["clusters"] = cluster_details

            # Pair distances
            pair_details = []
            for pair in metrics["cluster_pairs"]:
                pair_details.append({
                    "cluster_a": pair["clusters"][0],
                    "cluster_b": pair["clusters"][1],
                    "centroid_distance": round(pair["centroid_distance"], 6),
                    "mean_cross_distance": round(pair["mean_cross_distance"], 6),
                })
            entry["cluster_pairs"] = pair_details

            max_intra = max(c["intra_dist"] for c in metrics["clusters"].values()) or 1e-6
            best_inter = max(p["centroid_distance"] for p in metrics["cluster_pairs"])
            entry["separation_ratio"] = round(best_inter / max_intra, 4)
        else:
            entry["error"] = "Could not compute cluster metrics (< 2 valid clusters)"

        per_prompt[pid] = entry

    # Summary
    by_type = defaultdict(int)
    by_domain = defaultdict(lambda: defaultdict(int))
    distances_by_type = defaultdict(list)

    for pid, classification in zip(held_ids, classifications):
        by_type[classification] += 1
        domain = PROMPT_BY_ID[pid]["domain"]
        by_domain[domain][classification] += 1

        entry = per_prompt[pid]
        if "separation_ratio" in entry:
            distances_by_type[classification].append({
                "separation_ratio": entry["separation_ratio"],
                "silhouette": entry["silhouette"],
            })

    avg_by_type = {}
    for cls in CLASSIFICATION_LABELS:
        entries = distances_by_type.get(cls, [])
        if entries:
            avg_by_type[cls] = {
                "count": len(entries),
                "mean_separation_ratio": round(
                    np.mean([e["separation_ratio"] for e in entries]), 4
                ),
                "mean_silhouette": round(
                    np.mean([e["silhouette"] for e in entries]), 4
                ),
            }
        else:
            avg_by_type[cls] = {"count": 0, "mean_separation_ratio": 0, "mean_silhouette": 0}

    summary = {
        "total_held_contradictions": len(held_ids),
        "by_classification": dict(by_type),
        "by_domain": {d: dict(v) for d, v in by_domain.items()},
        "averages_by_type": avg_by_type,
        "thresholds_used": thresholds,
    }

    return {
        "summary": summary,
        "per_prompt": per_prompt,
    }


def print_summary(report: dict) -> None:
    """Print a human-readable summary table."""
    summary = report["summary"]

    print()
    print("=" * 78)
    print("  CONTRADICTION CLUSTER CLASSIFICATION REPORT")
    print("=" * 78)

    # Classification counts
    print("\n  Classification Counts:")
    print("  " + "-" * 50)
    for cls in CLASSIFICATION_LABELS:
        count = summary["by_classification"].get(cls, 0)
        pct = count / summary["total_held_contradictions"] * 100
        bar = "#" * int(pct / 2)
        print(f"    {cls:20s}  {count:3d}  ({pct:5.1f}%)  {bar}")
    print(f"    {'TOTAL':20s}  {summary['total_held_contradictions']:3d}")

    # Averages by type
    print("\n  Average Metrics by Type:")
    print("  " + "-" * 60)
    print(f"    {'Type':20s}  {'Sep.Ratio':>10s}  {'Silhouette':>10s}  {'Count':>6s}")
    for cls in CLASSIFICATION_LABELS:
        avg = summary["averages_by_type"].get(cls, {})
        print(
            f"    {cls:20s}  {avg.get('mean_separation_ratio', 0):10.4f}  "
            f"{avg.get('mean_silhouette', 0):10.4f}  {avg.get('count', 0):6d}"
        )

    # By domain
    print("\n  By Domain:")
    print("  " + "-" * 70)
    header = f"    {'Domain':25s}"
    for cls in CLASSIFICATION_LABELS:
        header += f"  {cls[:8]:>8s}"
    header += f"  {'Total':>6s}"
    print(header)

    all_domains = sorted(summary["by_domain"].keys())
    for domain in all_domains:
        row = f"    {domain:25s}"
        total = 0
        for cls in CLASSIFICATION_LABELS:
            count = summary["by_domain"][domain].get(cls, 0)
            total += count
            row += f"  {count:8d}"
        row += f"  {total:6d}"
        print(row)

    # Thresholds used
    thresholds = summary["thresholds_used"]
    print("\n  Thresholds (data-derived percentiles):")
    print("  " + "-" * 50)
    print(f"    Separation ratio P33: {thresholds['separation_p33']:.4f}")
    print(f"    Separation ratio P66: {thresholds['separation_p66']:.4f}")
    print(f"    Silhouette P33:       {thresholds['silhouette_p33']:.4f}")
    print(f"    Silhouette P66:       {thresholds['silhouette_p66']:.4f}")
    print(f"    Inter-cluster P50:    {thresholds['inter_p50']:.4f}")

    # Top genuine splits
    print("\n  Top Genuine Splits (highest separation ratio):")
    print("  " + "-" * 70)
    genuine = [
        (pid, entry)
        for pid, entry in report["per_prompt"].items()
        if entry["classification"] == "GENUINE_SPLIT"
    ]
    genuine.sort(key=lambda x: x[1].get("separation_ratio", 0), reverse=True)
    for pid, entry in genuine[:10]:
        text = textwrap.shorten(entry["prompt_text"], width=50, placeholder="...")
        sep = entry.get("separation_ratio", 0)
        sil = entry.get("silhouette", 0)
        print(f"    {pid:10s}  sep={sep:.3f}  sil={sil:.3f}  {text}")
        # Show cluster representatives (first sentence only)
        for cl in entry.get("clusters", []):
            rep = textwrap.shorten(cl["representative_responses"][0], width=70, placeholder="...")
            print(f"      Cluster {cl['cluster_id']} ({cl['size']:2d}): {rep}")

    # Top hedge variants
    print("\n  Top Hedge Variants (lowest separation ratio):")
    print("  " + "-" * 70)
    hedges = [
        (pid, entry)
        for pid, entry in report["per_prompt"].items()
        if entry["classification"] == "HEDGE_VARIANT"
    ]
    hedges.sort(key=lambda x: x[1].get("separation_ratio", 0))
    for pid, entry in hedges[:5]:
        text = textwrap.shorten(entry["prompt_text"], width=50, placeholder="...")
        sep = entry.get("separation_ratio", 0)
        sil = entry.get("silhouette", 0)
        print(f"    {pid:10s}  sep={sep:.3f}  sil={sil:.3f}  {text}")

    print()
    print("=" * 78)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Classify held contradictions")
    parser.add_argument("--force-embed", action="store_true", help="Force recompute embeddings")
    args = parser.parse_args()

    print("Loading held contradictions...")
    held_ids = load_held_contradictions()
    print(f"Found {len(held_ids)} held contradictions to classify.")

    print("Loading embeddings and responses...")
    all_metrics = []
    responses_map = {}
    embed_model = None  # Lazy-loaded if recompute needed
    recomputed = 0

    for pid in held_ids:
        responses = load_responses(pid, temperature=1.0)
        responses_map[pid] = responses
        embeddings, embed_model = load_embeddings(pid, 1.0, responses, embed_model)
        if embeddings.shape[0] != len(responses):
            print(f"  WARNING: {pid} embedding/response mismatch, skipping")
            all_metrics.append(None)
            continue

        labels = run_dbscan(embeddings)
        metrics = cluster_metrics(embeddings, labels)
        all_metrics.append(metrics)

    # Compute data-driven thresholds
    valid_metrics = [m for m in all_metrics if m is not None]
    print(f"Successfully clustered {len(valid_metrics)}/{len(held_ids)} prompts.")

    thresholds = compute_thresholds(valid_metrics)

    # Classify each
    classifications = [classify_one(m, thresholds) for m in all_metrics]

    # Build and save report
    report = build_report(held_ids, all_metrics, classifications, responses_map, thresholds)

    output_path = ANALYSIS_DIR / "contradiction_classification.json"
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    print(f"\nReport saved to {output_path}")

    # Print human-readable summary
    print_summary(report)


if __name__ == "__main__":
    main()
