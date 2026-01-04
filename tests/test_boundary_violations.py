"""
Boundary Violation Tests for Phase 6 (D2 Navigator + D3 Coherence)

Tests that the SSE system properly enforces read-only boundaries:
- D2 (Navigator): Forbidden write operations on claims and contradictions
- D3 (Coherence): Forbidden modification operations on coherence data
- Consistency: Boundaries enforced consistently across all operations
- Integrity: No partial modifications when boundary violations occur
"""

import pytest
import json
import numpy as np
import tempfile
import shutil
import os
from sse.interaction_layer import SSENavigator, SSEBoundaryViolation
from sse.coherence import CoherenceTracker, CoherenceBoundaryViolation


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_test_index():
    """Create a temporary test index with proper file structure."""
    tmpdir = tempfile.mkdtemp()
    
    # Create index data
    index_data = {
        "doc_id": "test.txt",
        "timestamp": "2026-01-01T00:00:00Z",
        "chunks": [
            {
                "chunk_id": "chunk0",
                "text": "Sleep can be helpful",
                "start_char": 0,
                "end_char": 20,
                "char_count": 20
            },
            {
                "chunk_id": "chunk1",
                "text": "Sleep is harmful",
                "start_char": 20,
                "end_char": 40,
                "char_count": 20
            }
        ],
        "claims": [
            {
                "claim_id": "clm0",
                "claim_text": "Sleep is beneficial",
                "chunk_id": "chunk0",
                "start_char": 0,
                "end_char": 20,
                "supporting_quotes": [
                    {
                        "quote_text": "Sleep can be helpful",
                        "chunk_id": "chunk0",
                        "start_char": 0,
                        "end_char": 20,
                        "char_count": 20,
                        "valid": True
                    }
                ],
                "ambiguity": {"hedge_score": 0.2}
            },
            {
                "claim_id": "clm1",
                "claim_text": "Sleep is detrimental",
                "chunk_id": "chunk1",
                "start_char": 20,
                "end_char": 40,
                "supporting_quotes": [
                    {
                        "quote_text": "Sleep is harmful",
                        "chunk_id": "chunk1",
                        "start_char": 20,
                        "end_char": 40,
                        "char_count": 20,
                        "valid": True
                    }
                ],
                "ambiguity": {"hedge_score": 0.1}
            }
        ],
        "clusters": [
            {"cluster_id": "cl0", "claims": ["clm0", "clm1"]}
        ],
        "contradictions": [
            {
                "claim_a": "clm0",
                "claim_b": "clm1",
                "relationship": "contradicts",
                "confidence": 0.95
            }
        ],
        "embeddings_index": "embeddings.npy"
    }
    
    # Write index to file
    index_path = os.path.join(tmpdir, "index.json")
    with open(index_path, "w") as f:
        json.dump(index_data, f)
    
    # Create embeddings file
    embeddings = np.random.randn(2, 384).astype("float32")
    np.save(os.path.join(tmpdir, "embeddings.npy"), embeddings)
    
    yield index_path
    
    # Cleanup
    shutil.rmtree(tmpdir)


@pytest.fixture
def index_dict():
    """Create in-memory index dict for CoherenceTracker (doesn't need files)."""
    return {
        "doc_id": "test.txt",
        "timestamp": "2026-01-01T00:00:00Z",
        "chunks": [
            {
                "chunk_id": "chunk0",
                "text": "Sleep can be helpful",
                "start_char": 0,
                "end_char": 20,
                "char_count": 20
            },
            {
                "chunk_id": "chunk1",
                "text": "Sleep is harmful",
                "start_char": 20,
                "end_char": 40,
                "char_count": 20
            }
        ],
        "claims": [
            {
                "claim_id": "clm0",
                "claim_text": "Sleep is beneficial",
                "chunk_id": "chunk0",
                "start_char": 0,
                "end_char": 20,
                "supporting_quotes": [
                    {
                        "quote_text": "Sleep can be helpful",
                        "chunk_id": "chunk0",
                        "start_char": 0,
                        "end_char": 20,
                        "char_count": 20,
                        "valid": True
                    }
                ],
                "ambiguity": {"hedge_score": 0.2}
            },
            {
                "claim_id": "clm1",
                "claim_text": "Sleep is detrimental",
                "chunk_id": "chunk1",
                "start_char": 20,
                "end_char": 40,
                "supporting_quotes": [
                    {
                        "quote_text": "Sleep is harmful",
                        "chunk_id": "chunk1",
                        "start_char": 20,
                        "end_char": 40,
                        "char_count": 20,
                        "valid": True
                    }
                ],
                "ambiguity": {"hedge_score": 0.1}
            }
        ],
        "clusters": [
            {"cluster_id": "cl0", "claims": ["clm0", "clm1"]}
        ],
        "contradictions": [
            {
                "claim_a": "clm0",
                "claim_b": "clm1",
                "relationship": "contradicts",
                "confidence": 0.95
            }
        ],
        "embeddings_index": "embeddings.npy"
    }


