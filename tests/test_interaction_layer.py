"""
Tests for SSE Interaction Layer (Phase 6, D2)

Validates that the navigator:
1. Correctly retrieves and displays data without synthesis
2. Preserves all contradictions and ambiguity
3. Respects the Interface Contract
4. Enforces forbidden operations
"""

import json
import os
import pytest
import tempfile
import numpy as np
from pathlib import Path

from sse.interaction_layer import SSENavigator, SSEBoundaryViolation


# Test data: minimal valid index
MINIMAL_INDEX = {
    "doc_id": "test.txt",
    "timestamp": "2024-01-01T00:00:00Z",
    "chunks": [
        {
            "chunk_id": "c0",
            "text": "Climate change is a major threat. Some experts disagree on the timeline.",
            "start_char": 0,
            "end_char": 76
        }
    ],
    "clusters": [
        {
            "cluster_id": "cls0",
            "chunk_ids": ["clm0"]
        }
    ],
    "claims": [
        {
            "claim_id": "clm0",
            "claim_text": "Climate change is a major threat",
            "supporting_quotes": [
                {
                    "quote_text": "Climate change is a major threat",
                    "chunk_id": "c0",
                    "start_char": 0,
                    "end_char": 32
                }
            ],
            "ambiguity": {
                "hedge_score": 0.1,
                "contains_conflict_markers": False,
                "open_questions": []
            }
        },
        {
            "claim_id": "clm1",
            "claim_text": "Experts disagree on the timeline",
            "supporting_quotes": [
                {
                    "quote_text": "Some experts disagree on the timeline",
                    "chunk_id": "c0",
                    "start_char": 38,
                    "end_char": 76
                }
            ],
            "ambiguity": {
                "hedge_score": 0.3,
                "contains_conflict_markers": True,
                "open_questions": ["What timeline?"]
            }
        }
    ],
    "contradictions": [
        {
            "pair": {
                "claim_id_a": "clm0",
                "claim_id_b": "clm1"
            },
            "label": "contradiction",
            "evidence_quotes": [
                {
                    "quote_text": "Climate change is a major threat",
                    "chunk_id": "c0",
                    "start_char": 0,
                    "end_char": 32
                },
                {
                    "quote_text": "Some experts disagree",
                    "chunk_id": "c0",
                    "start_char": 38,
                    "end_char": 59
                }
            ]
        }
    ]
}


