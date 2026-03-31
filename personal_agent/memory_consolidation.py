"""
Memory Consolidation Pass — Batch NLI Contradiction Sweep

Sweeps all alive memories for undetected contradictions. Unlike the store-time
detection in crt_ledger.py (which only checks new memories against existing),
this module performs pairwise checking across ALL memories using embedding
similarity as a pre-filter.

Strategy to avoid O(n^2):
1. Load all non-deprecated memories with vectors
2. For each memory, find k nearest neighbors by cosine similarity
3. Filter to pairs with similarity > threshold (semantically related enough)
4. Skip pairs already in the contradiction ledger
5. Run NLI check via GroundCheck for candidate pairs
6. Classify disposition (resolvable/held/evolving/contextual)
7. Act on findings: auto-deprecate resolvable, BDG edges for held, etc.

Philosophy:
- Contradictions are structure, not bugs
- Only auto-resolve when one side is clearly inferior
- Held contradictions increase importance signal
- Everything logged to contradiction ledger
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_PAIRS = 50
DEFAULT_K_NEIGHBORS = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.40
NLI_CONTRADICTION_THRESHOLD = 0.65

# Auto-resolution criteria: only deprecate when the evidence is overwhelming
AUTO_RESOLVE_TRUST_DELTA = 0.15     # weaker side must be this much lower
AUTO_RESOLVE_MIN_AGE_DELTA = 86400  # at least 1 day older
CONTESTED_TRUST_MULTIPLIER = 0.1    # from CRT config


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ConsolidationResult:
    """Summary of a consolidation pass."""
    pairs_checked: int = 0
    new_contradictions_found: int = 0
    auto_resolved: int = 0
    held_created: int = 0
    evolving_tracked: int = 0
    trust_updates: int = 0
    bdg_edges_added: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Candidate pair finding
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Fast cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _load_vectors(memories: list) -> Dict[str, np.ndarray]:
    """Extract memory_id → vector mapping from memory items."""
    import json
    vectors: Dict[str, np.ndarray] = {}
    for mem in memories:
        mem_id = getattr(mem, "memory_id", None)
        if not mem_id:
            continue

        # Try 'vector' attribute first (MemoryItem), then 'vector_json' (raw)
        vec = getattr(mem, "vector", None)
        if vec is not None and isinstance(vec, np.ndarray) and vec.shape[0] > 0:
            vectors[mem_id] = vec.astype(np.float32)
            continue

        vec_json = getattr(mem, "vector_json", None)
        if not vec_json:
            continue
        try:
            if isinstance(vec_json, str):
                vec = np.array(json.loads(vec_json), dtype=np.float32)
            elif isinstance(vec_json, (list, np.ndarray)):
                vec = np.array(vec_json, dtype=np.float32)
            else:
                continue
            if vec.shape[0] > 0:
                vectors[mem_id] = vec
        except Exception:
            continue
    return vectors


def _find_candidate_pairs(
    memories: list,
    vectors: Dict[str, np.ndarray],
    existing_pairs: Set[Tuple[str, str]],
    k_neighbors: int = DEFAULT_K_NEIGHBORS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_pairs: int = DEFAULT_MAX_PAIRS,
) -> List[Tuple[Any, Any, float]]:
    """Find memory pairs that are semantically related but not already in ledger.

    Returns list of (memory_a, memory_b, similarity) tuples.
    """
    # Build memory_id → memory lookup
    mem_lookup: Dict[str, Any] = {}
    for mem in memories:
        mid = getattr(mem, "memory_id", None)
        if mid:
            mem_lookup[mid] = mem

    # Only consider memories that have vectors
    active_ids = [mid for mid in mem_lookup if mid in vectors]
    if len(active_ids) < 2:
        return []

    candidates: List[Tuple[Any, Any, float]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    for i, mid_a in enumerate(active_ids):
        if len(candidates) >= max_pairs:
            break

        vec_a = vectors[mid_a]
        # Find k nearest neighbors
        sims: List[Tuple[str, float]] = []
        for mid_b in active_ids[i + 1:]:
            sim = _cosine_similarity(vec_a, vectors[mid_b])
            if sim >= similarity_threshold:
                sims.append((mid_b, sim))

        # Sort by similarity descending, take top k
        sims.sort(key=lambda x: -x[1])
        for mid_b, sim in sims[:k_neighbors]:
            pair_key = tuple(sorted([mid_a, mid_b]))
            if pair_key in existing_pairs or pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            candidates.append((mem_lookup[mid_a], mem_lookup[mid_b], sim))
            if len(candidates) >= max_pairs:
                break

    return candidates


# ---------------------------------------------------------------------------
# Auto-resolution logic
# ---------------------------------------------------------------------------

def _auto_resolve_if_clear(
    mem_a: Any,
    mem_b: Any,
    memory_system: Any,
) -> Optional[str]:
    """Auto-resolve a resolvable contradiction by deprecating the weaker side.

    Only resolves when one side is clearly inferior:
    - Lower trust AND older AND source_kind is model_output while other is principal

    Returns the deprecated memory_id, or None if not auto-resolvable.
    """
    trust_a = getattr(mem_a, "trust", 0.5)
    trust_b = getattr(mem_b, "trust", 0.5)
    ts_a = getattr(mem_a, "timestamp", 0)
    ts_b = getattr(mem_b, "timestamp", 0)
    source_a = getattr(mem_a, "source_kind", "principal")
    source_b = getattr(mem_b, "source_kind", "principal")
    authority_a = getattr(mem_a, "authority", "confirmed")
    authority_b = getattr(mem_b, "authority", "confirmed")

    # Never auto-deprecate locked memories
    if authority_a == "locked" or authority_b == "locked":
        return None

    # Check if A is clearly weaker
    a_weaker = (
        trust_a < trust_b - AUTO_RESOLVE_TRUST_DELTA
        and ts_a < ts_b - AUTO_RESOLVE_MIN_AGE_DELTA
        and source_a in ("model_output", "fallback")
        and source_b in ("principal", "user")
    )

    # Check if B is clearly weaker
    b_weaker = (
        trust_b < trust_a - AUTO_RESOLVE_TRUST_DELTA
        and ts_b < ts_a - AUTO_RESOLVE_MIN_AGE_DELTA
        and source_b in ("model_output", "fallback")
        and source_a in ("principal", "user")
    )

    if a_weaker:
        mid = getattr(mem_a, "memory_id", None)
        if mid:
            try:
                memory_system.deprecate_memory(
                    mid,
                    reason=f"consolidation_auto_resolve: superseded by {getattr(mem_b, 'memory_id', '?')}"
                )
                return mid
            except Exception as e:
                logger.warning(f"[CONSOLIDATION] Failed to deprecate {mid}: {e}")
    elif b_weaker:
        mid = getattr(mem_b, "memory_id", None)
        if mid:
            try:
                memory_system.deprecate_memory(
                    mid,
                    reason=f"consolidation_auto_resolve: superseded by {getattr(mem_a, 'memory_id', '?')}"
                )
                return mid
            except Exception as e:
                logger.warning(f"[CONSOLIDATION] Failed to deprecate {mid}: {e}")

    return None


# ---------------------------------------------------------------------------
# Core consolidation pass
# ---------------------------------------------------------------------------

def run_consolidation_pass(
    memory_system: Any,
    ledger: Any,
    memory_graph: Optional[Any] = None,
    max_pairs: int = DEFAULT_MAX_PAIRS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ConsolidationResult:
    """Sweep all alive memories for undetected contradictions.

    Strategy:
    1. Load all non-deprecated memories with vectors
    2. Find candidate pairs by embedding similarity
    3. Skip pairs already in contradiction ledger
    4. Run NLI check for each candidate
    5. Classify disposition and act accordingly
    6. Log all findings

    Args:
        memory_system: CRTMemorySystem instance
        ledger: ContradictionLedger instance
        memory_graph: Optional MemoryGraph for BDG edge creation
        max_pairs: Maximum pairs to check per pass
        similarity_threshold: Minimum similarity to consider a pair

    Returns:
        ConsolidationResult with counts and details
    """
    start_time = time.time()
    result = ConsolidationResult()

    # --- Step 1: Load memories ---
    try:
        all_memories = memory_system._load_all_memories()
        # Filter deprecated
        memories = [m for m in all_memories if not getattr(m, "deprecated", False)]
    except Exception as e:
        result.errors.append(f"Failed to load memories: {e}")
        return result

    if len(memories) < 2:
        result.duration_seconds = time.time() - start_time
        return result

    # --- Step 2: Load vectors ---
    vectors = _load_vectors(memories)
    if len(vectors) < 2:
        result.errors.append("Not enough memories with vectors for consolidation")
        result.duration_seconds = time.time() - start_time
        return result

    # --- Step 3: Get existing contradiction pairs ---
    existing_pairs: Set[Tuple[str, str]] = set()
    try:
        open_contras = ledger.get_open_contradictions(limit=1000)
        resolved_contras = ledger.get_resolved_contradictions(limit=1000)
        for c in list(open_contras) + list(resolved_contras):
            old_id = getattr(c, "old_memory_id", None)
            new_id = getattr(c, "new_memory_id", None)
            if old_id and new_id:
                existing_pairs.add(tuple(sorted([old_id, new_id])))
    except Exception as e:
        logger.warning(f"[CONSOLIDATION] Failed to load existing contradictions: {e}")

    # --- Step 4: Find candidate pairs ---
    candidates = _find_candidate_pairs(
        memories=memories,
        vectors=vectors,
        existing_pairs=existing_pairs,
        k_neighbors=DEFAULT_K_NEIGHBORS,
        similarity_threshold=similarity_threshold,
        max_pairs=max_pairs,
    )

    if not candidates:
        result.duration_seconds = time.time() - start_time
        logger.info("[CONSOLIDATION] No candidate pairs found")
        return result

    # --- Step 5: NLI check + disposition ---
    # Lazy-load NLI detector
    nli_detector = None
    try:
        from packages.groundcheck.groundcheck.semantic_contradiction import SemanticContradictionDetector
        nli_detector = SemanticContradictionDetector(use_nli=True)
    except ImportError:
        try:
            from groundcheck.semantic_contradiction import SemanticContradictionDetector
            nli_detector = SemanticContradictionDetector(use_nli=True)
        except ImportError:
            logger.warning("[CONSOLIDATION] GroundCheck NLI not available, using drift-only detection")

    # Lazy-load disposition classifier
    disposition_classify = None
    try:
        from .disposition_classifier import classify_contradiction as disposition_classify
    except ImportError:
        logger.warning("[CONSOLIDATION] Disposition classifier not available")

    for mem_a, mem_b, sim in candidates:
        result.pairs_checked += 1
        text_a = getattr(mem_a, "text", "")
        text_b = getattr(mem_b, "text", "")
        mid_a = getattr(mem_a, "memory_id", "?")
        mid_b = getattr(mem_b, "memory_id", "?")

        try:
            # Check for contradiction
            is_contradiction = False
            nli_confidence = 0.0

            if nli_detector:
                nli_result = nli_detector.check_contradiction(text_a, text_b)
                is_contradiction = nli_result.is_contradiction
                nli_confidence = nli_result.confidence
            else:
                # Fallback: use drift threshold
                drift = 1.0 - sim
                is_contradiction = drift > 0.28 and sim > similarity_threshold  # theta_contra from CRTConfig

            if not is_contradiction:
                continue

            result.new_contradictions_found += 1

            # Classify disposition
            disposition = "unknown"
            disposition_confidence = 0.0
            if disposition_classify:
                ts_a = getattr(mem_a, "timestamp", 0)
                ts_b = getattr(mem_b, "timestamp", 0)
                disp_result = disposition_classify(text_a, text_b, ts_a, ts_b, sim)
                disposition = getattr(disp_result, "disposition", "unknown")
                if hasattr(disposition, "value"):
                    disposition = disposition.value
                disposition_confidence = getattr(disp_result, "confidence", 0.0)

            # Record to ledger
            drift_mean = 1.0 - sim
            trust_a = getattr(mem_a, "trust", 0.5)
            trust_b = getattr(mem_b, "trust", 0.5)

            entry = ledger.record_contradiction(
                old_memory_id=mid_a,
                new_memory_id=mid_b,
                drift_mean=drift_mean,
                confidence_delta=abs(trust_a - trust_b),
                summary=f"Consolidation pass: {text_a[:50]} vs {text_b[:50]}",
                old_text=text_a,
                new_text=text_b,
                old_vector=vectors.get(mid_a),
                new_vector=vectors.get(mid_b),
                contradiction_type="conflict",
            )

            # Update disposition on the entry
            if disposition != "unknown":
                try:
                    conn = ledger._get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE contradictions SET
                            disposition = ?,
                            disposition_confidence = ?
                        WHERE ledger_id = ?
                    """, (disposition, disposition_confidence, entry.ledger_id))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

            # Act based on disposition
            if disposition == "resolvable":
                deprecated_id = _auto_resolve_if_clear(mem_a, mem_b, memory_system)
                if deprecated_id:
                    result.auto_resolved += 1
                    logger.info(f"[CONSOLIDATION] Auto-resolved: deprecated {deprecated_id}")

            elif disposition == "held":
                result.held_created += 1
                # Add BDG edge if graph available
                if memory_graph:
                    try:
                        from .memory_graph import ContradictionEdge, Disposition
                        edge = ContradictionEdge(
                            disposition=Disposition.HELD.value,
                            nli_score=nli_confidence,
                            overlap_integral=sim,
                            detected_at=time.time(),
                            classification_confidence=disposition_confidence,
                        )
                        memory_graph.add_contradiction(mid_a, mid_b, edge)
                        result.bdg_edges_added += 1
                    except Exception as e:
                        logger.warning(f"[CONSOLIDATION] Failed to add BDG edge: {e}")

                # Update belnap_state to "both" for held contradictions
                try:
                    conn = memory_system._get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE memories SET belnap_state = 'both' WHERE memory_id IN (?, ?)",
                        (mid_a, mid_b)
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

            elif disposition == "evolving":
                result.evolving_tracked += 1
                # Mark temporal status on the newer memory
                ts_a = getattr(mem_a, "timestamp", 0)
                ts_b = getattr(mem_b, "timestamp", 0)
                newer_id = mid_b if ts_b > ts_a else mid_a
                try:
                    conn = memory_system._get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE memories SET temporal_status = 'active' WHERE memory_id = ?",
                        (newer_id,)
                    )
                    older_id = mid_a if newer_id == mid_b else mid_b
                    cursor.execute(
                        "UPDATE memories SET temporal_status = 'past' WHERE memory_id = ?",
                        (older_id,)
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

            # Apply contested trust multiplier to both memories
            try:
                conn = memory_system._get_connection()
                cursor = conn.cursor()
                for mid in (mid_a, mid_b):
                    cursor.execute("""
                        UPDATE memories SET
                            contradiction_count = COALESCE(contradiction_count, 0) + 1
                        WHERE memory_id = ?
                    """, (mid,))
                conn.commit()
                conn.close()
                result.trust_updates += 2
            except Exception:
                pass

        except Exception as e:
            result.errors.append(f"Error checking {mid_a} vs {mid_b}: {e}")
            logger.warning(f"[CONSOLIDATION] Error: {e}")

    result.duration_seconds = time.time() - start_time

    logger.info(
        f"[CONSOLIDATION] pairs={result.pairs_checked} "
        f"found={result.new_contradictions_found} "
        f"resolved={result.auto_resolved} "
        f"held={result.held_created} "
        f"evolving={result.evolving_tracked} "
        f"bdg_edges={result.bdg_edges_added} "
        f"duration={result.duration_seconds:.1f}s"
    )

    return result
