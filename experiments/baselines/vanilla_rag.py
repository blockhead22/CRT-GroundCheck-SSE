"""Vanilla RAG baseline - no grounding verification."""

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class BaselineResult:
    """Standardized result format for all baselines."""
    passed: bool
    hallucinations: List[str]
    method: str
    latency_ms: float
    api_cost: float = 0.0
    grounding_map: Dict[str, str] = None
    contradicted_claims: List[str] = None
    requires_disclosure: bool = False
    
    def __post_init__(self):
        if self.grounding_map is None:
            self.grounding_map = {}
        if self.contradicted_claims is None:
            self.contradicted_claims = []
    

class VanillaRAG:
    """Baseline: No verification, assumes everything is grounded."""
    
    def verify(self, generated_text: str, retrieved_memories: List[Dict]) -> BaselineResult:
        """
        No verification - always passes.
        
        This represents standard RAG without post-generation verification.
        """
        import time
        start = time.time()
        
        # No verification logic - just return pass
        result = BaselineResult(
            passed=True,
            hallucinations=[],
            method="vanilla_rag",
            latency_ms=(time.time() - start) * 1000,
            api_cost=0.0,
            grounding_map={},
            contradicted_claims=[],
            requires_disclosure=False  # Never detects contradictions
        )
        
        end = time.time()
        result.latency_ms = (end - start) * 1000
        
        return result