@pytest.fixture
def temp_index():
    """Create a temporary index file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "index.json")
        with open(index_path, "w") as f:
            json.dump(MINIMAL_INDEX, f)
        yield index_path


@pytest.fixture
def temp_index_with_embeddings(temp_index):
    """Create a temporary index with embeddings for semantic search tests."""
    tmpdir = os.path.dirname(temp_index)
    
    # Create dummy embeddings (one per claim)
    embeddings = np.random.randn(2, 384).astype("float32")
    np.save(os.path.join(tmpdir, "embeddings.npy"), embeddings)
    
    yield temp_index


class TestSSENavigatorBasics:
    """Test basic navigator functionality."""
    
    def test_load_index(self, temp_index):
        """Navigator loads index correctly."""
        nav = SSENavigator(temp_index)
        assert nav.doc_id == "test.txt"
        assert len(nav.claims) == 2
        assert len(nav.contradictions) == 1
    
    def test_info(self, temp_index):
        """Navigator provides accurate index info."""
        nav = SSENavigator(temp_index)
        info = nav.info()
        assert info["num_claims"] == 2
        assert info["num_contradictions"] == 1
        assert info["num_chunks"] == 1


class TestRetrieval:
    """Test PERMITTED operations: retrieval."""
    
    def test_get_claim_by_id(self, temp_index):
        """Retrieve claim by ID."""
        nav = SSENavigator(temp_index)
        claim = nav.get_claim_by_id("clm0")
        assert claim is not None
        assert claim["claim_text"] == "Climate change is a major threat"
    
    def test_get_nonexistent_claim(self, temp_index):
        """Retrieve nonexistent claim returns None."""
        nav = SSENavigator(temp_index)
        claim = nav.get_claim_by_id("nonexistent")
        assert claim is None
    
    def test_get_all_claims(self, temp_index):
        """Retrieve all claims."""
        nav = SSENavigator(temp_index)
        claims = nav.get_all_claims()
        assert len(claims) == 2
    
    def test_get_all_contradictions(self, temp_index):
        """Retrieve all contradictions."""
        nav = SSENavigator(temp_index)
        contradictions = nav.get_contradictions()
        assert len(contradictions) == 1


class TestSearch:
    """Test PERMITTED operations: search and filtering."""
    
    def test_keyword_search(self, temp_index):
        """Search by keyword."""
        nav = SSENavigator(temp_index)
        results = nav.query("climate", method="keyword")
        assert len(results) > 0
        assert "Climate" in results[0]["claim_text"]
    
    def test_keyword_search_no_results(self, temp_index):
        """Keyword search with no results returns empty list."""
        nav = SSENavigator(temp_index)
        results = nav.query("xyz123notfound", method="keyword")
        assert len(results) == 0
    
    def test_get_uncertain_claims(self, temp_index):
        """Retrieve uncertain claims by hedge score."""
        nav = SSENavigator(temp_index)
        uncertain = nav.get_uncertain_claims(min_hedge=0.2)
        assert len(uncertain) == 1
        assert uncertain[0]["claim_id"] == "clm1"


class TestProvenance:
    """Test PERMITTED operations: provenance tracking."""
    
    def test_get_provenance(self, temp_index):
        """Retrieve exact source for a claim."""
        nav = SSENavigator(temp_index)
        prov = nav.get_provenance("clm0")
        assert prov["claim_id"] == "clm0"
        assert len(prov["supporting_quotes"]) == 1
        assert prov["supporting_quotes"][0]["start_char"] == 0
        assert prov["supporting_quotes"][0]["end_char"] == 32
    
    def test_get_provenance_nonexistent(self, temp_index):
        """Provenance for nonexistent claim raises ValueError."""
        nav = SSENavigator(temp_index)
        with pytest.raises(ValueError):
            nav.get_provenance("nonexistent")


class TestAmbiguityExposure:
    """Test PERMITTED operations: ambiguity exposure (as-is)."""
    
    def test_get_ambiguity(self, temp_index):
        """Retrieve ambiguity markers for a claim."""
        nav = SSENavigator(temp_index)
        ambiguity = nav.get_ambiguity("clm1")
        assert ambiguity["claim_id"] == "clm1"
        assert ambiguity["ambiguity"]["hedge_score"] == 0.3
        assert ambiguity["ambiguity"]["contains_conflict_markers"] is True


class TestContradictionHandling:
    """Test PERMITTED operations: contradiction exposure."""
    
    def test_get_contradictions_for_topic(self, temp_index):
        """Find contradictions about a topic."""
        nav = SSENavigator(temp_index)
        contradictions = nav.get_contradictions_for_topic("climate")
        assert len(contradictions) > 0
    
    def test_format_contradiction_shows_both_sides(self, temp_index):
        """Format contradiction shows both sides in full."""
        nav = SSENavigator(temp_index)
        contra = nav.get_contradictions()[0]
        formatted = nav.format_contradiction(contra)
        
        # Both claims must appear in full
        assert "Climate change is a major threat" in formatted
        assert "Experts disagree on the timeline" in formatted
        
        # Warning about no picking winners
        assert "Both claims are shown in full" in formatted
        assert "You decide what this means" in formatted


class TestForbiddenOperations:
    """Test FORBIDDEN operations raise SSEBoundaryViolation."""
    
    def test_forbid_synthesis(self, temp_index):
        """Synthesis is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.synthesize_answer("What is climate change?")
    
    def test_forbid_qa(self, temp_index):
        """QA-style answering is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.answer_question("Is climate change real?")
    
    def test_forbid_truth_picking(self, temp_index):
        """Picking winners is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.pick_best_claim("clm0", "clm1")
    
    def test_forbid_contradiction_resolution(self, temp_index):
        """Resolving contradictions is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.resolve_contradiction("clm0", "clm1")
    
    def test_forbid_ambiguity_softening(self, temp_index):
        """Softening ambiguity is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.soften_ambiguity("clm1")
    
    def test_forbid_hedge_removal(self, temp_index):
        """Removing hedge language is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.remove_hedge_language("clm1")
    
    def test_forbid_contradiction_suppression(self, temp_index):
        """Suppressing contradictions is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.suppress_contradiction("clm0")
    
    def test_forbid_silent_filtering(self, temp_index):
        """Silent filtering by confidence is forbidden."""
        nav = SSENavigator(temp_index)
        with pytest.raises(SSEBoundaryViolation):
            nav.filter_low_confidence(0.8)


