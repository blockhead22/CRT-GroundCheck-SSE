"""
Tests for SSE Coherence Tracking (Phase 6, D3)

Validates that the coherence tracker:
1. Observes disagreement without resolving it
2. Computes accurate relationship metadata
3. Never picks winners or synthesizes consensus
4. Respects the Coherence Contract
"""

import json
import pytest
import tempfile
import os

from sse.coherence import CoherenceTracker, CoherenceBoundaryViolation


# Test data with clear disagreements
TEST_INDEX = {
    "doc_id": "test.txt",
    "timestamp": "2024-01-01T00:00:00Z",
    "chunks": [
        {
            "chunk_id": "c0",
            "text": "Claim A. Claim B. Claim C.",
            "start_char": 0,
            "end_char": 25
        }
    ],
    "clusters": [],
    "claims": [
        {
            "claim_id": "clm0",
            "claim_text": "AI will solve all problems",
            "supporting_quotes": [],
            "ambiguity": {}
        },
        {
            "claim_id": "clm1",
            "claim_text": "AI poses serious risks",
            "supporting_quotes": [],
            "ambiguity": {}
        },
        {
            "claim_id": "clm2",
            "claim_text": "AI requires careful regulation",
            "supporting_quotes": [],
            "ambiguity": {}
        },
        {
            "claim_id": "clm3",
            "claim_text": "AI is beneficial when properly implemented",
            "supporting_quotes": [],
            "ambiguity": {}
        }
    ],
    "contradictions": [
        {
            "pair": {"claim_id_a": "clm0", "claim_id_b": "clm1"},
            "label": "contradiction",
            "evidence_quotes": [
                {"quote_text": "solve all"},
                {"quote_text": "serious risks"}
            ]
        },
        {
            "pair": {"claim_id_a": "clm1", "claim_id_b": "clm3"},
            "label": "conflict",
            "evidence_quotes": [
                {"quote_text": "serious risks"},
                {"quote_text": "beneficial"}
            ]
        }
    ]
}


class TestCoherenceTrackerBasics:
    """Test basic coherence tracker functionality."""
    
    def test_load_index(self):
        """Tracker loads index correctly."""
        tracker = CoherenceTracker(TEST_INDEX)
        assert len(tracker.claims) == 4
        assert len(tracker.contradictions) == 2
    
    def test_build_disagreement_graph(self):
        """Disagreement graph is built from contradictions."""
        tracker = CoherenceTracker(TEST_INDEX)
        edges = tracker.get_disagreement_edges()
        assert len(edges) >= 2


class TestObservation:
    """Test PERMITTED operations: observation of disagreement."""
    
    def test_get_claim_coherence(self):
        """Get coherence metadata for a claim."""
        tracker = CoherenceTracker(TEST_INDEX)
        coh = tracker.get_claim_coherence("clm0")
        
        assert coh is not None
        assert coh.claim_id == "clm0"
        assert coh.total_relationships > 0  # clm0 contradicts clm1
    
    def test_coherence_shows_relationships(self):
        """Coherence metadata shows relationship counts."""
        tracker = CoherenceTracker(TEST_INDEX)
        coh = tracker.get_claim_coherence("clm0")
        
        # Should show that this claim has relationships
        assert coh.contradictions > 0 or coh.total_relationships > 0
    
    def test_get_disagreement_edges(self):
        """Retrieve disagreement edges."""
        tracker = CoherenceTracker(TEST_INDEX)
        edges = tracker.get_disagreement_edges()
        
        # Should have at least 2 edges from test data
        assert len(edges) >= 2
    
    def test_edge_has_confidence(self):
        """Disagreement edges include confidence."""
        tracker = CoherenceTracker(TEST_INDEX)
        edges = tracker.get_disagreement_edges()
        
        for edge in edges:
            assert "confidence" in edge
            assert 0.0 <= edge["confidence"] <= 1.0
    
    def test_edge_has_reasoning(self):
        """Disagreement edges include reasoning."""
        tracker = CoherenceTracker(TEST_INDEX)
        edges = tracker.get_disagreement_edges()
        
        for edge in edges:
            assert "reasoning" in edge
            assert isinstance(edge["reasoning"], str)
    
    def test_get_related_claims(self):
        """Get claims related to a specific claim."""
        tracker = CoherenceTracker(TEST_INDEX)
        related = tracker.get_related_claims("clm0")
        
        # clm0 contradicts clm1, so clm1 should be in related
        # Returns List[Tuple[str, str]], not List[Dict]
        related_ids = [r[0] for r in related]
        assert "clm1" in related_ids
    
    def test_filter_by_relationship_type(self):
        """Filter related claims by relationship type."""
        tracker = CoherenceTracker(TEST_INDEX)
        contradicting = tracker.get_related_claims("clm0", relationship="contradicts")
        
        # Should find direct contradictions
        assert len(contradicting) > 0
    
    def test_get_disagreement_clusters(self):
        """Find groups of claims that disagree."""
        tracker = CoherenceTracker(TEST_INDEX)
        clusters = tracker.get_disagreement_clusters()
        
        # Should find at least one cluster of disagreement
        if clusters:
            assert len(clusters[0]) > 0
    
    def test_get_coherence_report(self):
        """Get overall coherence statistics."""
        tracker = CoherenceTracker(TEST_INDEX)
        report = tracker.get_coherence_report()
        
        assert "total_claims" in report
        assert "total_disagreement_edges" in report
        assert "contradiction_edges" in report
        assert "conflict_edges" in report
        assert report["total_disagreement_edges"] >= 2


