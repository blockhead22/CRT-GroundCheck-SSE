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
    overlap_integral: float = 0.0  # geometric overlap (future: splat)
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
