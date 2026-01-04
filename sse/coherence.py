"""
SSE Coherence Tracking (Phase 6, D3)

Observes and tracks disagreement patterns without resolving contradictions.

This module computes metadata about how claims relate to each other:
- Which claims agree/disagree
- Patterns of agreement/disagreement
- Confidence in relationships (based on evidence)
- Uncertainty about disagreement classification

CRITICAL: This module NEVER resolves contradictions, picks winners,
or softens ambiguity. It only OBSERVES and RECORDS disagreement.
"""

from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class DisagreementEdge:
    """Represents a disagreement relationship between two claims."""
    claim_id_a: str
    claim_id_b: str
    relationship: str  # "contradicts", "conflicts", "qualifies", "uncertain"
    confidence: float  # 0.0 to 1.0
    evidence_quotes: List[str]  # Supporting quotes from both claims
    reasoning: str  # Why this relationship exists (never prescriptive)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ClaimCoherence:
    """Coherence metadata for a single claim."""
    claim_id: str
    claim_text: str
    total_relationships: int  # How many other claims it relates to
    contradictions: int  # Direct contradictions
    conflicts: int  # Disagreements that don't contradict
    qualifications: int  # Claims that limit or qualify this one
    agreements: int  # Claims that align (if tracked)
    ambiguous_relationships: int  # Uncertain disagreements
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class CoherenceTracker:
    """
    Track disagreement patterns without resolution.
    
    This is NOT:
    - A resolver (it doesn't pick sides)
    - A synthesizer (it doesn't generate new knowledge)
    - A softener (it doesn't reduce ambiguity)
    
    This IS:
    - An observer (records disagreement patterns)
    - A metadata provider (exposes relationship structure)
    - A transparency tool (shows how claims relate without judgment)
    """
    
    def __init__(self, index: Dict):
        """
        Initialize coherence tracker from SSE index.
        
        Args:
            index: SSE index dictionary with claims and contradictions
        """
        self.claims = {c['claim_id']: c for c in index.get('claims', [])}
        self.contradictions = index.get('contradictions', [])
        self.edges: Dict[Tuple[str, str], DisagreementEdge] = {}
        
        # Build the disagreement graph
        self._build_disagreement_graph()
    
    # ===== OBSERVATION (permitted) =====
    
    def get_claim_coherence(self, claim_id: str) -> Optional[ClaimCoherence]:
        """
        Get coherence metadata for a single claim.
        
        Shows how this claim relates to all others, WITHOUT resolving conflicts.
        
        Returns:
            ClaimCoherence with relationship counts
        """
        if claim_id not in self.claims:
            return None
        
        claim = self.claims[claim_id]
        
        contradictions = 0
        conflicts = 0
        qualifications = 0
        agreements = 0
        ambiguous = 0
        
        # Count relationships for this claim
        for (a, b), edge in self.edges.items():
            if claim_id in (a, b):
                if edge.relationship == "contradicts":
                    contradictions += 1
                elif edge.relationship == "conflicts":
                    conflicts += 1
                elif edge.relationship == "qualifies":
                    qualifications += 1
                elif edge.relationship == "uncertain":
                    ambiguous += 1
                else:
                    agreements += 1
        
        total = contradictions + conflicts + qualifications + agreements + ambiguous
        
        return ClaimCoherence(
            claim_id=claim_id,
            claim_text=claim.get("claim_text"),
            total_relationships=total,
            contradictions=contradictions,
            conflicts=conflicts,
            qualifications=qualifications,
            agreements=agreements,
            ambiguous_relationships=ambiguous
        )
    
    def get_disagreement_edges(self, claim_id: Optional[str] = None) -> List[Dict]:
        """
        Get all disagreement edges (relationships).
        
        If claim_id provided, returns only edges involving that claim.
        Otherwise returns all edges.
        
        PERMITTED: Pure observation of disagreement structure.
        """
        if claim_id is None:
            return [e.to_dict() for e in self.edges.values()]
        
        # Filter edges for this claim
        result = []
        for (a, b), edge in self.edges.items():
            if claim_id in (a, b):
                result.append(edge.to_dict())
        
        return result
    
    def get_related_claims(self, claim_id: str, 
                          relationship: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        Get all claims related to this one.
        
        Args:
            claim_id: The claim to find relationships for
            relationship: Optional filter ("contradicts", "conflicts", etc.)
        
        Returns:
            List of (related_claim_id, relationship_type) tuples
        """
        result = []
        
        for (a, b), edge in self.edges.items():
            if claim_id == a:
                if relationship is None or edge.relationship == relationship:
                    result.append((b, edge.relationship))
            elif claim_id == b:
                if relationship is None or edge.relationship == relationship:
                    result.append((a, edge.relationship))
        
        return result
    
    def get_disagreement_clusters(self) -> List[Set[str]]:
        """
        Find groups of claims that all disagree with each other.
        
        PERMITTED: Pure observation of relationship structure.
        NOT PERMITTED: Picking which cluster is "correct"
        """
        # Build adjacency from edges
        adjacency = {}
        for claim_id in self.claims:
            adjacency[claim_id] = set()
        
        for (a, b), edge in self.edges.items():
            if edge.relationship in ("contradicts", "conflicts"):
                adjacency[a].add(b)
                adjacency[b].add(a)
        
        # Find connected components
        visited = set()
        clusters = []
        
        for claim_id in self.claims:
            if claim_id not in visited:
                cluster = self._dfs_cluster(claim_id, adjacency, visited)
                if len(cluster) > 1:  # Only return clusters with disagreement
                    clusters.append(cluster)
        
        return clusters
    
    def get_coherence_report(self) -> Dict:
        """
        Get overall coherence report for the index.
        
        Shows disagreement statistics WITHOUT claiming any claims are wrong.
        """
        total_edges = len(self.edges)
        contradiction_count = sum(1 for e in self.edges.values() 
                                 if e.relationship == "contradicts")
        conflict_count = sum(1 for e in self.edges.values() 
                            if e.relationship == "conflicts")
        qualification_count = sum(1 for e in self.edges.values() 
                                  if e.relationship == "qualifies")
        ambiguous_count = sum(1 for e in self.edges.values() 
                             if e.relationship == "uncertain")
        
        # Find highest-conflict claims
        claim_degrees = {}
        for claim_id in self.claims:
            coh = self.get_claim_coherence(claim_id)
            claim_degrees[claim_id] = coh.total_relationships if coh else 0
        
        high_conflict_claims = sorted(claim_degrees.items(), 
                                     key=lambda x: x[1], 
                                     reverse=True)[:5]
        
        clusters = self.get_disagreement_clusters()
        
        return {
            "total_claims": len(self.claims),
            "total_disagreement_edges": total_edges,
            "contradiction_edges": contradiction_count,
            "conflict_edges": conflict_count,
            "qualification_edges": qualification_count,
            "ambiguous_edges": ambiguous_count,
            "disagreement_density": total_edges / (len(self.claims) * (len(self.claims) - 1) / 2) if len(self.claims) > 1 else 0,
            "highest_conflict_claims": [
                {"claim_id": cid, "relationships": deg}
                for cid, deg in high_conflict_claims
            ],
            "disagreement_clusters": [list(cluster) for cluster in clusters],
            "num_isolated_claims": sum(1 for deg in claim_degrees.values() if deg == 0)
        }
    
    # ===== FORBIDDEN OPERATIONS =====
    
    def resolve_disagreement(self, *args, **kwargs):
        """FORBIDDEN: Resolving disagreements."""
        raise CoherenceBoundaryViolation(
            "resolve_disagreement",
            "Coherence tracking observes disagreement, it never resolves it. "
            "Both sides remain equally valid."
        )
    
    def pick_coherent_subset(self, *args, **kwargs):
        """FORBIDDEN: Selecting a coherent subset (filtering out disagreement)."""
        raise CoherenceBoundaryViolation(
            "pick_coherent_subset",
            "Coherence tracking never filters out disagreement. "
            "All claims are preserved."
        )
    
    def synthesize_resolution(self, *args, **kwargs):
        """FORBIDDEN: Creating a synthetic consensus."""
        raise CoherenceBoundaryViolation(
            "synthesize_resolution",
            "Coherence tracking never synthesizes resolutions. "
            "Disagreement is observed, not resolved."
        )
    
    # ===== INTERNAL HELPERS =====
    
    def _build_disagreement_graph(self):
        """Build edges from contradictions index."""
        for contra in self.contradictions:
            pair = contra.get("pair", {})
            claim_id_a = pair.get("claim_id_a")
            claim_id_b = pair.get("claim_id_b")
            
            if not claim_id_a or not claim_id_b:
                continue
            
            # Determine edge type
            label = contra.get("label", "contradiction")
            relationship = self._classify_relationship(label)
            
            # Calculate confidence (0-1 based on evidence quality)
            evidence = contra.get("evidence_quotes", [])
            confidence = min(1.0, len(evidence) / 2.0)  # More evidence = higher confidence
            
            # Get reasoning
            reasoning = self._generate_reasoning(claim_id_a, claim_id_b, label)
            
            # Create edge (canonical order: alphabetical)
            if claim_id_a < claim_id_b:
                key = (claim_id_a, claim_id_b)
            else:
                key = (claim_id_b, claim_id_a)
            
            edge = DisagreementEdge(
                claim_id_a=key[0],
                claim_id_b=key[1],
                relationship=relationship,
                confidence=confidence,
                evidence_quotes=[q.get("quote_text", "") for q in evidence],
                reasoning=reasoning
            )
            
            self.edges[key] = edge
    
    def _classify_relationship(self, label: str) -> str:
        """Classify disagreement type based on label."""
        label_lower = label.lower()
        
        if "contradict" in label_lower:
            return "contradicts"
        elif "conflict" in label_lower:
            return "conflicts"
        elif "qualif" in label_lower:
            return "qualifies"
        elif "uncertain" in label_lower or "ambiguous" in label_lower:
            return "uncertain"
        else:
            return "conflicts"
    
    def _generate_reasoning(self, claim_id_a: str, claim_id_b: str, label: str) -> str:
        """Generate plain-language reasoning about relationship."""
        claim_a = self.claims.get(claim_id_a, {})
        claim_b = self.claims.get(claim_id_b, {})
        
        text_a = claim_a.get("claim_text", "")[:50]
        text_b = claim_b.get("claim_text", "")[:50]
        
        return f"{text_a}... vs {text_b}... ({label})"
    
    def _dfs_cluster(self, start: str, adjacency: Dict, visited: Set) -> Set[str]:
        """DFS to find connected component."""
        stack = [start]
        cluster = set()
        
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            
            visited.add(node)
            cluster.add(node)
            
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    stack.append(neighbor)
        
        return cluster


class CoherenceBoundaryViolation(Exception):
    """Raised when coherence tracking boundary is violated."""
    
    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(
            f"Coherence Boundary Violation: {operation}\n"
            f"Reason: {reason}\n"
            f"Coherence tracking permits only: observation, metadata, transparency.\n"
            f"Coherence tracking forbids: resolution, synthesis, filtering disagreement."
        )
