"""
Robustness Sweep — Analyzer Perturbation Study
================================================
Tests whether the three-regime taxonomy (discrete fracture, continuous spread,
compressed templating) survives changes to:
  1. DBSCAN eps values (0.2, 0.3, 0.4, 0.5)
  2. Embedding model (MiniLM vs mpnet)
  3. Text normalization (raw vs normalized)

Runs on FROZEN response data — no new API calls needed.

Usage:
    python robustness_sweep.py --data-dir results/raw/qwen3_14b
    python robustness_sweep.py --data-dir results/raw/mistral_latest
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances, cosine_similarity

from prompts import ALL_PROMPTS, DOMAINS, PROMPT_BY_ID

BASE_DIR = Path(__file__).parent
TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]

EPS_VALUES = [0.2, 0.3, 0.4, 0.5]
EMBEDDING_MODELS = ["all-MiniLM-L6-v2", "all-mpnet-base-v2"]


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------
def normalize_response(text: str) -> str:
    """Collapse numeric variants, strip filler, normalize surface forms."""
    if not text or text.startswith("ERROR:"):
        return ""
    t = text.strip()
    # Collapse numeric approximations: "approximately 299,792" -> "~NUM"
    t = re.sub(r'approximately\s+[\d,]+\.?\d*', '~NUM', t, flags=re.IGNORECASE)
    t = re.sub(r'about\s+[\d,]+\.?\d*', '~NUM', t, flags=re.IGNORECASE)
    t = re.sub(r'around\s+[\d,]+\.?\d*', '~NUM', t, flags=re.IGNORECASE)
    t = re.sub(r'roughly\s+[\d,]+\.?\d*', '~NUM', t, flags=re.IGNORECASE)
    # Collapse bare large numbers with commas: "299,792,458" -> "NUM"
    t = re.sub(r'\b\d{1,3}(,\d{3})+(\.\d+)?\b', 'NUM', t)
    # Collapse unit variants
    t = re.sub(r'kilometers?\s*per\s*second', 'km/s', t, flags=re.IGNORECASE)
    t = re.sub(r'miles?\s*per\s*second', 'mi/s', t, flags=re.IGNORECASE)
    t = re.sub(r'meters?\s*per\s*second', 'm/s', t, flags=re.IGNORECASE)
    t = re.sub(r'km/s|m/s|mi/s', 'SPEED_UNIT', t)
    # Strip common filler phrases
    fillers = [
        r'\bthis is a complex (issue|question|topic)\b',
        r'\bthere are (multiple|many|various|different) perspectives\b',
        r'\bit depends on\b',
        r'\bthis is subjective\b',
        r'\bopinions (vary|differ)\b',
        r'\bgenerally speaking\b',
        r'\bin general\b',
        r'\boverall\b',
        r'\bhowever\b',
        r'\bthat being said\b',
    ]
    for filler in fillers:
        t = re.sub(filler, '', t, flags=re.IGNORECASE)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_raw(data_dir: Path) -> dict:
    """Load {prompt_id: {temperature: [response_texts]}}"""
    data = defaultdict(lambda: defaultdict(list))
    for path in sorted(data_dir.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                pid = record["prompt_id"]
                temp = record["temperature"]
                resp = record.get("response", "")
                data[pid][temp].append(resp)
    return data


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
def embed_texts(texts: list[str], model) -> np.ndarray:
    """Embed a list of texts, return (N, dim) array."""
    return model.encode(texts, show_progress_bar=False, batch_size=128)


# ---------------------------------------------------------------------------
# Metrics (per prompt-temperature cell)
# ---------------------------------------------------------------------------
def compute_cell_metrics(embeddings: np.ndarray, eps: float) -> dict:
    """Compute spread, mode count, template similarity for one cell."""
    n = len(embeddings)
    if n < 5:
        return {"spread": 0.0, "mode_count": 0, "template_sim": 1.0, "entropy": 0.0}

    dists = cosine_distances(embeddings)
    tri = dists[np.triu_indices(n, k=1)]
    spread = float(tri.mean()) if len(tri) > 0 else 0.0

    # DBSCAN clustering
    clustering = DBSCAN(eps=eps, min_samples=5, metric="precomputed")
    labels = clustering.fit_predict(dists)
    unique_labels = set(labels)
    mode_count = len([l for l in unique_labels if l >= 0])

    # Template similarity: mean within-cluster cosine similarity
    sims = cosine_similarity(embeddings)
    if mode_count > 0:
        within_sims = []
        for label in unique_labels:
            if label < 0:
                continue
            mask = labels == label
            if mask.sum() < 2:
                continue
            cluster_sims = sims[np.ix_(mask, mask)]
            tri_idx = np.triu_indices(mask.sum(), k=1)
            within_sims.extend(cluster_sims[tri_idx].tolist())
        template_sim = float(np.mean(within_sims)) if within_sims else 1.0
    else:
        # No clusters — compute overall similarity
        tri_sims = sims[np.triu_indices(n, k=1)]
        template_sim = float(tri_sims.mean()) if len(tri_sims) > 0 else 1.0

    # Entropy
    counts = []
    for label in unique_labels:
        counts.append(int(np.sum(labels == label)))
    total = sum(counts)
    probs = np.array(counts) / total if total > 0 else np.array([1.0])
    entropy = float(-np.sum(probs * np.log2(probs + 1e-12)))

    # Held contradiction check at this cell
    held = False
    if mode_count >= 2:
        cluster_sizes = sorted([np.sum(labels == l) for l in unique_labels if l >= 0], reverse=True)
        if len(cluster_sizes) >= 2:
            if cluster_sizes[0] / n > 0.2 and cluster_sizes[1] / n > 0.2:
                held = True

    return {
        "spread": spread,
        "mode_count": mode_count,
        "template_sim": template_sim,
        "entropy": entropy,
        "held": held,
    }


# ---------------------------------------------------------------------------
# Per-prompt cross-temperature metrics
# ---------------------------------------------------------------------------
def compute_prompt_metrics(cell_metrics: dict[float, dict]) -> dict:
    """Compute susceptibility and spread growth across temperatures."""
    temps = sorted(cell_metrics.keys())
    if len(temps) < 2:
        return {"dH_dT": 0.0, "spread_growth": 0.0, "max_modes": 0, "held_at_1": False}

    entropies = [cell_metrics[t]["entropy"] for t in temps]
    spreads = [cell_metrics[t]["spread"] for t in temps]
    modes = [cell_metrics[t]["mode_count"] for t in temps]

    # dH/dT via linear regression
    if len(temps) >= 2 and np.std(entropies) > 0:
        slope, _, _, _, _ = __import__("scipy.stats", fromlist=["linregress"]).linregress(temps, entropies)
        dH_dT = float(slope)
    else:
        dH_dT = 0.0

    # Spread growth: T=max minus T=0
    spread_growth = spreads[-1] - spreads[0] if len(spreads) >= 2 else 0.0

    # Max mode count across temps
    max_modes = max(modes)

    # Held contradiction at T=1.0
    held_at_1 = cell_metrics.get(1.0, {}).get("held", False)

    return {
        "dH_dT": dH_dT,
        "spread_growth": float(spread_growth),
        "max_modes": max_modes,
        "held_at_1": held_at_1,
    }


# ---------------------------------------------------------------------------
# Domain aggregation
# ---------------------------------------------------------------------------
def aggregate_by_domain(prompt_metrics: dict[str, dict]) -> dict[str, dict]:
    """Aggregate prompt-level metrics by domain."""
    domain_data = defaultdict(list)
    for pid, metrics in prompt_metrics.items():
        if pid in PROMPT_BY_ID:
            domain = PROMPT_BY_ID[pid]["domain"]
        else:
            # Try to infer from prefix
            prefix = pid.split("_")[0] + "_" + pid.split("_")[1] if "_" in pid else pid[:2]
            domain_map = {"fs": "factual_settled", "fc": "factual_contested",
                         "ma": "moral_ambiguous", "mc": "moral_clear", "oa": "opinion_aesthetic"}
            domain = domain_map.get(pid[:2], "unknown")
        domain_data[domain].append(metrics)

    results = {}
    for domain, metrics_list in sorted(domain_data.items()):
        dH_dTs = [m["dH_dT"] for m in metrics_list]
        spreads = [m["spread_growth"] for m in metrics_list]
        max_modes_list = [m["max_modes"] for m in metrics_list]
        held_count = sum(1 for m in metrics_list if m["held_at_1"])

        results[domain] = {
            "n": len(metrics_list),
            "mean_dH_dT": float(np.mean(dH_dTs)),
            "mean_spread_growth": float(np.mean(spreads)),
            "mean_max_modes": float(np.mean(max_modes_list)),
            "held_contradictions": held_count,
        }
    return results


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------
def run_sweep(data_dir: Path):
    print(f"\n{'='*60}")
    print(f"  ROBUSTNESS SWEEP — {data_dir.name}")
    print(f"{'='*60}\n")

    # Load raw data
    raw_data = load_raw(data_dir)
    n_prompts = len(raw_data)
    n_responses = sum(len(resps) for pid in raw_data for resps in raw_data[pid].values())
    print(f"Loaded {n_responses} responses across {n_prompts} prompts.\n")

    if n_prompts == 0:
        print("ERROR: No data found.")
        return

    # Also prepare normalized versions
    norm_data = defaultdict(lambda: defaultdict(list))
    for pid in raw_data:
        for temp in raw_data[pid]:
            norm_data[pid][temp] = [normalize_response(r) for r in raw_data[pid][temp]]

    results = {}

    for emb_model_name in EMBEDDING_MODELS:
        print(f"\n--- Embedding model: {emb_model_name} ---")
        from sentence_transformers import SentenceTransformer
        emb_model = SentenceTransformer(emb_model_name)

        for text_mode in ["raw", "normalized"]:
            print(f"  Text mode: {text_mode}")
            source = raw_data if text_mode == "raw" else norm_data

            # Embed all texts
            embeddings = {}
            all_texts = []
            text_keys = []
            for pid in source:
                for temp in source[pid]:
                    for i, text in enumerate(source[pid][temp]):
                        all_texts.append(text if text else " ")
                        text_keys.append((pid, temp, i))

            print(f"    Embedding {len(all_texts)} texts...")
            all_embs = emb_model.encode(all_texts, show_progress_bar=False, batch_size=256)

            # Rebuild into {pid: {temp: ndarray}}
            emb_dict = defaultdict(lambda: defaultdict(list))
            for (pid, temp, i), emb in zip(text_keys, all_embs):
                emb_dict[pid][temp].append(emb)
            for pid in emb_dict:
                for temp in emb_dict[pid]:
                    emb_dict[pid][temp] = np.array(emb_dict[pid][temp])

            for eps in EPS_VALUES:
                config_key = f"{emb_model_name.split('/')[-1]}|{text_mode}|eps={eps}"
                print(f"    eps={eps}...", end=" ")

                # Compute per-prompt metrics
                prompt_metrics = {}
                for pid in emb_dict:
                    cell_metrics = {}
                    for temp in sorted(emb_dict[pid].keys()):
                        cell_metrics[temp] = compute_cell_metrics(emb_dict[pid][temp], eps)
                    prompt_metrics[pid] = compute_prompt_metrics(cell_metrics)

                # Aggregate by domain
                domain_results = aggregate_by_domain(prompt_metrics)
                results[config_key] = domain_results

                # Quick summary
                domains_str = " | ".join(
                    f"{d[:8]}={domain_results[d]['mean_dH_dT']:.4f}"
                    for d in sorted(domain_results.keys())
                )
                total_held = sum(domain_results[d]["held_contradictions"] for d in domain_results)
                print(f"{domains_str} | held={total_held}")

        del emb_model  # Free GPU/RAM

    # ---------------------------------------------------------------------------
    # Summary: Check regime invariance
    # ---------------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  REGIME INVARIANCE CHECK")
    print(f"{'='*60}\n")

    # Check 1: Does factual > moral ordering hold across all configs?
    ordering_holds = 0
    ordering_total = 0
    for config_key, domain_results in results.items():
        fs = domain_results.get("factual_settled", {}).get("mean_dH_dT", 0)
        fc = domain_results.get("factual_contested", {}).get("mean_dH_dT", 0)
        mc = domain_results.get("moral_clear", {}).get("mean_dH_dT", 0)
        ma = domain_results.get("moral_ambiguous", {}).get("mean_dH_dT", 0)
        factual_mean = (fs + fc) / 2
        moral_mean = (mc + ma) / 2
        ordering_total += 1
        if factual_mean > moral_mean:
            ordering_holds += 1
            status = "PASS"
        else:
            status = "FAIL"
        print(f"  {status} factual({factual_mean:.4f}) > moral({moral_mean:.4f}) — {config_key}")

    print(f"\n  Domain ordering: {ordering_holds}/{ordering_total} configs pass\n")

    # Check 2: Spread growth by domain across configs
    print("  SPREAD GROWTH (mean across configs):")
    domain_spreads = defaultdict(list)
    for config_key, domain_results in results.items():
        for domain, metrics in domain_results.items():
            domain_spreads[domain].append(metrics["mean_spread_growth"])

    for domain in sorted(domain_spreads.keys()):
        vals = domain_spreads[domain]
        print(f"    {domain:20s}: mean={np.mean(vals):.4f}, std={np.std(vals):.4f}, "
              f"min={np.min(vals):.4f}, max={np.max(vals):.4f}")

    # Check 3: Mode count stability
    print("\n  MODE COUNT (mean max_modes across configs):")
    domain_modes = defaultdict(list)
    for config_key, domain_results in results.items():
        for domain, metrics in domain_results.items():
            domain_modes[domain].append(metrics["mean_max_modes"])

    for domain in sorted(domain_modes.keys()):
        vals = domain_modes[domain]
        print(f"    {domain:20s}: mean={np.mean(vals):.2f}, std={np.std(vals):.2f}, "
              f"min={np.min(vals):.2f}, max={np.max(vals):.2f}")

    # Check 4: Held contradictions stability
    print("\n  HELD CONTRADICTIONS (total across configs):")
    domain_held = defaultdict(list)
    for config_key, domain_results in results.items():
        for domain, metrics in domain_results.items():
            domain_held[domain].append(metrics["held_contradictions"])

    for domain in sorted(domain_held.keys()):
        vals = domain_held[domain]
        print(f"    {domain:20s}: mean={np.mean(vals):.1f}, min={min(vals)}, max={max(vals)}")

    # Save full results
    output_path = BASE_DIR / "results" / "analysis" / f"robustness_sweep_{data_dir.name}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Full results saved to {output_path}")

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robustness sweep over analyzer parameters")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to raw JSONL data directory")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: Directory not found: {data_dir}")
        sys.exit(1)

    run_sweep(data_dir)
