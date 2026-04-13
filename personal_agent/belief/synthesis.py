"""
Belief Synthesis Engine — Sprint 9

Answers worldview questions from compressed belief trajectories,
not individual fact recall:
- "What do I care about?"   → thematic synthesis across hundreds of memories
- "How have I changed?"     → temporal belief trajectory analysis
- "What contradicts?"       → contradiction-aware synthesis surfacing tensions

Design:
- Clustering uses existing 384D embeddings (all-MiniLM-L6-v2) + scipy agglomerative
- LLM used ONLY for natural-language prose generation
- Structural analysis (clustering, trajectories, tensions) is deterministic
- No new database tables — computed on-the-fly from existing memory + ledger
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryPoint:
    """A single point on a belief trajectory timeline."""
    value: str
    timestamp: float
    trust: float
    source: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BeliefTrajectory:
    """Temporal evolution of a belief/slot over time."""
    slot_or_theme: str
    snapshots: List[TrajectoryPoint]
    drift_magnitude: float        # total semantic drift across all transitions
    is_oscillating: bool          # True if value reverts to a prior value

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["snapshots"] = [s.to_dict() for s in self.snapshots]
        return d


@dataclass
class BeliefCluster:
    """A thematic grouping of related memories."""
    theme: str                         # human-readable label
    memory_ids: List[str]
    memory_texts: List[str]
    trust_range: Tuple[float, float]
    temporal_span: Tuple[float, float]
    centroid_vector: Optional[np.ndarray]
    contradiction_count: int
    confidence: float                  # representativeness within this cluster

    def to_dict(self) -> Dict:
        return {
            "theme": self.theme,
            "memory_count": len(self.memory_ids),
            "memory_texts": self.memory_texts[:5],  # representative sample
            "trust_range": list(self.trust_range),
            "temporal_span": list(self.temporal_span),
            "contradiction_count": self.contradiction_count,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class SynthesisResult:
    """Complete result of a belief synthesis operation."""
    synthesis_type: str                # "thematic" | "trajectory" | "contradiction_aware"
    summary_text: str                  # LLM-generated natural language synthesis
    clusters: List[BeliefCluster] = field(default_factory=list)
    trajectories: List[BeliefTrajectory] = field(default_factory=list)
    unresolved_tensions: List[Tuple[str, str]] = field(default_factory=list)
    representativeness: float = 0.0    # 0-1 how well synthesis covers evidence
    evidence_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "synthesis_type": self.synthesis_type,
            "summary_text": self.summary_text,
            "clusters": [c.to_dict() for c in self.clusters],
            "trajectories": [t.to_dict() for t in self.trajectories],
            "unresolved_tensions": self.unresolved_tensions,
            "representativeness": round(self.representativeness, 3),
            "evidence_count": self.evidence_count,
        }


# ---------------------------------------------------------------------------
# Query classification
# ---------------------------------------------------------------------------

_THEMATIC_PATTERNS = [
    r"what\s+do\s+(?:you\s+)?(?:know|remember)\s+about",
    r"(?:tell|show)\s+me\s+(?:about|what)\s+(?:me|my|i)",
    r"tell\s+me\s+what\s+you\s+(?:know|remember)\s+about\s+me",
    r"summar(?:ize|y)\s+(?:everything|all|me|my|what)",
    r"what\s+(?:do\s+)?i\s+care\s+about",
    r"what(?:'s|\s+is)\s+important\s+to\s+me",
    r"what\s+are\s+my\s+(?:interests?|hobbies?|values?|priorities?)",
    r"what\s+defines?\s+me",
    r"describe\s+me",
    r"who\s+am\s+i\s+(?:to\s+you|in\s+your)",
    r"what\s+(?:do\s+)?you\s+(?:think|believe)\s+about\s+me",
]

_TRAJECTORY_PATTERNS = [
    r"how\s+have\s+i\s+changed",
    r"how\s+have\s+my\s+(?:views?|opinions?|preferences?|beliefs?)\s+(?:changed|evolved|shifted)",
    r"what(?:'s|\s+has)\s+(?:changed|different)\s+about\s+(?:me|my)",
    r"how\s+(?:has|have)\s+(?:my|i)\s+(?:evolved|grown|shifted)",
    r"(?:show|tell)\s+me\s+(?:how|what)\s+(?:i(?:'ve)?|my)\s+(?:changed|evolved)",
    r"timeline\s+of\s+(?:my|how\s+i)",
    r"what\s+did\s+i\s+used?\s+to\s+(?:think|believe|feel)",
    r"track\s+(?:my|how)\s+(?:changes?|evolution)",
]

_CONTRADICTION_PATTERNS = [
    r"what\s+(?:are\s+)?my\s+contradictions?",
    r"where\s+do\s+i\s+contradict\s+(?:myself|me)",
    r"what(?:'s|\s+is)\s+inconsistent\s+(?:about|in)\s+(?:me|my|what)",
    r"(?:show|find|list)\s+(?:my\s+)?contradictions?",
    r"where\s+(?:am\s+i|do\s+i)\s+(?:inconsistent|conflicting)",
    r"what\s+tensions?\s+(?:exist|are\s+there)\s+in\s+(?:my|what)",
    r"conflicting\s+(?:beliefs?|views?|opinions?)",
]


def classify_synthesis_query(text: str) -> Optional[str]:
    """Classify a query as a synthesis type, or None if not a synthesis query.

    Returns: "thematic", "trajectory", "contradiction_aware", or None.
    """
    if not text:
        return None
    t = text.strip().lower()

    for pattern in _CONTRADICTION_PATTERNS:
        if re.search(pattern, t):
            return "contradiction_aware"

    for pattern in _TRAJECTORY_PATTERNS:
        if re.search(pattern, t):
            return "trajectory"

    for pattern in _THEMATIC_PATTERNS:
        if re.search(pattern, t):
            return "thematic"

    # Legacy compatibility: category + action patterns from _is_synthesis_query
    category_words = ("interests", "hobbies", "technologies", "skills",
                      "languages", "preferences", "values", "priorities")
    action_words = ("what", "tell", "list", "show", "describe")
    if any(w in t for w in category_words) and any(w in t for w in action_words):
        return "thematic"

    return None


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_beliefs(
    memories: list,
    distance_threshold: float = 0.65,
    min_cluster_size: int = 2,
) -> List[BeliefCluster]:
    """Cluster memories by semantic similarity using agglomerative clustering.

    Uses existing 384D vectors on MemoryItem objects.
    Returns clusters sorted by total evidence weight (sum of trust).
    """
    from scipy.cluster.hierarchy import fcluster, linkage

    if len(memories) < min_cluster_size:
        return []

    # Extract vectors — skip memories without valid vectors
    valid = []
    for m in memories:
        vec = getattr(m, "vector", None)
        if vec is not None and hasattr(vec, "__len__") and len(vec) > 0:
            valid.append(m)

    if len(valid) < min_cluster_size:
        return []

    # Build matrix
    vectors = np.array([m.vector for m in valid], dtype=np.float32)

    # Normalize for cosine distance
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    normalized = vectors / norms

    # Agglomerative clustering with cosine-like distance
    # Use 1 - cosine_sim = 1 - dot(a, b) as distance (vectors are already normalized)
    try:
        Z = linkage(normalized, method="average", metric="cosine")
        labels = fcluster(Z, t=distance_threshold, criterion="distance")
    except Exception as e:
        logger.warning("[SYNTHESIS] Clustering failed: %s", e)
        return []

    # Group by label
    groups: Dict[int, list] = defaultdict(list)
    for mem, label in zip(valid, labels):
        groups[label].append(mem)

    # Build BeliefCluster for each group
    clusters = []
    for label, mems in groups.items():
        if len(mems) < min_cluster_size:
            continue

        trusts = [m.trust for m in mems]
        timestamps = [m.timestamp for m in mems]

        # Trust-weighted centroid
        weights = np.array(trusts, dtype=np.float32)
        weight_sum = weights.sum()
        if weight_sum > 0:
            vecs = np.array([m.vector for m in mems], dtype=np.float32)
            centroid = np.average(vecs, axis=0, weights=weights)
        else:
            centroid = np.mean([m.vector for m in mems], axis=0)

        # Label the cluster by extracting dominant topics
        theme = _label_cluster(mems)

        # Count contradictions in this cluster
        contra_count = sum(getattr(m, "contradiction_count", 0) for m in mems)

        # Confidence: based on cluster tightness (avg pairwise similarity)
        if len(mems) >= 2:
            norm_vecs = normalized[[i for i, (mem, lab) in enumerate(zip(valid, labels)) if lab == label]]
            if len(norm_vecs) >= 2:
                sims = norm_vecs @ norm_vecs.T
                # Average of upper triangle
                mask = np.triu(np.ones_like(sims, dtype=bool), k=1)
                avg_sim = float(sims[mask].mean()) if mask.sum() > 0 else 0.5
                confidence = max(0.0, min(1.0, avg_sim))
            else:
                confidence = 0.5
        else:
            confidence = 0.5

        clusters.append(BeliefCluster(
            theme=theme,
            memory_ids=[m.memory_id for m in mems],
            memory_texts=[m.text for m in mems],
            trust_range=(min(trusts), max(trusts)),
            temporal_span=(min(timestamps), max(timestamps)),
            centroid_vector=centroid,
            contradiction_count=contra_count,
            confidence=confidence,
        ))

    # Sort by total evidence weight (sum of trust in cluster)
    clusters.sort(key=lambda c: sum(
        t for t in [c.trust_range[0], c.trust_range[1]]
    ) * len(c.memory_ids), reverse=True)

    return clusters


def _label_cluster(memories: list) -> str:
    """Generate a short label for a cluster based on dominant slots and keywords."""
    from ..fact_slots import extract_fact_slots

    slot_counter: Counter = Counter()
    word_counter: Counter = Counter()
    _STOP = {"i", "my", "me", "a", "the", "is", "am", "was", "are", "to",
             "in", "it", "of", "and", "or", "for", "that", "this", "with",
             "on", "at", "but", "be", "have", "has", "had", "do", "does",
             "not", "no", "so", "if", "an", "as", "from", "about", "up",
             "out", "just", "also", "been", "some", "like", "than", "can",
             "will", "would", "could", "should", "very", "really", "you",
             "your", "they", "their", "its", "we", "our", "he", "she",
             "him", "her", "his", "them", "what", "which", "when", "where",
             "how", "who", "all", "each", "every", "both", "few", "more",
             "most", "other", "only", "own", "same", "into", "over", "such",
             "get", "got", "went", "go", "know", "think", "want", "new"}

    for m in memories:
        text = getattr(m, "text", "")
        # Extract slots
        try:
            slots = extract_fact_slots(text)
            for slot_name, _val in slots:
                slot_counter[slot_name] += 1
        except Exception:
            pass

        # Keyword extraction (simple tf)
        words = re.findall(r"[a-z]{3,}", text.lower())
        for w in words:
            if w not in _STOP:
                word_counter[w] += 1

    # Prefer slot names as labels
    if slot_counter:
        top_slot = slot_counter.most_common(1)[0][0]
        # Humanize: "employer" -> "Career/Employer", "programming_language" -> "Programming Languages"
        label = top_slot.replace("_", " ").title()
        return label

    # Fall back to most common meaningful word
    if word_counter:
        top_words = [w for w, _c in word_counter.most_common(3)]
        return " / ".join(top_words).title()

    return "Miscellaneous"


# ---------------------------------------------------------------------------
# Belief trajectories
# ---------------------------------------------------------------------------

def build_belief_trajectory(
    memories: list,
    slot: str,
) -> Optional[BeliefTrajectory]:
    """Build a temporal trajectory for a specific slot across memories.

    Returns None if fewer than 2 distinct values exist.
    """
    from ..fact_slots import extract_fact_slots
    from ..crt_core import encode_vector

    # Collect (timestamp, value, trust, source) for this slot
    points: List[Tuple[float, str, float, str]] = []
    for m in memories:
        text = getattr(m, "text", "")
        try:
            slots = extract_fact_slots(text)
        except Exception:
            continue
        for slot_name, value in slots:
            if slot_name == slot and value:
                points.append((
                    m.timestamp,
                    value.strip(),
                    m.trust,
                    m.source.value if hasattr(m.source, "value") else str(m.source),
                ))

    if len(points) < 2:
        return None

    # Sort by timestamp
    points.sort(key=lambda p: p[0])

    # Deduplicate consecutive identical values
    deduped: List[Tuple[float, str, float, str]] = [points[0]]
    for p in points[1:]:
        if p[1].lower() != deduped[-1][1].lower():
            deduped.append(p)

    if len(deduped) < 2:
        return None

    # Build snapshots
    snapshots = [
        TrajectoryPoint(value=v, timestamp=ts, trust=t, source=src)
        for ts, v, t, src in deduped
    ]

    # Compute drift: pairwise cosine distance between consecutive value embeddings
    total_drift = 0.0
    try:
        for i in range(len(deduped) - 1):
            vec_a = encode_vector(deduped[i][1])
            vec_b = encode_vector(deduped[i + 1][1])
            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)
            if norm_a > 0 and norm_b > 0:
                cos_sim = np.dot(vec_a, vec_b) / (norm_a * norm_b)
                total_drift += 1.0 - max(0.0, float(cos_sim))
    except Exception as e:
        logger.warning("[SYNTHESIS] Drift computation failed: %s", e)

    # Detect oscillation: value reverts to a prior value
    seen_values: Set[str] = set()
    is_oscillating = False
    for ts, v, t, src in deduped:
        v_lower = v.lower()
        if v_lower in seen_values:
            is_oscillating = True
            break
        seen_values.add(v_lower)

    return BeliefTrajectory(
        slot_or_theme=slot,
        snapshots=snapshots,
        drift_magnitude=total_drift,
        is_oscillating=is_oscillating,
    )


def find_trajectory_slots(memories: list) -> List[str]:
    """Find all slots that have 2+ distinct values across memories (trajectory candidates)."""
    from ..fact_slots import extract_fact_slots

    slot_values: Dict[str, Set[str]] = defaultdict(set)

    for m in memories:
        text = getattr(m, "text", "")
        try:
            slots = extract_fact_slots(text)
            for slot_name, value in slots:
                if value:
                    slot_values[slot_name].add(value.strip().lower())
        except Exception:
            continue

    return [slot for slot, vals in slot_values.items() if len(vals) >= 2]


# ---------------------------------------------------------------------------
# Tension detection
# ---------------------------------------------------------------------------

def detect_unresolved_tensions(
    clusters: List[BeliefCluster],
    ledger,
) -> List[Tuple[str, str]]:
    """Detect unresolved tensions from the contradiction ledger and intra-cluster divergence.

    Phase G1: disposition-aware filtering.
    - ``held`` and ``evolving`` contradictions are genuine tensions to surface.
    - ``resolvable`` contradictions are actionable — still surfaced but annotated.
    - ``contextual`` contradictions are skipped (not really tensions).

    Returns human-readable tension pairs.
    """
    tensions: List[Tuple[str, str]] = []

    # 1. Ledger-based: open contradictions
    try:
        open_contras = ledger.get_open_contradictions(limit=50)
        for contra in open_contras:
            # Phase G1: skip contextual dispositions — they're not real tensions
            disposition = getattr(contra, "disposition", None)
            if disposition == "contextual":
                continue

            claim_a = getattr(contra, "claim_a_text", None) or ""
            claim_b = getattr(contra, "claim_b_text", None) or ""
            if claim_a and claim_b:
                # Annotate held/evolving tensions so prompt builder can frame them
                if disposition == "held":
                    tensions.append((f"[held] {claim_a[:120]}", f"[held] {claim_b[:120]}"))
                elif disposition == "evolving":
                    tensions.append((f"[evolving] {claim_a[:120]}", f"[evolving] {claim_b[:120]}"))
                else:
                    tensions.append((claim_a[:120], claim_b[:120]))
    except Exception as e:
        logger.warning("[SYNTHESIS] Ledger tension scan failed: %s", e)

    # 2. Intra-cluster: memories within same cluster that are semantically distant
    for cluster in clusters:
        if len(cluster.memory_texts) < 2:
            continue
        # Check if cluster has high internal contradiction count
        if cluster.contradiction_count > 0:
            # Already captured by ledger above, but note the cluster context
            pass

    # Deduplicate
    seen: Set[Tuple[str, str]] = set()
    unique: List[Tuple[str, str]] = []
    for a, b in tensions:
        key = (min(a, b), max(a, b))
        if key not in seen:
            seen.add(key)
            unique.append((a, b))

    return unique[:10]  # Cap at 10 tensions


# ---------------------------------------------------------------------------
# Representativeness
# ---------------------------------------------------------------------------

def compute_representativeness(
    clusters: List[BeliefCluster],
    total_memory_count: int,
) -> float:
    """How well do the clusters represent the full memory corpus?

    representativeness = coverage * (1 - 0.3 * avg_contradiction_density)
    """
    if total_memory_count == 0:
        return 0.0

    clustered_count = sum(len(c.memory_ids) for c in clusters)
    coverage = min(1.0, clustered_count / total_memory_count)

    # Contradiction density per cluster
    densities = []
    for c in clusters:
        n = len(c.memory_ids)
        if n > 0:
            densities.append(c.contradiction_count / n)
    avg_density = sum(densities) / len(densities) if densities else 0.0

    return max(0.0, min(1.0, coverage * (1.0 - 0.3 * avg_density)))


# ---------------------------------------------------------------------------
# LLM prompt construction
# ---------------------------------------------------------------------------

def _build_thematic_prompt(
    query: str,
    clusters: List[BeliefCluster],
    tensions: List[Tuple[str, str]],
    representativeness: float,
) -> str:
    """Build LLM prompt for thematic synthesis."""
    lines = [
        "You are the belief synthesis engine. Given clustered beliefs about the user, "
        "generate a natural, conversational synthesis that answers their question.",
        "Be warm and personal. Speak in second person ('You care about...', 'Your interests include...').",
        "Do NOT list raw facts — weave them into a coherent narrative.",
        "If confidence is low for a theme, hedge appropriately.",
        f"Representativeness of this analysis: {representativeness:.0%} of stored memories.",
        "",
        f"User asked: \"{query}\"",
        "",
    ]

    for i, cluster in enumerate(clusters[:8], 1):
        trust_lo, trust_hi = cluster.trust_range
        lines.append(f"Theme {i}: {cluster.theme} ({len(cluster.memory_ids)} memories, "
                      f"trust {trust_lo:.2f}-{trust_hi:.2f})")
        for text in cluster.memory_texts[:4]:
            lines.append(f"  - {text[:150]}")
        if cluster.contradiction_count > 0:
            lines.append(f"  [!] {cluster.contradiction_count} contradictions within this theme")
        lines.append("")

    if tensions:
        lines.append("Unresolved tensions in the user's beliefs:")
        for a, b in tensions[:5]:
            lines.append(f"  - \"{a[:80]}\" vs \"{b[:80]}\"")
        lines.append("")

    lines.append("Generate a natural synthesis (2-4 paragraphs). "
                 "Surface tensions if present — they're valuable self-knowledge.")

    return "\n".join(lines)


def _build_trajectory_prompt(
    query: str,
    trajectories: List[BeliefTrajectory],
) -> str:
    """Build LLM prompt for trajectory synthesis."""
    lines = [
        "You are the belief synthesis engine. The user is asking how their beliefs/preferences "
        "have changed over time. Generate a natural narrative describing their evolution.",
        "Use phrases like 'You used to...', 'Over time you shifted toward...'",
        "Note oscillations where the user went back and forth.",
        "",
        f"User asked: \"{query}\"",
        "",
    ]

    for traj in trajectories[:6]:
        lines.append(f"Slot: {traj.slot_or_theme} (total drift: {traj.drift_magnitude:.2f}"
                      f"{', oscillating' if traj.is_oscillating else ', monotonic'})")
        for snap in traj.snapshots:
            from datetime import datetime
            dt = datetime.fromtimestamp(snap.timestamp).strftime("%Y-%m-%d")
            lines.append(f"  {dt}: \"{snap.value}\" (trust: {snap.trust:.2f}, source: {snap.source})")
        lines.append("")

    if not trajectories:
        lines.append("No significant belief changes detected. Tell the user their views have been consistent.")

    lines.append("Generate a natural narrative (1-3 paragraphs) about how they've evolved.")
    return "\n".join(lines)


def _build_contradiction_prompt(
    query: str,
    tensions: List[Tuple[str, str]],
    clusters: List[BeliefCluster],
) -> str:
    """Build LLM prompt for contradiction-aware synthesis.

    Phase G1: tensions may carry disposition annotations ([held], [evolving]).
    """
    lines = [
        "You are the belief synthesis engine. The user wants to understand their internal "
        "contradictions and tensions. Present these thoughtfully — contradictions are "
        "normal and reveal complexity, not flaws.",
        "Frame as 'On one hand... on the other hand...' not 'You said X but also Y.'",
        "Tensions marked [held] are simultaneously true — frame as genuine complexity.",
        "Tensions marked [evolving] show the user changing over time — frame as growth.",
        "",
        f"User asked: \"{query}\"",
        "",
    ]

    if tensions:
        lines.append("Known tensions:")
        for i, (a, b) in enumerate(tensions[:8], 1):
            lines.append(f"  {i}. \"{a[:100]}\" vs \"{b[:100]}\"")
        lines.append("")

    # Add context from clusters that have internal contradictions
    conflicted = [c for c in clusters if c.contradiction_count > 0]
    if conflicted:
        lines.append("Themes with internal conflict:")
        for c in conflicted[:4]:
            lines.append(f"  - {c.theme}: {c.contradiction_count} contradictions "
                          f"across {len(c.memory_ids)} memories")
        lines.append("")

    if not tensions and not conflicted:
        lines.append("No significant contradictions found. Tell the user their beliefs "
                     "appear consistent (this is a positive finding).")

    lines.append("Generate a thoughtful analysis (2-3 paragraphs). "
                 "Help the user see their complexity as a feature, not a bug.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main synthesis entry point
# ---------------------------------------------------------------------------

def synthesize(
    query: str,
    memories: list,
    ledger,
    cloud_service=None,
    thread_id: str = "default",
) -> SynthesisResult:
    """Main synthesis entry point.

    Args:
        query: The user's question
        memories: List of MemoryItem objects (pre-filtered to USER/EXTERNAL)
        ledger: ContradictionLedger instance
        cloud_service: CloudFeatureService for LLM generation (optional)
        thread_id: Current thread ID

    Returns:
        SynthesisResult with natural language synthesis + structured data
    """
    synthesis_type = classify_synthesis_query(query) or "thematic"

    logger.info(
        "[SYNTHESIS] type=%s memories=%d query='%s'",
        synthesis_type, len(memories), query[:80],
    )

    # Step 1: Cluster all memories
    clusters = cluster_beliefs(memories)

    # Step 2: Build trajectories (for trajectory and thematic modes)
    trajectories: List[BeliefTrajectory] = []
    if synthesis_type in ("trajectory", "thematic"):
        traj_slots = find_trajectory_slots(memories)
        for slot in traj_slots[:10]:  # cap slot scan
            traj = build_belief_trajectory(memories, slot)
            if traj is not None:
                trajectories.append(traj)
        # Sort by drift magnitude (most change first)
        trajectories.sort(key=lambda t: t.drift_magnitude, reverse=True)

    # Step 3: Detect tensions
    tensions = detect_unresolved_tensions(clusters, ledger)

    # Step 4: Compute representativeness
    representativeness = compute_representativeness(clusters, len(memories))

    # Step 5: Build LLM prompt and generate
    if synthesis_type == "trajectory":
        prompt = _build_trajectory_prompt(query, trajectories)
    elif synthesis_type == "contradiction_aware":
        prompt = _build_contradiction_prompt(query, tensions, clusters)
    else:
        prompt = _build_thematic_prompt(query, clusters, tensions, representativeness)

    # Generate via cloud service (OpenAI tier 1)
    summary_text = _generate_synthesis_text(prompt, cloud_service)

    # Fallback: deterministic summary if LLM unavailable
    if not summary_text:
        summary_text = _build_deterministic_summary(
            synthesis_type, clusters, trajectories, tensions,
        )

    return SynthesisResult(
        synthesis_type=synthesis_type,
        summary_text=summary_text,
        clusters=clusters,
        trajectories=trajectories,
        unresolved_tensions=tensions,
        representativeness=representativeness,
        evidence_count=len(memories),
    )


def _generate_synthesis_text(prompt: str, cloud_service) -> Optional[str]:
    """Call cloud LLM to generate synthesis prose."""
    if cloud_service is None:
        return None

    try:
        from personal_agent.local_only_policy import is_strict_local_only_mode

        if is_strict_local_only_mode(uid=1):
            logger.info("[SYNTHESIS] Skipping cloud synthesis text in strict local-only mode")
            return None
    except Exception:
        pass

    try:
        result = cloud_service.generate_response(
            user_message=prompt,
            retrieved_memories=None,
            conversation_history=None,
            self_model_snapshot=None,
        )
        if result and len(result.strip()) > 20:
            return result.strip()
    except Exception as e:
        logger.warning("[SYNTHESIS] Cloud generation failed: %s", e)

    return None


def _build_deterministic_summary(
    synthesis_type: str,
    clusters: List[BeliefCluster],
    trajectories: List[BeliefTrajectory],
    tensions: List[Tuple[str, str]],
) -> str:
    """Fallback deterministic summary when cloud LLM is unavailable."""
    lines: List[str] = []

    if synthesis_type == "thematic":
        if not clusters:
            return "I don't have enough stored memories to synthesize a thematic summary yet."
        lines.append("Based on what I know about you, here are the main themes:\n")
        for i, c in enumerate(clusters[:6], 1):
            lines.append(f"**{c.theme}** ({len(c.memory_ids)} memories, "
                          f"trust {c.trust_range[0]:.2f}-{c.trust_range[1]:.2f})")
            for text in c.memory_texts[:3]:
                lines.append(f"  - {text[:120]}")
            lines.append("")

    elif synthesis_type == "trajectory":
        if not trajectories:
            return "Your views and preferences have been fairly consistent — I haven't detected significant changes over time."
        lines.append("Here's how some of your beliefs have evolved:\n")
        for traj in trajectories[:5]:
            from datetime import datetime
            first = traj.snapshots[0]
            last = traj.snapshots[-1]
            d1 = datetime.fromtimestamp(first.timestamp).strftime("%b %Y")
            d2 = datetime.fromtimestamp(last.timestamp).strftime("%b %Y")
            osc = " (you've gone back and forth)" if traj.is_oscillating else ""
            lines.append(f"**{traj.slot_or_theme}**: {first.value} ({d1}) -> {last.value} ({d2}){osc}")
        lines.append("")

    elif synthesis_type == "contradiction_aware":
        if not tensions:
            return "I don't see any significant contradictions in your stored beliefs. Your views appear consistent."
        lines.append("Here are some tensions I've noticed in your beliefs:\n")
        for i, (a, b) in enumerate(tensions[:6], 1):
            lines.append(f"{i}. \"{a[:100]}\" vs \"{b[:100]}\"")
        lines.append("\nContradictions are natural — they often reflect genuine complexity in how you think about things.")

    if tensions and synthesis_type != "contradiction_aware":
        lines.append("\n---\nNote: I also noticed some unresolved tensions:")
        for a, b in tensions[:3]:
            lines.append(f"  - \"{a[:80]}\" vs \"{b[:80]}\"")

    return "\n".join(lines) if lines else "I don't have enough information to generate this synthesis yet."
