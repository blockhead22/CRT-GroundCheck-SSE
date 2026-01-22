"""Tests for baseline grounding verification methods."""

import pytest
import sys
from pathlib import Path

# Add experiments directory to path to find baselines
sys.path.insert(0, str(Path(__file__).parent))

from baselines.vanilla_rag import VanillaRAG, BaselineResult
from baselines.selfcheck_gpt import SelfCheckGPT
from baselines.cove import ChainOfVerification


class TestVanillaRAG:
    """Tests for Vanilla RAG baseline."""
    
    def test_always_passes(self):
        """Vanilla RAG should always pass verification."""
        rag = VanillaRAG()
        
        # Test with valid content
        result = rag.verify(
            "User works at Microsoft",
            [{"id": "m1", "text": "User works at Microsoft"}]
        )
        assert isinstance(result, BaselineResult)
        assert result.passed is True
        assert result.hallucinations == []
        assert result.method == "vanilla_rag"
        
        # Test with contradicting content - still passes
        result = rag.verify(
            "User works at Amazon",
            [{"id": "m1", "text": "User works at Microsoft"}]
        )
        assert result.passed is True
        assert result.hallucinations == []
    
    def test_zero_cost(self):
        """Vanilla RAG should have zero API cost."""
        rag = VanillaRAG()
        result = rag.verify("Test", [{"id": "m1", "text": "Test"}])
        assert result.api_cost == 0.0
    
    def test_fast_latency(self):
        """Vanilla RAG should be very fast."""
        rag = VanillaRAG()
        result = rag.verify("Test", [{"id": "m1", "text": "Test"}])
        assert result.latency_ms < 10  # Should be sub-millisecond


class TestSelfCheckGPT:
    """Tests for SelfCheckGPT baseline."""
    
    def test_mock_implementation(self):
        """Test mock implementation without API key."""
        gpt = SelfCheckGPT(num_samples=5)
        
        # Test with grounded content
        result = gpt.verify(
            "User works at Microsoft",
            [{"id": "m1", "text": "User works at Microsoft"}]
        )
        assert isinstance(result, dict)
        assert "passed" in result
        assert "method" in result
        assert "selfcheck_gpt_mock" in result["method"]
        assert result["api_cost"] == 0.0
    
    def test_detects_hallucination(self):
        """Mock should detect facts not in memories."""
        gpt = SelfCheckGPT()
        
        # Completely different fact
        result = gpt.verify(
            "User works at Amazon",
            [{"id": "m1", "text": "User likes coffee"}]
        )
        # Mock checks if "amazon" substring is in memories
        assert not result["passed"]
        assert len(result["hallucinations"]) > 0
    
    def test_accepts_grounded_facts(self):
        """Mock should accept facts that appear in memories."""
        gpt = SelfCheckGPT()
        
        result = gpt.verify(
            "User works at Microsoft",
            [{"id": "m1", "text": "User works at Microsoft"}]
        )
        assert result["passed"]
        assert result["hallucinations"] == []


class TestChainOfVerification:
    """Tests for Chain-of-Verification baseline."""
    
    def test_mock_implementation(self):
        """Test mock implementation without API key."""
        cove = ChainOfVerification()
        
        result = cove.verify(
            "User works at Microsoft",
            [{"id": "m1", "text": "User works at Microsoft"}]
        )
        assert isinstance(result, dict)
        assert "passed" in result
        assert "method" in result
        assert "cove_mock" in result["method"]
        assert result["api_cost"] == 0.0
    
    def test_detects_hallucination(self):
        """Mock should detect facts not in memories."""
        cove = ChainOfVerification()
        
        result = cove.verify(
            "User works at Amazon",
            [{"id": "m1", "text": "User likes coffee"}]
        )
        assert not result["passed"]
        assert len(result["hallucinations"]) > 0
    
    def test_accepts_grounded_facts(self):
        """Mock should accept facts in memories."""
        cove = ChainOfVerification()
        
        result = cove.verify(
            "User works at Microsoft",
            [{"id": "m1", "text": "User works at Microsoft"}]
        )
        assert result["passed"]
        assert result["hallucinations"] == []


class TestBaselineComparison:
    """Integration tests comparing all baselines."""
    
    def test_all_baselines_work(self):
        """Verify all baselines can process same input."""
        text = "User works at Microsoft"
        memories = [{"id": "m1", "text": "User works at Microsoft"}]
        
        # Vanilla RAG
        rag = VanillaRAG()
        rag_result = rag.verify(text, memories)
        assert rag_result.passed
        
        # SelfCheckGPT
        gpt = SelfCheckGPT()
        gpt_result = gpt.verify(text, memories)
        assert gpt_result["passed"]
        
        # CoVe
        cove = ChainOfVerification()
        cove_result = cove.verify(text, memories)
        assert cove_result["passed"]
    
    def test_vanilla_rag_differs_from_smart_methods(self):
        """Vanilla RAG should differ from other methods on hallucinations."""
        hallucinated_text = "User works at Amazon"
        memories = [{"id": "m1", "text": "User likes coffee"}]
        
        # Vanilla RAG always passes
        rag = VanillaRAG()
        rag_result = rag.verify(hallucinated_text, memories)
        assert rag_result.passed  # Always true
        
        # Smart methods should catch it
        gpt = SelfCheckGPT()
        gpt_result = gpt.verify(hallucinated_text, memories)
        assert not gpt_result["passed"]  # Should fail
        
        cove = ChainOfVerification()
        cove_result = cove.verify(hallucinated_text, memories)
        assert not cove_result["passed"]  # Should fail


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