# ============================================================================
# D2 NAVIGATOR BOUNDARY VIOLATIONS
# ============================================================================

class TestNavigatorBoundaryViolations:
    """Test D2 (Navigator) boundary violations - forbidden write operations."""

    def test_navigator_cannot_modify_claims(self, temp_test_index):
        """Navigator should not allow direct claim modification."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.modify_claim("clm0", {"claim_text": "Modified claim"})

    def test_navigator_cannot_delete_claims(self, temp_test_index):
        """Navigator should not allow claim deletion."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.delete_claim("clm0")

    def test_navigator_cannot_add_claims(self, temp_test_index):
        """Navigator should not allow adding new claims."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.add_claim({"claim_id": "clm99", "claim_text": "New claim"})

    def test_navigator_cannot_modify_contradictions(self, temp_test_index):
        """Navigator should not allow contradiction modification."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.modify_contradiction("clm0", "clm1", {"confidence": 0.5})

    def test_navigator_cannot_delete_contradictions(self, temp_test_index):
        """Navigator should not allow contradiction deletion."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.delete_contradiction("clm0", "clm1")

    def test_navigator_cannot_add_contradictions(self, temp_test_index):
        """Navigator should not allow adding new contradictions."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.add_contradiction({
                "claim_a": "clm0",
                "claim_b": "clm1",
                "relationship": "conflicts"
            })

    def test_navigator_cannot_filter_contradictions(self, temp_test_index):
        """Navigator should not allow filtering contradictions from results."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.query_without_contradictions("sleep")

    def test_navigator_cannot_filter_unconfident_claims(self, temp_test_index):
        """Navigator should not allow filtering uncertain claims."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.filter_high_confidence_only(min_confidence=0.9)

    def test_navigator_cannot_filter_ambiguous_claims(self, temp_test_index):
        """Navigator should not allow filtering claims with ambiguity."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.filter_unambiguous_claims()

    def test_navigator_cannot_resolve_contradictions(self, temp_test_index):
        """Navigator should not allow resolving contradictions."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.resolve_contradiction("clm0", "clm1", winner="clm0")

    def test_navigator_cannot_synthesize_view(self, temp_test_index):
        """Navigator should not allow synthesizing a unified view."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.synthesize_unified_view()

    def test_navigator_cannot_pick_preferred_claims(self, temp_test_index):
        """Navigator should not allow picking preferred claims."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.pick_preferred_claims(["clm0"])

    def test_navigator_cannot_reorder_claims(self, temp_test_index):
        """Navigator should not allow reordering claims."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.reorder_claims(["clm1", "clm0"])

    def test_navigator_cannot_suppress_claims(self, temp_test_index):
        """Navigator should not allow suppressing claims."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.suppress_claim("clm0")

    def test_navigator_cannot_weight_claims(self, temp_test_index):
        """Navigator should not allow weighting claims differently."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.set_claim_weight("clm0", 0.5)

    def test_navigator_cannot_merge_claims(self, temp_test_index):
        """Navigator should not allow merging claims."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.merge_claims("clm0", "clm1", "merged")

    def test_navigator_cannot_split_claims(self, temp_test_index):
        """Navigator should not allow splitting claims."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.split_claim("clm0", ["part1", "part2"])

    def test_navigator_cannot_change_relationship_type(self, temp_test_index):
        """Navigator should not allow changing relationship types."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.change_relationship_type("clm0", "clm1", "qualifies")

    def test_navigator_modification_exception_has_message(self, temp_test_index):
        """Boundary violation exception should have clear message."""
        nav = SSENavigator(temp_test_index)
        
        try:
            nav.modify_claim("clm0", {})
        except SSEBoundaryViolation as e:
            msg = str(e).lower()
            assert "modify" in msg or "forbidden" in msg


# ============================================================================
# D3 COHERENCE BOUNDARY VIOLATIONS
# ============================================================================

