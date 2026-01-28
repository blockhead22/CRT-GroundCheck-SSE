"""
Inference - Runtime inference with LLM fallback

This module provides the main interface for generating responses:
1. Try micro-transformer first (fast, learned patterns)
2. Fall back to LLM for complex/novel queries
3. Continue learning from LLM outputs
"""

import torch
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Callable
from dataclasses import dataclass
import json
import re

from .model import MicroTransformer, MicroTransformerConfig, SimpleTokenizer
from .data_extractor import TrainingExample


@dataclass
class InferenceResult:
    """Result from inference."""
    response: str
    thinking: str
    used_llm: bool
    confidence: float
    latency_ms: float
    source: str  # 'micro' or 'llm'
    

class ReasoningInference:
    """
    Inference engine with LLM fallback.
    
    Strategy:
    1. Run micro-transformer on input
    2. Assess confidence (perplexity-based)
    3. If confident → return micro response
    4. If not confident → fall back to LLM
    5. Log LLM response for future training
    """
    
    def __init__(
        self,
        model_path: str = "models/reasoning_learner/model",
        device: str = 'auto',
        confidence_threshold: float = 0.6,
        llm_callback: Optional[Callable] = None,
        collect_training_data: bool = True,
    ):
        """
        Initialize inference engine.
        
        Args:
            model_path: Path to saved micro-transformer
            device: 'cuda', 'cpu', or 'auto'
            confidence_threshold: Threshold for using micro response
            llm_callback: Function to call LLM (query, facts) -> (thinking, response)
            collect_training_data: Whether to log LLM responses for training
        """
        self.confidence_threshold = confidence_threshold
        self.llm_callback = llm_callback
        self.collect_training_data = collect_training_data
        
        # Device selection
        if device == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
            
        # Load model if exists
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        
        model_path = Path(model_path)
        if (model_path / 'model.pt').exists():
            self.load_model(str(model_path))
            
        # Training data collection
        self.training_buffer: List[TrainingExample] = []
        self.training_data_path = Path("data/collected_training_data.jsonl")
        
    def load_model(self, path: str):
        """Load the micro-transformer model."""
        try:
            self.model = MicroTransformer.load(path, self.device)
            self.model.eval()
            
            tokenizer_path = Path(path) / 'tokenizer.json'
            if tokenizer_path.exists():
                self.tokenizer = SimpleTokenizer.load(str(tokenizer_path))
            else:
                self.tokenizer = SimpleTokenizer()
                
            self.model_loaded = True
            print(f"[ReasoningInference] Loaded model from {path}")
            print(f"[ReasoningInference] Device: {self.device}")
            print(f"[ReasoningInference] Parameters: {self.model.n_params:,}")
            
        except Exception as e:
            print(f"[ReasoningInference] Failed to load model: {e}")
            self.model_loaded = False
            
    @torch.no_grad()
    def generate_micro(
        self, 
        query: str, 
        facts: List[str],
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> Tuple[str, str, float]:
        """
        Generate using micro-transformer.
        
        Returns:
            (thinking, response, confidence)
        """
        if not self.model_loaded:
            return "", "", 0.0
            
        # Format input
        facts_str = "\n".join(f"- {f}" for f in facts) if facts else "(no facts)"
        prompt = f"<query>{query}</query>\n<facts>\n{facts_str}\n</facts>\n<think>"
        
        # Tokenize
        tokens = self.tokenizer.encode(prompt, add_special_tokens=True)
        input_ids = torch.tensor([tokens], device=self.device)
        
        # Generate
        output_ids = self.model.generate(
            input_ids,
            max_new_tokens=max_tokens,
            temperature=temperature,
            stop_tokens=[
                self.tokenizer.special_tokens.get('</response>', 11),
                self.tokenizer.special_tokens.get('<eos>', 2),
            ],
        )
        
        # Decode
        output_text = self.tokenizer.decode(output_ids[0].tolist())
        
        # Calculate confidence (based on generation perplexity)
        confidence = self._calculate_confidence(input_ids, output_ids)
        
        # Extract thinking and response
        thinking = self._extract_section(output_text, "<think>", "</think>")
        response = self._extract_section(output_text, "<response>", "</response>")
        
        return thinking, response, confidence
        
    def _extract_section(self, text: str, start_tag: str, end_tag: str) -> str:
        """Extract content between tags."""
        try:
            if start_tag in text:
                start = text.index(start_tag) + len(start_tag)
                if end_tag in text[start:]:
                    end = text.index(end_tag, start)
                    return text[start:end].strip()
                else:
                    return text[start:].strip()
        except:
            pass
        return ""
        
    @torch.no_grad()
    def _calculate_confidence(
        self, 
        input_ids: torch.Tensor, 
        output_ids: torch.Tensor
    ) -> float:
        """
        Calculate confidence based on generation quality.
        
        Uses perplexity of the generated sequence - lower perplexity = higher confidence.
        """
        if not self.model_loaded:
            return 0.0
            
        # Get logits for the generated sequence
        logits, _ = self.model(output_ids)
        
        # Calculate perplexity on generated portion
        gen_start = input_ids.shape[1]
        gen_logits = logits[:, gen_start-1:-1, :]
        gen_targets = output_ids[:, gen_start:]
        
        if gen_logits.shape[1] == 0:
            return 0.5
            
        # Cross entropy loss
        loss = torch.nn.functional.cross_entropy(
            gen_logits.reshape(-1, gen_logits.size(-1)),
            gen_targets.reshape(-1),
            reduction='mean',
            ignore_index=self.tokenizer.special_tokens['<pad>']
        )
        
        perplexity = torch.exp(loss).item()
        
        # Convert perplexity to confidence (0-1)
        # Lower perplexity = higher confidence
        # PPL of 1 = perfect, PPL of 100 = poor
        confidence = max(0.0, min(1.0, 1.0 - (perplexity - 1) / 50))
        
        return confidence
        
    def call_llm(self, query: str, facts: List[str]) -> Tuple[str, str]:
        """Call the LLM via callback."""
        if self.llm_callback:
            return self.llm_callback(query, facts)
        return "", f"I can help with that, but I need more context. {query}"
        
    def generate(
        self,
        query: str,
        facts: List[str] = None,
        force_llm: bool = False,
        force_micro: bool = False,
    ) -> InferenceResult:
        """
        Generate a response with automatic fallback.
        
        Args:
            query: User query
            facts: Known facts for context
            force_llm: Always use LLM
            force_micro: Always use micro (even if low confidence)
            
        Returns:
            InferenceResult with response, source, confidence, etc.
        """
        facts = facts or []
        start_time = time.time()
        
        # Try micro first (unless forced to use LLM)
        micro_thinking = ""
        micro_response = ""
        micro_confidence = 0.0
        
        if not force_llm and self.model_loaded:
            micro_thinking, micro_response, micro_confidence = self.generate_micro(query, facts)
            
        # Decide whether to use micro or LLM
        use_micro = (
            force_micro or 
            (not force_llm and micro_confidence >= self.confidence_threshold and micro_response)
        )
        
        if use_micro:
            latency = (time.time() - start_time) * 1000
            return InferenceResult(
                response=micro_response,
                thinking=micro_thinking,
                used_llm=False,
                confidence=micro_confidence,
                latency_ms=latency,
                source='micro',
            )
        
        # Fall back to LLM
        llm_thinking, llm_response = self.call_llm(query, facts)
        latency = (time.time() - start_time) * 1000
        
        # Collect for training
        if self.collect_training_data and llm_thinking and llm_response:
            self._collect_example(query, facts, llm_thinking, llm_response)
            
        return InferenceResult(
            response=llm_response,
            thinking=llm_thinking,
            used_llm=True,
            confidence=0.9,  # Assume LLM is confident
            latency_ms=latency,
            source='llm',
        )
        
    def _collect_example(self, query: str, facts: List[str], thinking: str, response: str):
        """Collect training example from LLM output."""
        example = TrainingExample(
            query=query,
            facts=facts,
            thinking=thinking,
            response=response,
        )
        
        self.training_buffer.append(example)
        
        # Periodically flush to disk
        if len(self.training_buffer) >= 10:
            self._flush_training_buffer()
            
    def _flush_training_buffer(self):
        """Write collected examples to disk."""
        if not self.training_buffer:
            return
            
        self.training_data_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.training_data_path, 'a', encoding='utf-8') as f:
            for example in self.training_buffer:
                f.write(json.dumps(example.to_dict(), ensure_ascii=False) + '\n')
                
        print(f"[ReasoningInference] Flushed {len(self.training_buffer)} examples to {self.training_data_path}")
        self.training_buffer = []
        
    def get_stats(self) -> Dict:
        """Get inference statistics."""
        stats = {
            'model_loaded': self.model_loaded,
            'device': self.device,
            'confidence_threshold': self.confidence_threshold,
            'collected_examples': len(self.training_buffer),
        }
        
        if self.model_loaded:
            stats['model_params'] = self.model.n_params
            stats['model_size_mb'] = self.model.n_params * 4 / 1024 / 1024
            
        return stats
        
    def __del__(self):
        """Flush any remaining training data."""
        try:
            self._flush_training_buffer()
        except:
            pass


