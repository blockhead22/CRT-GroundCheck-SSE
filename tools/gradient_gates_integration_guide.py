"""
Gradient Gates Integration for CRT RAG

Integrates learned response-type classification and gradient gates
into the existing CRT RAG system.

Changes:
1. Replace binary gate checks with gradient gates v2
2. Add response-type prediction before gate checks
3. Integrate active learning event logging
4. Add grounding score computation

This is a PATCH file - shows exactly what to change in crt_rag.py
"""

# Location: personal_agent/crt_rag.py
# Add import at top of file (around line 20):

from .active_learning import get_active_learning_coordinator

# ---

# In CRTEnhancedRAG.__init__ (around line 70):
# Add after self.runtime_config = get_runtime_config()

        # Active learning coordinator
        try:
            self.active_learning = get_active_learning_coordinator()
        except Exception:
            self.active_learning = None  # Graceful degradation

# ---

# Create new method in CRTEnhancedRAG class:

    def _compute_grounding_score(
        self,
        answer: str,
        retrieved_memories: List[Tuple[MemoryItem, float]],
    ) -> float:
        """
        Compute grounding score (0-1) for an answer.
        
        Higher score = more grounded in retrieved memories.
        Lower score = more synthesis/generation.
        
        Simple heuristic for now:
        - Check if key facts from answer appear in memories
        - Penalize if answer is much longer than memories
        - Reward if answer quotes memories directly
        """
        if not retrieved_memories or not answer:
            return 0.0
        
        answer_lower = answer.lower()
        
        # Extract key phrases from memories
        memory_text = " ".join(mem.text.lower() for mem, _ in retrieved_memories[:3])
        
        # Simple word overlap
        answer_words = set(answer_lower.split())
        memory_words = set(memory_text.split())
        
        if not answer_words:
            return 0.0
        
        overlap = len(answer_words & memory_words)
        overlap_ratio = overlap / len(answer_words)
        
        # Check for direct quotes (quotation marks or high word overlap)
        has_quotes = '"' in answer or "'" in answer
        quote_bonus = 0.2 if has_quotes else 0.0
        
        # Penalize if answer is much longer than grounding
        len_ratio = len(answer) / max(len(memory_text), 1)
        length_penalty = 0.0
        if len_ratio > 2.0:
            length_penalty = 0.2
        
        grounding_score = min(1.0, overlap_ratio + quote_bonus - length_penalty)
        return max(0.0, grounding_score)

    def _classify_contradiction_severity(
        self,
        open_contradictions: List,
        query_slots: Set[str],
    ) -> str:
        """
        Classify contradiction severity: blocking/note/none.
        
        blocking: Contradictions that affect the current query
        note: Contradictions exist but don't affect this query
        none: No contradictions
        """
        if not open_contradictions:
            return "none"
        
        # Check if any contradictions affect the query slots
        for contra in open_contradictions:
            affects_slots_str = getattr(contra, "affects_slots", None)
            if affects_slots_str and query_slots:
                affects_slots = set(affects_slots_str.split(","))
                if affects_slots & query_slots:
                    return "blocking"  # Affects current query
        
        # Contradictions exist but don't affect this query
        return "note"

# ---

# Modify the gate check in answer() method (around line 1250):
# REPLACE the old gate check with this:

            # Predict response type using active learning
            response_type = "conversational"  # Default fallback
            if self.active_learning:
                try:
                    response_type = self.active_learning.predict_response_type(user_query)
                except Exception:
                    pass  # Use fallback
            
            # Compute grounding score
            grounding_score = self._compute_grounding_score(answer_text, retrieved)
            
            # Classify contradiction severity
            query_slots = set(self._infer_slots_from_query(user_query))
            contradiction_severity = self._classify_contradiction_severity(
                open_contradictions, query_slots
            )
            
            # Check gates v2 (gradient gates)
            gates_passed, gate_reason = self.crt_math.check_reconstruction_gates_v2(
                intent_align=response_metadata.get("intent_alignment", 0.0),
                memory_align=response_metadata.get("memory_alignment", 0.0),
                response_type=response_type,
                grounding_score=grounding_score,
                contradiction_severity=contradiction_severity,
            )
            
            # Log gate event for active learning
            if self.active_learning:
                try:
                    event_id = self.active_learning.record_gate_event(
                        question=user_query,
                        response_type_predicted=response_type,
                        intent_align=response_metadata.get("intent_alignment", 0.0),
                        memory_align=response_metadata.get("memory_alignment", 0.0),
                        grounding_score=grounding_score,
                        gates_passed=gates_passed,
                        gate_reason=gate_reason,
                        thread_id=thread_id,
                        session_id=self.session_id,
                    )
                    # Store event_id in metadata for later correction tracking
                    response_metadata["gate_event_id"] = event_id
                except Exception as e:
                    print(f"Warning: Active learning logging failed: {e}")
            
            # Add to metadata
            response_metadata["response_type"] = response_type
            response_metadata["grounding_score"] = grounding_score
            response_metadata["contradiction_severity"] = contradiction_severity

# ---

# NOTE: This is a PATCH guide. Actual integration requires:
# 1. Finding exact line numbers in your crt_rag.py
# 2. Replacing old gate checks with new v2 calls
# 3. Testing that it works

# The key changes are:
# - Import active_learning
# - Initialize coordinator in __init__
# - Add _compute_grounding_score method
# - Add _classify_contradiction_severity method  
# - Replace gate checks with v2 + logging

print("""
Integration Guide for Gradient Gates
=====================================

Files to modify:
1. personal_agent/crt_rag.py
   - Add import: from .active_learning import get_active_learning_coordinator
   - Add coordinator in __init__
   - Add _compute_grounding_score method
   - Add _classify_contradiction_severity method
   - Replace gate checks with v2 version

2. personal_agent/crt_core.py
   - Already done: check_reconstruction_gates_v2 added

3. tools/train_response_classifier.py
   - Already done: training script created

4. personal_agent/active_learning.py
   - Already done: coordinator implemented

Next steps:
1. Generate training data: python tools/bootstrap_training_data.py --output training_data/bootstrap_v1.jsonl
2. Train initial model: python tools/train_response_classifier.py --input training_data/bootstrap_v1.jsonl --output models/response_classifier.joblib
3. Test gradient gates: Run stress test and compare pass rates
4. Monitor active learning: Check dashboard for learning stats
""")
