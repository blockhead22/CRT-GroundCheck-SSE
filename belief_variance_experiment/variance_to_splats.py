"""Variance-to-Loci Pipeline
================================
Converts LLM belief variance experiment output into BeliefLocus instances.

The key insight: each prompt's response distribution across 100 samples
IS a Gaussian (or mixture of Gaussians) in embedding space. The mean
of the response embeddings = the locus center (mu). The per-dimension
variance of the response embeddings = the locus covariance (sigma).
The inverse of the entropy = confidence (alpha).

This means LLM response distributions under temperature variation
are LITERALLY belief loci already. No conversion needed — just
extraction.

For each prompt at each temperature, we get one locus.
For each prompt ACROSS temperatures, we get a trajectory.
That trajectory is the input to predictive contradiction detection.

The multi-modal prompts (where DBSCAN finds 2+ clusters) become
MULTIPLE loci per prompt — representing held contradictions in
the model's belief space.
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances

# Add parent path so we can import personal_agent as a package
_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from personal_agent.memory_splats import BeliefLocus, create_locus, MemorySplat, create_splat
from personal_agent.info_geometry import fisher_rao_distance
from personal_agent.predictive_contradiction import (
    extract_trajectory, analyze_convergence, Urgency,
)
from personal_agent.disposition_classifier import (
    Disposition, DispositionSignals, classify_contradiction,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "results" / "raw"
EMBED_DIR = BASE_DIR / "results" / "embeddings"
SPLAT_DIR = BASE_DIR / "results" / "splats"

TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_embeddings() -> dict[str, dict[float, np.ndarray]]:
    """Load cached embeddings from analyze.py's output.

    Returns: {prompt_id: {temperature: ndarray(N, dim)}}
    """
    data: dict[str, dict[float, np.ndarray]] = defaultdict(dict)
    if not EMBED_DIR.exists():
        print(f"No embeddings found at {EMBED_DIR}")
        print("Run analyze.py first to generate embeddings.")
        return data

    for path in sorted(EMBED_DIR.glob("*.npy")):
        # filename format: {prompt_id}_{temperature}.npy
        stem = path.stem
        # Split on last underscore (prompt_id may contain underscores)
        last_under = stem.rfind("_")
        if last_under < 0:
            continue
        prompt_id = stem[:last_under]
        try:
            temp = float(stem[last_under + 1:])
        except ValueError:
            continue
        data[prompt_id][temp] = np.load(path)

    return data


def load_raw_metadata() -> dict[str, dict]:
    """Load prompt metadata (domain, text) from raw JSONL files."""
    meta: dict[str, dict] = {}
    if not RAW_DIR.exists():
        return meta

    for path in sorted(RAW_DIR.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                pid = record["prompt_id"]
                if pid not in meta:
                    meta[pid] = {
                        "domain": record.get("domain", "unknown"),
                        "text": "",  # original text not in raw, but domain is
                    }
                break  # one record per file is enough for metadata
    return meta


# ---------------------------------------------------------------------------
# Core conversion: response distribution -> BeliefLocus
# ---------------------------------------------------------------------------
@dataclass
class BeliefSplat:
    """A belief extracted from LLM response distribution.

    This wraps BeliefLocus with experiment-specific metadata.
    """
    splat: BeliefLocus
    prompt_id: str
    domain: str
    temperature: float
    n_responses: int
    n_clusters: int  # from DBSCAN — 1=unimodal, 2+=multi-modal
    entropy: float  # semantic entropy at this temperature
    cluster_label: int  # which cluster this splat represents (-1 for all)


def distribution_to_splat(
    prompt_id: str,
    embeddings: np.ndarray,
    temperature: float,
    domain: str = "unknown",
    confidence_from_entropy: bool = True,
) -> BeliefSplat:
    """Convert a response distribution into a single BeliefLocus.

    mu = mean of embeddings (the model's "average belief")
    sigma = per-dimension variance (the model's uncertainty shape)
    alpha = inverse entropy (high entropy = low confidence)
    """
    mu = np.mean(embeddings, axis=0).astype(np.float32)
    sigma = np.var(embeddings, axis=0).astype(np.float32)

    # Floor sigma to avoid degenerate zero-variance dimensions
    sigma = np.maximum(sigma, 1e-8)

    # Compute entropy for confidence
    distances = cosine_distances(embeddings)
    # Use adaptive eps: median pairwise distance * 0.5
    upper_tri = distances[np.triu_indices_from(distances, k=1)]
    adaptive_eps = float(np.median(upper_tri) * 0.5) if len(upper_tri) > 0 else 0.3
    adaptive_eps = max(adaptive_eps, 0.05)  # floor
    clustering = DBSCAN(eps=adaptive_eps, min_samples=5, metric="precomputed")
    labels = clustering.fit_predict(distances)
    unique_labels = set(labels)
    counts = [np.sum(labels == l) for l in unique_labels]
    total = sum(counts)
    if total > 0:
        probs = np.array(counts) / total
        entropy = -np.sum(probs * np.log2(probs + 1e-12))
    else:
        entropy = 0.0

    n_clusters = len([l for l in unique_labels if l >= 0])

    # Confidence: inverse entropy, normalized to [0, 1]
    # entropy=0 -> alpha=1.0 (completely certain)
    # entropy=3 -> alpha~0.25 (very uncertain)
    if confidence_from_entropy:
        alpha = float(1.0 / (1.0 + entropy))
    else:
        alpha = 0.8  # default

    belief_locus = BeliefLocus(
        memory_id=f"llm_{prompt_id}_T{temperature}",
        mu=mu,
        sigma=sigma,
        alpha=alpha,
        text=f"LLM belief: {prompt_id} at T={temperature}",
        memory_type="belief",
        created_at=temperature,  # use temperature as pseudo-time for trajectory
        last_updated=temperature,
    )

    return BeliefSplat(
        splat=belief_locus,
        prompt_id=prompt_id,
        domain=domain,
        temperature=temperature,
        n_responses=len(embeddings),
        n_clusters=n_clusters,
        entropy=entropy,
        cluster_label=-1,
    )


def distribution_to_multi_splats(
    prompt_id: str,
    embeddings: np.ndarray,
    temperature: float,
    domain: str = "unknown",
    eps: float = 0.3,
    min_samples: int = 5,
) -> list[BeliefSplat]:
    """Convert a multi-modal response distribution into MULTIPLE loci.

    If DBSCAN finds 2+ clusters, each cluster becomes its own locus.
    This represents held contradictions: the model has 2+ stable
    positions on the same question.

    If unimodal, returns a single locus (same as distribution_to_splat).
    """
    distances = cosine_distances(embeddings)
    # Use adaptive eps if default is too tight
    upper_tri = distances[np.triu_indices_from(distances, k=1)]
    adaptive_eps = float(np.median(upper_tri) * 0.5) if len(upper_tri) > 0 else eps
    adaptive_eps = max(adaptive_eps, 0.05)
    clustering = DBSCAN(eps=adaptive_eps, min_samples=min_samples, metric="precomputed")
    labels = clustering.fit_predict(distances)

    unique_real = sorted(set(l for l in labels if l >= 0))

    if len(unique_real) <= 1:
        # Unimodal — return single splat
        return [distribution_to_splat(prompt_id, embeddings, temperature, domain)]

    # Multi-modal — one splat per cluster
    splats = []
    for cluster_id in unique_real:
        mask = labels == cluster_id
        cluster_embeddings = embeddings[mask]

        if len(cluster_embeddings) < 3:
            continue

        mu = np.mean(cluster_embeddings, axis=0).astype(np.float32)
        sigma = np.var(cluster_embeddings, axis=0).astype(np.float32)
        sigma = np.maximum(sigma, 1e-8)

        # Confidence proportional to cluster size
        cluster_fraction = len(cluster_embeddings) / len(embeddings)
        alpha = float(cluster_fraction)

        belief_locus = BeliefLocus(
            memory_id=f"llm_{prompt_id}_T{temperature}_c{cluster_id}",
            mu=mu,
            sigma=sigma,
            alpha=alpha,
            text=f"LLM belief: {prompt_id} at T={temperature}, cluster {cluster_id}",
            memory_type="belief",
            created_at=temperature,
            last_updated=temperature,
        )

        splats.append(BeliefSplat(
            splat=belief_locus,
            prompt_id=prompt_id,
            domain=domain,
            temperature=temperature,
            n_responses=len(cluster_embeddings),
            n_clusters=len(unique_real),
            entropy=0.0,  # computed per-cluster doesn't apply
            cluster_label=cluster_id,
        ))

    return splats


# ---------------------------------------------------------------------------
# Trajectory construction: splats across temperatures for one prompt
# ---------------------------------------------------------------------------
@dataclass
class BeliefTrajectory:
    """A prompt's belief evolution across temperatures.

    Temperature acts as a "perturbation intensity" -- analogous to
    time in the standard locus trajectory. As temperature rises,
    the model's belief may:
      - Stay stable (factual_settled)
      - Widen smoothly (growing uncertainty)
      - Split into modes (held contradiction revealed)
      - Phase-transition (discontinuous jump)
    """
    prompt_id: str
    domain: str
    splats_by_temp: dict[float, list[BeliefSplat]]
    primary_splats: list[BeliefLocus]  # one per temp, for trajectory analysis

    # Computed metrics
    susceptibility: float = 0.0  # dH/dT
    is_multi_modal: bool = False  # any temperature shows 2+ clusters
    max_clusters: int = 1
    phase_transition_temp: Optional[float] = None  # temp where modality jumps


def build_trajectory(
    prompt_id: str,
    embeddings_by_temp: dict[float, np.ndarray],
    domain: str = "unknown",
) -> BeliefTrajectory:
    """Build a full belief trajectory for one prompt across temperatures."""
    splats_by_temp: dict[float, list[BeliefSplat]] = {}
    primary_splats: list[BeliefLocus] = []

    sorted_temps = sorted(embeddings_by_temp.keys())

    for temp in sorted_temps:
        emb = embeddings_by_temp[temp]
        if len(emb) == 0:
            continue

        # Get multi-modal decomposition
        multi = distribution_to_multi_splats(prompt_id, emb, temp, domain)
        splats_by_temp[temp] = multi

        # Primary splat = the full-distribution splat (for trajectory)
        primary = distribution_to_splat(prompt_id, emb, temp, domain)
        primary_splats.append(primary.splat)

    # Wire up trajectory snapshots on primary splats
    # Each primary splat at temperature T gets all previous states as trajectory
    if len(primary_splats) >= 2:
        for i in range(1, len(primary_splats)):
            for j in range(i):
                primary_splats[i].trajectory.append({
                    'mu': primary_splats[j].mu.copy(),
                    'sigma': primary_splats[j].sigma.copy(),
                    'alpha': primary_splats[j].alpha,
                    'timestamp': primary_splats[j].created_at,
                })

    # Compute susceptibility (from entropy vs temperature)
    if len(sorted_temps) >= 2:
        entropies = []
        temps = []
        for temp in sorted_temps:
            if temp in splats_by_temp and splats_by_temp[temp]:
                entropies.append(splats_by_temp[temp][0].entropy)
                temps.append(temp)
        if len(temps) >= 2:
            from scipy.stats import linregress
            slope, _, _, _, _ = linregress(temps, entropies)
            susceptibility = slope
        else:
            susceptibility = 0.0
    else:
        susceptibility = 0.0

    # Detect multi-modality
    max_clusters = max(
        (max(s.n_clusters for s in slist) if slist else 1)
        for slist in splats_by_temp.values()
    ) if splats_by_temp else 1

    is_multi_modal = max_clusters >= 2

    # Detect phase transition
    phase_transition_temp = None
    if len(sorted_temps) >= 2:
        cluster_counts = []
        for temp in sorted_temps:
            if temp in splats_by_temp:
                cluster_counts.append(
                    max(s.n_clusters for s in splats_by_temp[temp])
                    if splats_by_temp[temp] else 1
                )
            else:
                cluster_counts.append(1)

        for i in range(1, len(cluster_counts)):
            if cluster_counts[i] > cluster_counts[i - 1]:
                phase_transition_temp = sorted_temps[i]
                break

    return BeliefTrajectory(
        prompt_id=prompt_id,
        domain=domain,
        splats_by_temp=splats_by_temp,
        primary_splats=primary_splats,
        susceptibility=susceptibility,
        is_multi_modal=is_multi_modal,
        max_clusters=max_clusters,
        phase_transition_temp=phase_transition_temp,
    )


# ---------------------------------------------------------------------------
# Cross-prompt analysis: contradiction detection between beliefs
# ---------------------------------------------------------------------------
@dataclass
class LLMContradiction:
    """A detected contradiction between two LLM beliefs."""
    prompt_a: str
    prompt_b: str
    domain_a: str
    domain_b: str
    fisher_distance: float
    cosine_sim: float
    overlap: float
    urgency: str  # from predictive contradiction
    disposition: str  # from disposition classifier


def find_cross_prompt_contradictions(
    trajectories: dict[str, BeliefTrajectory],
    temperature: float = 1.0,
    fisher_threshold: float = 5.0,
    cosine_threshold: float = 0.7,
) -> list[LLMContradiction]:
    """Find contradictions between different prompts' beliefs.

    Two beliefs contradict if they are semantically similar (high cosine)
    but informationally distant (high Fisher). This means: they talk
    about similar things but the model is uncertain between them.
    """
    contradictions = []
    prompt_ids = sorted(trajectories.keys())

    for i in range(len(prompt_ids)):
        traj_a = trajectories[prompt_ids[i]]
        if temperature not in traj_a.splats_by_temp:
            continue
        splat_a = traj_a.primary_splats[-1] if traj_a.primary_splats else None
        if splat_a is None:
            continue

        for j in range(i + 1, len(prompt_ids)):
            traj_b = trajectories[prompt_ids[j]]
            if temperature not in traj_b.splats_by_temp:
                continue
            splat_b = traj_b.primary_splats[-1] if traj_b.primary_splats else None
            if splat_b is None:
                continue

            # Compute distances
            cos = float(np.dot(splat_a.mu, splat_b.mu) / (
                np.linalg.norm(splat_a.mu) * np.linalg.norm(splat_b.mu) + 1e-10
            ))

            if cos < cosine_threshold:
                continue  # not similar enough to contradict

            fisher = fisher_rao_distance(splat_a, splat_b)

            if fisher < fisher_threshold:
                continue  # not informationally distant enough

            # This is a contradiction candidate: similar topic, different belief
            from personal_agent.memory_splats import overlap_integral
            overlap = overlap_integral(splat_a, splat_b)

            contradictions.append(LLMContradiction(
                prompt_a=prompt_ids[i],
                prompt_b=prompt_ids[j],
                domain_a=traj_a.domain,
                domain_b=traj_b.domain,
                fisher_distance=fisher,
                cosine_sim=cos,
                overlap=overlap,
                urgency="detected",
                disposition="unknown",
            ))

    # Sort by Fisher distance (most informative contradictions first)
    contradictions.sort(key=lambda c: c.fisher_distance, reverse=True)
    return contradictions


def find_held_contradictions(
    trajectories: dict[str, BeliefTrajectory],
) -> list[dict]:
    """Find prompts where the model holds two stable positions.

    A held contradiction is a prompt where:
    - At T=1.0, DBSCAN finds 2+ clusters
    - Each major cluster has >20% of responses
    - The clusters are semantically distinct (cosine distance > 0.2)

    These are the LLM's version of "held contradictions" — topics
    where the model genuinely doesn't have a settled position.
    """
    held = []

    for pid, traj in trajectories.items():
        if not traj.is_multi_modal:
            continue

        # Check T=1.0 specifically
        target_temp = 1.0
        if target_temp not in traj.splats_by_temp:
            continue

        cluster_splats = traj.splats_by_temp[target_temp]
        if len(cluster_splats) < 2:
            continue

        # Check cluster sizes
        total_responses = sum(s.n_responses for s in cluster_splats)
        major_clusters = [
            s for s in cluster_splats
            if s.n_responses / total_responses > 0.20
        ]

        if len(major_clusters) < 2:
            continue

        # Check semantic distance between cluster centers
        for ci in range(len(major_clusters)):
            for cj in range(ci + 1, len(major_clusters)):
                a = major_clusters[ci].splat
                b = major_clusters[cj].splat
                cos = float(np.dot(a.mu, b.mu) / (
                    np.linalg.norm(a.mu) * np.linalg.norm(b.mu) + 1e-10
                ))
                cos_dist = 1.0 - cos

                if cos_dist > 0.2:  # semantically distinct
                    fisher = fisher_rao_distance(a, b)
                    held.append({
                        "prompt_id": pid,
                        "domain": traj.domain,
                        "n_clusters": len(cluster_splats),
                        "cluster_sizes": [s.n_responses for s in cluster_splats],
                        "cosine_distance": cos_dist,
                        "fisher_distance": fisher,
                        "susceptibility": traj.susceptibility,
                        "phase_transition_temp": traj.phase_transition_temp,
                    })

    # Sort by Fisher distance
    held.sort(key=lambda h: h["fisher_distance"], reverse=True)
    return held


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
def run_pipeline(save: bool = True) -> dict:
    """Run the full variance-to-splats pipeline.

    1. Load embeddings (from analyze.py)
    2. Convert each prompt's distribution to splats
    3. Build trajectories across temperatures
    4. Detect cross-prompt contradictions
    5. Find held contradictions
    6. Save results
    """
    print("=" * 60)
    print("  VARIANCE → LOCI PIPELINE")
    print("=" * 60)

    # 1. Load
    print("\n[1/5] Loading embeddings...")
    embeddings = load_embeddings()
    metadata = load_raw_metadata()

    if not embeddings:
        print("No embeddings found. Run the experiment and analyze.py first.")
        return {}

    print(f"  Loaded {len(embeddings)} prompts")

    # 2-3. Build trajectories
    print("\n[2/5] Building belief trajectories...")
    trajectories: dict[str, BeliefTrajectory] = {}

    for pid, temp_embeddings in embeddings.items():
        domain = metadata.get(pid, {}).get("domain", "unknown")
        traj = build_trajectory(pid, temp_embeddings, domain)
        trajectories[pid] = traj

    # Stats
    n_total = len(trajectories)
    n_multi = sum(1 for t in trajectories.values() if t.is_multi_modal)
    n_phase = sum(1 for t in trajectories.values() if t.phase_transition_temp is not None)

    print(f"  {n_total} trajectories built")
    print(f"  {n_multi} multi-modal ({n_multi/n_total*100:.1f}%)")
    print(f"  {n_phase} with phase transitions ({n_phase/n_total*100:.1f}%)")

    # Domain breakdown
    print("\n  Susceptibility by domain:")
    from collections import Counter
    domain_suscept = defaultdict(list)
    for t in trajectories.values():
        domain_suscept[t.domain].append(t.susceptibility)

    for domain in sorted(domain_suscept.keys()):
        vals = domain_suscept[domain]
        print(f"    {domain:20s}: mean={np.mean(vals):.4f}, "
              f"std={np.std(vals):.4f}, n={len(vals)}")

    # 4. Cross-prompt contradictions
    print("\n[3/5] Detecting cross-prompt contradictions...")
    contradictions = find_cross_prompt_contradictions(trajectories)
    print(f"  {len(contradictions)} contradiction pairs found")

    if contradictions:
        print(f"  Top 3:")
        for c in contradictions[:3]:
            print(f"    {c.prompt_a} <-> {c.prompt_b}: "
                  f"Fisher={c.fisher_distance:.2f}, cos={c.cosine_sim:.3f}")

    # 5. Held contradictions
    print("\n[4/5] Finding held contradictions...")
    held = find_held_contradictions(trajectories)
    print(f"  {len(held)} held contradictions found")

    if held:
        print(f"  Top 5:")
        for h in held[:5]:
            print(f"    {h['prompt_id']} ({h['domain']}): "
                  f"{h['n_clusters']} clusters, "
                  f"Fisher={h['fisher_distance']:.2f}, "
                  f"suscept={h['susceptibility']:.4f}")

    # 6. Save
    results = {
        "n_prompts": n_total,
        "n_multi_modal": n_multi,
        "n_phase_transitions": n_phase,
        "n_contradictions": len(contradictions),
        "n_held": len(held),
        "domain_susceptibility": {
            d: {"mean": float(np.mean(v)), "std": float(np.std(v)), "n": len(v)}
            for d, v in domain_suscept.items()
        },
        "held_contradictions": held,
        "top_contradictions": [
            {
                "prompt_a": c.prompt_a,
                "prompt_b": c.prompt_b,
                "domain_a": c.domain_a,
                "domain_b": c.domain_b,
                "fisher_distance": c.fisher_distance,
                "cosine_sim": c.cosine_sim,
            }
            for c in contradictions[:50]
        ],
        "trajectories_summary": {
            pid: {
                "domain": t.domain,
                "susceptibility": t.susceptibility,
                "is_multi_modal": t.is_multi_modal,
                "max_clusters": t.max_clusters,
                "phase_transition_temp": t.phase_transition_temp,
                "n_primary_splats": len(t.primary_splats),
            }
            for pid, t in trajectories.items()
        },
    }

    if save:
        SPLAT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = SPLAT_DIR / "pipeline_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n[5/5] Results saved to {out_path}")

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)

    return results


# ---------------------------------------------------------------------------
# Synthetic test (runs without experiment data)
# ---------------------------------------------------------------------------
def run_synthetic_test():
    """Test the pipeline with synthetic data.

    Creates fake response distributions that simulate:
    - factual_settled: tight cluster, low variance
    - moral_ambiguous: two distinct clusters (held contradiction)
    - opinion: wide single cluster, high variance
    """
    print("=" * 60)
    print("  SYNTHETIC TEST")
    print("=" * 60)

    np.random.seed(42)
    dim = 384

    # Create a base direction for each "topic"
    topic_a = np.random.randn(dim).astype(np.float32)
    topic_a /= np.linalg.norm(topic_a)

    topic_b = np.random.randn(dim).astype(np.float32)
    topic_b /= np.linalg.norm(topic_b)

    topic_c = np.random.randn(dim).astype(np.float32)
    topic_c /= np.linalg.norm(topic_c)

    results = {}

    for temp in TEMPERATURES:
        noise_scale = 0.01 + temp * 0.05  # more noise at higher temp

        # Factual: tight cluster around topic_a
        factual_embs = np.array([
            topic_a + np.random.randn(dim).astype(np.float32) * noise_scale * 0.3
            for _ in range(100)
        ])

        # Moral ambiguous: two clusters that split at higher temps
        if temp >= 0.7:
            # Two distinct positions — need enough separation for DBSCAN
            # In 384D, add a large directional offset so cosine distance > eps
            offset = np.random.randn(dim).astype(np.float32)
            offset /= np.linalg.norm(offset)
            cluster1 = np.array([
                topic_b + np.random.randn(dim).astype(np.float32) * noise_scale * 0.5
                for _ in range(50)
            ])
            cluster2 = np.array([
                topic_b + offset * 2.0 + np.random.randn(dim).astype(np.float32) * noise_scale * 0.5
                for _ in range(50)
            ])
            moral_embs = np.vstack([cluster1, cluster2])
        else:
            moral_embs = np.array([
                topic_b + np.random.randn(dim).astype(np.float32) * noise_scale
                for _ in range(100)
            ])

        # Opinion: wide single cluster
        opinion_embs = np.array([
            topic_c + np.random.randn(dim).astype(np.float32) * noise_scale * 2.0
            for _ in range(100)
        ])

        results[f"synth_factual_{temp}"] = factual_embs
        results[f"synth_moral_{temp}"] = moral_embs
        results[f"synth_opinion_{temp}"] = opinion_embs

    # Build trajectories
    synth_embeds: dict[str, dict[float, np.ndarray]] = defaultdict(dict)
    for key, embs in results.items():
        parts = key.rsplit("_", 1)
        prompt_id = parts[0]
        temp = float(parts[1])
        synth_embeds[prompt_id][temp] = embs

    print("\nBuilding trajectories from synthetic data...")
    trajectories: dict[str, BeliefTrajectory] = {}
    domains = {"synth_factual": "factual_settled", "synth_moral": "moral_ambiguous", "synth_opinion": "opinion_aesthetic"}
    for pid, temp_embs in synth_embeds.items():
        domain = domains.get(pid, "unknown")
        traj = build_trajectory(pid, temp_embs, domain)
        trajectories[pid] = traj

    # Report
    for pid, traj in trajectories.items():
        print(f"\n  {pid}:")
        print(f"    Domain: {traj.domain}")
        print(f"    Susceptibility (dH/dT): {traj.susceptibility:.4f}")
        print(f"    Multi-modal: {traj.is_multi_modal}")
        print(f"    Max clusters: {traj.max_clusters}")
        print(f"    Phase transition at T={traj.phase_transition_temp}")
        print(f"    Primary splats: {len(traj.primary_splats)}")

        if traj.primary_splats:
            first = traj.primary_splats[0]
            last = traj.primary_splats[-1]
            print(f"    Uncertainty (T=0): {first.total_uncertainty:.4f}")
            print(f"    Uncertainty (T=max): {last.total_uncertainty:.4f}")
            print(f"    Confidence (T=0): {first.alpha:.4f}")
            print(f"    Confidence (T=max): {last.alpha:.4f}")

    # Cross-prompt analysis
    print("\n  Cross-prompt contradictions:")
    contras = find_cross_prompt_contradictions(trajectories, temperature=1.0,
                                                fisher_threshold=0.0,
                                                cosine_threshold=-1.0)
    for c in contras[:5]:
        print(f"    {c.prompt_a} <-> {c.prompt_b}: "
              f"Fisher={c.fisher_distance:.2f}, cos={c.cosine_sim:.3f}")

    # Held contradictions
    print("\n  Held contradictions:")
    held = find_held_contradictions(trajectories)
    if held:
        for h in held:
            print(f"    {h['prompt_id']}: {h['n_clusters']} clusters, "
                  f"Fisher={h['fisher_distance']:.2f}")
    else:
        print("    None detected (expected: synth_moral should show at T>=0.7)")

    # Test predictive contradiction on the trajectory
    print("\n  Predictive contradiction (factual trajectory):")
    factual_traj = trajectories.get("synth_factual")
    if factual_traj and len(factual_traj.primary_splats) >= 2:
        state = extract_trajectory(factual_traj.primary_splats[-1])
        if state:
            print(f"    Center speed: {state.center_speed:.6f}")
            print(f"    Cov velocity: {state.covariance_velocity:.6f}")
            print(f"    Widening: {state.is_widening}")

    print("\n" + "=" * 60)
    print("  SYNTHETIC TEST COMPLETE")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Variance → Loci Pipeline")
    parser.add_argument("--synthetic", action="store_true",
                        help="Run synthetic test (no experiment data needed)")
    parser.add_argument("--no-save", action="store_true",
                        help="Don't save results to disk")
    args = parser.parse_args()

    if args.synthetic:
        run_synthetic_test()
    else:
        run_pipeline(save=not args.no_save)
