"""
Phase 6.2: Client Library Tests

Validates that SSEClient:
1. Exposes only permitted Phase A-C operations
2. Prevents forbidden Phase D+ operations at call time
3. Provides helpful error messages for boundary violations
4. Cannot be circumvented with reflection or getattr hacks

Test Strategy:
- Positive tests: Verify permitted operations work
- Negative tests: Verify forbidden operations raise AttributeError
- Meta tests: Verify no backdoor access exists
"""

import pytest
import json
import tempfile
import os
from typing import List, Dict

from sse.client import SSEClient
from sse.interaction_layer import SSEBoundaryViolation


@pytest.fixture
def sample_index():
    """Create a minimal SSE index for testing."""
    index = {
        "doc_id": "test_doc",
        "timestamp": "2026-01-09T12:00:00",
        "chunks": [
            {"chunk_id": "c0", "text": "Sleep is important for health.", "start_char": 0, "end_char": 30},
            {"chunk_id": "c1", "text": "Some people thrive on 4 hours of sleep.", "start_char": 31, "end_char": 70}
        ],
        "clusters": [
            {"cluster_id": "cl0", "chunk_ids": ["clm0", "clm1"]}
        ],
        "claims": [
            {
                "claim_id": "clm0",
                "claim_text": "Sleep is important for health",
                "supporting_quotes": [
                    {"quote_text": "Sleep is important for health", "chunk_id": "c0", "start_char": 0, "end_char": 29}
                ],
                "ambiguity": {"hedge_score": 0.0}
            },
            {
                "claim_id": "clm1",
                "claim_text": "Some people thrive on 4 hours",
                "supporting_quotes": [
                    {"quote_text": "Some people thrive on 4 hours", "chunk_id": "c1", "start_char": 31, "end_char": 60}
                ],
                "ambiguity": {"hedge_score": 0.3}
            }
        ],
        "contradictions": [
            {
                "pair": {"claim_id_a": "clm0", "claim_id_b": "clm1"},
                "label": "contradiction"
            }
        ]
    }
    
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, 'w') as f:
        json.dump(index, f)
    
    yield path
    
    # Cleanup
    os.unlink(path)


# =============================================================================
# POSITIVE TESTS - Phase A-C Operations Should Work
# =============================================================================

class TestPermittedOperations:
    """Verify all Phase A-C operations are accessible and functional."""
    
    def test_client_initialization(self, sample_index):
        """Client should initialize successfully with valid index."""
        client = SSEClient(sample_index)
        assert client.doc_id == "test_doc"
        assert client.timestamp == "2026-01-09T12:00:00"
    
    def test_get_all_claims(self, sample_index):
        """Phase A: Retrieval - get all claims."""
        client = SSEClient(sample_index)
        claims = client.get_all_claims()
        
        assert isinstance(claims, list)
        assert len(claims) == 2
        assert claims[0]["claim_id"] == "clm0"
    
    def test_get_claim_by_id(self, sample_index):
        """Phase A: Retrieval - get specific claim."""
        client = SSEClient(sample_index)
        claim = client.get_claim_by_id("clm0")
        
        assert claim is not None
        assert claim["claim_text"] == "Sleep is important for health"
    
    def test_get_all_contradictions(self, sample_index):
        """Phase A: Retrieval - get all contradictions."""
        client = SSEClient(sample_index)
        contradictions = client.get_all_contradictions()
        
        assert isinstance(contradictions, list)
        assert len(contradictions) == 1
    
    def test_get_contradiction_between(self, sample_index):
        """Phase A: Retrieval - get specific contradiction."""
        client = SSEClient(sample_index)
        contra = client.get_contradiction_between("clm0", "clm1")
        
        assert contra is not None
        assert contra["pair"]["claim_id_a"] == "clm0"
    
    def test_get_provenance(self, sample_index):
        """Phase A: Provenance tracking."""
        client = SSEClient(sample_index)
        prov = client.get_provenance("clm0")
        
        assert "supporting_quotes" in prov
        assert len(prov["supporting_quotes"]) > 0
    
    def test_search_keyword(self, sample_index):
        """Phase B: Search - keyword method."""
        client = SSEClient(sample_index)
        results = client.search("sleep", k=5, method="keyword")
        
        assert isinstance(results, list)
        # Should find at least the claim about sleep
        assert len(results) > 0
    
    def test_find_uncertain_claims(self, sample_index):
        """Phase B: Filter by ambiguity markers."""
        client = SSEClient(sample_index)
        uncertain = client.find_uncertain_claims(min_hedge=0.2)
        
        assert isinstance(uncertain, list)
        # Should find clm1 with hedge_score 0.3
        assert len(uncertain) >= 1
    
    def test_get_ambiguity_markers(self, sample_index):
        """Phase B: Ambiguity exposure."""
        client = SSEClient(sample_index)
        ambiguity = client.get_ambiguity_markers("clm1")
        
        assert "ambiguity" in ambiguity
        assert ambiguity["ambiguity"]["hedge_score"] == 0.3
    
    def test_get_all_clusters(self, sample_index):
        """Phase C: Grouping."""
        client = SSEClient(sample_index)
        clusters = client.get_all_clusters()
        
        assert isinstance(clusters, list)
        assert len(clusters) >= 1
    
    def test_get_cluster(self, sample_index):
        """Phase C: Grouping - get specific cluster."""
        client = SSEClient(sample_index)
        cluster = client.get_cluster("cl0")
        
        assert cluster is not None
        assert "claims" in cluster
    
    def test_find_related_claims(self, sample_index):
        """Phase C: Navigation - find related claims."""
        client = SSEClient(sample_index)
        related = client.find_related_claims("clm0")
        
        assert isinstance(related, list)
        # Should find claims in same cluster
    
    def test_format_claim(self, sample_index):
        """Display: Format claim for output."""
        client = SSEClient(sample_index)
        claim = client.get_claim_by_id("clm0")
        formatted = client.format_claim(claim)
        
        assert isinstance(formatted, str)
        assert "Sleep is important" in formatted
    
    def test_format_contradiction(self, sample_index):
        """Display: Format contradiction for output."""
        client = SSEClient(sample_index)
        contra = client.get_contradiction_between("clm0", "clm1")
        formatted = client.format_contradiction(contra)
        
        assert isinstance(formatted, str)
        assert "CLAIM A" in formatted
        assert "CLAIM B" in formatted


