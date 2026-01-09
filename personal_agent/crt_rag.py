"""
CRT-Enhanced RAG Engine

Integrates CRT principles into RAG:
- Trust-weighted retrieval (not just similarity)
- Belief vs speech separation
- Reconstruction gates (Holden constraints)
- Contradiction detection and ledger tracking
- Trust evolution on retrieval
- Memory-first philosophy

Philosophy:
- Coherence over time > single-query accuracy
- Memory informs retrieval, retrieval updates memory
- Fallback can speak, but doesn't create high-trust beliefs
- Gates prevent "sounding good while drifting"
"""

import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
import time

from .crt_core import CRTMath, CRTConfig, MemorySource, SSEMode, encode_vector
from .crt_memory import CRTMemorySystem, MemoryItem
from .crt_ledger import ContradictionLedger, ContradictionEntry
from .reasoning import ReasoningEngine, ReasoningMode


class CRTEnhancedRAG:
    """
    RAG engine with CRT principles.
    
    Differences from standard RAG:
    1. Retrieval weighted by trust, not just similarity
    2. Outputs gated by intent/memory alignment
    3. Contradictions create ledger entries, not silent overwrites
    4. Trust evolves based on alignment/drift
    5. Fallback speech separated from belief storage
    """
    
    def __init__(
        self,
        memory_db: str = "personal_agent/crt_memory.db",
        ledger_db: str = "personal_agent/crt_ledger.db",
        config: Optional[CRTConfig] = None,
        llm_client=None
    ):
        """Initialize CRT-enhanced RAG."""
        self.config = config or CRTConfig()
        self.crt_math = CRTMath(self.config)
        
        # CRT components
        self.memory = CRTMemorySystem(memory_db, self.config)
        self.ledger = ContradictionLedger(ledger_db, self.config)
        
        # Reasoning engine
        self.reasoning = ReasoningEngine(llm_client)
        
        # Session tracking
        import uuid
        self.session_id = str(uuid.uuid4())[:8]
    
    # ========================================================================
    # Trust-Weighted Retrieval
    # ========================================================================
    
    def retrieve(
        self,
        query: str,
        k: int = 5,
        min_trust: float = 0.0
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Retrieve memories using CRT trust-weighted scoring.
        
        R_i = s_i · ρ_i · w_i
        where:
        - s_i = similarity(query, memory)
        - ρ_i = recency_weight
        - w_i = α·trust + (1-α)·confidence
        
        This is fundamentally different from standard RAG's pure similarity.
        """
        return self.memory.retrieve_memories(query, k, min_trust)
    
    # ========================================================================
    # Query with CRT Principles
    # ========================================================================
    
    def query(
        self,
        user_query: str,
        user_marked_important: bool = False,
        mode: Optional[ReasoningMode] = None
    ) -> Dict[str, Any]:
        """
        Query with CRT principles applied.
        
        Process:
        0. Store user input as memory (USER source)
        1. Trust-weighted retrieval
        2. Generate candidate output (reasoning)
        3. Check reconstruction gates (intent + memory alignment)
        4. If gates pass → belief (high trust)
        5. If gates fail → speech (low trust fallback)
        6. Detect contradictions
        7. Update trust scores
        8. Queue reflection if needed
        
        Returns both the response AND CRT metadata.
        """
        # 0. Store user input as USER memory (always high trust)
        self.memory.store_memory(
            text=user_query,
            confidence=0.95,  # User statements are high confidence
            source=MemorySource.USER,
            context={'type': 'user_input'},
            user_marked_important=user_marked_important
        )
        
        # 1. Trust-weighted retrieval
        retrieved = self.retrieve(user_query, k=5)
        
        if not retrieved:
            # No memories → fallback speech
            return self._fallback_response(user_query)
        
        # Extract best prior belief
        best_prior = retrieved[0][0] if retrieved else None
        
        # 2. Generate candidate output using reasoning
        reasoning_context = {
            'retrieved_docs': [
                {'text': mem.text, 'trust': mem.trust, 'confidence': mem.confidence}
                for mem, score in retrieved
            ],
            'contradictions': [],  # Will detect after generation
            'memory_context': []
        }
        
        reasoning_result = self.reasoning.reason(
            query=user_query,
            context=reasoning_context,
            mode=mode
        )
        
        candidate_output = reasoning_result['answer']
        candidate_vector = encode_vector(candidate_output)
        
        # 3. Check reconstruction gates
        # For conversational AI, intent alignment = reasoning confidence
        # (Did we confidently answer the question?)
        intent_align = reasoning_result['confidence']
        
        # Memory alignment (output → retrieved memories)
        memory_align = self.crt_math.memory_alignment(
            output_vector=candidate_vector,
            retrieved_memories=[
                {'vector': mem.vector} for mem, _ in retrieved
            ],
            retrieval_scores=[score for _, score in retrieved]
        )
        
        gates_passed, gate_reason = self.crt_math.check_reconstruction_gates(
            intent_align, memory_align
        )
        
        # 4. Belief vs Speech decision
        if gates_passed:
            response_type = "belief"
            source = MemorySource.SYSTEM
            confidence = reasoning_result['confidence']
        else:
            response_type = "speech"
            source = MemorySource.FALLBACK
            confidence = reasoning_result['confidence'] * 0.7  # Degrade confidence
        
        # 5. Detect contradictions (only on similar topics)
        contradiction_detected = False
        contradiction_entry = None
        
        if best_prior:
            drift = self.crt_math.drift_meaning(candidate_vector, best_prior.vector)
            similarity = 1.0 - drift  # Similarity is inverse of drift
            
            # Only check for contradictions if topics are HIGHLY related (similarity > 0.5)
            # This means drift < 0.5, so we're only checking near-identical topics
            if similarity > 0.5:
                is_contra, contra_reason = self.crt_math.detect_contradiction(
                    drift=drift,
                    confidence_new=confidence,
                    confidence_prior=best_prior.confidence,
                    source=source
                )
                
                if is_contra:
                    contradiction_detected = True
                    
                    # Store new memory first
                    new_memory = self.memory.store_memory(
                        text=candidate_output,
                        confidence=confidence,
                        source=source,
                        context={'query': user_query, 'type': response_type},
                        user_marked_important=user_marked_important,
                        contradiction_signal=1.0
                    )
                    
                    # Create ledger entry (NO OVERWRITE)
                    contradiction_entry = self.ledger.record_contradiction(
                        old_memory_id=best_prior.memory_id,
                        new_memory_id=new_memory.memory_id,
                        drift_mean=drift,
                        confidence_delta=best_prior.confidence - confidence,
                        query=user_query,
                        summary=contra_reason
                    )
                    
                    # Degrade old memory trust
                    self.memory.evolve_trust_for_contradiction(best_prior, candidate_vector)
                    
                    # Compute volatility and maybe queue reflection
                    volatility = self.crt_math.compute_volatility(
                        drift=drift,
                        memory_alignment=memory_align,
                        is_contradiction=True,
                        is_fallback=(source == MemorySource.FALLBACK)
                    )
                    
                    if self.crt_math.should_reflect(volatility):
                        self.ledger.queue_reflection(
                            ledger_id=contradiction_entry.ledger_id,
                            volatility=volatility,
                            context={
                                'query': user_query,
                                'drift': drift,
                                'intent_align': intent_align,
                                'memory_align': memory_align
                            }
                        )
        
        # 6. Store memory (if not already stored due to contradiction)
        if not contradiction_detected:
            new_memory = self.memory.store_memory(
                text=candidate_output,
                confidence=confidence,
                source=source,
                context={'query': user_query, 'type': response_type},
                user_marked_important=user_marked_important
            )
            
            # Update trust for aligned memories
            if best_prior and gates_passed:
                self.memory.evolve_trust_for_alignment(best_prior, candidate_vector)
        
        # 7. Record belief or speech
        if response_type == "belief":
            self.memory.record_belief(
                query=user_query,
                response=candidate_output,
                memory_ids=[mem.memory_id for mem, _ in retrieved],
                avg_trust=np.mean([mem.trust for mem, _ in retrieved])
            )
        else:
            self.memory.record_speech(
                query=user_query,
                response=candidate_output,
                source="fallback_gates_failed"
            )
        
        # 8. Return comprehensive result
        return {
            # User-facing
            'answer': candidate_output,
            'thinking': reasoning_result.get('thinking'),
            'mode': reasoning_result['mode'],
            'confidence': reasoning_result['confidence'],
            
            # CRT metadata
            'response_type': response_type,  # "belief" or "speech"
            'gates_passed': gates_passed,
            'gate_reason': gate_reason,
            'intent_alignment': intent_align,
            'memory_alignment': memory_align,
            
            # Contradiction tracking
            'contradiction_detected': contradiction_detected,
            'contradiction_entry': contradiction_entry.to_dict() if contradiction_entry else None,
            
            # Retrieved context
            'retrieved_memories': [
                {
                    'text': mem.text,
                    'trust': mem.trust,
                    'confidence': mem.confidence,
                    'source': mem.source.value,
                    'sse_mode': mem.sse_mode.value,
                    'score': score
                }
                for mem, score in retrieved
            ],
            
            # Trust evolution
            'best_prior_trust': best_prior.trust if best_prior else None,
            
            # Session
            'session_id': self.session_id
        }
    
    def _fallback_response(self, query: str) -> Dict:
        """Generate fallback response when no memories exist."""
        # Simple fallback
        result = self.reasoning.reason(
            query=query,
            context={'retrieved_docs': [], 'contradictions': []},
            mode=ReasoningMode.QUICK
        )
        
        # Store as low-trust speech
        self.memory.store_memory(
            text=result['answer'],
            confidence=0.3,
            source=MemorySource.FALLBACK,
            context={'query': query, 'type': 'fallback_no_memory'}
        )
        
        self.memory.record_speech(query, result['answer'], "no_memory")
        
        return {
            'answer': result['answer'],
            'thinking': None,
            'mode': 'quick',
            'confidence': 0.3,
            'response_type': 'speech',
            'gates_passed': False,
            'gate_reason': 'No memories available',
            'contradiction_detected': False,
            'retrieved_memories': []
        }
    
    # ========================================================================
    # CRT Analytics
    # ========================================================================
    
    def get_crt_status(self) -> Dict:
        """Get CRT system health and statistics."""
        return {
            'belief_speech_ratio': self.memory.get_belief_speech_ratio(),
            'contradiction_stats': self.ledger.get_contradiction_stats(),
            'pending_reflections': len(self.ledger.get_reflection_queue()),
            'memory_count': len(self.memory._load_all_memories()),
            'session_id': self.session_id
        }
    
    def get_open_contradictions(self) -> List[Dict]:
        """Get unresolved contradictions requiring reflection."""
        entries = self.ledger.get_open_contradictions()
        return [e.to_dict() for e in entries]
    
    def get_reflection_queue(self) -> List[Dict]:
        """Get pending reflections."""
        return self.ledger.get_reflection_queue()