class TestCoherenceBoundaryViolations:
    """Test D3 (Coherence) boundary violations - forbidden write operations."""

    def test_coherence_cannot_modify_edges(self, index_dict):
        """CoherenceTracker should not allow modifying edges."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.modify_edge("clm0", "clm1", confidence=0.5)

    def test_coherence_cannot_delete_edges(self, index_dict):
        """CoherenceTracker should not allow deleting edges."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.delete_edge("clm0", "clm1")

    def test_coherence_cannot_filter_disagreements(self, index_dict):
        """CoherenceTracker should not allow filtering disagreements."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.filter_high_confidence_edges(min_confidence=0.9)

    def test_coherence_cannot_hide_clusters(self, index_dict):
        """CoherenceTracker should not allow hiding clusters."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.hide_disagreement_clusters()

    def test_coherence_cannot_suppress_relationships(self, index_dict):
        """CoherenceTracker should not allow suppressing relationships."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.suppress_relationship("clm0", "clm1")

    def test_coherence_cannot_mark_disagreements_resolved(self, index_dict):
        """CoherenceTracker should not allow marking disagreements as resolved."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.mark_disagreement_resolved("clm0", "clm1")

    def test_coherence_cannot_pick_winning_claim(self, index_dict):
        """CoherenceTracker should not allow picking a winning claim."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.pick_winning_claim("clm0", "clm1")

    def test_coherence_cannot_weight_claims(self, index_dict):
        """CoherenceTracker should not allow weighting claims differently."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.weight_claim("clm0", 0.8)

    def test_coherence_cannot_suppress_claim(self, index_dict):
        """CoherenceTracker should not allow suppressing claims."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.suppress_claim("clm0")

    def test_coherence_cannot_resolve_disagreement(self, index_dict):
        """CoherenceTracker should not allow resolving disagreements."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.resolve_disagreement("clm0", "clm1")

    def test_coherence_cannot_pick_subset_of_claims(self, index_dict):
        """CoherenceTracker should not allow picking subset of claims."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.pick_subset_of_claims(["clm0"])

    def test_coherence_cannot_synthesize_unified_view(self, index_dict):
        """CoherenceTracker should not allow synthesizing unified view."""
        tracker = CoherenceTracker(index_dict)
        
        with pytest.raises(CoherenceBoundaryViolation):
            tracker.synthesize_unified_view()

    def test_coherence_violation_exception_has_message(self, index_dict):
        """Boundary violation exception should have clear message."""
        tracker = CoherenceTracker(index_dict)
        
        try:
            tracker.modify_edge("clm0", "clm1", confidence=0.5)
        except CoherenceBoundaryViolation as e:
            msg = str(e).lower()
            assert "modify" in msg or "forbidden" in msg


# ============================================================================
# OBSERVATION VS MODIFICATION
# ============================================================================

class TestObservationVsModification:
    """Test that observation (reads) are allowed while modification (writes) are forbidden."""

    def test_claim_retrieval_allowed(self, temp_test_index):
        """Claim retrieval should not raise exceptions."""
        nav = SSENavigator(temp_test_index)
        claim = nav.get_claim_by_id("clm0")
        assert claim is not None

    def test_query_allowed(self, temp_test_index):
        """Querying should not raise exceptions."""
        nav = SSENavigator(temp_test_index)
        results = nav.query("sleep", k=5)
        assert isinstance(results, list)

    def test_coherence_observation_allowed(self, temp_test_index):
        """Coherence observation should not raise exceptions."""
        nav = SSENavigator(temp_test_index)
        
        coh = nav.get_claim_coherence("clm0")
        assert coh is not None
        
        edges = nav.get_disagreement_edges()
        assert isinstance(edges, list)

    def test_all_read_operations_allowed(self, temp_test_index):
        """All read operations should succeed without exceptions."""
        nav = SSENavigator(temp_test_index)
        
        # These should all work (reads, no exceptions)
        read_ops = [
            nav.get_claim_by_id("clm0"),
            nav.query("test"),
            nav.get_contradictions(),
            nav.get_provenance("clm0"),
            nav.get_uncertain_claims(),
            nav.get_cluster("cl0"),
            nav.get_claim_coherence("clm0"),
            nav.get_disagreement_edges(),
            nav.get_related_claims("clm0"),
            nav.get_disagreement_clusters(),
            nav.get_coherence_report(),
            nav.info(),
        ]
        
        for result in read_ops:
            assert result is not None or result == []


# ============================================================================
# INTEGRITY AND ATOMICITY
# ============================================================================

class TestIntegrityAndAtomicity:
    """Test that modifications don't partially succeed when boundary is violated."""

    def test_integrity_maintained_after_failed_modification(self, temp_test_index):
        """Index should remain unchanged after failed modification attempt."""
        nav = SSENavigator(temp_test_index)
        original_claims = [c["claim_id"] for c in nav.claims]
        
        try:
            nav.modify_claim("clm0", {"claim_text": "Modified"})
        except SSEBoundaryViolation:
            pass  # Expected
        
        current_claims = [c["claim_id"] for c in nav.claims]
        assert original_claims == current_claims, "Claims were modified despite boundary violation"

    def test_multiple_consecutive_violations(self, temp_test_index):
        """Multiple boundary violation attempts should all fail."""
        nav = SSENavigator(temp_test_index)
        
        for i in range(3):
            with pytest.raises(SSEBoundaryViolation):
                nav.modify_claim(f"clm{i % 2}", {})


