"""Memory Graph — Phase 1 (NetworkX + JSON persistence)

A graph where memories are nodes and relationships are typed edges.
Edge types:
  - CONTRADICTS: NLI-detected contradiction with disposition classification
  - SUPERSEDES: temporal replacement (new fact overwrites old)
  - RELATED_TO: semantic similarity above threshold

Nodes carry:
  - text, embedding, trust, confidence, timestamps
  - memory_type (fact/preference/event/belief)
  - belnap_state (T/F/Both/Neither)
  - disposition (for contradiction edges)

Persistence: JSON serialization to disk.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Tuple, Set
from pathlib import Path

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("WARNING: networkx not installed. pip install networkx")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MemoryType(Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    EVENT = "event"
    BELIEF = "belief"
    IDENTITY = "identity"


class BelnapState(Enum):
    TRUE = "T"           # Affirmed, no contradicting evidence
    FALSE = "F"          # Explicitly contradicted and deprecated
    BOTH = "Both"        # Held contradiction — evidence on both sides
    NEITHER = "Neither"  # Unknown, insufficient evidence


class EdgeType(Enum):
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    SUPPORTS = "supports"        # Paper Definition 3.2 — evidential grounding
    RELATED_TO = "related_to"
    DERIVED_FROM = "derived_from"


class Disposition(Enum):
    RESOLVABLE = "resolvable"
    HELD = "held"
    EVOLVING = "evolving"
    CONTEXTUAL = "contextual"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MemoryNode:
    """A single memory in the graph."""
    memory_id: str
    text: str
    created_at: float
    memory_type: str = "belief"       # fact|preference|event|belief|identity
    belnap_state: str = "T"           # T|F|Both|Neither
    trust: float = 0.7
    confidence: float = 0.8
    valid_at: Optional[float] = None
    invalid_at: Optional[float] = None
    superseded_by: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    # Embedding stored separately (not in JSON for size)
    _embedding: Optional[object] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop('_embedding', None)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'MemoryNode':
        d.pop('_embedding', None)
        return cls(**d)


@dataclass
class ContradictionEdge:
    """Metadata for a CONTRADICTS edge."""
    disposition: str          # resolvable|held|evolving|contextual
    nli_score: float = 0.0   # NLI contradiction confidence
    overlap_integral: float = 0.0  # geometric overlap (future: belief locus)
    detected_at: float = 0.0
    classification_confidence: float = 0.0
    rule_trace: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Memory Graph
# ---------------------------------------------------------------------------

class MemoryGraph:
    """Graph-based memory store with typed edges."""

    def __init__(self, persist_path: Optional[str] = None):
        if not HAS_NETWORKX:
            raise ImportError("networkx required: pip install networkx")

        self.graph = nx.DiGraph()
        self.persist_path = persist_path
        self._embeddings: Dict[str, object] = {}  # memory_id -> numpy array

        if persist_path and os.path.exists(persist_path):
            self.load(persist_path)

    # -------------------------------------------------------------------
    # Node operations
    # -------------------------------------------------------------------

    def add_memory(self, node: MemoryNode, embedding=None) -> str:
        """Add a memory node to the graph."""
        self.graph.add_node(node.memory_id, **node.to_dict())
        if embedding is not None:
            self._embeddings[node.memory_id] = embedding
        return node.memory_id

    def get_memory(self, memory_id: str) -> Optional[MemoryNode]:
        """Get a memory node by ID."""
        if memory_id not in self.graph:
            return None
        data = dict(self.graph.nodes[memory_id])
        return MemoryNode.from_dict(data)

    def get_embedding(self, memory_id: str):
        """Get the embedding for a memory."""
        return self._embeddings.get(memory_id)

    def update_belnap(self, memory_id: str, state: BelnapState):
        """Update a memory's Belnap truth state."""
        if memory_id in self.graph:
            self.graph.nodes[memory_id]['belnap_state'] = state.value

    def deprecate(self, memory_id: str, superseded_by: str, reason: str = ""):
        """Mark a memory as deprecated/superseded."""
        if memory_id in self.graph:
            self.graph.nodes[memory_id]['belnap_state'] = BelnapState.FALSE.value
            self.graph.nodes[memory_id]['superseded_by'] = superseded_by
            self.graph.nodes[memory_id]['invalid_at'] = time.time()
            self.add_edge(superseded_by, memory_id, EdgeType.SUPERSEDES,
                         metadata={"reason": reason})

    # -------------------------------------------------------------------
    # Edge operations
    # -------------------------------------------------------------------

    def add_edge(self, source_id: str, target_id: str, edge_type: EdgeType,
                 metadata: Optional[dict] = None):
        """Add a typed edge between two memories."""
        data = {"edge_type": edge_type.value, "created_at": time.time()}
        if metadata:
            data.update(metadata)
        self.graph.add_edge(source_id, target_id, **data)

    def add_contradiction(self, memory_a: str, memory_b: str,
                          contradiction: ContradictionEdge):
        """Add a CONTRADICTS edge with full metadata."""
        data = {
            "edge_type": EdgeType.CONTRADICTS.value,
            "disposition": contradiction.disposition,
            "nli_score": contradiction.nli_score,
            "overlap_integral": contradiction.overlap_integral,
            "detected_at": contradiction.detected_at or time.time(),
            "classification_confidence": contradiction.classification_confidence,
            "rule_trace": contradiction.rule_trace,
        }
        # Contradictions are bidirectional
        self.graph.add_edge(memory_a, memory_b, **data)
        self.graph.add_edge(memory_b, memory_a, **data)

        # Update Belnap states based on disposition
        if contradiction.disposition == Disposition.HELD.value:
            self.update_belnap(memory_a, BelnapState.BOTH)
            self.update_belnap(memory_b, BelnapState.BOTH)
        elif contradiction.disposition == Disposition.RESOLVABLE.value:
            # Don't auto-resolve — flag for resolution
            pass
        elif contradiction.disposition == Disposition.EVOLVING.value:
            # Mark newer as Neither (uncertain)
            pass

    def add_similarity_edge(self, memory_a: str, memory_b: str,
                            similarity: float, threshold: float = 0.7):
        """Add a RELATED_TO edge if similarity exceeds threshold."""
        if similarity >= threshold:
            self.add_edge(memory_a, memory_b, EdgeType.RELATED_TO,
                         {"similarity": similarity})

    # -------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------

    def get_contradictions(self, memory_id: str) -> List[Tuple[str, dict]]:
        """Get all contradictions for a memory."""
        results = []
        for _, target, data in self.graph.edges(memory_id, data=True):
            if data.get('edge_type') == EdgeType.CONTRADICTS.value:
                results.append((target, data))
        return results

    def get_held_contradictions(self) -> List[Tuple[str, str, dict]]:
        """Get all HELD contradictions in the graph."""
        results = []
        seen = set()
        for u, v, data in self.graph.edges(data=True):
            if (data.get('edge_type') == EdgeType.CONTRADICTS.value and
                    data.get('disposition') == Disposition.HELD.value):
                pair = tuple(sorted([u, v]))
                if pair not in seen:
                    seen.add(pair)
                    results.append((u, v, data))
        return results

    def get_evolving_contradictions(self) -> List[Tuple[str, str, dict]]:
        """Get all EVOLVING contradictions — beliefs in flux."""
        results = []
        seen = set()
        for u, v, data in self.graph.edges(data=True):
            if (data.get('edge_type') == EdgeType.CONTRADICTS.value and
                    data.get('disposition') == Disposition.EVOLVING.value):
                pair = tuple(sorted([u, v]))
                if pair not in seen:
                    seen.add(pair)
                    results.append((u, v, data))
        return results

    def get_neighbors(self, memory_id: str, hops: int = 1,
                      edge_types: Optional[List[EdgeType]] = None) -> Set[str]:
        """Get N-hop neighborhood, optionally filtered by edge type."""
        if memory_id not in self.graph:
            return set()

        visited = {memory_id}
        frontier = {memory_id}

        for _ in range(hops):
            next_frontier = set()
            for node in frontier:
                for _, target, data in self.graph.edges(node, data=True):
                    if edge_types is None or data.get('edge_type') in [e.value for e in edge_types]:
                        if target not in visited:
                            next_frontier.add(target)
                            visited.add(target)
                # Also check incoming edges (graph is directed)
                for source, _, data in self.graph.in_edges(node, data=True):
                    if edge_types is None or data.get('edge_type') in [e.value for e in edge_types]:
                        if source not in visited:
                            next_frontier.add(source)
                            visited.add(source)
            frontier = next_frontier

        visited.discard(memory_id)
        return visited

    def get_subgraph(self, memory_id: str, hops: int = 2) -> 'MemoryGraph':
        """Extract a subgraph around a memory."""
        neighbor_ids = self.get_neighbors(memory_id, hops)
        neighbor_ids.add(memory_id)

        sub = MemoryGraph()
        sub_nx = self.graph.subgraph(neighbor_ids).copy()
        sub.graph = sub_nx
        sub._embeddings = {k: v for k, v in self._embeddings.items()
                          if k in neighbor_ids}
        return sub

    def contradiction_density(self, memory_id: str) -> float:
        """Count contradictions per memory — proxy for importance."""
        contras = self.get_contradictions(memory_id)
        return len(contras)

    def topic_contradiction_density(self) -> Dict[str, float]:
        """For each memory, compute its contradiction density.
        Higher = more important (inverse entrenchment thesis)."""
        densities = {}
        for node in self.graph.nodes:
            densities[node] = self.contradiction_density(node)
        return densities

    # -------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------

    def stats(self) -> dict:
        """Graph summary statistics."""
        edge_counts = {}
        disposition_counts = {}
        belnap_counts = {}

        for _, _, data in self.graph.edges(data=True):
            et = data.get('edge_type', 'unknown')
            edge_counts[et] = edge_counts.get(et, 0) + 1
            if et == EdgeType.CONTRADICTS.value:
                disp = data.get('disposition', 'unknown')
                disposition_counts[disp] = disposition_counts.get(disp, 0) + 1

        for _, data in self.graph.nodes(data=True):
            bs = data.get('belnap_state', 'T')
            belnap_counts[bs] = belnap_counts.get(bs, 0) + 1

        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "edge_types": edge_counts,
            "dispositions": disposition_counts,
            "belnap_states": belnap_counts,
            "held_contradictions": len(self.get_held_contradictions()),
            "evolving_contradictions": len(self.get_evolving_contradictions()),
            "embeddings_stored": len(self._embeddings),
        }

    # -------------------------------------------------------------------
    # Persistence (JSON)
    # -------------------------------------------------------------------

    def save(self, path: Optional[str] = None):
        """Save graph to JSON."""
        path = path or self.persist_path
        if not path:
            raise ValueError("No persist path specified")

        data = {
            "nodes": [],
            "edges": [],
        }
        for node_id, node_data in self.graph.nodes(data=True):
            data["nodes"].append({"id": node_id, **node_data})

        for source, target, edge_data in self.graph.edges(data=True):
            clean_data = {}
            for k, v in edge_data.items():
                if HAS_NUMPY and isinstance(v, np.ndarray):
                    continue
                clean_data[k] = v
            data["edges"].append({
                "source": source,
                "target": target,
                **clean_data,
            })

        # Save embeddings separately as .npy if numpy available
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        if HAS_NUMPY and self._embeddings:
            emb_path = path.replace('.json', '_embeddings.npz')
            np.savez_compressed(emb_path,
                               **{k: v for k, v in self._embeddings.items()})

    def load(self, path: Optional[str] = None):
        """Load graph from JSON."""
        path = path or self.persist_path
        if not path or not os.path.exists(path):
            return

        with open(path) as f:
            data = json.load(f)

        self.graph = nx.DiGraph()
        for node in data.get("nodes", []):
            node_id = node.pop("id")
            self.graph.add_node(node_id, **node)

        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            self.graph.add_edge(source, target, **edge)

        # Load embeddings if available
        if HAS_NUMPY:
            emb_path = path.replace('.json', '_embeddings.npz')
            if os.path.exists(emb_path):
                loaded = np.load(emb_path)
                self._embeddings = {k: loaded[k] for k in loaded.files}