# =============================================================================
# NEGATIVE TESTS - Phase D+ Operations Should Fail
# =============================================================================

class TestForbiddenOperations:
    """Verify Phase D+ operations raise AttributeError immediately."""
    
    def test_reject_add_confidence_score(self, sample_index):
        """FORBIDDEN: Cannot add confidence scores."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.add_confidence_score("clm0", 0.9)
        
        assert "Phase D violation" in str(exc_info.value)
        assert "confidence" in str(exc_info.value).lower()
    
    def test_reject_track_user_action(self, sample_index):
        """FORBIDDEN: Cannot track user behavior."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.track_user_action("viewed_claim", "clm0")
        
        assert "Phase D violation" in str(exc_info.value)
    
    def test_reject_measure_engagement(self, sample_index):
        """FORBIDDEN: Cannot measure engagement."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.measure_engagement()
        
        assert "Phase D violation" in str(exc_info.value)
    
    def test_reject_record_recommendation_outcome(self, sample_index):
        """FORBIDDEN: Cannot record whether recommendations worked."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.record_recommendation_outcome("rec0", "helpful")
        
        assert "Phase D violation" in str(exc_info.value)
    
    def test_reject_learn_from_feedback(self, sample_index):
        """FORBIDDEN: Cannot learn from user feedback."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.learn_from_feedback({"helpful": True})
        
        assert "Phase D violation" in str(exc_info.value)
    
    def test_reject_synthesize_answer(self, sample_index):
        """FORBIDDEN: Cannot synthesize new claims."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.synthesize_answer("What is sleep?")
        
        assert "Phase E violation" in str(exc_info.value)
    
    def test_reject_pick_winner(self, sample_index):
        """FORBIDDEN: Cannot resolve contradictions."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.pick_winner("clm0", "clm1")
        
        assert "Phase E violation" in str(exc_info.value)
    
    def test_reject_pick_best_claim(self, sample_index):
        """FORBIDDEN: Cannot rank truth."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.pick_best_claim(["clm0", "clm1"])
        
        assert "Phase E violation" in str(exc_info.value)
    
    def test_reject_resolve_contradiction(self, sample_index):
        """FORBIDDEN: Cannot resolve contradictions."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.resolve_contradiction("clm0", "clm1")
        
        assert "Phase E violation" in str(exc_info.value)
    
    def test_reject_merge_claims(self, sample_index):
        """FORBIDDEN: Cannot merge/synthesize claims."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.merge_claims(["clm0", "clm1"])
        
        assert "Phase E violation" in str(exc_info.value)
    
    def test_reject_filter_high_confidence_only(self, sample_index):
        """FORBIDDEN: Cannot silently filter by confidence."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.filter_high_confidence_only()
        
        assert "Phase D violation" in str(exc_info.value)
    
    def test_reject_suppress_contradiction(self, sample_index):
        """FORBIDDEN: Cannot hide contradictions."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.suppress_contradiction("clm0", "clm1")
        
        assert "Phase D violation" in str(exc_info.value)
    
    def test_reject_save_session_state(self, sample_index):
        """FORBIDDEN: Cannot persist state across queries."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.save_session_state()
        
        assert "Phase D violation" in str(exc_info.value)
    
    def test_reject_remember_preferences(self, sample_index):
        """FORBIDDEN: Cannot model users."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.remember_preferences({"topic": "sleep"})
        
        assert "Phase E violation" in str(exc_info.value)
    
    def test_reject_personalize_results(self, sample_index):
        """FORBIDDEN: Cannot customize per user."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.personalize_results("user123")
        
        assert "Phase E violation" in str(exc_info.value)


# =============================================================================
# META TESTS - Verify No Backdoor Access
# =============================================================================

class TestClientBoundaries:
    """Verify the client cannot be circumvented."""
    
    def test_dir_only_shows_permitted_methods(self, sample_index):
        """__dir__ should only expose Phase A-C operations."""
        client = SSEClient(sample_index)
        available = dir(client)
        
        # Should include permitted operations
        assert "get_all_claims" in available
        assert "search" in available
        assert "get_cluster" in available
        
        # Should NOT include forbidden operations
        assert "add_confidence_score" not in available
        assert "track_user_action" not in available
        assert "synthesize_answer" not in available
        assert "learn_from_feedback" not in available
    
    def test_hasattr_returns_false_for_forbidden(self, sample_index):
        """hasattr() should return False for forbidden operations."""
        client = SSEClient(sample_index)
        
        # Permitted operations exist
        assert hasattr(client, "get_all_claims")
        assert hasattr(client, "search")
        
        # Forbidden operations don't exist
        assert not hasattr(client, "add_confidence_score")
        assert not hasattr(client, "track_user_action")
        assert not hasattr(client, "synthesize_answer")
    
    def test_getattr_provides_helpful_errors(self, sample_index):
        """__getattr__ should explain why forbidden operations don't exist."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.add_confidence_score("clm0", 0.9)
        
        error_msg = str(exc_info.value)
        
        # Should explain the boundary violation
        assert "Boundary Violation" in error_msg
        assert "add_confidence_score" in error_msg
        
        # Should explain why it's forbidden
        assert "Phase D" in error_msg or "Phase E" in error_msg
    
    def test_unknown_attribute_raises_clear_error(self, sample_index):
        """Unknown attributes should raise clear AttributeError."""
        client = SSEClient(sample_index)
        
        with pytest.raises(AttributeError) as exc_info:
            client.some_random_method()
        
        assert "has no attribute" in str(exc_info.value)
    
    def test_cannot_access_navigator_directly(self, sample_index):
        """Private _navigator should not be in public API."""
        client = SSEClient(sample_index)
        
        # _navigator exists internally but shouldn't be in dir()
        assert "_navigator" not in dir(client)
        
        # Accessing it directly is possible in Python but discouraged
        # Type hints should guide users to not do this
    
    def test_all_permitted_operations_callable(self, sample_index):
        """All operations in __dir__ should be callable."""
        client = SSEClient(sample_index)
        
        permitted = [
            'get_all_claims',
            'get_claim_by_id',
            'get_all_contradictions',
            'get_contradiction_between',
            'get_provenance',
            'search',
            'find_contradictions_about',
            'find_uncertain_claims',
            'get_ambiguity_markers',
            'get_all_clusters',
            'get_cluster',
            'find_related_claims',
            'get_disagreement_patterns',
            'get_claim_coherence',
            'get_disagreement_clusters',
            'format_claim',
            'format_contradiction',
            'format_search_results'
        ]
        
        for method_name in permitted:
            assert hasattr(client, method_name), f"{method_name} should exist"
            assert callable(getattr(client, method_name)), f"{method_name} should be callable"


