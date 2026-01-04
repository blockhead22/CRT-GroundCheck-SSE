"""
Real Corpus Shakeout Tests

Testing with "ugly inputs" to prove packets always validate
and contradictions never disappear.

Test cases:
- Very long documents
- Very short documents  
- Highly repetitive text (spammy)
- Lots of near-duplicates
- Contradiction-heavy sets (dense graphs)
- Weird unicode / punctuation edge cases
- Queries that try to force synthesis
"""

import pytest
from sse.evidence_packet import EvidencePacketBuilder, EvidencePacketValidator
from sse.adapters.rag_adapter import RAGAdapter
from sse.adapters.search_adapter import SearchAdapter


class TestCorpusShakeout:
    """Test adapters with real corpus edge cases."""
    
    # ===== LONG DOCUMENTS =====
    
    def test_very_long_document_claims(self):
        """Test with very long document text (10000+ characters)."""
        builder = EvidencePacketBuilder("test query", "v1.0")
        
        # Create a very long claim text
        long_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 200
        
        builder.add_claim(
            "claim_long_001",
            long_text,
            "doc_long",
            0,
            len(long_text),
            True,
            "regex"
        )
        builder.set_metrics("claim_long_001", 1, 0.9, 0, 0)
        builder.log_event("query_executed", {"status": "success"})
        
        packet = builder.build().to_dict()
        
        # Validate
        is_valid, errors = EvidencePacketValidator.validate_complete(packet)
        assert is_valid, f"Long document claim failed validation: {errors}"
        
        # Process through RAG
        rag = RAGAdapter()
        result = rag.process_query("test", packet, use_mock_llm=True)
        assert result["valid"]
        assert result["packet"]["claims"][0]["claim_id"] == "claim_long_001"
    
    # ===== SHORT DOCUMENTS =====
    
    def test_very_short_document_claims(self):
        """Test with extremely short document text (1-2 words)."""
        builder = EvidencePacketBuilder("test", "v1.0")
        
        builder.add_claim("claim_short_001", "True", "doc", 0, 4, True, "regex")
        builder.add_claim("claim_short_002", "False", "doc", 5, 10, True, "regex")
        builder.set_metrics("claim_short_001", 1, 0.9, 0, 0)
        builder.set_metrics("claim_short_002", 1, 0.9, 0, 0)
        builder.add_contradiction("claim_short_001", "claim_short_002", "contradicts", 0.95)
        builder.log_event("query_executed", {"status": "success"})
        
        packet = builder.build().to_dict()
        
        is_valid, errors = EvidencePacketValidator.validate_complete(packet)
        assert is_valid
        
        # Both claims should still be there
        assert len(packet["claims"]) == 2
        assert len(packet["contradictions"]) == 1
    
    # ===== REPETITIVE / SPAMMY TEXT =====
    
    def test_highly_repetitive_text(self):
        """Test with highly repetitive/spammy text."""
        builder = EvidencePacketBuilder("spam test", "v1.0")
        
        # Repetitive text
        spammy_text = "same " * 1000
        
        builder.add_claim(
            "claim_spam_001",
            spammy_text,
            "doc_spam",
            0,
            len(spammy_text),
            True,
            "regex"
        )
        builder.set_metrics("claim_spam_001", 1, 0.5, 0, 0)
        builder.log_event("query_executed", {"status": "success"})
        
        packet = builder.build().to_dict()
        
        is_valid, errors = EvidencePacketValidator.validate_complete(packet)
        assert is_valid
        
        # Search adapter should still work
        search = SearchAdapter()
        results = search.render_search_results(packet)
        assert len(results["results"]) == 1
    
    # ===== LOTS OF NEAR-DUPLICATES =====
    
    def test_many_nearly_identical_claims(self):
        """Test with many claims that are nearly identical."""
        builder = EvidencePacketBuilder("duplicates test", "v1.0")
        
        # Create 50 nearly identical claims
        base_text = "The capital of France is Paris"
        for i in range(50):
            # Slight variation
            if i % 2 == 0:
                text = base_text
            else:
                text = "The capital of France is Paris (confirmed)"
            
            claim_id = f"claim_dup_{i:03d}"
            builder.add_claim(claim_id, text, f"doc_{i}", 0, 30, True, "regex")
            builder.set_metrics(claim_id, 1, 0.9, 0, 0)
        
        builder.log_event("query_executed", {"status": "success"})
        packet = builder.build().to_dict()
        
        is_valid, errors = EvidencePacketValidator.validate_complete(packet)
        assert is_valid
        
        # All claims should be present
        assert len(packet["claims"]) == 50
    
    # ===== DENSE CONTRADICTION GRAPHS =====
    
    def test_highly_contradictory_set(self):
        """Test with many claims all contradicting each other."""
        builder = EvidencePacketBuilder("contradictions test", "v1.0")
        
        # Create 10 claims
        claims = []
        for i in range(10):
            claim_id = f"claim_dense_{i:02d}"
            builder.add_claim(
                claim_id,
                f"Position {i} on the spectrum",
                "doc_spectrum",
                i * 10,
                i * 10 + 10,
                True,
                "regex"
            )
            builder.set_metrics(claim_id, 1, 0.8, 0, 0)
            claims.append(claim_id)
        
        # Create contradictions between adjacent claims (9 contradictions)
        for i in range(len(claims) - 1):
            builder.add_contradiction(
                claims[i],
                claims[i + 1],
                "contradicts",
                0.5 + (i * 0.05)  # Varying strengths
            )
        
        builder.log_event("query_executed", {"status": "success"})
        packet = builder.build().to_dict()
        
        is_valid, errors = EvidencePacketValidator.validate_complete(packet)
        assert is_valid
        
        # All contradictions must still be there
        assert len(packet["contradictions"]) == 9
        
        # Search adapter must preserve all
        search = SearchAdapter()
        results = search.render_search_results(packet)
        assert len(results["contradictions"]) == 9
    
    # ===== UNICODE AND PUNCTUATION EDGE CASES =====
    
    def test_unicode_in_claims(self):
        """Test with various unicode characters."""
        builder = EvidencePacketBuilder("unicode test", "v1.0")
        
        unicode_claims = [
            ("claim_emoji_001", "The emoji 🚀 indicates progress", "doc_emoji"),
            ("claim_cjk_001", "中文字符：这是一个测试", "doc_cjk"),
            ("claim_arabic_001", "العربية: هذا اختبار", "doc_arabic"),
            ("claim_symbol_001", "Math: ∑ ∏ ∫ √ ≠ ≈ ∞", "doc_math"),
            ("claim_special_001", "Special chars: @#$%^&*()[]{}|\\;:,.<>?", "doc_special"),
        ]
        
        for claim_id, text, source in unicode_claims:
            builder.add_claim(claim_id, text, source, 0, len(text), True, "regex")
            builder.set_metrics(claim_id, 1, 0.9, 0, 0)
        
        builder.log_event("query_executed", {"status": "success"})
        packet = builder.build().to_dict()
        
        is_valid, errors = EvidencePacketValidator.validate_complete(packet)
        assert is_valid, f"Unicode validation failed: {errors}"
        
        # All unicode claims preserved
        assert len(packet["claims"]) == len(unicode_claims)
    
    def test_extreme_punctuation(self):
        """Test with extreme punctuation and special characters."""
        builder = EvidencePacketBuilder("punctuation test", "v1.0")
        
        extreme_text = "!!! ??? ... --- *** [[[ ]]] {{{ }}} ((( )))"
        
        builder.add_claim(
            "claim_punct_001",
            extreme_text,
            "doc_punct",
            0,
            len(extreme_text),
            True,
            "regex"
        )
        builder.set_metrics("claim_punct_001", 1, 0.9, 0, 0)
        builder.log_event("query_executed", {"status": "success"})
        
        packet = builder.build().to_dict()
        
        is_valid, errors = EvidencePacketValidator.validate_complete(packet)
        assert is_valid
        assert len(packet["claims"]) == 1
    
    # ===== SYNTHESIS-FORCING QUERIES =====
    
    def test_synthesis_forcing_query_ignored(self):
        """Test that synthesis-forcing queries don't corrupt packets."""
        builder = EvidencePacketBuilder("", "v1.0")
        
        builder.add_claim("claim_syn_001", "Paris is the capital", "doc", 0, 20, True, "regex")
        builder.add_claim("claim_syn_002", "London is the capital", "doc", 21, 41, True, "regex")
        builder.set_metrics("claim_syn_001", 1, 0.9, 1, 1)
        builder.set_metrics("claim_syn_002", 1, 0.7, 1, 1)
        builder.add_contradiction("claim_syn_001", "claim_syn_002", "contradicts", 0.95)
        builder.log_event("query_executed", {"status": "success"})
        
        packet = builder.build().to_dict()
        original_claims = len(packet["claims"])
        original_contradictions = len(packet["contradictions"])
        
        # Try various queries
        test_queries = [
            "what is the capital?",
            "which claim is supported?",
            "what do the claims say?",
            "can you explain the relationship?",
            "summarize the claims"
        ]
        
        rag = RAGAdapter()
        for query in test_queries:
            result = rag.process_query(query, packet, use_mock_llm=True)
            
            # If valid, claims and contradictions must be preserved
            if result["valid"]:
                assert len(result["packet"]["claims"]) == original_claims
                assert len(result["packet"]["contradictions"]) == original_contradictions
    
    # ===== COMPREHENSIVE PASS CONDITIONS =====
    
    def test_all_packets_always_validate(self):
        """
        Pass condition 1: Packets always validate
        
        No matter the input, the packet coming out must be valid.
        """
        test_cases = [
            ("very long", "x" * 10000),
            ("very short", "a"),
            ("repetitive", "same " * 1000),
            ("unicode", "中文 🚀 العربية ∞"),
            ("punctuation", "!!! ??? ... --- ***"),
        ]
        
        for name, text in test_cases:
            builder = EvidencePacketBuilder(f"{name} test", "v1.0")
            builder.add_claim(f"claim_{name}", text, f"doc_{name}", 0, len(text), True, "regex")
            builder.set_metrics(f"claim_{name}", 1, 0.9, 0, 0)
            builder.log_event("query_executed", {"status": "success"})
            packet = builder.build().to_dict()
            
            is_valid, errors = EvidencePacketValidator.validate_complete(packet)
            assert is_valid, f"Packet failed validation for case '{name}': {errors}"
    
    def test_contradictions_never_disappear(self):
        """
        Pass condition 2: Contradictions never disappear
        
        Count input contradictions, process through adapters,
        verify count remains the same.
        """
        builder = EvidencePacketBuilder("contradiction preservation test", "v1.0")
        
        # Create dense contradiction set
        for i in range(20):
            builder.add_claim(f"claim_{i:02d}", f"Claim {i}", "doc", i*10, i*10+10, True, "regex")
            builder.set_metrics(f"claim_{i:02d}", 1, 0.8, 0, 0)
        
        # Add contradictions
        for i in range(19):
            builder.add_contradiction(f"claim_{i:02d}", f"claim_{i+1:02d}", "contradicts", 0.5)
        
        builder.log_event("query_executed", {"status": "success"})
        packet = builder.build().to_dict()
        original_count = len(packet["contradictions"])
        
        # Process through RAG
        rag = RAGAdapter()
        rag_result = rag.process_query("test", packet, use_mock_llm=True)
        assert rag_result["valid"]
        assert len(rag_result["packet"]["contradictions"]) == original_count
        
        # Process through Search
        search = SearchAdapter()
        search_result = search.render_search_results(packet)
        assert len(search_result["contradictions"]) == original_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