# ============================================================================
# EXCEPTION HIERARCHY AND MESSAGING
# ============================================================================

class TestBoundaryExceptionHierarchy:
    """Test exception hierarchy and messaging for boundary violations."""

    def test_sse_boundary_violation_is_exception(self):
        """SSEBoundaryViolation should inherit from Exception."""
        assert issubclass(SSEBoundaryViolation, Exception)

    def test_coherence_boundary_violation_is_exception(self):
        """CoherenceBoundaryViolation should inherit from Exception."""
        assert issubclass(CoherenceBoundaryViolation, Exception)

    def test_sse_boundary_violation_has_message(self):
        """SSEBoundaryViolation should preserve message."""
        exc = SSEBoundaryViolation("test_operation", "Test message")
        assert "Test message" in str(exc)

    def test_coherence_boundary_violation_has_message(self):
        """CoherenceBoundaryViolation should preserve message."""
        exc = CoherenceBoundaryViolation("test_operation", "Test message")
        assert "Test message" in str(exc)

    def test_navigator_exceptions_are_actionable(self, temp_test_index):
        """Navigator exceptions should explain what's forbidden."""
        nav = SSENavigator(temp_test_index)
        
        try:
            nav.modify_claim("clm0", {})
        except SSEBoundaryViolation as e:
            msg = str(e).lower()
            # Should mention the operation and that it's forbidden
            assert any(word in msg for word in ["modify", "claim", "forbidden", "boundary"])

    def test_coherence_exceptions_are_actionable(self, index_dict):
        """Coherence exceptions should explain what's forbidden."""
        tracker = CoherenceTracker(index_dict)
        
        try:
            tracker.modify_edge("clm0", "clm1", confidence=0.5)
        except CoherenceBoundaryViolation as e:
            msg = str(e).lower()
            # Should mention the operation and that it's forbidden
            assert any(word in msg for word in ["modify", "edge", "forbidden", "boundary"])


# ============================================================================
# EDGE CASES
# ============================================================================

class TestBoundaryViolationEdgeCases:
    """Test edge cases and error conditions."""

    def test_modification_with_none_arguments(self, temp_test_index):
        """Modification with None should still be forbidden."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.modify_claim("clm0", None)

    def test_modification_with_empty_dict(self, temp_test_index):
        """Modification with empty dict should still be forbidden."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.modify_claim("clm0", {})

    def test_modification_nonexistent_claim(self, temp_test_index):
        """Modification of nonexistent claim should raise boundary violation."""
        nav = SSENavigator(temp_test_index)
        
        with pytest.raises(SSEBoundaryViolation):
            nav.modify_claim("nonexistent", {"claim_text": "Modified"})

    def test_violation_after_successful_read(self, temp_test_index):
        """Boundary should still be enforced after successful read."""
        nav = SSENavigator(temp_test_index)
        
        # This should work (read)
        claim = nav.get_claim_by_id("clm0")
        assert claim is not None
        
        # This should fail (write)
        with pytest.raises(SSEBoundaryViolation):
            nav.modify_claim("clm0", {})

    def test_consistency_across_instances(self, temp_test_index):
        """Same operation should be forbidden on different instances."""
        for i in range(3):
            nav = SSENavigator(temp_test_index)
            with pytest.raises(SSEBoundaryViolation):
                nav.modify_claim("clm0", {})

    def test_allowed_operations_always_succeed(self, temp_test_index):
        """Same allowed operation should always succeed."""
        nav = SSENavigator(temp_test_index)
        
        # Multiple calls of same allowed operation
        for i in range(5):
            claim = nav.get_claim_by_id("clm0")
            assert claim is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
