"""Chain-of-Verification (CoVe) baseline."""

from typing import List, Dict
import time
import os


class ChainOfVerification:
    """
    Chain-of-Verification baseline.
    
    Method:
    1. Generate verification questions for each claim
    2. Ask LLM to answer questions using retrieved context
    3. Check if answers support original claims
    
    Limitations:
    - Does NOT handle contradictions in context
    - Expensive (multiple LLM calls)
    - Can inherit errors from question generation
    """
    
    def __init__(self, num_questions_per_claim: int = 2):
        self.num_questions = num_questions_per_claim
        self.has_api_key = os.getenv("OPENAI_API_KEY") is not None
        
        if not self.has_api_key:
            print("Warning: OPENAI_API_KEY not set. CoVe will use mock responses.")
    
    def verify(self, generated_text: str, retrieved_memories: List[Dict]) -> Dict:
        """Verify using chain-of-verification."""
        start = time.time()
        
        if not self.has_api_key:
            return self._mock_verify(generated_text, retrieved_memories, start)
        
        # Step 1: Extract claims from generated text
        claims = self._extract_claims(generated_text)
        
        # Step 2: Generate verification questions for each claim
        questions = []
        for claim in claims:
            questions.extend(self._generate_verification_questions(claim))
        
        # Step 3: Answer questions using retrieved context
        context = "\n".join([m.get("text", "") for m in retrieved_memories])
        answers = [self._answer_question(q, context) for q in questions]
        
        # Step 4: Check if answers support original claims
        hallucinations = []
        for claim, answer in zip(claims, answers):
            if not self._answer_supports_claim(claim, answer):
                hallucinations.append(claim)
        
        # Calculate cost (2 LLM calls per claim: question gen + answering)
        num_calls = len(claims) * 2
        api_cost = (num_calls * 100 * 0.15) / 1_000_000
        
        return {
            "passed": len(hallucinations) == 0,
            "hallucinations": hallucinations,
            "method": "cove",
            "latency_ms": (time.time() - start) * 1000,
            "api_cost": api_cost,
            "num_questions": len(questions)
        }
    
    def _extract_claims(self, text: str) -> List[str]:
        """Extract factual claims from text."""
        import re
        # Simple: split on sentences
        claims = re.split(r'[.!?]', text)
        return [c.strip() for c in claims if c.strip()]
    
    def _generate_verification_questions(self, claim: str) -> List[str]:
        """Generate verification questions for a claim using LLM."""
        from openai import OpenAI
        client = OpenAI()
        
        prompt = f"""Given this claim: "{claim}"

Generate {self.num_questions} yes/no questions to verify if this claim is supported by evidence.

Format: One question per line."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        questions = response.choices[0].message.content.strip().split('\n')
        return [q.strip() for q in questions if q.strip()][:self.num_questions]
    
    def _answer_question(self, question: str, context: str) -> str:
        """Answer verification question using context."""
        from openai import OpenAI
        client = OpenAI()
        
        prompt = f"""Context: {context}

Question: {question}

Answer with yes/no and brief explanation."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        
        return response.choices[0].message.content
    
    def _answer_supports_claim(self, claim: str, answer: str) -> bool:
        """Check if answer supports the claim."""
        answer_lower = answer.lower()
        # Simple heuristic: check for "yes" and lack of negation
        return "yes" in answer_lower and "no" not in answer_lower[:10]
    
    def _mock_verify(self, generated_text: str, retrieved_memories: List[Dict], start_time: float) -> Dict:
        """
        Mock implementation without API.
        
        Note: CoVe doesn't detect contradictions well because it verifies if
        facts can be answered from context, not whether there are conflicts.
        """
        import sys
        from pathlib import Path
        
        # Add groundcheck to path
        groundcheck_path = str(Path(__file__).parent.parent.parent / "groundcheck")
        if groundcheck_path not in sys.path:
            sys.path.insert(0, groundcheck_path)
        
        from groundcheck.fact_extractor import extract_fact_slots
        
        # Extract facts
        claimed_facts = extract_fact_slots(generated_text)
        memory_text = " ".join([m.get("text", "") for m in retrieved_memories])
        memory_facts = extract_fact_slots(memory_text)
        
        # Simple check: is the claim mentioned in memories? (ignores contradictions)
        hallucinations = []
        for slot, fact in claimed_facts.items():
            fact_str = str(fact.value).lower()
            # Simple check: is this fact mentioned anywhere in memories?
            if fact_str not in memory_text.lower():
                hallucinations.append(fact.value)
        
        # CoVe assumes if a fact is in ANY memory, the answer is yes
        # It doesn't check for contradictions across memories
        
        return {
            "passed": len(hallucinations) == 0,
            "hallucinations": hallucinations,
            "method": "cove_mock",
            "latency_ms": (time.time() - start_time) * 1000,
            "api_cost": 0.0,
            "note": "Mock implementation - OpenAI API key not available"
        }