# Convenience function for integration
def create_inference_engine(
    llm_callback: Optional[Callable] = None,
    model_path: str = "models/reasoning_learner/model",
    confidence_threshold: float = 0.6,
) -> ReasoningInference:
    """
    Create inference engine for integration with CRT API.
    
    Usage:
        # In crt_api.py
        from personal_agent.reasoning_learner import create_inference_engine
        
        def llm_callback(query, facts):
            # Call your LLM here
            response = ollama_client.chat(...)
            return thinking, response
            
        inference = create_inference_engine(llm_callback)
        
        # In streaming endpoint
        result = inference.generate(query, facts)
        if result.used_llm:
            # Full LLM response
        else:
            # Fast micro response
    """
    return ReasoningInference(
        model_path=model_path,
        llm_callback=llm_callback,
        confidence_threshold=confidence_threshold,
    )


if __name__ == "__main__":
    # Test inference
    print("Testing ReasoningInference...")
    
    # Create engine (will fail to load model if not trained)
    engine = ReasoningInference(
        model_path="models/reasoning_learner/model",
        confidence_threshold=0.5,
    )
    
    print(f"\nStats: {engine.get_stats()}")
    
    # Test generation (will use fallback if model not loaded)
    test_queries = [
        ("What is my name?", ["name=Nick (0.95)"]),
        ("What is 2 + 2?", []),
        ("Hello!", []),
    ]
    
    for query, facts in test_queries:
        print(f"\nQuery: {query}")
        print(f"Facts: {facts}")
        
        result = engine.generate(query, facts)
        print(f"Response: {result.response}")
        print(f"Source: {result.source}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Latency: {result.latency_ms:.1f}ms")
