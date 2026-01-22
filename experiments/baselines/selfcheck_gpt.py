"""SelfCheckGPT baseline - consistency-based verification."""

from typing import List, Dict
import time
from collections import Counter
import os


class SelfCheckGPT:
    """
    SelfCheckGPT baseline using LLM sampling for consistency checking.
    
    Method:
    1. Sample N responses from LLM given same prompt
    2. Extract facts from each response
    3. Facts that appear inconsistently are hallucinations
    
    Limitations:
    - Does NOT detect contradictions in retrieved context
    - Expensive (requires N LLM calls)
    - Slower than deterministic methods
    """
    
    def __init__(self, num_samples: int = 5, consistency_threshold: float = 0.6):
        """
        Args:
            num_samples: Number of LLM samples to generate
            consistency_threshold: Fraction of samples that must agree
        """
        self.num_samples = num_samples
        self.consistency_threshold = consistency_threshold
        
        # Check if OpenAI API key available
        self.has_api_key = os.getenv("OPENAI_API_KEY") is not None
        if not self.has_api_key:
            print("Warning: OPENAI_API_KEY not set. SelfCheckGPT will use mock responses.")
    
    def verify(self, generated_text: str, retrieved_memories: List[Dict]) -> Dict:
        """
        Verify grounding using consistency checking.
        
        Args:
            generated_text: The LLM output to verify
            retrieved_memories: Retrieved context (used for re-prompting)
        
        Returns:
            BaselineResult with verification details
        """
        start = time.time()
        
        if not self.has_api_key:
            # Mock implementation for testing without API
            return self._mock_verify(generated_text, retrieved_memories, start)
        
        # Step 1: Sample N responses from LLM
        samples = self._generate_samples(retrieved_memories)
        
        # Step 2: Extract facts from original and samples
        original_facts = self._extract_facts(generated_text)
        sample_facts = [self._extract_facts(s) for s in samples]
        
        # Step 3: Check consistency of each fact
        hallucinations = []
        for fact in original_facts:
            # Count how many samples contain this fact
            count = sum(1 for s_facts in sample_facts if self._fact_in_list(fact, s_facts))
            consistency = count / len(samples)
            
            if consistency < self.consistency_threshold:
                hallucinations.append(fact)
        
        # Calculate cost (OpenAI GPT-4o mini: ~$0.15/1M tokens)
        # Assume ~100 tokens per sample
        api_cost = (self.num_samples * 100 * 0.15) / 1_000_000
        
        return {
            "passed": len(hallucinations) == 0,
            "hallucinations": hallucinations,
            "method": "selfcheck_gpt",
            "latency_ms": (time.time() - start) * 1000,
            "api_cost": api_cost,
            "num_samples": self.num_samples,
            "consistency_threshold": self.consistency_threshold,
            "grounding_map": {},
            "contradicted_claims": [],
            "requires_disclosure": False  # SelfCheckGPT doesn't detect contradictions in context
        }
    
    def _generate_samples(self, retrieved_memories: List[Dict]) -> List[str]:
        """Generate N sample responses from LLM."""
        from openai import OpenAI
        client = OpenAI()
        
        # Construct prompt from memories
        context = "\n".join([m.get("text", "") for m in retrieved_memories])
        prompt = f"Based on this context:\n{context}\n\nAnswer the query naturally."
        
        samples = []
        for _ in range(self.num_samples):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7  # Encourage variation
            )
            samples.append(response.choices[0].message.content)
        
        return samples
    
    def _extract_facts(self, text: str) -> List[str]:
        """
        Extract facts from text.
        Simplified: Split sentences and extract noun phrases.
        """
        # Simple fact extraction: split on punctuation
        import re
        facts = re.split(r'[.!?]', text)
        facts = [f.strip() for f in facts if f.strip()]
        return facts
    
    def _fact_in_list(self, fact: str, fact_list: List[str]) -> bool:
        """Check if fact appears in list (fuzzy matching)."""
        fact_lower = fact.lower()
        for f in fact_list:
            if fact_lower in f.lower() or f.lower() in fact_lower:
                return True
        return False
    
    def _mock_verify(self, generated_text: str, retrieved_memories: List[Dict], start_time: float) -> Dict:
        """
        Mock implementation when API key not available.
        Uses simple heuristic: check if output facts are in memories.
        
        Note: SelfCheckGPT doesn't detect contradictions well because it only
        checks consistency of generated outputs, not contradictions in context.
        """
        import sys
        from pathlib import Path
        
        # Add groundcheck to path
        groundcheck_path = str(Path(__file__).parent.parent.parent / "groundcheck")
        if groundcheck_path not in sys.path:
            sys.path.insert(0, groundcheck_path)
        
        from groundcheck.fact_extractor import extract_fact_slots
        
        # Extract facts from generated text
        claimed_facts = extract_fact_slots(generated_text)
        
        # Extract facts from memories
        memory_text = " ".join([m.get("text", "") for m in retrieved_memories])
        memory_facts = extract_fact_slots(memory_text)
        
        # Check if claimed facts are in memories (simple substring check)
        hallucinations = []
        for slot, fact in claimed_facts.items():
            fact_str = str(fact.value).lower()
            # Simple check: is this fact mentioned anywhere in memories?
            if fact_str not in memory_text.lower():
                hallucinations.append(fact.value)
        
        # Mock: SelfCheckGPT doesn't detect contradictions well
        # It assumes if a fact is mentioned in ANY memory, it's fine
        # (ignoring that there might be conflicting info in other memories)
        
        return {
            "passed": len(hallucinations) == 0,
            "hallucinations": hallucinations,
            "method": "selfcheck_gpt_mock",
            "latency_ms": (time.time() - start_time) * 1000,
            "api_cost": 0.0,
            "note": "Mock implementation - OpenAI API key not available",
            "grounding_map": {},
            "contradicted_claims": [],
            "requires_disclosure": False  # SelfCheckGPT doesn't detect contradictions in context
        }
