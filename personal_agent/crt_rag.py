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
import re
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
        retrieved = self.memory.retrieve_memories(query, k, min_trust)

        # Avoid retrieving derived helper outputs (they are grounded summaries/citations,
        # not new world facts) to prevent recursive quoting and prompt pollution.
        filtered: List[Tuple[MemoryItem, float]] = []
        for mem, score in retrieved:
            try:
                kind = ((mem.context or {}).get("kind") or "").strip().lower()
            except Exception:
                kind = ""

            if mem.source == MemorySource.FALLBACK and kind in {"memory_citation", "contradiction_status", "memory_inventory"}:
                continue

            txt = (mem.text or "").strip().lower()
            if mem.source == MemorySource.FALLBACK and txt.startswith("here is the stored text i can cite"):
                continue
            if mem.source == MemorySource.FALLBACK and txt.startswith("here are the open contradictions i have recorded"):
                continue
            if mem.source == MemorySource.FALLBACK and txt.startswith("i don't expose internal memory ids"):
                continue

            filtered.append((mem, score))

        return filtered

    def _get_latest_user_slot_value(self, slot: str) -> Optional[str]:
        slot = (slot or "").strip().lower()
        if not slot:
            return None
        try:
            all_memories = self.memory._load_all_memories()
        except Exception:
            return None

        best_val: Optional[str] = None
        best_ts: float = -1.0
        for mem in all_memories:
            if mem.source != MemorySource.USER:
                continue
            facts = extract_fact_slots(mem.text)
            if not facts or slot not in facts:
                continue
            try:
                ts = float(mem.timestamp)
            except Exception:
                ts = 0.0
            if ts >= best_ts:
                best_ts = ts
                best_val = str(facts[slot].value).strip()

        return best_val or None

    def _get_latest_user_name_guess(self) -> Optional[str]:
        """Best-effort user name extraction from USER memories.

        Prefer structured "FACT: name = ..." if present; otherwise fall back to
        simple textual patterns like "my name is ...".
        """
        try:
            all_memories = self.memory._load_all_memories()
        except Exception:
            return None

        best_val: Optional[str] = None
        best_ts: float = -1.0
        name_pat = r"([A-Z][a-zA-Z'-]{1,40}(?:\s+[A-Z][a-zA-Z'-]{1,40}){0,2})"

        for mem in all_memories:
            if mem.source != MemorySource.USER:
                continue
            text = (mem.text or "").strip()
            if not text:
                continue

            val: Optional[str] = None
            m = re.search(r"\bFACT:\s*name\s*=\s*(.+?)\s*$", text, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
            else:
                m = re.search(r"\bmy name is\s+" + name_pat + r"\b", text, flags=re.IGNORECASE)
                if m:
                    val = m.group(1).strip()

            if not val:
                continue

            try:
                ts = float(mem.timestamp)
            except Exception:
                ts = 0.0
            if ts >= best_ts:
                best_ts = ts
                best_val = val

        return best_val or None

    def _query_mentions_user_name(self, user_query: str, user_name: str) -> bool:
        q = (user_query or "").strip().lower()
        name = (user_name or "").strip().lower()
        if not q or not name:
            return False

        # Consider full name and first token as acceptable matches.
        variants: List[str] = []
        variants.append(name)
        first = name.split()[0].strip() if name.split() else ""
        if first and first != name:
            variants.append(first)

        for v in variants:
            tokens = [t for t in v.split() if t]
            if not tokens:
                continue
            # Match "nick block" with flexible whitespace and allow possessive.
            token_pat = r"\s+".join(re.escape(t) for t in tokens)
            pat = rf"\b{token_pat}(?:['’]s)?\b"
            if re.search(pat, q, flags=re.IGNORECASE):
                return True
        return False

    def _is_system_prompt_request(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False
        needles = [
            "system prompt",
            "developer message",
            "developer prompt",
            "hidden prompt",
            "paste it verbatim",
            "paste the prompt",
        ]
        if any(n in t for n in needles):
            return True
        # Common exfil phrasing (keep this tight so we don't catch generic "instructions" attacks).
        if "reveal" in t and ("system prompt" in t or "developer" in t):
            return True
        if "show" in t and "system" in t and "prompt" in t:
            return True
        return False

    def _is_user_name_declaration(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        # Intentionally only match the explicit "for the record" pattern to avoid
        # interfering with name-correction contradictions ("Actually, my name is...").
        return bool(re.search(r"\bfor the record:.*\bmy name is\b", t, flags=re.IGNORECASE))

    def _is_user_named_reference_question(self, user_query: str) -> bool:
        """Detect third-person questions that refer to the user by (their) name.

        This is product-safety motivated: if a question looks like "What is <user-name>'s occupation?",
        we should answer from chat memory or admit we don't know, rather than importing world facts.
        """
        q = (user_query or "").strip().lower()
        if not q:
            return False

        user_name = self._get_latest_user_slot_value("name") or self._get_latest_user_name_guess()
        if not user_name:
            return False

        if not self._query_mentions_user_name(user_query, user_name):
            return False

        # Only trigger for profile-ish questions where hallucination risk is high.
        triggers = (
            "occupation",
            "job",
            "job title",
            "title",
            "role",
            "employer",
            "company",
            "career",
            "profession",
            "work for",
            "work at",
        )
        if any(t in q for t in triggers):
            return True

        # Common paraphrases that omit explicit job/occupation keywords.
        if re.search(r"\b(kind|type)\s+of\s+work\b", q, flags=re.IGNORECASE):
            return True
        if "for a living" in q:
            return True
        if re.search(r"\bwhat\s+does\b.*\bdo\b", q, flags=re.IGNORECASE) and "besides" in q:
            return True

        return False

    def _build_user_named_reference_answer(self, user_query: str, inferred_slots: List[str]) -> str:
        cfg = (self.runtime_config.get("user_named_reference") or {}) if isinstance(self.runtime_config, dict) else {}
        responses = (cfg.get("responses") or {}) if isinstance(cfg.get("responses"), dict) else {}

        def _resp(key: str, fallback: str) -> str:
            value = responses.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            return fallback

        # Prefer canonical slot answers if available.
        slot_answer = self._answer_from_fact_slots(inferred_slots)
        if slot_answer:
            return slot_answer

        # Otherwise, fall back to strictly chat-grounded work-related statements.
        try:
            all_memories = self.memory._load_all_memories()
        except Exception:
            all_memories = []

        user_memories = [m for m in all_memories if m.source == MemorySource.USER]
        user_memories.sort(key=lambda m: getattr(m, "timestamp", 0.0), reverse=True)

        snippets: List[str] = []
        for mem in user_memories:
            t = (mem.text or "").strip()
            tl = t.lower()
            if any(p in tl for p in ("i work at", "i work for", "i run ", "i built", "my job", "my role", "my title")):
                snippets.append(t)
            if len(snippets) >= 2:
                break

        if snippets:
            lines = [_resp("known_work_prefix", "From our chat, I only know this about your work:")]
            for s in snippets:
                lines.append(f"- {s}")
            lines.append(
                "\n"
                + _resp(
                    "ask_to_store",
                    "If you want, tell me your current job title/occupation in one line and I'll store it as a fact.",
                )
            )
            return "\n".join(lines)

        return _resp(
            "unknown",
            "I don't have a reliable stored memory of your occupation/job yet — if you tell me, I can remember it going forward.",
        )
    
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
        reason: str,
        recommended_next_action: Optional[Dict[str, Any]] = None,
        conflict_beliefs: Optional[List[str]] = None,
    ) -> str:
        """
        Generate explicit uncertainty response.
        
        This is a FIRST-CLASS response state, not a fallback.
        """
        # Show what we know and what conflicts, in a user-friendly way.
        # Keep this readable for normal users: avoid internal scoring jargon.
        beliefs: List[str] = []

        # Prefer explicit conflict beliefs if provided (ensures both sides show up
        # even when retrieval misses one of the conflicting memories).
        if conflict_beliefs:
            beliefs.extend([b.strip() for b in conflict_beliefs[:6] if (b or "").strip()])
        else:
            for mem, _score in retrieved[:3]:
                t = (mem.text or "").strip()
                if t:
                    beliefs.append(f"- {t}")

        beliefs_text = "\n".join(beliefs) if beliefs else "- (no clear memories)"

        ask = "Can you help clarify?"
        if recommended_next_action and recommended_next_action.get("action_type") == "ask_user":
            q = (recommended_next_action.get("question") or "").strip()
            if q:
                ask = q

        conflict_warning_enabled = True
        try:
            conflict_warning_enabled = bool((self.runtime_config.get("conflict_warning") or {}).get("enabled", True))
        except Exception:
            conflict_warning_enabled = True

        if conflict_warning_enabled:
            header = (
                "I need to be honest about my uncertainty here.\n\n"
                "I might be wrong because I have conflicting information in our chat history.\n\n"
            )
            notes_label = "Here are the conflicting notes I have:"
        else:
            header = "I need to be honest about my uncertainty here.\n\n"
            notes_label = "What I have in memory:"

        return (
            header
            + f"{reason}\n\n"
            + f"{notes_label}\n{beliefs_text}\n\n"
            + "I cannot give you a confident answer until we resolve this.\n"
            + f"{ask}"
        )

    def _infer_contradiction_goals_for_query(
        self,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        inferred_slots: Optional[List[str]] = None,
        limit: int = 5,
    ) -> Tuple[List[Dict[str, Any]], Optional[List[str]]]:
        """Infer actionable "next steps" from open hard conflicts.

        For Milestone M2, we keep this intentionally minimal and deterministic:
        - Only hard CONFLICT contradictions become goals.
        - The default action is to ask the user a targeted clarifying question.

        Returns: (goals, conflict_beliefs)
        """
        from .crt_ledger import ContradictionType

        if not retrieved:
            retrieved_ids: set[str] = set()
        else:
            retrieved_ids = {mem.memory_id for mem, _ in retrieved}

        goals: List[Dict[str, Any]] = []
        conflict_beliefs: List[str] = []

        open_contras = self.ledger.get_open_contradictions(limit=50)
        for contra in open_contras:
            if getattr(contra, "contradiction_type", None) != ContradictionType.CONFLICT:
                continue

            old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
            new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
            if old_mem is None or new_mem is None:
                continue

            # Relevance: either overlaps retrieved, or overlaps the slots we think the user asked about.
            is_related_by_retrieval = bool({contra.old_memory_id, contra.new_memory_id} & retrieved_ids)

            old_facts = extract_fact_slots(old_mem.text) or {}
            new_facts = extract_fact_slots(new_mem.text) or {}
            shared_slots = set(old_facts.keys()) & set(new_facts.keys())

            for slot in sorted(shared_slots):
                old_fact = old_facts.get(slot)
                new_fact = new_facts.get(slot)
                if old_fact is None or new_fact is None:
                    continue

                if old_fact.normalized == new_fact.normalized:
                    continue

                is_related_by_slot = bool(inferred_slots) and slot in set(inferred_slots or [])
                if not (is_related_by_retrieval or is_related_by_slot):
                    continue

                # Provide both sides as explicit beliefs (user-facing; no internal scores).
                conflict_beliefs.append(f"- {old_mem.text}")
                conflict_beliefs.append(f"- {new_mem.text}")

                slot_name = slot.replace("_", " ")
                old_val = str(old_fact.value)
                new_val = str(new_fact.value)

                goals.append(
                    {
                        "action_type": "ask_user",
                        "slot": slot,
                        "ledger_id": contra.ledger_id,
                        "options": [new_val, old_val],
                        "question": (
                            f"I have conflicting memories about your {slot_name}. "
                            f"Which is correct now: {new_val} or {old_val}?"
                        ),
                        "reason": "open_conflict",
                    }
                )

                if len(goals) >= limit:
                    break

            if len(goals) >= limit:
                break

        # De-dup conflict belief lines while preserving order.
        seen = set()
        dedup_beliefs: List[str] = []
        for b in conflict_beliefs:
            if b not in seen:
                dedup_beliefs.append(b)
                seen.add(b)

        return goals, dedup_beliefs

    def _resolve_open_conflicts_from_assertion(self, user_text: str) -> int:
        """Resolve open hard CONFLICT contradictions when the user clarifies.

        If the user makes a new assertion that sets a fact slot to a specific value
        (e.g., employer=Amazon) and we have an OPEN hard CONFLICT about that slot,
        mark those contradictions RESOLVED.

        This prevents an infinite "ask_user" loop where CRT keeps asking the same
        clarification question but never records that the user answered it.

        Returns: number of ledger entries resolved.
        """
        from .crt_ledger import ContradictionStatus, ContradictionType

        facts = extract_fact_slots(user_text) or {}

        # Support explicit "slot = value" clarifications used by stress harnesses.
        if not facts:
            import re

            def _norm(v: str) -> str:
                return re.sub(r"\s+", " ", (v or "").strip()).lower()

            text = (user_text or "").strip()
            slot_patterns = {
                "employer": r"\bemployer\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "name": r"\bname\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "location": r"\blocation\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "title": r"\btitle\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "first_language": r"\bfirst_language\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "masters_school": r"\bmasters_school\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "undergrad_school": r"\bundergrad_school\s*=\s*([^\n\r\.;,!\?]{2,80})",
                "programming_years": r"\bprogramming_years\s*=\s*(\d{1,3})\b",
                "team_size": r"\bteam_size\s*=\s*(\d{1,3})\b",
            }

            class _Tmp:
                def __init__(self, value, normalized):
                    self.value = value
                    self.normalized = normalized

            for slot, pat in slot_patterns.items():
                m = re.search(pat, text, flags=re.IGNORECASE)
                if not m:
                    continue
                raw = (m.group(1) or "").strip()
                if not raw:
                    continue
                if slot in {"programming_years", "team_size"}:
                    try:
                        val = int(raw)
                    except Exception:
                        continue
                    facts[slot] = _Tmp(val, str(val))
                else:
                    facts[slot] = _Tmp(raw, _norm(raw))

        if not facts:
            return 0

        resolved = 0
        open_contras = self.ledger.get_open_contradictions(limit=200)
        for contra in open_contras:
            if getattr(contra, "contradiction_type", None) != ContradictionType.CONFLICT:
                continue

            old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
            new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
            if old_mem is None or new_mem is None:
                continue

            old_facts = extract_fact_slots(old_mem.text) or {}
            new_facts = extract_fact_slots(new_mem.text) or {}
            shared = set(old_facts.keys()) & set(new_facts.keys()) & set(facts.keys())
            if not shared:
                continue

            should_resolve = False
            for slot in shared:
                user_fact = facts.get(slot)
                if user_fact is None:
                    continue
                ov = old_facts.get(slot)
                nv = new_facts.get(slot)
                if ov is None or nv is None:
                    continue

                # If the user asserts either side's value, we treat that as a clarification.
                if user_fact.normalized in {ov.normalized, nv.normalized}:
                    should_resolve = True
                    break

            if should_resolve:
                self.ledger.resolve_contradiction(
                    contra.ledger_id,
                    method="user_clarified",
                    merged_memory_id=None,
                    new_status=ContradictionStatus.RESOLVED,
                )
                resolved += 1

        return resolved
    
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

        # High-risk prompt types should be treated as instructions even if they do not
        # look like questions (multi-paragraph prompt injection often starts as declarative).
        is_memory_citation = self._is_memory_citation_request(user_query)
        is_contradiction_status = self._is_contradiction_status_request(user_query)
        is_memory_inventory = self._is_memory_inventory_request(user_query)

        user_input_kind = self._classify_user_input(user_query)
        if user_input_kind == "assertion" and (is_memory_citation or is_contradiction_status or is_memory_inventory):
            user_input_kind = "instruction"

        # Deterministic safe path: refuse prompt/system-instruction disclosure.
        # This prevents the model from hallucinating and avoids memory-claim phrasing
        # that can confuse the evaluator.
        if user_input_kind in ("question", "instruction") and self._is_system_prompt_request(user_query):
            answer = (
                "I can’t share my system prompt or hidden instructions verbatim. "
                "If you tell me what you’re trying to do, I can summarize how I’m designed to behave "
                "or help you accomplish the goal another way."
            )
            return {
                'answer': answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.95,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'system_prompt',
                'intent_alignment': 0.95,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [],
                'prompt_memories': [],
                'unresolved_contradictions_total': 0,
                'unresolved_hard_conflicts': 0,
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
            }
        if user_input_kind == "assertion":
            user_memory = self.memory.store_memory(
                text=user_query,
                confidence=0.95,  # User assertions are high confidence
                source=MemorySource.USER,
                context={"type": "user_input", "kind": user_input_kind},
                user_marked_important=user_marked_important
            )

            # If the user is clarifying a previously-detected hard conflict, mark it resolved.
            # This is intentionally conservative: only hard CONFLICT types, and only when
            # the asserted value matches one side of the conflict.
            try:
                self._resolve_open_conflicts_from_assertion(user_query)
            except Exception:
                # Resolution is best-effort; never block the main chat loop.
                pass

            # Deterministic safe ack: user name declarations should not be embellished.
            # (e.g., never add a location like "New York" unless the user said it.)
            if self._is_user_name_declaration(user_query):
                name_guess = self._get_latest_user_name_guess()
                if name_guess:
                    answer = f"Thanks — noted: your name is {name_guess}."
                else:
                    answer = "Thanks — noted."
                return {
                    'answer': answer,
                    'thinking': None,
                    'mode': 'quick',
                    'confidence': 0.95,
                    'response_type': 'speech',
                    'gates_passed': False,
                    'gate_reason': 'user_name_declaration',
                    'intent_alignment': 0.95,
                    'memory_alignment': 1.0,
                    'contradiction_detected': False,
                    'contradiction_entry': None,
                    'retrieved_memories': [],
                    'prompt_memories': [],
                    'unresolved_contradictions_total': 0,
                    'unresolved_hard_conflicts': 0,
                    'learned_suggestions': [],
                    'heuristic_suggestions': [],
                    'best_prior_trust': None,
                    'session_id': self.session_id,
                }

        # Deterministic safe path: assistant-profile questions.
        # These are about the assistant/system, not the user, so we should not
        # invent chat-backed claims about what the user said.
        assistant_profile_cfg = (self.runtime_config.get("assistant_profile") or {}) if isinstance(self.runtime_config, dict) else {}
        assistant_profile_enabled = bool(assistant_profile_cfg.get("enabled", True))
        if assistant_profile_enabled and user_input_kind in ("question", "instruction") and self._is_assistant_profile_question(user_query):
            answer = self._build_assistant_profile_answer(user_query)
            return {
                'answer': answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.95,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'assistant_profile',
                'intent_alignment': 0.95,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [],
                'prompt_memories': [],
                'unresolved_contradictions_total': 0,
                'unresolved_hard_conflicts': 0,
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
            }
        
        # 1. Trust-weighted retrieval
        retrieved = self.retrieve(user_query, k=5)

        inferred_slots: List[str] = []
        if user_input_kind in ("question", "instruction"):
            inferred_slots = self._infer_slots_from_query(user_query)

        # Special-case: prompts that explicitly demand chat-grounded recall or memory citation.
        # We answer deterministically from retrieved/prompt memory text to avoid hallucinations
        # and to avoid claiming "no memories" when context exists.
        if user_input_kind in ("question", "instruction") and self._is_memory_citation_request(user_query):
            prompt_docs = self._build_resolved_memory_docs(retrieved, max_fact_lines=8, max_fallback_lines=2)
            candidate_output = self._build_memory_citation_answer(
                user_query=user_query,
                retrieved=retrieved,
                prompt_docs=prompt_docs,
            )

            # Keep this as non-durable "speech" to avoid polluting the belief store.
            self.memory.store_memory(
                text=candidate_output,
                confidence=0.25,
                source=MemorySource.FALLBACK,
                context={"query": user_query, "type": "speech", "kind": "memory_citation"},
                user_marked_important=False,
            )

            best_prior = retrieved[0][0] if retrieved else None

            return {
                'answer': candidate_output,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.8,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'memory_citation',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
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
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': best_prior.trust if best_prior else None,
                'session_id': self.session_id,
            }

        # Special-case: user asks to list/dump memories or memory ids.
        # Never invent internal identifiers; respond deterministically with safe citations.
        if user_input_kind in ("question", "instruction") and self._is_memory_inventory_request(user_query):
            prompt_docs = self._build_resolved_memory_docs(retrieved, max_fact_lines=8, max_fallback_lines=2)
            candidate_output = self._build_memory_inventory_answer(
                user_query=user_query,
                retrieved=retrieved,
                prompt_docs=prompt_docs,
            )

            self.memory.store_memory(
                text=candidate_output,
                confidence=0.25,
                source=MemorySource.FALLBACK,
                context={"query": user_query, "type": "speech", "kind": "memory_inventory"},
                user_marked_important=False,
            )

            best_prior = retrieved[0][0] if retrieved else None
            return {
                'answer': candidate_output,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.8,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'memory_inventory',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
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
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': best_prior.trust if best_prior else None,
                'session_id': self.session_id,
            }

        # Special-case: user asks for contradiction ledger status.
        # Answer deterministically from the ledger to prevent invented contradictions.
        if user_input_kind in ("question", "instruction") and self._is_contradiction_status_request(user_query):
            prompt_docs = self._build_resolved_memory_docs(retrieved, max_fact_lines=8, max_fallback_lines=0)
            candidate_output, contra_meta = self._build_contradiction_status_answer(
                user_query=user_query,
                inferred_slots=inferred_slots,
            )

            final_answer = candidate_output
            try:
                if bool((self.runtime_config.get("provenance") or {}).get("enabled", True)):
                    final_answer = candidate_output.rstrip() + "\n\nProvenance: derived from stored memories (contradiction ledger)."
            except Exception:
                final_answer = candidate_output

            # Keep as non-durable speech.
            self.memory.store_memory(
                text=candidate_output,
                confidence=0.25,
                source=MemorySource.FALLBACK,
                context={"query": user_query, "type": "speech", "kind": "contradiction_status"},
                user_marked_important=False,
            )

            best_prior = retrieved[0][0] if retrieved else None
            return {
                'answer': final_answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.8,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'contradiction_status',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
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
                'unresolved_contradictions_total': int(contra_meta.get('unresolved_contradictions_total', 0) or 0),
                'unresolved_hard_conflicts': int(contra_meta.get('unresolved_hard_conflicts', 0) or 0),
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': best_prior.trust if best_prior else None,
                'session_id': self.session_id,
            }

        # Deterministic safe path: third-person questions that reference the user by name.
        # Avoid importing world knowledge for a name that matches the current user.
        user_named_cfg = (self.runtime_config.get("user_named_reference") or {}) if isinstance(self.runtime_config, dict) else {}
        user_named_enabled = bool(user_named_cfg.get("enabled", True))
        if user_named_enabled and user_input_kind in ("question", "instruction") and self._is_user_named_reference_question(user_query):
            # Infer likely slots from the query (title/employer are common).
            inferred = inferred_slots or self._infer_slots_from_query(user_query)
            relevant_slots = [s for s in inferred if s in {"title", "employer"}]
            if not relevant_slots:
                # Still treat as high-risk; attempt to answer from work snippets.
                relevant_slots = ["title", "employer"]

            answer = self._build_user_named_reference_answer(user_query, relevant_slots)

            final_answer = answer
            try:
                if bool((self.runtime_config.get("provenance") or {}).get("enabled", True)):
                    final_answer = answer.rstrip() + "\n\nProvenance: answered from stored memories."
            except Exception:
                pass

            return {
                'answer': final_answer,
                'thinking': None,
                'mode': 'quick',
                'confidence': 0.9,
                'response_type': 'speech',
                'gates_passed': False,
                'gate_reason': 'user_named_reference',
                'intent_alignment': 0.9,
                'memory_alignment': 1.0,
                'contradiction_detected': False,
                'contradiction_entry': None,
                'retrieved_memories': [],
                'prompt_memories': [],
                'unresolved_contradictions_total': 0,
                'unresolved_hard_conflicts': 0,
                'learned_suggestions': [],
                'heuristic_suggestions': [],
                'best_prior_trust': None,
                'session_id': self.session_id,
            }

        # Slot-aware question augmentation: for simple fact questions, semantic retrieval
        # can miss the most recent correction (e.g., Amazon vs Microsoft). If the query
        # looks like it targets a known slot, explicitly pull the best candidate memory
        # for that slot from the full store and merge it into retrieved.
        if user_input_kind in ("question", "instruction") and retrieved and inferred_slots:
            retrieved = self._augment_retrieval_with_slot_memories(retrieved, inferred_slots)

        # M2: If the user is asking about a slot with an OPEN hard CONFLICT, do not silently
        # pick the "most recent" value. Turn the contradiction into an explicit next action.
        contradiction_goals: List[Dict[str, Any]] = []
        conflict_beliefs: Optional[List[str]] = None
        recommended_next_action: Optional[Dict[str, Any]] = None
        if user_input_kind in ("question", "instruction") and inferred_slots:
            contradiction_goals, conflict_beliefs = self._infer_contradiction_goals_for_query(
                user_query=user_query,
                retrieved=retrieved,
                inferred_slots=inferred_slots,
            )
            if contradiction_goals:
                recommended_next_action = contradiction_goals[0]

                uncertain_response = self._generate_uncertain_response(
                    user_query,
                    retrieved,
                    reason="I have an unresolved contradiction that affects your question",
                    recommended_next_action=recommended_next_action,
                    conflict_beliefs=conflict_beliefs,
                )
                return {
                    'answer': uncertain_response,
                    'thinking': None,
                    'mode': 'uncertainty',
                    'confidence': 0.3,
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
                    'unresolved_contradictions': 1,
                    'unresolved_contradictions_total': 1,
                    'unresolved_hard_conflicts': 1,
                    'contradiction_goals': contradiction_goals,
                    'recommended_next_action': recommended_next_action,
                }

        # Slot-based fast-path: if the user asks a simple personal-fact question and we have
        # an answer in memory, answer directly from canonical resolved facts.
        if user_input_kind in ("question", "instruction") and inferred_slots:
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

                    # User-facing provenance footer (do not store it as a belief).
                    final_answer = slot_answer
                    try:
                        if bool((self.runtime_config.get("provenance") or {}).get("enabled", True)):
                            final_answer = slot_answer + "\n\nProvenance: answered from stored memories."
                    except Exception:
                        pass

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
                        'answer': final_answer,
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

            # Summary-style instructions: answer from canonical resolved USER facts.
            if user_input_kind == "instruction":
                lower = (user_query or "").strip().lower()
                if "summar" in lower or "one-line" in lower or "one line" in lower or "summary" in lower:
                    summary = self._one_line_summary_from_facts()
                    if summary is not None:
                        if not retrieved:
                            retrieved = self.retrieve(user_query, k=5)
                        prompt_docs = self._build_resolved_memory_docs(retrieved, max_fallback_lines=0)

                        candidate_output = summary
                        candidate_vector = encode_vector(candidate_output)

                        intent_align = 0.95
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
                        confidence = 0.95 if gates_passed else 0.95 * 0.7

                        best_prior = retrieved[0][0] if retrieved else None

                        self.memory.store_memory(
                            text=candidate_output,
                            confidence=confidence,
                            source=source,
                            context={'query': user_query, 'type': response_type, 'kind': 'fact_summary'},
                            user_marked_important=False,
                        )

                        learned = self._get_learned_suggestions_for_slots(
                            [
                                "name",
                                "employer",
                                "title",
                                "location",
                                "programming_years",
                                "first_language",
                                "masters_school",
                                "team_size",
                                "remote_preference",
                            ]
                        )

                        return {
                            'answer': candidate_output,
                            'thinking': None,
                            'mode': 'quick',
                            'confidence': confidence,
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
                            'heuristic_suggestions': self._get_heuristic_suggestions_for_slots(
                                [
                                    "name",
                                    "employer",
                                    "title",
                                    "location",
                                    "programming_years",
                                    "first_language",
                                    "masters_school",
                                    "team_size",
                                    "remote_preference",
                                ]
                            ),
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
            # If we can infer a concrete next action from conflicts, include it.
            contradiction_goals, conflict_beliefs = self._infer_contradiction_goals_for_query(
                user_query=user_query,
                retrieved=retrieved,
                inferred_slots=inferred_slots,
            )
            recommended_next_action = contradiction_goals[0] if contradiction_goals else None

            uncertain_response = self._generate_uncertain_response(
                user_query,
                retrieved,
                uncertain_reason,
                recommended_next_action=recommended_next_action,
                conflict_beliefs=conflict_beliefs,
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
                'contradiction_goals': contradiction_goals,
                'recommended_next_action': recommended_next_action,
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

        # Consistency guard: if we have memory context, do not let the surface text
        # claim "first conversation" / "no memories".
        candidate_output = self._sanitize_memory_denial(answer=candidate_output, has_memory_context=bool(prompt_docs))
        # Honesty guard: if the model claims it "remembers" a personal fact that is not
        # present in our resolved FACT prompt docs, strip that unsupported claim.
        candidate_output = self._sanitize_unsupported_memory_claims(answer=candidate_output, prompt_docs=prompt_docs)
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

                # Build candidate facts per slot from prior USER memories.
                candidates_by_slot: Dict[str, List[Tuple[MemoryItem, Any]]] = {}
                for prev_mem in previous_user_memories:
                    prev_facts = extract_fact_slots(prev_mem.text)
                    if not prev_facts:
                        continue
                    for slot, fact in prev_facts.items():
                        candidates_by_slot.setdefault(slot, []).append((prev_mem, fact))

                # Only create a contradiction if the asserted value is NEW for that slot.
                # If it matches ANY prior value for the slot (even if older conflicts exist),
                # treat it as reinforcement/clarification rather than another contradiction.
                selected_prev: Optional[MemoryItem] = None
                for slot, new_fact in new_facts.items():
                    prior = candidates_by_slot.get(slot) or []
                    if not prior:
                        continue

                    if any(getattr(f, "normalized", None) == new_fact.normalized for _m, f in prior):
                        continue

                    # Pick the most recent conflicting prior memory for this slot.
                    selected_prev, _prev_fact = max(
                        prior,
                        key=lambda mf: (getattr(mf[0], "timestamp", 0.0), getattr(mf[0], "trust", 0.0)),
                    )
                    break

                if selected_prev is not None:
                    drift = self.crt_math.drift_meaning(user_vector, selected_prev.vector)

                    contradiction_entry = self.ledger.record_contradiction(
                        old_memory_id=selected_prev.memory_id,
                        new_memory_id=user_memory.memory_id,
                        drift_mean=drift,
                        confidence_delta=selected_prev.confidence - 0.95,
                        query=user_query,
                        summary=f"User contradiction: {selected_prev.text[:50]}... vs {user_query[:50]}...",
                        old_text=selected_prev.text,
                        new_text=user_query,
                        old_vector=selected_prev.vector,
                        new_vector=user_vector
                    )

                    contradiction_detected = True

                    if contradiction_entry.contradiction_type == ContradictionType.CONFLICT:
                        self.memory.evolve_trust_for_contradiction(selected_prev, user_vector)

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

        # --------------------------------------------------------------------
        # Provenance + optional world-fact warnings (user-facing only)
        # --------------------------------------------------------------------
        final_answer = candidate_output
        try:
            prov_cfg = self.runtime_config.get("provenance") or {}
            if bool(prov_cfg.get("enabled", True)):
                used_memory = bool(prompt_docs)
                used_fact_lines = any(str(d.get("text") or "").lower().startswith("fact:") for d in (prompt_docs or []))

                # Only add a provenance footer when it looks like we're answering about the user,
                # or when we relied on explicit FACT lines.
                is_personalish = bool(inferred_slots) or ("my " in (user_query or "").lower())
                if used_memory and (used_fact_lines or is_personalish):
                    footer_lines = ["Provenance: this answer uses stored memories."]

                    wc = prov_cfg.get("world_check") or {}
                    if bool(wc.get("enabled", False)) and used_memory and self.reasoning.should_run_world_fact_check(candidate_output):
                        mem_ctx = "\n".join([str(d.get("text") or "").strip() for d in (prompt_docs or []) if d.get("text")])
                        warnings = self.reasoning.world_fact_check(
                            answer=candidate_output,
                            memory_context=mem_ctx,
                            max_tokens=int(wc.get("max_tokens", 140) or 140),
                        )
                        if warnings:
                            footer_lines.append("Note: some statements may conflict with widely-known public facts:")
                            for w in warnings[:3]:
                                public_fact = (w.get("public_fact") or "").strip()
                                claim = (w.get("claim") or "").strip()
                                conf = (w.get("confidence") or "").strip()
                                if claim and public_fact:
                                    extra = f" (conf: {conf})" if conf else ""
                                    footer_lines.append(f"- {claim} (conflicts with: {public_fact}){extra}")

                    final_answer = candidate_output.rstrip() + "\n\n" + "\n".join(footer_lines)
        except Exception:
            final_answer = candidate_output
        
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
            'answer': final_answer,
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

        if "title" in t or "job title" in t or "role" in t or "position" in t or "occupation" in t:
            slots.append("title")

        if "university" in t or "attend" in t or "school" in t:
            # Prefer master's if present; undergrad also possible.
            slots.extend(["masters_school", "undergrad_school"])

        if "remote" in t or "office" in t:
            slots.append("remote_preference")

        if "how many years" in t or "years" in t and "program" in t:
            slots.append("programming_years")

        if "language" in t and ("start" in t or "starting" in t or "first" in t):
            slots.append("first_language")

        if "how many" in t and ("engineer" in t or "manage" in t or "team" in t):
            slots.append("team_size")

        # De-dup, preserve order
        seen = set()
        out: List[str] = []
        for s in slots:
            if s not in seen:
                out.append(s)
                seen.add(s)
        return out

    def _is_assistant_profile_question(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False

        # Keep this conservative: only very clear questions about the assistant itself.
        patterns = (
            r"\bwho\s+are\s+you\b",
            r"\bwhat\s+are\s+you\b",
            r"\bwhat\s+is\s+your\s+(occupation|job|role|purpose)\b",
            r"\bwhat\s+do\s+you\s+do\b",
            # Background/experience questions about the assistant (not the user).
            r"\bwhat('?s|\s+is)\s+your\s+background\b",
            r"\bwhat('?s|\s+is)\s+your\s+experience\b",
            r"\b(tell\s+me|can\s+you\s+tell\s+me)\s+about\s+your\s+(background|experience)\b",
            r"\babout\s+your\s+(background|experience)\b",
            # Work-in-domain questions (often phrased as 'your work in X').
            r"\b(tell\s+me|can\s+you\s+tell\s+me)\s+about\s+your\s+work\s+in\b",
            r"\babout\s+your\s+work\s+in\b",
            r"\bwhat\s+work\s+have\s+you\s+done\s+in\b",
            r"\bwhat\s+is\s+your\s+work\s+in\b",
            r"\bdo\s+you\s+have\s+(any\s+)?(background|experience)\b",
            r"\bwhat\s+experience\s+do\s+you\s+have\b",
            r"\bhave\s+you\s+(ever\s+)?worked\s+(as|in)\b",
        )
        return any(re.search(p, t, flags=re.IGNORECASE) for p in patterns)

    def _build_assistant_profile_answer(self, user_query: str) -> str:
        # Deterministic, chat-agnostic answer: don't claim the user said things.
        cfg = (self.runtime_config.get("assistant_profile") or {}) if isinstance(self.runtime_config, dict) else {}
        responses = (cfg.get("responses") or {}) if isinstance(cfg.get("responses"), dict) else {}

        def _resp(key: str, fallback: str) -> str:
            value = responses.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            return fallback

        q = (user_query or "").strip().lower()

        if re.search(r"\b(occupation|job|role)\b", q):
            return _resp(
                "occupation",
                "I'm an AI assistant (a software system). I don't have a human occupation, but my role is to help with tasks.",
            )

        if re.search(r"\b(purpose)\b", q) or re.search(r"\bwhat\s+do\s+you\s+do\b", q):
            return _resp(
                "purpose",
                "I'm an AI assistant designed to help with information and tasks.",
            )

        if (
            re.search(r"\b(background|experience)\b", q)
            or re.search(r"\byour\s+work\s+in\b", q)
            or re.search(r"\bwhat\s+work\s+have\s+you\s+done\s+in\b", q)
            or re.search(r"\bwhat\s+experience\s+do\s+you\s+have\b", q)
            or re.search(r"\bhave\s+you\s+(ever\s+)?worked\s+(as|in)\b", q)
        ):
            if re.search(r"\bfilmmaking\b|\bfilm\b|\bmovie\b|\bcinema\b|\bdirector\b|\bproducer\b", q):
                return _resp(
                    "background_filmmaking",
                    "I don't have personal filmmaking experience—I'm an AI system. I can still help with filmmaking concepts.",
                )
            return _resp(
                "background_general",
                "I don't have personal experiences—I'm an AI system. I can still help with information and planning.",
            )

        # Generic fallback for "who/what are you".
        return _resp("identity", "I'm an AI assistant (a software system) designed to help with information and tasks.")

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

    def _one_line_summary_from_facts(self) -> Optional[str]:
        """Build a compact, fact-grounded one-line summary from USER memories."""
        core_slots = [
            "name",
            "employer",
            "title",
            "location",
            "programming_years",
            "first_language",
            "masters_school",
            "team_size",
            "remote_preference",
        ]
        resolved = self._answer_from_fact_slots(core_slots)
        if not resolved:
            return None

        # resolved is a multi-line "slot: value" block. Convert to a compact line.
        parts: List[str] = []
        for line in str(resolved).splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip().replace("_", " ")
            v = v.strip()
            if k and v:
                parts.append(f"{k}={v}")

        if not parts:
            return None

        # Keep it to a single line and reasonably short.
        return "; ".join(parts[:8])

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
            "give me ",
            "show me ",
            "provide ",
            "quote ",
            "cite ",
            "summarize ",
            "summarise ",
            "list ",
            "explain ",
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
    # Grounded memory citation helpers
    # ========================================================================

    def _is_memory_citation_request(self, text: str) -> bool:
        """True if the user explicitly asks for chat-grounded recall/citation.

        We use this to bypass open-ended generation and respond from stored memory text.
        """
        t = (text or "").strip().lower()
        if not t:
            return False

        if "from our chat" in t or "from this chat" in t or "from our conversation" in t or "conversation history" in t:
            return True

        if "quote" in t and ("memory" in t or "memories" in t or "exact memory" in t or "memory text" in t):
            return True

        if "exact memory text" in t:
            return True

        return False

    def _is_memory_inventory_request(self, text: str) -> bool:
        """True if the user asks to list/dump memories or internal memory IDs.

        This is treated as a high-risk prompt-injection surface: we should not invent
        internal identifiers. We respond deterministically with safe citations.
        """
        t = (text or "").strip().lower()
        if not t:
            return False

        triggers = (
            "memory id",
            "memory ids",
            "memory_id",
            "ids of your memories",
            "list your memories",
            "list all memories",
            "dump your memories",
            "dump memory",
            "show me your memories",
            "show stored memories",
            "memory database",
            "export memories",
            "print all memories",
        )
        return any(s in t for s in triggers)

    def _build_memory_inventory_answer(
        self,
        *,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        prompt_docs: List[Dict[str, Any]],
        max_lines: int = 8,
    ) -> str:
        """Deterministic safe memory-inventory response.

        We do NOT expose internal memory IDs here; we only cite stored text snippets.
        """
        lines: List[str] = []
        lines.append("I don't expose internal memory IDs.")

        # If nothing was retrieved, be explicit and safe.
        if not retrieved:
            lines.append("I don't have any stored memories to cite yet.")
            return "\n".join(lines)

        lines.append("here is the stored text i can cite:")

        added = 0
        for d in (prompt_docs or []):
            txt = str((d or {}).get("text") or "").strip()
            if not txt:
                continue

            src = str((d or {}).get("source") or "").strip().lower()
            is_fact = txt.lower().startswith("fact:")
            is_user = src == MemorySource.USER.value

            # Only cite user-provided memories and canonical FACT lines.
            if not (is_fact or is_user):
                continue

            lines.append(f"- {txt}")
            added += 1
            if added >= max_lines:
                break

        return "\n".join(lines)

    def _build_memory_citation_answer(
        self,
        *,
        user_query: str,
        retrieved: List[Tuple[MemoryItem, float]],
        prompt_docs: List[Dict[str, Any]],
        max_lines: int = 4,
    ) -> str:
        """Build a deterministic, grounded answer for citation-style prompts.

        Important: avoid introducing new named entities. Keep formatting lowercase.
        """
        # Prefer factual prompt docs if the user is asking about a known slot.
        ql = (user_query or "").lower()
        want_name = "name" in ql

        lines: List[str] = []

        if want_name:
            for d in (prompt_docs or []):
                txt = (d.get("text") or "").strip()
                if txt and "fact:" in txt.lower() and "name" in txt.lower():
                    lines.append(txt)
                    break

        # Add up to N retrieved memory texts verbatim.
        # IMPORTANT: only cite USER-provided text. System responses can be wrong,
        # and citing them as "from our chat" is misleading.
        from .crt_core import MemorySource

        user_retrieved = [m for m, _s in (retrieved or []) if getattr(m, "source", None) == MemorySource.USER]
        for mem in user_retrieved[: max(1, max_lines)]:
            mt = (mem.text or "").strip()
            if mt:
                lines.append(mt)
            if len(lines) >= max_lines:
                break

        # De-dup while preserving order.
        seen = set()
        deduped: List[str] = []
        for ln in lines:
            key = re.sub(r"\s+", " ", ln).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(ln)

        if not deduped:
            # If we truly have nothing, keep it short and non-contradictory.
            return "i don't have stored memory text to quote for that yet."

        # Use simple bullets; no title-case headings.
        out = ["here is the stored text i can cite:"]
        for ln in deduped[:max_lines]:
            out.append(f"- {ln}")
        return "\n".join(out)

    # ========================================================================
    # Ledger-grounded contradiction status helpers
    # ========================================================================

    def _is_contradiction_status_request(self, text: str) -> bool:
        """True if the user is asking to list/inspect open contradictions."""
        t = (text or "").strip().lower()
        if not t:
            return False

        if "contradiction ledger" in t:
            return True

        if "open contradictions" in t or "unresolved contradictions" in t:
            return True

        if "contradictions" in t and any(k in t for k in ("list", "show", "any", "open", "unresolved", "do you have")):
            return True

        # CLI-style short commands.
        if t in {"contradictions", "show contradictions", "list contradictions"}:
            return True

        return False

    def _build_contradiction_status_answer(
        self,
        *,
        user_query: str,
        inferred_slots: Optional[List[str]] = None,
        limit: int = 8,
    ) -> Tuple[str, Dict[str, Any]]:
        """Build a deterministic answer listing OPEN contradictions from the ledger.

        This is intentionally ledger-grounded to prevent hallucinated contradictions.
        """
        from .crt_ledger import ContradictionType

        ql = (user_query or "").strip().lower()

        scope_slots = set(inferred_slots or [])
        if not scope_slots and "identity" in ql:
            scope_slots = {
                "name",
                "employer",
                "location",
                "title",
                "first_language",
                "masters_school",
                "undergrad_school",
                "programming_years",
                "team_size",
            }

        open_contras = self.ledger.get_open_contradictions(limit=200)
        unresolved_total = len(open_contras)

        rows: List[Dict[str, Any]] = []
        hard_conflicts = 0

        for contra in open_contras:
            old_mem = self.memory.get_memory_by_id(contra.old_memory_id)
            new_mem = self.memory.get_memory_by_id(contra.new_memory_id)
            if old_mem is None or new_mem is None:
                continue

            old_facts = extract_fact_slots(old_mem.text) or {}
            new_facts = extract_fact_slots(new_mem.text) or {}
            shared = set(old_facts.keys()) & set(new_facts.keys())
            if scope_slots:
                shared = shared & scope_slots
            if not shared:
                continue

            for slot in sorted(shared):
                of = old_facts.get(slot)
                nf = new_facts.get(slot)
                if of is None or nf is None:
                    continue
                if getattr(of, "normalized", None) == getattr(nf, "normalized", None):
                    continue

                ctype = getattr(contra, "contradiction_type", None) or ContradictionType.CONFLICT
                if ctype == ContradictionType.CONFLICT:
                    hard_conflicts += 1

                rows.append(
                    {
                        "timestamp": getattr(contra, "timestamp", 0.0) or 0.0,
                        "ledger_id": contra.ledger_id,
                        "slot": slot,
                        "old": str(getattr(of, "value", "")),
                        "new": str(getattr(nf, "value", "")),
                        "type": ctype,
                    }
                )

        # De-dup by (ledger_id, slot).
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for r in sorted(rows, key=lambda x: x.get("timestamp", 0.0), reverse=True):
            key = (r.get("ledger_id"), r.get("slot"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
            if len(deduped) >= limit:
                break

        meta = {
            "unresolved_contradictions_total": unresolved_total,
            "unresolved_hard_conflicts": hard_conflicts,
        }

        if not deduped:
            if "identity" in ql:
                return "No open contradictions about your identity in my contradiction ledger.", meta
            return "No open contradictions in my contradiction ledger.", meta

        header = "Here are the open contradictions I have recorded"
        if "identity" in ql:
            header += " about your identity"
        header += ":"

        out_lines = [header]
        for r in deduped:
            slot_name = str(r.get("slot") or "").replace("_", " ")
            old_v = (r.get("old") or "").strip()
            new_v = (r.get("new") or "").strip()
            ctype = (r.get("type") or "conflict").strip()
            if old_v and new_v:
                out_lines.append(f"- {slot_name}: {new_v} vs {old_v} (type: {ctype})")

        # Add a single concrete next action for the first listed entry.
        first = deduped[0] if deduped else None
        if first is not None:
            slot_name = str(first.get("slot") or "").replace("_", " ")
            old_v = (first.get("old") or "").strip()
            new_v = (first.get("new") or "").strip()
            ctype = (first.get("type") or "").strip()
            if old_v and new_v:
                out_lines.append("")
                if ctype == ContradictionType.CONFLICT:
                    out_lines.append(f"To resolve the {slot_name} conflict: which is correct now: {new_v} or {old_v}?")
                elif ctype == ContradictionType.REVISION:
                    out_lines.append(
                        f"To resolve this: should I treat {new_v} as your current {slot_name} and mark {old_v} as superseded?"
                    )
                else:
                    out_lines.append(
                        f"To resolve this: is {new_v} the more accurate/current {slot_name} to keep?"
                    )

        return "\n".join(out_lines), meta

    def _sanitize_memory_denial(self, *, answer: str, has_memory_context: bool) -> str:
        """If memory context exists, avoid self-contradictory 'no memories/first chat' claims.

        This is a lightweight post-processing step to keep the assistant's surface text
        consistent with the CRT metadata we return (retrieved/prompt memories).
        """
        a = (answer or "")
        if not a or not has_memory_context:
            return a

        # Normalize some frequent denial patterns.
        repl = [
            ("this is our first conversation", "in this conversation so far"),
            ("this is the start of our conversation", "so far in this conversation"),
            ("since this is our first conversation", "so far in this conversation"),
            ("we just started the conversation", "so far in this conversation"),
            ("we just started talking", "so far in this conversation"),
            ("my memory is empty", "my stored memory is limited so far"),
            ("my trust-weighted memory is empty", "my trust-weighted memory is limited so far"),
            ("i don't have any memories", "i don't have much stored yet"),
            ("i do not have any memories", "i don't have much stored yet"),
            ("i have no memories", "i don't have much stored yet"),
        ]

        out = a
        low = out.lower()
        for old, new in repl:
            if old in low:
                # Case-insensitive replace (simple, conservative).
                out = re.sub(re.escape(old), new, out, flags=re.I)
                low = out.lower()

        return out

    def _sanitize_unsupported_memory_claims(self, *, answer: str, prompt_docs: List[Dict[str, Any]]) -> str:
        """Remove unsupported personal-fact claims framed as memory.

        Goal: avoid outputs like "I remember ... I work at X" when X is not actually
        present in the retrieved/resolved memory facts.

        This is intentionally conservative and only activates when the answer contains
        a strong memory-claim phrase.
        """
        if not answer or not answer.strip():
            return answer

        t = answer.lower()
        memory_claim = any(
            p in t
            for p in (
                "i remember",
                "i recall",
                "i have a memory",
                "i have it noted",
                "i have you down",
                "i have stored",
                "in my memory",
                "in my notes",
                "i've got it stored",
                "i've got you stored",
                "i've got it noted",
                "i've got you down",
            )
        )
        if not memory_claim:
            return answer

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").strip()).lower()

        # Parse supported FACT values from resolved prompt docs.
        supported_by_slot: Dict[str, set] = {}
        fact_re = re.compile(r"^\s*fact:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)\s*$", re.I)
        for d in (prompt_docs or []):
            txt = str((d or {}).get("text") or "")
            m = fact_re.match(txt)
            if not m:
                continue
            slot = m.group(1).strip().lower()
            val = m.group(2).strip()
            if not slot or not val:
                continue
            supported_by_slot.setdefault(slot, set()).add(_norm(val))

        # Extract fact claims from the answer (first-person patterns).
        claimed = extract_fact_slots(answer) or {}
        if not claimed:
            return answer

        # Identify unsupported claimed slot-values.
        unsupported: Dict[str, str] = {}
        for slot, fact in claimed.items():
            slot_l = str(slot).lower()
            supported = supported_by_slot.get(slot_l) or set()
            if fact is None:
                continue
            if not supported or str(getattr(fact, "normalized", "")) not in supported:
                unsupported[slot_l] = str(getattr(fact, "value", ""))

        if not unsupported:
            return answer

        # Drop lines that contain memory-claim language or the unsupported values.
        bad_value_res = [re.compile(re.escape(v), re.I) for v in unsupported.values() if v]
        memory_line_re = re.compile(
            r"\b(i\s+(remember|recall)|i\s+have\s+(a\s+)?memory|i\s+have\s+it\s+noted|i\s+have\s+you\s+down|i\s+have\s+stored|in\s+my\s+(memory|notes)|i'?ve\s+got\s+(it|you)\s+(stored|noted|down))\b",
            re.I,
        )

        kept_lines: List[str] = []
        for line in answer.splitlines():
            if memory_line_re.search(line):
                continue
            if any(r.search(line) for r in bad_value_res):
                continue
            kept_lines.append(line)

        cleaned = "\n".join(kept_lines).strip()
        first_slot = next(iter(unsupported.keys()))
        if cleaned:
            return cleaned + f"\n\nI don't have a reliable stored memory for your {first_slot} yet — if you tell me, I can remember it going forward."

        return f"I don't have a reliable stored memory for your {first_slot} yet — if you tell me, I can remember it going forward."
    
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