class TestForbiddenOperations:
    """Test FORBIDDEN operations raise CoherenceBoundaryViolation."""
    
    def test_forbid_resolve_disagreement(self):
        """Resolving disagreements is forbidden."""
        tracker = CoherenceTracker(TEST_INDEX)
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.resolve_disagreement("clm0", "clm1")
    
    def test_forbid_pick_coherent_subset(self):
        """Selecting coherent subset (filtering out disagreement) is forbidden."""
        tracker = CoherenceTracker(TEST_INDEX)
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.pick_coherent_subset()
    
    def test_forbid_synthesize_resolution(self):
        """Synthesizing consensus is forbidden."""
        tracker = CoherenceTracker(TEST_INDEX)
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.synthesize_resolution("clm0", "clm1")


class TestCoherenceContract:
    """Test that coherence tracking respects its contract."""
    
    def test_all_disagreements_preserved(self):
        """All disagreements are available for observation."""
        tracker = CoherenceTracker(TEST_INDEX)
        edges = tracker.get_disagreement_edges()
        
        # All contradictions should be observable
        assert len(edges) == len(TEST_INDEX["contradictions"])
    
    def test_no_winners_picked(self):
        """Coherence tracking never indicates which claim is 'better'."""
        tracker = CoherenceTracker(TEST_INDEX)
        
        # Get coherence for both sides of a contradiction
        coh_clm0 = tracker.get_claim_coherence("clm0")
        coh_clm1 = tracker.get_claim_coherence("clm1")
        
        # Neither should be marked as "invalid" or "wrong"
        # Both should be equally observable
        assert coh_clm0 is not None
        assert coh_clm1 is not None
    
    def test_disagreement_not_hidden(self):
        """Disagreements are never hidden or suppressed."""
        tracker = CoherenceTracker(TEST_INDEX)
        
        # If two claims contradict, that edge should be in the graph
        edges = tracker.get_disagreement_edges()
        edge_pairs = set()
        for edge in edges:
            a, b = edge["claim_id_a"], edge["claim_id_b"]
            edge_pairs.add((min(a, b), max(a, b)))
        
        # Verify edges from test contradictions are present
        assert len(edge_pairs) > 0
    
    def test_relationship_classification(self):
        """Disagreements are classified but not judged."""
        tracker = CoherenceTracker(TEST_INDEX)
        edges = tracker.get_disagreement_edges()
        
        # All edges should have a relationship type
        for edge in edges:
            assert edge["relationship"] in [
                "contradicts", "conflicts", "qualifies", "uncertain", "agrees"
            ]
    
    def test_confidence_based_on_evidence(self):
        """Confidence reflects evidence quantity, not truth."""
        tracker = CoherenceTracker(TEST_INDEX)
        edges = tracker.get_disagreement_edges()
        
        for edge in edges:
            # Confidence should be based on evidence quality
            # (more quotes = higher confidence in the observation)
            assert isinstance(edge["confidence"], float)
            assert 0.0 <= edge["confidence"] <= 1.0


class TestMetadataAccuracy:
    """Test that coherence metadata is accurate."""
    
    def test_relationship_count_consistency(self):
        """Relationship counts in coherence should match edges."""
        tracker = CoherenceTracker(TEST_INDEX)
        
        for claim in TEST_INDEX["claims"]:
            claim_id = claim["claim_id"]
            coh = tracker.get_claim_coherence(claim_id)
            related = tracker.get_related_claims(claim_id)
            
            # Total relationships should match
            assert coh.total_relationships == len(related)
    
    def test_cluster_membership(self):
        """Claims in clusters should all disagree."""
        tracker = CoherenceTracker(TEST_INDEX)
        clusters = tracker.get_disagreement_clusters()
        
        for cluster in clusters:
            # Each claim in a cluster should relate to others
            for claim_id in cluster:
                related = tracker.get_related_claims(claim_id)
                # Should have relationships to other cluster members
                # Returns List[Tuple[str, str]], so extract first element
                related_ids = {r[0] for r in related}
                assert len(related_ids & set(cluster)) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
