"""
Search Adapter (Phase 4.2)

Human-facing truth-disclosure UI layer. Can reorder, group, cluster, and render,
but never suppress. Uses topology (not truth) to highlight contradictions.

Design principle: Present the full contradiction landscape to the user.
No filtering, no synthesis, no winner-picking.
"""

import json
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict


class SearchAdapter:
    """
    Search results adapter for contradiction-aware visualization.
    
    Consumes EvidencePacket and produces structured output for UI rendering
    that highlights contradictions and clusters without suppressing any claims.
    
    Contract:
    - Input: EvidencePacket dict (validated)
    - Processing: Build UI-friendly structure, highlight contradictions
    - Output: Reordered/grouped claims + contradiction graph
    - Gate: Schema validation before return (implicit in output format)
    """

    def __init__(self):
        """Initialize search adapter."""
        pass

    def render_search_results(
        self,
        packet_dict: Dict[str, Any],
        highlight_contradictions: bool = True,
    ) -> Dict[str, Any]:
        """
        Render EvidencePacket as search results.
        
        Args:
            packet_dict: EvidencePacket dict
            highlight_contradictions: Whether to highlight contradictions
            
        Returns:
            {
                "query": search query,
                "summary": brief overview,
                "results": [
                    {
                        "claim_id": "claim_xxx",
                        "text": "claim text",
                        "source": "doc_id",
                        "contradiction_count": N,
                        "contradicts_with": ["claim_yyy", "claim_zzz"],
                        "cluster_id": cluster_id or None,
                        "relevance": 0.0-1.0,
                    }
                ],
                "contradictions": [
                    {
                        "from_id": "claim_xxx",
                        "to_id": "claim_yyy",
                        "relationship": "contradicts|qualifies|extends",
                        "strength": 0.0-1.0,
                        "from_text": "...",
                        "to_text": "...",
                    }
                ],
                "clusters": [
                    {
                        "cluster_id": 0,
                        "members": ["claim_xxx", "claim_yyy"],
                        "description": "Group of X contradicting claims",
                    }
                ],
                "statistics": {
                    "total_claims": N,
                    "claims_with_contradictions": N,
                    "contradiction_edges": N,
                    "clusters": N,
                }
            }
        """
        claims = packet_dict["claims"]
        contradictions = packet_dict["contradictions"]
        metrics = packet_dict["support_metrics"]
        clusters = packet_dict["clusters"]
        
        # Build contradiction lookup
        contradictions_by_claim = self._build_contradiction_index(contradictions)
        
        # Build claim lookup
        claims_by_id = {c["claim_id"]: c for c in claims}
        
        # Build cluster lookup
        clusters_by_member = self._build_cluster_index(clusters)
        
        # Build results
        results = []
        for claim in claims:
            claim_id = claim["claim_id"]
            contradiction_list = contradictions_by_claim.get(claim_id, [])
            
            result = {
                "claim_id": claim_id,
                "text": claim["claim_text"],
                "source": claim["source_document_id"],
                "extraction_verified": claim["extraction_verified"],
                "contradiction_count": metrics[claim_id]["contradiction_count"],
                "contradicts_with": contradiction_list,
                "cluster_id": clusters_by_member.get(claim_id),
                "relevance": metrics[claim_id]["retrieval_score"],
                "source_count": metrics[claim_id]["source_count"],
            }
            results.append(result)
        
        # Sort by relevance then by contradiction count (highest first)
        results.sort(
            key=lambda r: (-r["relevance"], -r["contradiction_count"])
        )
        
        # Build contradiction edges
        contradiction_edges = []
        for contra in contradictions:
            edge = {
                "from_id": contra["claim_a_id"],
                "to_id": contra["claim_b_id"],
                "relationship": contra["relationship_type"],
                "strength": contra["topology_strength"],
                "from_text": claims_by_id[contra["claim_a_id"]]["claim_text"],
                "to_text": claims_by_id[contra["claim_b_id"]]["claim_text"],
            }
            contradiction_edges.append(edge)
        
        # Build cluster descriptions
        cluster_descriptions = []
        for i, cluster_members in enumerate(clusters):
            description = (
                f"Group {i+1}: {len(cluster_members)} claims "
                f"with contradictions among them"
            )
            cluster_descriptions.append({
                "cluster_id": i,
                "members": cluster_members,
                "description": description,
                "member_count": len(cluster_members),
            })
        
        # Build summary
        claims_with_contradictions = sum(
            1 for r in results if r["contradiction_count"] > 0
        )
        summary = (
            f"Found {len(results)} claims. "
            f"{claims_with_contradictions} have contradictions with others. "
            f"{len(clusters)} contradiction clusters detected."
        )
        
        return {
            "query": packet_dict["metadata"]["query"],
            "summary": summary,
            "results": results,
            "contradictions": contradiction_edges,
            "clusters": cluster_descriptions,
            "statistics": {
                "total_claims": len(results),
                "claims_with_contradictions": claims_with_contradictions,
                "contradiction_edges": len(contradiction_edges),
                "clusters": len(cluster_descriptions),
            }
        }

    def _build_contradiction_index(
        self,
        contradictions: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Build index of contradictions by claim.
        
        Returns:
            {claim_id: [claim_id, claim_id, ...]}
        """
        index = defaultdict(list)
        for contra in contradictions:
            claim_a = contra["claim_a_id"]
            claim_b = contra["claim_b_id"]
            
            # Both directions (bidirectional)
            if claim_b not in index[claim_a]:
                index[claim_a].append(claim_b)
            if claim_a not in index[claim_b]:
                index[claim_b].append(claim_a)
        
        return dict(index)

    def _build_cluster_index(
        self,
        clusters: List[List[str]]
    ) -> Dict[str, int]:
        """
        Build index of cluster membership.
        
        Returns:
            {claim_id: cluster_id}
        """
        index = {}
        for cluster_id, members in enumerate(clusters):
            for member in members:
                index[member] = cluster_id
        return index

    def render_contradiction_graph(
        self,
        packet_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Render contradiction graph structure (for visualization).
        
        Returns:
            {
                "nodes": [{"id": "claim_xxx", "label": "...", "contradictions": N}],
                "edges": [{"source": "claim_xxx", "target": "claim_yyy", "strength": 0.95}],
            }
        """
        claims = packet_dict["claims"]
        contradictions = packet_dict["contradictions"]
        metrics = packet_dict["support_metrics"]
        
        # Build nodes
        nodes = []
        for claim in claims:
            node = {
                "id": claim["claim_id"],
                "label": claim["claim_text"][:100],  # Truncate for display
                "source": claim["source_document_id"],
                "contradictions": metrics[claim["claim_id"]]["contradiction_count"],
                "relevance": metrics[claim["claim_id"]]["retrieval_score"],
            }
            nodes.append(node)
        
        # Build edges
        edges = []
        for contra in contradictions:
            edge = {
                "source": contra["claim_a_id"],
                "target": contra["claim_b_id"],
                "relationship": contra["relationship_type"],
                "strength": contra["topology_strength"],
            }
            edges.append(edge)
        
        return {
            "query": packet_dict["metadata"]["query"],
            "nodes": nodes,
            "edges": edges,
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "nodes_with_contradictions": sum(1 for n in nodes if n["contradictions"] > 0),
                "average_edge_strength": (
                    sum(e["strength"] for e in edges) / len(edges)
                    if edges else 0.0
                ),
            }
        }

    def highlight_high_contradiction_nodes(
        self,
        packet_dict: Dict[str, Any],
        threshold: float = 2.0,  # topology-based, not truth-based
    ) -> Dict[str, Any]:
        """
        Highlight claims that are highly connected in contradiction graph.
        
        Uses topology (contradiction_count + cluster_membership_count),
        NOT truth or credibility.
        
        Args:
            packet_dict: EvidencePacket
            threshold: Minimum topology score to highlight
            
        Returns:
            {
                "high_contradiction_nodes": [
                    {
                        "claim_id": "claim_xxx",
                        "text": "...",
                        "topology_score": 3.5,  # contradiction_count + cluster_count
                        "contradiction_count": 2,
                        "cluster_count": 1,
                    }
                ]
            }
        """
        claims = packet_dict["claims"]
        metrics = packet_dict["support_metrics"]
        
        highlighted = []
        for claim in claims:
            claim_id = claim["claim_id"]
            metric = metrics[claim_id]
            
            # Topology score: pure topology, no truth judgment
            topology_score = (
                metric["contradiction_count"] +
                metric["cluster_membership_count"]
            )
            
            if topology_score >= threshold:
                highlighted.append({
                    "claim_id": claim_id,
                    "text": claim["claim_text"],
                    "topology_score": topology_score,
                    "contradiction_count": metric["contradiction_count"],
                    "cluster_count": metric["cluster_membership_count"],
                })
        
        # Sort by topology score descending
        highlighted.sort(key=lambda x: -x["topology_score"])
        
        return {
            "query": packet_dict["metadata"]["query"],
            "high_contradiction_nodes": highlighted,
            "threshold": threshold,
            "count": len(highlighted),
        }


# Export
__all__ = ["SearchAdapter"]