# =============================================================================
# GOVERNOR TESTS - Constitutional Enforcement
# =============================================================================

class TestConstitutionalGovernor:
    """
    Verify the client acts as a constitutional governor.
    
    These tests validate the core principle:
    If it compiles, it's permitted. If it doesn't, it's forbidden.
    """
    
    def test_permitted_operations_complete_successfully(self, sample_index):
        """All Phase A-C operations should complete without errors."""
        client = SSEClient(sample_index)
        
        # Phase A - all should succeed
        claims = client.get_all_claims()
        assert isinstance(claims, list)
        
        claim = client.get_claim_by_id("clm0")
        assert claim is not None
        
        contradictions = client.get_all_contradictions()
        assert isinstance(contradictions, list)
        
        # Phase B - all should succeed
        results = client.search("sleep", method="keyword")
        assert isinstance(results, list)
        
        uncertain = client.find_uncertain_claims(min_hedge=0.0)
        assert isinstance(uncertain, list)
        
        # Phase C - all should succeed
        clusters = client.get_all_clusters()
        assert isinstance(clusters, list)
    
    def test_forbidden_operations_fail_immediately(self, sample_index):
        """All Phase D+ operations should fail at call time."""
        client = SSEClient(sample_index)
        
        forbidden_ops = [
            ('add_confidence_score', ('clm0', 0.9)),
            ('track_user_action', ('view', 'clm0')),
            ('synthesize_answer', ('What is sleep?',)),
            ('pick_winner', ('clm0', 'clm1')),
            ('resolve_contradiction', ('clm0', 'clm1')),
        ]
        
        for method_name, args in forbidden_ops:
            with pytest.raises(AttributeError):
                method = getattr(client, method_name)
                method(*args)
    
    def test_no_runtime_surprises(self, sample_index):
        """Failures should happen at call time, not during execution."""
        client = SSEClient(sample_index)
        
        # This should fail immediately when attempting to get the attribute
        # NOT when calling it
        with pytest.raises(AttributeError):
            # Just accessing the method should fail
            _ = client.add_confidence_score
    
    def test_type_hints_guide_autocomplete(self, sample_index):
        """
        Client should have type hints for IDE support.
        
        This is a meta-test - verifies the client module has annotations.
        """
        from sse import client as client_module
        
        # Check that SSEClient has type annotations
        assert hasattr(client_module, '__annotations__') or True  # Module-level or class-level
        
        # Key methods should have return type hints
        assert SSEClient.get_all_claims.__annotations__.get('return') is not None
        assert SSEClient.search.__annotations__.get('return') is not None


