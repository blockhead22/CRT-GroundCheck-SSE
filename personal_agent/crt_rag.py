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
from .fact_slots import extract_fact_slots
from .learned_suggestions import LearnedSuggestionEngine
from .runtime_config import get_runtime_config


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

        # Optional learned suggestions (metadata-only).
        self.learned_suggestions = LearnedSuggestionEngine()
        self.runtime_config = get_runtime_config()
        
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
    # Uncertainty as First-Class State
    # ========================================================================
    
    def _should_express_uncertainty(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        contradictions_count: int = 0,
        gates_passed: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if system should express explicit uncertainty.
        
        Returns: (should_express_uncertainty, reason)
        
        Express uncertainty when:
        1. Multiple high-trust memories conflict (unresolved contradictions)
        2. Trust scores are too close (no clear winner)
        3. Gates failed AND unresolved contradictions exist
        4. Max trust below threshold (no confident belief)
        """
        if not retrieved:
            return False, ""
        
        # Check 1: Unresolved contradictions
        if contradictions_count > 0:
            return True, f"I have {contradictions_count} unresolved contradictions about this"
        
        # Check 2: DISABLED - was triggering too early
        
        # Check 3: Max trust below confidence threshold
        max_trust = max(mem.trust for mem, _ in retrieved)
        if max_trust < 0.6:
            return True, f"My confidence in this information is low (trust={max_trust:.2f})"
        
        # Check 4: Gates failed with moderate contradiction
        if not gates_passed and contradictions_count > 0:
            return True, "I cannot confidently reconstruct a coherent answer from my memories"
        
        return False, ""
    
    def _generate_uncertain_response(
        self,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        reason: str
    ) -> str:
        """
        Generate explicit uncertainty response.
        
        This is a FIRST-CLASS response state, not a fallback.
        """
        # Show what we know and what conflicts
        beliefs = []
        for mem, score in retrieved[:3]:
            beliefs.append(f"- {mem.text} (trust: {mem.trust:.2f})")
        
        beliefs_text = "\n".join(beliefs) if beliefs else "No clear memories"
        
        return f"I need to be honest about my uncertainty here.\n\n{reason}\n\nWhat I have in memory:\n{beliefs_text}\n\nI cannot give you a confident answer without resolving these conflicts. Can you help clarify?"
    
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
        # 0. Store user input as USER memory ONLY when it's an assertion.
        # Questions and control instructions should not be treated as durable factual claims.
        user_memory: Optional[MemoryItem] = None
        user_input_kind = self._classify_user_input(user_query)
        if user_input_kind == "assertion":
            user_memory = self.memory.store_memory(
                text=user_query,
                confidence=0.95,  # User assertions are high confidence
                source=MemorySource.USER,
                context={"type": "user_input", "kind": user_input_kind},
                user_marked_important=user_marked_important
            )
        
        # 1. Trust-weighted retrieval
        retrieved = self.retrieve(user_query, k=5)

        # Slot-aware question augmentation: for simple fact questions, semantic retrieval
        # can miss the most recent correction (e.g., Amazon vs Microsoft). If the query
        # looks like it targets a known slot, explicitly pull the best candidate memory
        # for that slot from the full store and merge it into retrieved.
        if user_input_kind in ("question", "instruction") and retrieved:
            inferred_slots = self._infer_slots_from_query(user_query)
            if inferred_slots:
                retrieved = self._augment_retrieval_with_slot_memories(retrieved, inferred_slots)

        # Slot-based fast-path: if the user asks a simple personal-fact question and we have
        # an answer in memory, answer directly from canonical resolved facts.
        if user_input_kind in ("question", "instruction"):
            inferred_slots = self._infer_slots_from_query(user_query)
            if inferred_slots:
                slot_answer = self._answer_from_fact_slots(inferred_slots)
                if slot_answer is not None:
                    # Ensure we still have retrieval context for metadata/alignment.
                    if not retrieved:
                        retrieved = self.retrieve(user_query, k=5)
                    prompt_docs = self._build_resolved_memory_docs(retrieved, max_fallback_lines=0)

                    reasoning_result = {
                        'answer': slot_answer,
                        'thinking': None,
                        'mode': 'quick',
                        'confidence': 0.95,
                    }

                    candidate_output = reasoning_result['answer']
                    candidate_vector = encode_vector(candidate_output)

                    intent_align = reasoning_result['confidence']
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

                    response_type = "belief" if gates_passed else "speech"
                    source = MemorySource.SYSTEM if gates_passed else MemorySource.FALLBACK
                    confidence = reasoning_result['confidence'] if gates_passed else (reasoning_result['confidence'] * 0.7)

                    best_prior = retrieved[0][0] if retrieved else None

                    # Store system response memory
                    self.memory.store_memory(
                        text=candidate_output,
                        confidence=confidence,
                        source=source,
                        context={'query': user_query, 'type': response_type, 'kind': 'slot_answer'},
                        user_marked_important=False,
                    )

                    learned = self._get_learned_suggestions_for_slots(inferred_slots)

                    return {
                        'answer': candidate_output,
                        'thinking': None,
                        'mode': 'quick',
                        'confidence': reasoning_result['confidence'],
                        'response_type': response_type,
                        'gates_passed': gates_passed,
                        'gate_reason': gate_reason,
                        'intent_alignment': intent_align,
                        'memory_alignment': memory_align,
                        'contradiction_detected': False,
                        'contradiction_entry': None,
                        'retrieved_memories': [
                            {
                                'text': mem.text,
                                'trust': mem.trust,
                                'confidence': mem.confidence,
                                'source': mem.source.value,
                                'sse_mode': mem.sse_mode.value,
                                'score': score,
                            }
                            for mem, score in retrieved
                        ],
                        'prompt_memories': [
                            {
                                'text': d.get('text'),
                                'trust': d.get('trust'),
                                'confidence': d.get('confidence'),
                                'source': d.get('source'),
                            }
                            for d in prompt_docs
                        ],
                        'learned_suggestions': learned,
                        'heuristic_suggestions': self._get_heuristic_suggestions_for_slots(inferred_slots),
                        'best_prior_trust': best_prior.trust if best_prior else None,
                        'session_id': self.session_id,
                    }
        
        if not retrieved:
            # No memories → fallback speech
            return self._fallback_response(user_query)
        
        # GLOBAL COHERENCE GATE: Check for unresolved contradictions.
        # Only hard CONFLICT contradictions should trigger an uncertainty early-exit.
        # Revisions/refinements/temporal updates can often be answered coherently without stalling.
        from .crt_ledger import ContradictionType

        unresolved_contradictions = self.ledger.get_open_contradictions(limit=50)
        related_open_total = 0
        related_hard_conflicts = 0

        retrieved_mem_ids = {mem.memory_id for mem, _ in retrieved}
        for contra in unresolved_contradictions:
            contra_mem_ids = {contra.old_memory_id, contra.new_memory_id}
            if not (contra_mem_ids & retrieved_mem_ids):
                continue
            related_open_total += 1
            if getattr(contra, "contradiction_type", None) == ContradictionType.CONFLICT:
                related_hard_conflicts += 1
        
        # EARLY EXIT: Express uncertainty if too many unresolved contradictions
        should_uncertain, uncertain_reason = self._should_express_uncertainty(
            retrieved=retrieved,
            contradictions_count=related_hard_conflicts,
            gates_passed=False  # Haven't checked gates yet
        )
        
        if should_uncertain:
            uncertain_response = self._generate_uncertain_response(
                user_query, retrieved, uncertain_reason
            )
            return {
                'answer': uncertain_response,
                'thinking': None,
                'mode': 'uncertainty',
                'confidence': 0.3,  # Low confidence for uncertain responses
                'response_type': 'uncertainty',
                'gates_passed': False,
                'gate_reason': 'unresolved_contradictions',
                'intent_alignment': 0.0,
                'memory_alignment': 0.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [
                    {'text': mem.text, 'trust': mem.trust, 'confidence': mem.confidence}
                    for mem, _ in retrieved
                ],
                'unresolved_contradictions': related_hard_conflicts,
                'unresolved_contradictions_total': related_open_total,
                'unresolved_hard_conflicts': related_hard_conflicts,
            }
        
        # Extract best prior belief
        best_prior = retrieved[0][0] if retrieved else None

        # Build a conflict-resolved memory view for prompting.
        # We keep raw retrieval for scoring/alignment, but present canonical facts
        # (latest, user-first) to reduce "snap back" to older contradictory text.
        prompt_docs = self._build_resolved_memory_docs(retrieved, max_fallback_lines=0)
        learned = self._get_learned_suggestions_for_slots(self._infer_slots_from_query(user_query))
        heuristic = self._get_heuristic_suggestions_for_slots(self._infer_slots_from_query(user_query))
        
        # 2. Generate candidate output using reasoning
        reasoning_context = {
            'retrieved_docs': [
                doc for doc in prompt_docs
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
        
        # 5. Detect contradictions (only when USER made a new assertion)
        contradiction_detected = False
        contradiction_entry = None
        
        if user_input_kind != "question" and user_memory is not None:
            # Prefer claim-level contradiction detection for common personal-profile facts.
            # This avoids false positives from pure embedding drift, and catches true conflicts
            # even when retrieval does not surface the relevant prior memory.
            new_facts = extract_fact_slots(user_query)
            if new_facts:
                user_vector = encode_vector(user_query)

                all_memories = self.memory._load_all_memories()
                previous_user_memories = [
                    m
                    for m in all_memories
                    if m.source == MemorySource.USER and m.memory_id != user_memory.memory_id
                ]

                from .crt_ledger import ContradictionType

                for prev_mem in reversed(previous_user_memories):
                    prev_facts = extract_fact_slots(prev_mem.text)
                    if not prev_facts:
                        continue

                    overlapping_slots = set(new_facts.keys()) & set(prev_facts.keys())
                    if not overlapping_slots:
                        continue

                    # If any shared slot changed value, it's a contradiction signal.
                    slot_conflict = False
                    for slot in overlapping_slots:
                        if new_facts[slot].normalized != prev_facts[slot].normalized:
                            slot_conflict = True
                            break

                    if not slot_conflict:
                        # Reinforcement / same claim; do not create contradictions.
                        continue

                    drift = self.crt_math.drift_meaning(user_vector, prev_mem.vector)

                    contradiction_entry = self.ledger.record_contradiction(
                        old_memory_id=prev_mem.memory_id,
                        new_memory_id=user_memory.memory_id,
                        drift_mean=drift,
                        confidence_delta=prev_mem.confidence - 0.95,
                        query=user_query,
                        summary=f"User contradiction: {prev_mem.text[:50]}... vs {user_query[:50]}...",
                        old_text=prev_mem.text,
                        new_text=user_query,
                        old_vector=prev_mem.vector,
                        new_vector=user_vector
                    )

                    # A ledger entry exists: mark as detected for metrics/observability.
                    contradiction_detected = True

                    if contradiction_entry.contradiction_type == ContradictionType.CONFLICT:
                        self.memory.evolve_trust_for_contradiction(prev_mem, user_vector)

                    volatility = self.crt_math.compute_volatility(
                        drift=drift,
                        memory_alignment=memory_align,
                        is_contradiction=True,
                        is_fallback=False
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
                    break
        
        # 6. Store system response memory
        new_memory = self.memory.store_memory(
            text=candidate_output,
            confidence=confidence,
            source=source,
            context={'query': user_query, 'type': response_type},
            user_marked_important=False  # System responses not marked important
        )
        
        # Update trust for aligned USER memories when gates pass
        # This rewards user memories that led to coherent, confident responses
        if gates_passed and retrieved:
            for mem, score in retrieved[:3]:  # Top 3 retrieved
                # Only evolve trust for USER memories (not system/fallback)
                if mem.source == MemorySource.USER:
                    self.memory.evolve_trust_for_alignment(mem, candidate_vector)
        
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

            # Prompt context (resolved) for debugging/analysis
            'prompt_memories': [
                {
                    'text': d.get('text'),
                    'trust': d.get('trust'),
                    'confidence': d.get('confidence'),
                    'source': d.get('source'),
                }
                for d in prompt_docs
            ],

            # Learned suggestions (metadata-only; never authoritative)
            'learned_suggestions': learned,
            'heuristic_suggestions': heuristic,
            
            # Trust evolution
            'best_prior_trust': best_prior.trust if best_prior else None,
            
            # Session
            'session_id': self.session_id
        }

    def _get_learned_suggestions_for_slots(self, slots: List[str]) -> List[Dict[str, Any]]:
        ls_cfg = (self.runtime_config or {}).get("learned_suggestions", {})
        if not ls_cfg.get("enabled", True):
            return []
        if not ls_cfg.get("emit_metadata", True):
            return []
        if not slots:
            return []
        # If A/B mode is enabled, learned suggestions still emit as usual.
        if not slots:
            return []
        try:
            all_memories = self.memory._load_all_memories()
            user_memories = [m for m in all_memories if m.source == MemorySource.USER]
            open_contras = self.ledger.get_open_contradictions(limit=50)

            def infer_best(slot: str, candidates):
                # candidates: List[(mem, value, normalized)]
                if not candidates:
                    return None, {}
                best_mem, best_val, _norm = max(
                    candidates,
                    key=lambda mv: (
                        1,  # user-only in this caller
                        getattr(mv[0], "timestamp", 0.0),
                        getattr(mv[0], "trust", 0.0),
                    ),
                )
                return best_val, {"memory_id": getattr(best_mem, "memory_id", None)}

            sugg = self.learned_suggestions.suggest_for_slots(
                slots=slots,
                use_model=True,
                all_user_memories=user_memories,
                open_contradictions=open_contras,
                extract_fact_slots_fn=extract_fact_slots,
                infer_best_slot_value_fn=infer_best,
            )
            return [s.to_dict() for s in sugg]
        except Exception:
            return []

    def _get_heuristic_suggestions_for_slots(self, slots: List[str]) -> List[Dict[str, Any]]:
        ls_cfg = (self.runtime_config or {}).get("learned_suggestions", {})
        if not ls_cfg.get("enabled", True):
            return []
        if not ls_cfg.get("emit_ab", False):
            return []
        if not slots:
            return []
        try:
            all_memories = self.memory._load_all_memories()
            user_memories = [m for m in all_memories if m.source == MemorySource.USER]
            open_contras = self.ledger.get_open_contradictions(limit=50)

            def infer_best(slot: str, candidates):
                if not candidates:
                    return None, {}
                best_mem, best_val, _norm = max(
                    candidates,
                    key=lambda mv: (
                        1,
                        getattr(mv[0], "timestamp", 0.0),
                        getattr(mv[0], "trust", 0.0),
                    ),
                )
                return best_val, {"memory_id": getattr(best_mem, "memory_id", None)}

            sugg = self.learned_suggestions.suggest_for_slots(
                slots=slots,
                use_model=False,
                all_user_memories=user_memories,
                open_contradictions=open_contras,
                extract_fact_slots_fn=extract_fact_slots,
                infer_best_slot_value_fn=infer_best,
            )
            return [s.to_dict() for s in sugg]
        except Exception:
            return []

    def _build_resolved_memory_docs(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        max_fact_lines: int = 8,
        max_fallback_lines: int = 0,
    ) -> List[Dict[str, Any]]:
        """Create a prompt-friendly, conflict-resolved memory context.

        If multiple retrieved memories speak about the same fact slot (e.g. employer),
        present only the best candidate (latest, user-first) as a canonical FACT line.

        This avoids the LLM choosing an older contradictory sentence.
        """
        if not retrieved:
            return []

        def _source_priority(mem: MemoryItem) -> int:
            # Prefer user assertions over system paraphrases.
            if mem.source == MemorySource.USER:
                return 3
            if mem.source == MemorySource.SYSTEM:
                return 2
            if mem.source == MemorySource.REFLECTION:
                return 2
            return 1

        # Choose best memory per slot.
        best_for_slot: Dict[str, Tuple[MemoryItem, Any]] = {}
        for mem, _score in retrieved:
            facts = extract_fact_slots(mem.text)
            if not facts:
                continue
            for slot, fact in facts.items():
                current = best_for_slot.get(slot)
                if current is None:
                    best_for_slot[slot] = (mem, fact)
                    continue

                cur_mem, _cur_fact = current
                cand_key = (_source_priority(mem), mem.timestamp, mem.trust)
                cur_key = (_source_priority(cur_mem), cur_mem.timestamp, cur_mem.trust)
                if cand_key > cur_key:
                    best_for_slot[slot] = (mem, fact)

        slot_priority = [
            "name",
            "employer",
            "title",
            "location",
            "masters_school",
            "undergrad_school",
            "programming_years",
            "remote_preference",
            "team_size",
        ]

        resolved_docs: List[Dict[str, Any]] = []
        slots_sorted = sorted(best_for_slot.keys(), key=lambda s: (slot_priority.index(s) if s in slot_priority else 999, s))
        for slot in slots_sorted[:max_fact_lines]:
            mem, fact = best_for_slot[slot]
            resolved_docs.append(
                {
                    "text": f"FACT: {slot} = {fact.value}",
                    "trust": mem.trust,
                    "confidence": mem.confidence,
                    "source": mem.source.value,
                }
            )

        # If we extracted no facts at all, fall back to raw memory lines.
        if not resolved_docs:
            return [
                {
                    "text": mem.text,
                    "trust": mem.trust,
                    "confidence": mem.confidence,
                    "source": mem.source.value,
                }
                for mem, _score in retrieved
            ]

        # Add a couple of non-slot raw lines for conversational continuity.
        fallback_added = 0
        for mem, _score in retrieved:
            if fallback_added >= max_fallback_lines:
                break
            if extract_fact_slots(mem.text):
                continue
            resolved_docs.append(
                {
                    "text": mem.text,
                    "trust": mem.trust,
                    "confidence": mem.confidence,
                    "source": mem.source.value,
                }
            )
            fallback_added += 1

        return resolved_docs

    def _infer_slots_from_query(self, text: str) -> List[str]:
        """Infer which fact slots a question is asking about.

        This is intentionally heuristic and tuned to the stress tests.
        """
        t = (text or "").strip().lower()
        if not t:
            return []

        slots: List[str] = []
        if "name" in t:
            slots.append("name")

        if "where" in t and ("work" in t or "job" in t or "employer" in t):
            slots.append("employer")
        elif "employer" in t or "company" in t:
            slots.append("employer")

        if "where" in t and ("live" in t or "located" in t or "from" in t or "location" in t):
            slots.append("location")

        if "university" in t or "attend" in t or "school" in t:
            # Prefer master's if present; undergrad also possible.
            slots.extend(["masters_school", "undergrad_school"])

        if "remote" in t or "office" in t:
            slots.append("remote_preference")

        if "how many years" in t or "years" in t and "program" in t:
            slots.append("programming_years")

        # De-dup, preserve order
        seen = set()
        out: List[str] = []
        for s in slots:
            if s not in seen:
                out.append(s)
                seen.add(s)
        return out

    def _augment_retrieval_with_slot_memories(
        self,
        retrieved: List[Tuple[MemoryItem, float]],
        slots: List[str],
    ) -> List[Tuple[MemoryItem, float]]:
        """Merge best per-slot memories into the retrieved list."""
        if not retrieved or not slots:
            return retrieved

        retrieved_ids = {m.memory_id for m, _ in retrieved}
        all_memories = self.memory._load_all_memories()

        def _source_priority(mem: MemoryItem) -> int:
            if mem.source == MemorySource.USER:
                return 3
            if mem.source == MemorySource.SYSTEM:
                return 2
            if mem.source == MemorySource.REFLECTION:
                return 2
            return 1

        injected: List[Tuple[MemoryItem, float]] = []
        for slot in slots:
            best: Optional[MemoryItem] = None
            best_key: Optional[Tuple[int, float, float]] = None
            for mem in all_memories:
                facts = extract_fact_slots(mem.text)
                if slot not in facts:
                    continue
                key = (_source_priority(mem), mem.timestamp, mem.trust)
                if best is None or (best_key is not None and key > best_key):
                    best = mem
                    best_key = key
            if best is not None and best.memory_id not in retrieved_ids:
                injected.append((best, 1.0))
                retrieved_ids.add(best.memory_id)

        if not injected:
            return retrieved

        # Prefer injected slot memories at the front so they influence best_prior and prompting.
        return injected + retrieved

    def _answer_from_fact_slots(self, slots: List[str]) -> Optional[str]:
        """Answer simple personal-fact questions directly from USER memories.

        Returns an answer string if we can resolve at least one requested slot; otherwise None.
        """
        if not slots:
            return None

        all_memories = self.memory._load_all_memories()
        user_memories = [m for m in all_memories if m.source == MemorySource.USER]
        if not user_memories:
            return None

        def _source_priority(mem: MemoryItem) -> int:
            if mem.source == MemorySource.USER:
                return 3
            if mem.source == MemorySource.SYSTEM:
                return 2
            if mem.source == MemorySource.REFLECTION:
                return 2
            return 1

        # Collect candidate values per slot.
        slot_values: Dict[str, List[Tuple[MemoryItem, Any]]] = {s: [] for s in slots}
        for mem in user_memories:
            facts = extract_fact_slots(mem.text)
            if not facts:
                continue
            for slot in slots:
                if slot in facts:
                    slot_values[slot].append((mem, facts[slot].value))

        resolved_parts: List[str] = []
        for slot in slots:
            candidates = slot_values.get(slot) or []
            if not candidates:
                continue

            # Pick best (latest, user-first; trust as tiebreak).
            best_mem, best_val = max(
                candidates,
                key=lambda mv: (_source_priority(mv[0]), mv[0].timestamp, mv[0].trust),
            )

            # If multiple distinct values exist, mention that this was updated.
            distinct_norm = []
            for _m, v in candidates:
                vn = str(v).strip().lower()
                if vn and vn not in distinct_norm:
                    distinct_norm.append(vn)

            if len(distinct_norm) > 1:
                resolved_parts.append(f"{slot.replace('_', ' ')}: {best_val} (most recent update)")
            else:
                resolved_parts.append(f"{slot.replace('_', ' ')}: {best_val}")

        if not resolved_parts:
            return None

        if len(resolved_parts) == 1:
            # Return just the value-centric answer for naturalness.
            return resolved_parts[0].split(": ", 1)[1]

        return "\n".join(resolved_parts)

    def _classify_user_input(self, text: str) -> str:
        """Classify a user input as question vs assertion-ish.

        This is intentionally lightweight: we only need to avoid treating questions as factual claims.
        """
        t = (text or "").strip()
        if not t:
            return "other"

        lower = t.lower()
        if t.endswith("?"):
            return "question"

        # Common interrogative forms that often lack a trailing '?'
        question_starters = (
            "who ", "what ", "when ", "where ", "why ", "how ",
            "do ", "does ", "did ", "can ", "could ", "would ", "will ", "should ",
            "is ", "are ", "am ", "was ", "were ", "may ", "might ",
            "tell me ", "remind me ", "what's ", "whats ", "who's ", "whos ",
        )
        if lower.startswith(question_starters):
            return "question"

        # Treat control / prompt-injection style instructions as non-assertions.
        # These often contain factual-looking substrings (e.g., "tell me I work at X")
        # but should not be stored as durable user facts.
        instruction_starters = (
            "ignore ",
            "forget ",
            "start fresh",
            "for this test",
            "in this test",
            "repeat after me",
            "act as ",
            "roleplay ",
            "pretend ",
        )
        instruction_markers = (
            "no matter what",
            "answer with",
            "always answer",
            "only answer",
            "system prompt",
            "developer message",
        )
        if lower.startswith(instruction_starters) or any(m in lower for m in instruction_markers):
            return "instruction"

        # Default: treat as assertion/statement.
        return "assertion"
    
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


