"""DNNT inference with LLM fallback."""

import os
import torch
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Callable, Any
from dataclasses import dataclass
import json

from .model import DNNTMicroTransformer, DNNTConfig, SimpleTokenizer
from .data_extractor import TrainingExample
from .trust_gate import TrustGate, TrustGateConfig


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
        model_path: str = "models/dnnt/model",
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
        self.model_path = Path(model_path)
        self._loaded_signature: tuple[float, float, float] | None = None
        self._last_reload_check_at: float = 0.0
        self.auto_reload_enabled = str(
            os.getenv("CRT_DNNT_HOT_RELOAD", "true")
        ).strip().lower() in {"1", "true", "yes", "y", "on"}
        self.reload_check_interval_sec = float(os.getenv("CRT_DNNT_HOT_RELOAD_CHECK_INTERVAL_SEC", "10"))
        self.hot_reload_count = 0
        self.hot_reload_errors = 0
        self.last_hot_reload_reason = "n/a"
        self.last_hot_reload_at = 0.0

        if (self.model_path / 'model.pt').exists():
            self.load_model(str(self.model_path))
            
        # Training data collection
        self.training_buffer: List[TrainingExample] = []
        self.training_data_path = Path("data/dnnt_collected_training_data.jsonl")
        self.training_gate = TrustGate(
            TrustGateConfig(
                min_fact_trust=float(os.getenv("CRT_DNNT_MIN_FACT_TRUST", "0.55")),
                max_unresolved_contradictions=int(os.getenv("CRT_DNNT_MAX_UNRESOLVED_CONTRADICTIONS", "0")),
                require_groundcheck_pass=str(os.getenv("CRT_DNNT_REQUIRE_GROUNDCHECK", "false")).strip().lower()
                in {"1", "true", "yes", "y", "on"},
                reject_if_corrected_within_turns=int(
                    os.getenv("CRT_DNNT_REJECT_IF_CORRECTED_WITHIN_TURNS", "0")
                ),
            )
        )
        self.training_gate_accepted = 0
        self.training_gate_rejected = 0
        self.last_training_gate_reason = "n/a"
        
    def load_model(self, path: str):
        """Load the micro-transformer model."""
        try:
            self.model = DNNTMicroTransformer.load(path, self.device)
            self.model.eval()
            
            tokenizer_path = Path(path) / 'tokenizer.json'
            if tokenizer_path.exists():
                self.tokenizer = SimpleTokenizer.load(str(tokenizer_path))
            else:
                self.tokenizer = SimpleTokenizer()
                
            self.model_loaded = True
            self._loaded_signature = self._model_signature(Path(path))
            print(f"[ReasoningInference] Loaded model from {path}")
            print(f"[ReasoningInference] Device: {self.device}")
            print(f"[ReasoningInference] Parameters: {self.model.n_params:,}")
            
        except Exception as e:
            print(f"[ReasoningInference] Failed to load model: {e}")
            self.model_loaded = False

    @staticmethod
    def _file_mtime(path: Path) -> float:
        try:
            return float(path.stat().st_mtime)
        except Exception:
            return 0.0

    def _model_signature(self, model_dir: Path) -> tuple[float, float, float]:
        return (
            self._file_mtime(model_dir / "model.pt"),
            self._file_mtime(model_dir / "config.json"),
            self._file_mtime(model_dir / "tokenizer.json"),
        )

    def _maybe_hot_reload_model(self) -> None:
        """Reload model weights if files changed on disk."""
        if not self.auto_reload_enabled:
            return
        now = time.time()
        if (now - self._last_reload_check_at) < max(self.reload_check_interval_sec, 0.1):
            return
        self._last_reload_check_at = now

        if not (self.model_path / "model.pt").exists():
            return

        current_sig = self._model_signature(self.model_path)
        if self._loaded_signature is None:
            self.last_hot_reload_reason = "initial_signature_missing"
            self.load_model(str(self.model_path))
            return
        if current_sig == self._loaded_signature:
            self.last_hot_reload_reason = "no_change"
            return

        try:
            before_sig = self._loaded_signature
            self.load_model(str(self.model_path))
            if self.model_loaded and self._loaded_signature != before_sig:
                self.hot_reload_count += 1
                self.last_hot_reload_reason = "reloaded"
                self.last_hot_reload_at = now
            else:
                self.hot_reload_errors += 1
                self.last_hot_reload_reason = "reload_failed"
        except Exception as e:
            self.hot_reload_errors += 1
            self.last_hot_reload_reason = f"reload_failed:{e}"
            
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
        training_meta: Optional[Dict[str, Any]] = None,
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
        self._maybe_hot_reload_model()
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
            self._collect_example(query, facts, llm_thinking, llm_response, training_meta=training_meta)
            
        return InferenceResult(
            response=llm_response,
            thinking=llm_thinking,
            used_llm=True,
            confidence=0.9,  # Assume LLM is confident
            latency_ms=latency,
            source='llm',
        )
        
    def _collect_example(
        self,
        query: str,
        facts: List[str],
        thinking: str,
        response: str,
        training_meta: Optional[Dict[str, Any]] = None,
    ):
        """Collect training example from LLM output."""
        accepted, reason = self.training_gate.should_accept(facts=facts or [], meta=training_meta or {})
        self.last_training_gate_reason = reason
        if not accepted:
            self.training_gate_rejected += 1
            return

        example = TrainingExample(
            query=query,
            facts=facts,
            thinking=thinking,
            response=response,
        )
        
        self.training_buffer.append(example)
        self.training_gate_accepted += 1
        
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
            'model_path': str(self.model_path),
            'confidence_threshold': self.confidence_threshold,
            'collected_examples': len(self.training_buffer),
            'training_gate_accepted': self.training_gate_accepted,
            'training_gate_rejected': self.training_gate_rejected,
            'training_gate_last_reason': self.last_training_gate_reason,
            'hot_reload_enabled': self.auto_reload_enabled,
            'hot_reload_count': self.hot_reload_count,
            'hot_reload_errors': self.hot_reload_errors,
            'hot_reload_last_reason': self.last_hot_reload_reason,
            'hot_reload_last_at': self.last_hot_reload_at,
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
    model_path: str = "models/dnnt/model",
    confidence_threshold: float = 0.6,
) -> ReasoningInference:
    """
    Create inference engine for integration with CRT API.
    
    Usage:
        # In crt_api.py
        from personal_agent.dnnt import create_inference_engine
        
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
        model_path="models/dnnt/model",
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