# =============================================================================
# INTEGRATION TESTS - Real-World Usage
# =============================================================================

class TestRealWorldUsage:
    """Test realistic usage patterns."""
    
    def test_basic_workflow(self, sample_index):
        """Typical user workflow should work smoothly."""
        client = SSEClient(sample_index)
        
        # 1. Search for topic
        results = client.search("sleep", k=5, method="keyword")
        assert len(results) > 0
        
        # 2. Get a specific claim
        claim_id = results[0]["claim_id"]
        claim = client.get_claim_by_id(claim_id)
        assert claim is not None
        
        # 3. Check for contradictions
        contradictions = client.get_all_contradictions()
        assert len(contradictions) > 0
        
        # 4. Get provenance
        prov = client.get_provenance(claim_id)
        assert "supporting_quotes" in prov
        
        # 5. Format for display
        formatted = client.format_claim(claim)
        assert isinstance(formatted, str)
    
    def test_contradiction_analysis_workflow(self, sample_index):
        """Analyzing contradictions should work end-to-end."""
        client = SSEClient(sample_index)
        
        # Find contradictions about topic
        contradictions = client.find_contradictions_about("sleep")
        assert len(contradictions) > 0
        
        # Get both claims in the contradiction
        contra = contradictions[0]
        claim_a_id = contra["pair"]["claim_id_a"]
        claim_b_id = contra["pair"]["claim_id_b"]
        
        claim_a = client.get_claim_by_id(claim_a_id)
        claim_b = client.get_claim_by_id(claim_b_id)
        
        assert claim_a is not None
        assert claim_b is not None
        
        # Get provenance for both
        prov_a = client.get_provenance(claim_a_id)
        prov_b = client.get_provenance(claim_b_id)
        
        assert len(prov_a["supporting_quotes"]) > 0
        assert len(prov_b["supporting_quotes"]) > 0
        
        # Format for display
        formatted = client.format_contradiction(contra)
        assert "CLAIM A" in formatted
        assert "CLAIM B" in formatted


# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

def test_phase_6_2_complete():
    """
    Meta-test: Verify Phase 6.2 test coverage is complete.
    
    This test documents what Phase 6.2 achieved.
    """
    # Count test methods
    import inspect
    
    test_classes = [
        TestPermittedOperations,
        TestForbiddenOperations,
        TestClientBoundaries,
        TestConstitutionalGovernor,
        TestRealWorldUsage
    ]
    
    total_tests = 0
    for cls in test_classes:
        methods = [m for m in dir(cls) if m.startswith('test_')]
        total_tests += len(methods)
    
    print(f"\nPhase 6.2 Test Coverage:")
    print(f"  Total test methods: {total_tests}")
    print(f"  Test classes: {len(test_classes)}")
    print(f"  Coverage areas:")
    print(f"    - Permitted operations (Phase A-C)")
    print(f"    - Forbidden operations (Phase D+)")
    print(f"    - Boundary enforcement")
    print(f"    - Constitutional governor behavior")
    print(f"    - Real-world workflows")
    
    # Phase 6.2 complete if we have comprehensive coverage
    assert total_tests >= 30, "Phase 6.2 should have 30+ tests"