class TestDisplay:
    """Test display formatting (structural only, no paraphrasing)."""
    
    def test_format_claim_shows_verbatim_text(self, temp_index):
        """Format claim shows verbatim text from index."""
        nav = SSENavigator(temp_index)
        claim = nav.get_claim_by_id("clm0")
        formatted = nav.format_claim(claim)
        
        # Exact text from index, no paraphrasing
        assert "Climate change is a major threat" in formatted
        assert "Climate change is a significant issue" not in formatted
    
    def test_format_claim_shows_offsets(self, temp_index):
        """Format claim includes byte offsets for verification."""
        nav = SSENavigator(temp_index)
        claim = nav.get_claim_by_id("clm0")
        formatted = nav.format_claim(claim)
        
        assert "[0:32]" in formatted  # Exact byte offsets
    
    def test_format_search_results(self, temp_index):
        """Format search results shows all claims."""
        nav = SSENavigator(temp_index)
        results = nav.query("climate", method="keyword")
        formatted = nav.format_search_results(results)
        
        assert "Found" in formatted
        for result in results:
            assert result["claim_text"] in formatted


class TestInterfaceContract:
    """Test that navigator respects the Interface Contract."""
    
    def test_all_displayed_content_is_from_index(self, temp_index):
        """All displayed content comes directly from the index, never synthesized."""
        nav = SSENavigator(temp_index)
        claims = nav.get_all_claims()
        
        for claim in claims:
            formatted = nav.format_claim(claim)
            # The formatted output must be a restructuring of index data
            # (no new text generated)
            claim_text = claim.get("claim_text")
            assert claim_text in formatted
    
    def test_no_synthesis_in_navigation(self, temp_index):
        """Navigation operations never generate new text."""
        nav = SSENavigator(temp_index)
        
        # Get various results
        claims = nav.get_all_claims()
        contradictions = nav.get_contradictions()
        uncertain = nav.get_uncertain_claims(min_hedge=0.0)
        
        # All content must come from index
        original_claim_texts = {c["claim_text"] for c in MINIMAL_INDEX["claims"]}
        nav_claim_texts = {c["claim_text"] for c in claims}
        
        assert original_claim_texts == nav_claim_texts
    
    def test_contradictions_never_suppressed(self, temp_index):
        """All contradictions are always available."""
        nav = SSENavigator(temp_index)
        
        # Every contradiction in index must be retrievable
        index_contra_count = len(MINIMAL_INDEX["contradictions"])
        retrieved_contra_count = len(nav.get_contradictions())
        
        assert retrieved_contra_count == index_contra_count
    
    def test_ambiguity_always_exposed(self, temp_index):
        """Ambiguity markers are always shown, never hidden."""
        nav = SSENavigator(temp_index)
        
        # High-ambiguity claims must be discoverable
        uncertain = nav.get_uncertain_claims(min_hedge=0.0)
        
        # Claim with high hedge score must be included
        claim_ids = {c["claim_id"] for c in uncertain}
        assert "clm1" in claim_ids  # clm1 has hedge_score 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
