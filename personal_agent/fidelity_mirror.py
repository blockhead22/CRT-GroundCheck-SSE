"""
Fidelity Mirror — Post-generation belief integrity check.

The "breathing cycle" from the Holden architecture: after generating a response,
compress it back down and verify it faithfully represents the belief state.

Three checks:
  1. Belief fidelity — did the response use the injected memories?
  2. Request alignment — did it answer what was asked?
  3. Factual grounding — are claims traceable to trust-weighted memories?

Returns a FidelityScore. If below threshold, the response should be hedged
or retried. If above, cited memories get trust reinforcement.

Design: synchronous, lightweight (embedding math only, no LLM calls).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FidelityScore:
    """Result of fidelity mirror check."""
    belief_fidelity: float = 0.0    # Did the response use injected memories?
    request_alignment: float = 0.0  # Did it answer the actual question?
    factual_grounding: float = 0.0  # Are claims traceable to memories?
    composite: float = 0.0          # Weighted average
    passed: bool = True
    findings: List[str] = field(default_factory=list)
    latency_ms: float = 0.0


# Weights for composite score
# Belief fidelity is de-weighted because embedding similarity can't catch
# negation (e.g., "I do NOT work at studio" is similar to "works at studio").
# NLI enforcement gate handles that case. Fidelity mirror focuses on
# request alignment (did it answer the question?) and grounding (are claims
# traceable to memories?).
_W_BELIEF = 0.2
_W_REQUEST = 0.4
_W_GROUNDING = 0.4

# Threshold below which the response should be hedged
FIDELITY_THRESHOLD = 0.25


def _encode(text: str) -> Optional[np.ndarray]:
    """Encode text to embedding vector. Returns None on failure."""
    try:
        from personal_agent.crt_core import encode_vector
        vec = encode_vector(text)
        if vec is not None:
            return np.array(vec, dtype=np.float32)
    except Exception:
        pass
    return None


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-8 or norm_b < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _wobble_expand(memories: List[Dict[str, Any]], query_vec: np.ndarray,
                    damping: float = 0.7, max_extra: int = 10) -> List[Dict[str, Any]]:
    """Expand memory set via BDG edge propagation (wobble).

    Takes the retrieved memories and finds additional memories connected
    through the BDG that cosine retrieval missed. Returns the expanded set.
    """
    try:
        from personal_agent.memory_graph import get_live_bdg
        live_bdg = get_live_bdg()
        if live_bdg is None:
            return memories
        live_bdg.ensure_built()
        graph = live_bdg.bdg.graph if hasattr(live_bdg, 'bdg') and live_bdg.bdg else None
        if graph is None or graph.number_of_nodes() < 5:
            return memories
    except Exception:
        return memories

    # Get memory IDs from the retrieved set
    retrieved_ids = set()
    for mem in memories:
        mid = mem.get("memory_id") or mem.get("id", "")
        if mid:
            retrieved_ids.add(mid)

    # If no IDs available, try to match by text against BDG nodes
    if not retrieved_ids:
        for mem in memories:
            mem_text = (mem.get("text") or "")[:100].lower().strip()
            if not mem_text:
                continue
            for nid, ndata in graph.nodes(data=True):
                node_text = (ndata.get("text") or "")[:100].lower().strip()
                if node_text and (mem_text in node_text or node_text in mem_text):
                    retrieved_ids.add(nid)
                    break  # one match per memory is enough
            if len(retrieved_ids) >= 5:
                break

    if not retrieved_ids:
        logger.info("[FIDELITY_MIRROR] Wobble skipped: no memory IDs matched in BDG")
        return memories

    logger.info(f"[FIDELITY_MIRROR] Wobble starting: {len(retrieved_ids)} seed nodes in BDG")

    # Propagate through edges from retrieved memories
    from collections import deque
    propagated = {}  # node_id -> resonance score
    queue = deque()

    for mid in retrieved_ids:
        if graph.has_node(mid):
            trust = float(next((m.get("trust", 0.5) for m in memories
                               if (m.get("memory_id") or m.get("id", "")) == mid), 0.5))
            queue.append((mid, trust, 0))

    while queue:
        node, resonance, depth = queue.popleft()
        if depth > 3:
            continue
        # Forward: outgoing SUPPORTS edges
        for _, succ, edata in graph.out_edges(node, data=True):
            etype = edata.get("edge_type", "SUPPORTS")
            if etype == "CONTRADICTS":
                continue
            w = edata.get("weight", 0.5)
            prop = resonance * w * damping
            if prop > 0.05 and succ not in retrieved_ids:
                if succ not in propagated or prop > propagated[succ]:
                    propagated[succ] = prop
                    queue.append((succ, prop, depth + 1))
        # Backward: incoming SUPPORTS edges
        for pred, _, edata in graph.in_edges(node, data=True):
            etype = edata.get("edge_type", "SUPPORTS")
            if etype == "CONTRADICTS":
                continue
            w = edata.get("weight", 0.5)
            prop = resonance * w * damping * 0.5
            if prop > 0.05 and pred not in retrieved_ids:
                if pred not in propagated or prop > propagated[pred]:
                    propagated[pred] = prop
                    queue.append((pred, prop, depth + 1))

    if not propagated:
        return memories

    # Fetch the propagated memories from the graph node data
    extra = []
    for node_id, resonance in sorted(propagated.items(), key=lambda x: -x[1])[:max_extra]:
        node_data = graph.nodes.get(node_id, {})
        text = node_data.get("text", "")
        trust = node_data.get("trust", node_data.get("confidence", 0.3))
        if text:
            extra.append({
                "text": text,
                "trust": trust,
                "memory_id": node_id,
                "_wobble_propagated": True,
                "_wobble_resonance": resonance,
            })

    if extra:
        logger.info(f"[FIDELITY_MIRROR] Wobble expanded: +{len(extra)} memories via BDG edges")

    return memories + extra


def check_fidelity(
    response: str,
    query: str,
    memories: List[Dict[str, Any]],
    *,
    threshold: float = FIDELITY_THRESHOLD,
) -> FidelityScore:
    """Run the fidelity mirror on a generated response.

    Args:
        response: The generated response text.
        query: The user's original query.
        memories: Retrieved memories used for generation (dicts with 'text' and 'trust').

    Returns:
        FidelityScore with per-dimension scores and composite.
    """
    t0 = time.perf_counter()
    findings: List[str] = []

    # Self-referential queries (about the system itself) are grounded in the
    # system prompt, not in retrieved memories. Lower the threshold so the
    # fidelity mirror doesn't penalize accurate self-description.
    _q_lower = query.lower()
    _SELF_REF_PATTERNS = [
        "how do you work", "how does this system", "explain your",
        "what are you", "how are you built", "your architecture",
        "how does aether", "how does crt", "what can you do",
        "what concerns you", "what do you think", "could you improve",
        "how do you think", "explain deeper", "explain how",
        # System-opinion queries: introspective but grounded in system docs, not user memories
        "goal of this", "what is the goal", "what's the goal",
        "worst part", "best part", "coolest part", "most interesting part",
        "what would you change", "one big change", "one change",
        "what makes this", "how is it different", "what is special",
        "biggest problem", "biggest weakness", "biggest strength",
        # Codebase exploration queries
        "using the codebase", "find.*codebase", "in the codebase",
        "look at the code", "in the code",
    ]
    if any(p in _q_lower for p in _SELF_REF_PATTERNS):
        threshold = min(threshold, 0.10)  # Very relaxed for self-description

    # Short-circuit: if no memories, can't check fidelity
    if not memories or not response or not query:
        return FidelityScore(
            belief_fidelity=0.5,  # neutral — no memories to check against
            request_alignment=0.5,
            factual_grounding=0.5,
            composite=0.5,
            passed=True,
            findings=["No memories available for fidelity check"],
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    response_vec = _encode(response[:1000])  # Cap to avoid slow encoding
    query_vec = _encode(query)

    if response_vec is None or query_vec is None:
        return FidelityScore(
            composite=0.5, passed=True,
            findings=["Encoding failed"],
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    # Wobble expansion: use BDG edges to find associated memories
    memories = _wobble_expand(memories, query_vec)

    # --- Check 1: Belief Fidelity ---
    # How much does the response overlap with the injected memories?
    # High score = response is grounded in what the system believes.
    mem_sims = []
    for mem in memories:
        mem_text = mem.get("text", "")
        if not mem_text:
            continue
        mem_vec = _encode(mem_text[:300])
        if mem_vec is not None:
            sim = _cosine_sim(response_vec, mem_vec)
            trust = float(mem.get("trust", 0.5))
            # Trust-weighted similarity: high-trust memories matter more
            mem_sims.append(sim * (0.5 + 0.5 * trust))

    belief_fidelity = float(np.mean(mem_sims)) if mem_sims else 0.0
    if belief_fidelity < 0.2:
        findings.append(
            f"Low belief fidelity ({belief_fidelity:.2f}) — response may not use injected memories"
        )

    # --- Check 2: Request Alignment ---
    # How well does the response match the original query's intent?
    request_alignment = _cosine_sim(response_vec, query_vec)
    if request_alignment < 0.2:
        findings.append(
            f"Low request alignment ({request_alignment:.2f}) — response may not answer the question"
        )

    # --- Check 3: Factual Grounding ---
    # What fraction of the response's semantic content is traceable to memories?
    # Split response into sentences, check each against memory bank.
    sentences = [s.strip() for s in response.split('.') if len(s.strip()) > 20]

    grounded_count = 0  # Initialize before branches to avoid UnboundLocalError
    if len(sentences) <= 1:
        # Short/conversational response — use whole response similarity to memories
        # instead of sentence-level grounding (which fails on one-liners)
        if mem_sims:
            factual_grounding = min(1.0, max(mem_sims) * 1.5)  # boost: short = likely grounded
        else:
            factual_grounding = 0.5  # neutral
        if len(sentences) == 0:
            findings.append("Response too short for sentence-level grounding (using whole-response)")
    else:
        for sent in sentences[:10]:  # Cap at 10 sentences
            sent_vec = _encode(sent)
            if sent_vec is None:
                continue
            max_sim = 0.0
            for mem in memories:
                mem_text = mem.get("text", "")
                if not mem_text:
                    continue
                mem_vec = _encode(mem_text[:300])
                if mem_vec is not None:
                    sim = _cosine_sim(sent_vec, mem_vec)
                    max_sim = max(max_sim, sim)
            if max_sim > 0.4:  # Sentence is grounded if any memory is similar
                grounded_count += 1

        factual_grounding = grounded_count / max(len(sentences[:10]), 1)
    if factual_grounding < 0.3:
        findings.append(
            f"Low factual grounding ({factual_grounding:.2f}) — "
            f"{len(sentences[:10]) - grounded_count}/{len(sentences[:10])} sentences ungrounded"
        )

    # --- Composite Score ---
    composite = (
        _W_BELIEF * belief_fidelity
        + _W_REQUEST * request_alignment
        + _W_GROUNDING * factual_grounding
    )
    passed = composite >= threshold

    if not passed:
        findings.append(
            f"Fidelity check FAILED (composite={composite:.3f}, threshold={threshold})"
        )

    elapsed = (time.perf_counter() - t0) * 1000
    return FidelityScore(
        belief_fidelity=round(belief_fidelity, 3),
        request_alignment=round(request_alignment, 3),
        factual_grounding=round(factual_grounding, 3),
        composite=round(composite, 3),
        passed=passed,
        findings=findings,
        latency_ms=round(elapsed, 1),
    )