# ---------------------------------------------------------------------------
# Belief Dependency Graph — Cascade Paper (Section 3)
# ---------------------------------------------------------------------------

@dataclass
class CascadeResult:
    """Result of a cascade propagation (Definition 3.5)."""
    source: str
    affected_nodes: Set[str]
    impacts: Dict[str, float]       # node_id -> impact
    depth: int
    width: int                      # max nodes at any single depth level
    total_nodes: int
    total_impact: float
    converged: bool
    depth_map: Dict[str, int]       # node_id -> depth
    width_per_level: Dict[int, int]
    blocked_by_firewall: Set[str] = field(default_factory=set)
    # Cascade pressure — cumulative incoming impact per node (SUM, not MAX)
    incoming_pressure: Dict[str, float] = field(default_factory=dict)
    max_pressure: float = 0.0
    avg_pressure: float = 0.0


class BeliefDependencyGraph:
    """Formal BDG for cascade complexity analysis (paper Definitions 3.2-3.6).

    Wraps a NetworkX digraph with typed edges (SUPPORTS, CONTRADICTS, SUPERSEDES)
    and cascade propagation with geometric damping (Theorem 4.3).

    Nodes are BeliefLocus instances (Definition 3.1).
    """

    def __init__(self, cascade_threshold: float = 0.01):
        if not HAS_NETWORKX:
            raise ImportError("networkx required: pip install networkx")
        self.graph = nx.DiGraph()
        self._belief_loci: Dict[str, object] = {}
        self.cascade_threshold = cascade_threshold

    # --- Node operations ---

    def add_belief(self, belief_locus) -> str:
        """Add a belief state (BeliefLocus) to the graph."""
        self.graph.add_node(belief_locus.memory_id,
                            text=belief_locus.text,
                            memory_type=belief_locus.memory_type,
                            alpha=belief_locus.alpha)
        self._belief_loci[belief_locus.memory_id] = belief_locus
        return belief_locus.memory_id

    def get_belief_locus(self, memory_id: str):
        return self._belief_loci.get(memory_id)

    # Backwards compatibility alias
    get_splat = get_belief_locus

    # --- Edge operations ---

    def add_dependency(self, source: str, target: str,
                       edge_type: EdgeType, weight: float = 0.5):
        """Add a typed, weighted dependency edge."""
        self.graph.add_edge(source, target,
                            edge_type=edge_type.value,
                            weight=max(0.0, min(1.0, weight)))

    # --- Graph properties ---

    @property
    def num_nodes(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def num_edges(self) -> int:
        return self.graph.number_of_edges()

    @property
    def is_dag(self) -> bool:
        return nx.is_directed_acyclic_graph(self.graph)

    def longest_path_length(self) -> float:
        if self.is_dag:
            return nx.dag_longest_path_length(self.graph)
        # For non-DAG, compute on SUPPORTS/SUPERSEDES subgraph
        G_dag = nx.DiGraph()
        for u, v, d in self.graph.edges(data=True):
            if d.get("edge_type") != EdgeType.CONTRADICTS.value:
                G_dag.add_edge(u, v, **d)
        if nx.is_directed_acyclic_graph(G_dag) and G_dag.number_of_edges() > 0:
            return nx.dag_longest_path_length(G_dag)
        return 0

    def max_out_degree(self) -> int:
        if self.num_nodes == 0:
            return 0
        return max(d for _, d in self.graph.out_degree())

    # --- Cascade propagation (Definition 3.5, Theorem 4.3) ---

    def propagate_cascade(self, source_id: str, delta_0: float,
                          lipschitz_constant: float = 0.9,
                          use_dispositions: bool = True,
                          held_nodes: Optional[Set[str]] = None,
                          max_depth: int = 100) -> CascadeResult:
        """BFS cascade with geometric damping and MAX aggregation.

        Args:
            source_id: Node to start cascade from.
            delta_0: Initial revision impact (Fisher-Rao distance).
            lipschitz_constant: L — how much each node amplifies/dampens.
            use_dispositions: If True, HELD disposition blocks propagation.
            held_nodes: Explicit set of held node IDs (overrides disposition).
            max_depth: Safety limit.

        Returns:
            CascadeResult with affected nodes, impacts, depth, width.
        """
        from collections import deque

        if held_nodes is None:
            held_nodes = set()

        affected = {source_id: delta_0}
        depth_map = {source_id: 0}
        width_per_level: Dict[int, int] = {0: 1}
        blocked = set()
        queue = deque([(source_id, delta_0, 0)])
        total_impact = delta_0
        max_depth_reached = 0
        # Track cumulative incoming pressure per node (SUM aggregation)
        incoming_pressure: Dict[str, List[float]] = {}

        while queue:
            node, impact, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # Held nodes absorb but don't propagate
            if node in held_nodes and node != source_id:
                continue
            if use_dispositions and node != source_id:
                node_data = self.graph.nodes.get(node, {})
                if node_data.get("disposition") == Disposition.HELD.value:
                    continue

            for _, succ, edata in self.graph.out_edges(node, data=True):
                w = edata.get("weight", 0.5)
                propagated = w * lipschitz_constant * impact

                if propagated <= self.cascade_threshold:
                    continue

                if succ in held_nodes:
                    blocked.add(succ)

                # Track all incoming impacts for pressure (SUM)
                if succ not in incoming_pressure:
                    incoming_pressure[succ] = []
                incoming_pressure[succ].append(propagated)

                # MAX aggregation (Definition 3.5)
                if succ in affected and propagated <= affected[succ]:
                    continue

                affected[succ] = propagated
                new_depth = depth + 1
                depth_map[succ] = new_depth
                width_per_level[new_depth] = width_per_level.get(new_depth, 0) + 1
                max_depth_reached = max(max_depth_reached, new_depth)
                total_impact += propagated
                queue.append((succ, propagated, new_depth))

        max_width = max(width_per_level.values()) if width_per_level else 0
        rho = lipschitz_constant * max(
            (edata.get("weight", 0.5)
             for _, _, edata in self.graph.edges(data=True)),
            default=0.5
        )

        # Compute pressure sums per node
        pressure_sums = {node: sum(impacts) for node, impacts in incoming_pressure.items()}
        pressure_values = list(pressure_sums.values())
        max_pressure = max(pressure_values) if pressure_values else 0.0
        avg_pressure = (sum(pressure_values) / len(pressure_values)) if pressure_values else 0.0

        return CascadeResult(
            source=source_id,
            affected_nodes=set(affected.keys()),
            impacts=affected,
            depth=max_depth_reached,
            width=max_width,
            total_nodes=len(affected),
            total_impact=total_impact,
            converged=(rho < 1),
            depth_map=depth_map,
            width_per_level=dict(width_per_level),
            blocked_by_firewall=blocked,
            incoming_pressure=pressure_sums,
            max_pressure=max_pressure,
            avg_pressure=avg_pressure,
        )

    # --- Backward Propagation (Belief Backpropagation) ---

    def propagate_backward(self, corrected_id: str, loss: float,
                           damping_factor: float = 0.9,
                           max_depth: int = 50) -> CascadeResult:
        """BFS backward cascade: gradient flows from corrected node to supporters.

        Mirrors propagate_cascade() but traverses in_edges (predecessors).
        Only follows SUPPORTS / DERIVED_FROM / RELATED_TO edges backward.

        Args:
            corrected_id: Node where the error was detected.
            loss: Epistemic loss (initial gradient magnitude).
            damping_factor: Decay per hop (same role as lipschitz_constant).
            max_depth: Safety limit.

        Returns:
            CascadeResult with affected upstream nodes and gradient impacts.
        """
        from collections import deque

        affected = {corrected_id: loss}
        depth_map = {corrected_id: 0}
        width_per_level: Dict[int, int] = {0: 1}
        queue = deque([(corrected_id, loss, 0)])
        total_impact = loss
        max_depth_reached = 0
        incoming_pressure: Dict[str, List[float]] = {}

        skip_edge_types = {EdgeType.CONTRADICTS.value, "CONTRADICTS"}

        while queue:
            node, gradient, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for pred, _, edata in self.graph.in_edges(node, data=True):
                if pred == corrected_id:
                    continue

                edge_type = edata.get("edge_type", "SUPPORTS")
                if edge_type in skip_edge_types:
                    continue

                w = edata.get("weight", 0.5)
                propagated = w * damping_factor * gradient

                if propagated <= self.cascade_threshold:
                    continue

                if pred not in incoming_pressure:
                    incoming_pressure[pred] = []
                incoming_pressure[pred].append(propagated)

                # MAX aggregation
                if pred in affected and propagated <= affected[pred]:
                    continue

                affected[pred] = propagated
                new_depth = depth + 1
                depth_map[pred] = new_depth
                width_per_level[new_depth] = width_per_level.get(new_depth, 0) + 1
                max_depth_reached = max(max_depth_reached, new_depth)
                total_impact += propagated
                queue.append((pred, propagated, new_depth))

        max_width = max(width_per_level.values()) if width_per_level else 0
        pressure_sums = {n: sum(ps) for n, ps in incoming_pressure.items()}
        pressure_vals = list(pressure_sums.values())

        return CascadeResult(
            source=corrected_id,
            affected_nodes=set(affected.keys()),
            impacts=affected,
            depth=max_depth_reached,
            width=max_width,
            total_nodes=len(affected),
            total_impact=total_impact,
            converged=(damping_factor < 1),
            depth_map=depth_map,
            width_per_level=dict(width_per_level),
            blocked_by_firewall=set(),
            incoming_pressure=pressure_sums,
            max_pressure=max(pressure_vals) if pressure_vals else 0.0,
            avg_pressure=(sum(pressure_vals) / len(pressure_vals)) if pressure_vals else 0.0,
        )

    # --- Reachability (Proposition 5.3) ---

    def effective_reachable_set(self, source: str,
                                held_nodes: Set[str]) -> Set[str]:
        """Nodes reachable from source without passing through held nodes."""
        from collections import deque
        visited = {source}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            if node in held_nodes and node != source:
                continue
            for _, succ in self.graph.out_edges(node):
                if succ not in visited:
                    visited.add(succ)
                    queue.append(succ)
        return visited

    # --- Instability analysis (Theorem 4.4) ---

    def cycle_amplification(self, cycle_nodes: List[str]) -> float:
        """Compute product of edge weights around a cycle."""
        product = 1.0
        for i in range(len(cycle_nodes)):
            src = cycle_nodes[i]
            tgt = cycle_nodes[(i + 1) % len(cycle_nodes)]
            edata = self.graph.get_edge_data(src, tgt) or {}
            product *= edata.get("weight", 0.5)
        return product

    def find_unstable_cycles(self, lipschitz_constant: float = 1.0,
                             max_cycles: int = 100) -> List[Tuple[List[str], float]]:
        """Find cycles with amplification factor > 1 (Theorem 4.4)."""
        unstable = []
        count = 0
        for cycle in nx.simple_cycles(self.graph):
            amp = self.cycle_amplification(cycle)
            # Cycle amplification factor: product(w_i) * L^m
            lambda_cycle = amp * (lipschitz_constant ** len(cycle))
            if lambda_cycle > 1.0:
                unstable.append((cycle, lambda_cycle))
            count += 1
            if count >= max_cycles:
                break
        return unstable


# ---------------------------------------------------------------------------
# Live BDG — Production singleton for cascade propagation
# ---------------------------------------------------------------------------

import threading as _bdg_threading

CASCADE_TRUST_FACTOR = 0.3   # impact * this = trust reduction (conservative)
SIMILARITY_THRESHOLD = 0.5   # cosine sim threshold for RELATED_TO edges
LIPSCHITZ_CONSTANT = 0.9     # geometric damping per hop
CASCADE_THRESHOLD = 0.01     # minimum impact to continue propagation


class LiveBDG:
    """Production wrapper around BeliefDependencyGraph.

    Lazy-builds from the live memory DB on first use.
    Incrementally updated as memories and contradictions are added.
    Thread-safe via RLock.
    """

    def __init__(self, memory_system, ledger):
        self.memory_system = memory_system
        self.ledger = ledger
        self.bdg = BeliefDependencyGraph(cascade_threshold=CASCADE_THRESHOLD)
        self._built = False
        self._lock = _bdg_threading.RLock()
        self._vectors: Dict[str, object] = {}  # memory_id -> np.ndarray
        print("[BDG] LiveBDG singleton created (lazy build on first use)")

    def ensure_built(self):
        """Lazy-build the full BDG from production data. Idempotent."""
        with self._lock:
            if self._built:
                return

            import json as _json
            import time as _time
            t0 = _time.perf_counter()

            # Load all active memories
            try:
                conn = self.memory_system._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT memory_id, vector_json, text, memory_type,
                           belnap_state, trust, sigma
                    FROM memories
                    WHERE deprecated = 0 AND vector_json IS NOT NULL
                """)
                rows = cursor.fetchall()
                conn.close()
            except Exception as e:
                print(f"[BDG] ERROR loading memories: {e}")
                return

            if not HAS_NUMPY:
                print("[BDG] ERROR: numpy not available, cannot build BDG")
                return

            # Parse embeddings and add nodes
            ids = []
            vectors = []
            skipped = 0

            for row in rows:
                mid, vec_json, text, mtype, belnap, trust, sigma_blob = row
                try:
                    vec = np.array(_json.loads(vec_json), dtype=np.float32)
                    if len(vec) == 0:
                        skipped += 1
                        continue
                except Exception:
                    skipped += 1
                    continue

                mtype_clean = mtype if mtype in ("fact", "preference", "event", "belief", "identity") else "belief"

                # Add node to BDG graph directly (lightweight, no BeliefLocus needed for edges)
                self.bdg.graph.add_node(mid,
                    text=(text or "")[:200],
                    memory_type=mtype_clean,
                    belnap_state=belnap or "true",
                    trust=trust or 0.5,
                    alpha=trust or 0.5,
                )
                self._vectors[mid] = vec
                ids.append(mid)
                vectors.append(vec)

            node_count = len(ids)
            print(f"[BDG] Loaded {node_count} nodes ({skipped} skipped)")

            if node_count == 0:
                self._built = True
                return

            # Compute pairwise cosine similarity (vectorized)
            mat = np.stack(vectors)  # (n, 384)
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms = np.clip(norms, 1e-8, None)
            mat_norm = mat / norms
            sim_matrix = mat_norm @ mat_norm.T  # (n, n)

            # Add RELATED_TO edges above threshold
            edge_count = 0
            pairs = np.argwhere(np.triu(sim_matrix > SIMILARITY_THRESHOLD, k=1))
            for i, j in pairs:
                mid_i, mid_j = ids[i], ids[j]
                sim = float(sim_matrix[i, j])
                # Direction: older -> newer by node index (approximation)
                self.bdg.graph.add_edge(mid_i, mid_j,
                    edge_type=EdgeType.RELATED_TO.value,
                    weight=sim)
                edge_count += 1

            print(f"[BDG] Added {edge_count} RELATED_TO edges (threshold={SIMILARITY_THRESHOLD})")

            # Load contradictions from ledger
            contra_count = 0
            try:
                ledger_conn = self.ledger._get_connection()
                ledger_cursor = ledger_conn.cursor()
                ledger_cursor.execute("""
                    SELECT old_memory_id, new_memory_id, drift_mean, disposition
                    FROM contradictions
                """)
                for old_id, new_id, drift, disp in ledger_cursor.fetchall():
                    if old_id in self.bdg.graph and new_id in self.bdg.graph:
                        weight = max(0.1, min(1.0, drift or 0.5))
                        self.bdg.graph.add_edge(old_id, new_id,
                            edge_type=EdgeType.CONTRADICTS.value, weight=weight)
                        self.bdg.graph.add_edge(new_id, old_id,
                            edge_type=EdgeType.CONTRADICTS.value, weight=weight)
                        contra_count += 1
                ledger_conn.close()
            except Exception as e:
                print(f"[BDG] WARNING loading ledger contradictions: {e}")

            elapsed = _time.perf_counter() - t0
            print(f"[BDG] Built: {node_count} nodes, {edge_count + contra_count * 2} edges, "
                  f"{contra_count} contradictions ({elapsed:.2f}s)")

            self._built = True

    def add_memory(self, memory_id: str, vector, text: str,
                   memory_type: str = "observation", trust: float = 0.5):
        """Incrementally add a new memory node + similarity edges."""
        with self._lock:
            if not HAS_NUMPY or vector is None:
                return

            vec = np.asarray(vector, dtype=np.float32)
            if len(vec) == 0:
                return

            self.bdg.graph.add_node(memory_id,
                text=text[:200],
                memory_type=memory_type,
                belnap_state="true",
                trust=trust,
                alpha=trust,
            )
            self._vectors[memory_id] = vec

            # Compute similarity against existing nodes
            new_edges = 0
            vec_norm = vec / max(np.linalg.norm(vec), 1e-8)

            for existing_id, existing_vec in self._vectors.items():
                if existing_id == memory_id:
                    continue
                ev_norm = existing_vec / max(np.linalg.norm(existing_vec), 1e-8)
                sim = float(np.dot(vec_norm, ev_norm))
                if sim > SIMILARITY_THRESHOLD:
                    self.bdg.graph.add_edge(existing_id, memory_id,
                        edge_type=EdgeType.RELATED_TO.value, weight=sim)
                    new_edges += 1

            print(f"[BDG] add_memory: {memory_id}, {new_edges} new edges")

    def add_contradiction(self, old_id: str, new_id: str, drift_mean: float):
        """Add bidirectional CONTRADICTS edge."""
        with self._lock:
            weight = max(0.1, min(1.0, drift_mean))
            self.bdg.graph.add_edge(old_id, new_id,
                edge_type=EdgeType.CONTRADICTS.value, weight=weight)
            self.bdg.graph.add_edge(new_id, old_id,
                edge_type=EdgeType.CONTRADICTS.value, weight=weight)
            print(f"[BDG] add_contradiction: {old_id} <-> {new_id}, weight={weight:.3f}")

    def run_cascade(self, source_id: str, delta_0: float) -> Optional[CascadeResult]:
        """Run cascade propagation from a revised node."""
        self.ensure_built()

        with self._lock:
            if source_id not in self.bdg.graph:
                print(f"[BDG_CASCADE] WARNING: source {source_id} not in graph, skipping")
                return None

            # Collect held nodes (Proposition 5.3)
            held_nodes = set()
            for nid, ndata in self.bdg.graph.nodes(data=True):
                if ndata.get("belnap_state") == "both":
                    held_nodes.add(nid)

            if held_nodes:
                print(f"[BDG_CASCADE] {len(held_nodes)} held nodes acting as firewalls")

        # Run cascade (read-only on graph, safe outside lock)
        result = self.bdg.propagate_cascade(
            source_id, delta_0,
            lipschitz_constant=LIPSCHITZ_CONSTANT,
            held_nodes=held_nodes,
        )

        print(f"[BDG_CASCADE] source={source_id}, delta_0={delta_0:.3f}, "
              f"affected={result.total_nodes}, depth={result.depth}, "
              f"total_impact={result.total_impact:.3f}, converged={result.converged}")

        if result.depth > 0:
            # Log damping curve
            from collections import defaultdict as _ddict
            depth_impacts = _ddict(list)
            for nid, impact in result.impacts.items():
                depth_impacts[result.depth_map[nid]].append(impact)
            for d in sorted(depth_impacts.keys()):
                imps = depth_impacts[d]
                print(f"[BDG_CASCADE]   depth {d}: {len(imps)} nodes, "
                      f"avg_impact={sum(imps)/len(imps):.4f}")

        return result


# Module-level singleton
_live_bdg_instance: Optional[LiveBDG] = None
_live_bdg_lock = _bdg_threading.Lock()


def get_live_bdg(memory_system=None, ledger=None) -> Optional[LiveBDG]:
    """Get or create the LiveBDG singleton.

    First call must provide memory_system and ledger.
    Subsequent calls can omit them.
    """
    global _live_bdg_instance
    with _live_bdg_lock:
        if _live_bdg_instance is None:
            if memory_system is not None and ledger is not None:
                _live_bdg_instance = LiveBDG(memory_system, ledger)
            else:
                return None
        return _live_bdg_instance


# ---------------------------------------------------------------------------
# Integration with disposition classifier
# ---------------------------------------------------------------------------

def build_test_graph():
    """Build a test graph with the same cases from disposition_classifier.py."""
    from disposition_classifier import classify_contradiction, Disposition as DispClass

    graph = MemoryGraph()

    # Test memories — pairs that contradict
    test_pairs = [
        # RESOLVABLE
        ("I work at Google", "I work at Microsoft",
         "fact", "fact", 0, 86400 * 180, 0.85),
        ("Meeting is on Monday at 3pm", "Meeting moved to Tuesday at 2pm",
         "event", "event", 0, 86400, 0.8),

        # HELD
        ("I love my job", "My job is killing me",
         "belief", "belief", 0, 86400 * 14, 0.7),
        ("I'm an introvert", "I love performing on stage",
         "identity", "identity", 0, 86400 * 30, 0.4),
        ("I want to have kids someday", "I don't think I want kids",
         "belief", "belief", 0, 86400 * 45, 0.7),
        ("I hate AI", "I've spent a year building an AI system",
         "belief", "belief", 0, 86400 * 365, 0.3),

        # EVOLVING
        ("I used to love React", "Now I prefer Vue",
         "preference", "preference", 0, 86400 * 90, 0.7),
        ("I'm happy with my career in finance",
         "I've been thinking about switching to tech",
         "identity", "belief", 0, 86400 * 120, 0.6),

        # CONTEXTUAL
        ("I'm really disciplined at work", "At home I'm kind of lazy",
         "identity", "identity", 0, 86400, 0.5),

        # Non-contradicting (just related)
        ("I like coffee", "I drink coffee every morning",
         "preference", "preference", 0, 86400 * 5, 0.85),
    ]

    for i, (text_a, text_b, type_a, type_b, ts_a, ts_b, sim) in enumerate(test_pairs):
        # Create memory nodes
        id_a = f"mem_{i:03d}_a"
        id_b = f"mem_{i:03d}_b"

        node_a = MemoryNode(
            memory_id=id_a, text=text_a, created_at=ts_a,
            memory_type=type_a, trust=0.7, confidence=0.8,
        )
        node_b = MemoryNode(
            memory_id=id_b, text=text_b, created_at=ts_b,
            memory_type=type_b, trust=0.7, confidence=0.8,
        )
        graph.add_memory(node_a)
        graph.add_memory(node_b)

        # Classify the contradiction
        result = classify_contradiction(text_a, text_b, ts_a, ts_b, sim)

        if result.disposition.value != "unknown":
            # Add contradiction edge
            edge = ContradictionEdge(
                disposition=result.disposition.value,
                nli_score=0.9,  # placeholder — would come from NLI
                detected_at=time.time(),
                classification_confidence=result.confidence,
                rule_trace=result.rule_trace,
            )
            graph.add_contradiction(id_a, id_b, edge)

        # Add similarity edge for related pairs
        if sim > 0.7:
            graph.add_similarity_edge(id_a, id_b, sim)

    return graph


# ---------------------------------------------------------------------------
# Main — test the graph
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("MEMORY GRAPH — Phase 1 Test")
    print("=" * 70)

    graph = build_test_graph()

    # Print stats
    stats = graph.stats()
    print(f"\n  Nodes: {stats['nodes']}")
    print(f"  Edges: {stats['edges']}")
    print(f"  Edge types: {stats['edge_types']}")
    print(f"  Dispositions: {stats['dispositions']}")
    print(f"  Belnap states: {stats['belnap_states']}")

    # Show held contradictions
    print(f"\n  --- HELD CONTRADICTIONS ({stats['held_contradictions']}) ---")
    for a, b, data in graph.get_held_contradictions():
        node_a = graph.get_memory(a)
        node_b = graph.get_memory(b)
        print(f"    [{node_a.belnap_state}] \"{node_a.text}\"")
        print(f"    [{node_b.belnap_state}] \"{node_b.text}\"")
        print(f"    Trace: {' -> '.join(data.get('rule_trace', []))}")
        print()

    # Show evolving
    print(f"  --- EVOLVING CONTRADICTIONS ({stats['evolving_contradictions']}) ---")
    for a, b, data in graph.get_evolving_contradictions():
        node_a = graph.get_memory(a)
        node_b = graph.get_memory(b)
        print(f"    \"{node_a.text}\"  -->  \"{node_b.text}\"")
        print(f"    Trace: {' -> '.join(data.get('rule_trace', []))}")
        print()

    # Test subgraph extraction
    print("  --- SUBGRAPH TEST ---")
    job_love = "mem_002_a"  # "I love my job"
    neighbors = graph.get_neighbors(job_love, hops=2)
    print(f"  2-hop neighbors of \"{graph.get_memory(job_love).text}\":")
    for n in neighbors:
        node = graph.get_memory(n)
        if node:
            print(f"    - \"{node.text}\" (belnap={node.belnap_state})")

    # Test contradiction density (importance proxy)
    print("\n  --- CONTRADICTION DENSITY (importance proxy) ---")
    densities = graph.topic_contradiction_density()
    sorted_densities = sorted(densities.items(), key=lambda x: x[1], reverse=True)
    for mem_id, density in sorted_densities[:10]:
        if density > 0:
            node = graph.get_memory(mem_id)
            print(f"    density={density:.0f} | \"{node.text}\"")

    # Test persistence
    print("\n  --- PERSISTENCE TEST ---")
    save_path = "test_memory_graph.json"
    graph.save(save_path)
    print(f"  Saved to {save_path}")

    # Reload
    graph2 = MemoryGraph(persist_path=save_path)
    stats2 = graph2.stats()
    assert stats2['nodes'] == stats['nodes'], f"Node count mismatch: {stats2['nodes']} vs {stats['nodes']}"
    assert stats2['edges'] == stats['edges'], f"Edge count mismatch: {stats2['edges']} vs {stats['edges']}"
    print(f"  Reloaded: {stats2['nodes']} nodes, {stats2['edges']} edges -- MATCH")

    # Cleanup
    os.remove(save_path)
    print(f"  Cleaned up {save_path}")

    print(f"\n{'='*70}")
    print("MEMORY GRAPH TEST COMPLETE")
    print(f"{'='*70}")
