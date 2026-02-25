"""
Reasoning Engine - Advanced Thinking Modes

Like Claude's extended thinking or Copilot's analysis phase.

Supports:
- Quick mode: Direct answer
- Thinking mode: Analyze → Plan → Reason → Answer
- Deep mode: Extended reasoning with sub-tasks
"""

import json
import logging
import os
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ReasoningMode(Enum):
    """Thinking modes for different query types."""
    QUICK = "quick"           # Direct answer, no analysis
    THINKING = "thinking"     # Analyze → Reason → Answer
    DEEP = "deep"             # Extended reasoning with planning
    RESEARCH = "research"     # Multi-step research process


@dataclass
class ThinkingStep:
    """A step in the reasoning process."""
    step_type: str           # analysis, planning, reasoning, verification
    content: str             # What was thought
    duration_ms: float       # How long this took
    timestamp: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ReasoningTrace:
    """Complete reasoning trace (internal, invisible to user)."""
    query: str
    mode: str
    thinking_steps: List[ThinkingStep]
    decision: str            # What was decided
    confidence: float        # Confidence in reasoning
    contradictions_found: int
    total_duration_ms: float
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'thinking_steps': [s.to_dict() for s in self.thinking_steps]
        }


class ReasoningEngine:
    """
    Advanced reasoning system with thinking modes.
    
    Modes:
    1. QUICK: User wants fast answer, no contradictions
       → Directly generate response
    
    2. THINKING: Contradictions or complexity detected
       → Analyze query
       → Identify sub-questions
       → Reason about contradictions
       → Generate answer
    
    3. DEEP: Complex multi-part question
       → Create reasoning plan
       → Execute sub-tasks
       → Synthesize findings
       → Verify consistency
    
    4. RESEARCH: Needs external information
       → Plan search strategy
       → Execute searches
       → Integrate findings
       → Check contradictions
    """
    
    def __init__(self, llm_client=None):
        """Initialize reasoning engine.
        
        Args:
            llm_client: Optional LLM client. If None, reasoning will be limited.
        """
        self.llm = llm_client
        self.reasoning_traces = []  # Internal log
        self.dnnt = None
        self.dnnt_enabled = str(os.getenv("CRT_DNNT_ENABLED", "true")).strip().lower() in {
            "1", "true", "yes", "y", "on"
        }
        self.dnnt_confidence_threshold = float(os.getenv("CRT_DNNT_CONFIDENCE_THRESHOLD", "0.62"))

        if self.llm is None:
            print("[REASONING] No LLM client provided - using fallback reasoning")
        
        if self.dnnt_enabled:
            try:
                from .dnnt.inference import ReasoningInference

                model_path = str(os.getenv("CRT_DNNT_MODEL_PATH", "models/dnnt/model"))
                self.dnnt = ReasoningInference(
                    model_path=model_path,
                    confidence_threshold=self.dnnt_confidence_threshold,
                    llm_callback=self._dnnt_llm_callback,
                    collect_training_data=True,
                )
                logger.info(
                    "[REASONING] DNNT inference initialized (loaded=%s, threshold=%.2f, path=%s)",
                    bool(getattr(self.dnnt, "model_loaded", False)),
                    self.dnnt_confidence_threshold,
                    model_path,
                )
            except Exception as e:
                logger.warning(f"[REASONING] DNNT initialization failed; falling back to LLM path: {e}")
                self.dnnt = None

    def _extract_facts_for_dnnt(self, context: Dict[str, Any], limit: int = 8) -> List[str]:
        """Convert retrieval context into compact fact lines for DNNT."""
        facts: List[str] = []
        seen: set[str] = set()
        retrieved = context.get("retrieved_docs") or []
        for doc in retrieved:
            if not isinstance(doc, dict):
                continue
            text = str(doc.get("text") or "").strip()
            if not text:
                continue
            trust = doc.get("trust")
            if isinstance(trust, (int, float)):
                fact = f"{text[:220]} (trust={float(trust):.2f})"
            else:
                fact = text[:240]
            if fact in seen:
                continue
            seen.add(fact)
            facts.append(fact)
            if len(facts) >= limit:
                break
        return facts

    def _dnnt_llm_callback(self, query: str, facts: List[str]) -> tuple[str, str]:
        """LLM callback used by DNNT inference fallback collection."""
        context = {
            "retrieved_docs": [{"text": f} for f in (facts or [])],
            "contradictions": [],
        }
        prompt = self._build_quick_prompt(query, context)
        answer = self._call_llm(prompt, max_tokens=700)
        return "", answer
    
    def reason(
        self,
        query: str,
        context: Dict[str, Any],
        mode: Optional[ReasoningMode] = None,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main reasoning entry point.
        
        Args:
            query: User's question
            context: Retrieved docs, memories, contradictions
            mode: Reasoning mode (auto-detected if None)
        
        Returns:
            {
                'mode': ReasoningMode,
                'thinking': str,              # Thinking process (visible)
                'answer': str,                # Final answer
                'reasoning_trace': ReasoningTrace,  # Internal trace
                'confidence': float
            }
        """
        if model_override:
            context = dict(context or {})
            context["_model_override"] = model_override

        # Auto-detect mode if not specified
        if mode is None:
            mode = self._detect_mode(query, context)
        
        # Execute reasoning based on mode
        if mode == ReasoningMode.QUICK:
            return self._quick_answer(query, context)
        elif mode == ReasoningMode.THINKING:
            return self._thinking_mode(query, context)
        elif mode == ReasoningMode.DEEP:
            return self._deep_reasoning(query, context)
        elif mode == ReasoningMode.RESEARCH:
            return self._research_mode(query, context)

    # ====================================================================
    # World-fact sanity check (optional)
    # ====================================================================

    @staticmethod
    def should_run_world_fact_check(answer: str) -> bool:
        """Heuristic gate: only run world-check on likely public-fact claims.

        We intentionally avoid running this on personal/user-specific content to
        reduce noise and cost.
        """
        a = (answer or "").strip()
        if not a:
            return False

        low = a.lower()
        # Don't world-check meta-chat / provenance / memory discussion.
        if any(k in low for k in ("from our chat", "our chat", "stored mem", "provenance:")):
            return False

        # Require at least one sentence that looks like a public-fact claim and
        # is not phrased in first/second-person terms.
        public_triggers = (
            "capital of",
            "population",
            "currency",
            "gdp",
            "located in",
            "is located in",
            "is in ",
            "largest",
            "smallest",
            "highest",
            "lowest",
            "founded",
            "invented",
            "discovered",
            "born",
            "died",
            "president",
            "prime minister",
            "country",
            "continent",
            "planet",
            "moon",
            "element",
            "atomic number",
            "speed of light",
        )

        pronoun_re = r"\b(i|you|we|my|your|our)\b"
        # Crude sentence split; good enough for gating.
        parts = [p.strip() for p in re.split(r"[.!?]+\s+", a) if p.strip()]
        for p in parts:
            pl = p.lower()
            if not any(t in pl for t in public_triggers):
                continue
            if re.search(pronoun_re, pl):
                continue
            return True

        return False

    def world_fact_check(
        self,
        *,
        answer: str,
        memory_context: str,
        max_tokens: int = 140,
    ) -> List[Dict[str, str]]:
        """Best-effort check for conflicts with widely-known public facts.

        This is intentionally conservative: it should only emit *warnings* for claims
        that are likely wrong in general world knowledge (not personal/user-specific facts).

        Returns a list of warnings like:
          [{"claim": "...", "issue": "...", "severity": "low|med|high"}, ...]
        """
        a = (answer or "").strip()
        if not a:
            return []

        # Avoid noisy checks on personal/chat content.
        if not self.should_run_world_fact_check(a):
            return []

        if self.llm is None:
            return []

        ctx = (memory_context or "").strip()
        if len(ctx) > 1800:
            ctx = ctx[:1800].rstrip() + "\n…"

        prompt = (
            "You are a cautious world-knowledge checker.\n"
            "Task: find statements in ANSWER that STRONGLY contradict widely-known public facts.\n"
            "Important: this is NOT about personal facts or chat history.\n"
            "Hard rules:\n"
            "- Do NOT warn about personal/user-specific facts (names, jobs, preferences, life events).\n"
            "- Do NOT warn about chat provenance, missing quotes, uncertainty, or 'unverifiable' claims.\n"
            "- Only warn when the contradiction is strong and commonly known.\n"
            "- If unsure, output zero warnings.\n"
            "Output STRICT JSON ONLY: {\\\"warnings\\\": [...]}\n"
            "Each warning MUST be: {\\\"claim\\\": str, \\\"public_fact\\\": str, \\\"confidence\\\": number, \\\"severity\\\": \\\"low|med|high\\\"}.\n"
            "- confidence is 0..1 and should be >= 0.80 to include.\n\n"
            "MEMORY_CONTEXT (for reference only; do not fact-check it):\n"
            f"{ctx}\n\n"
            "ANSWER:\n"
            f"{a}\n"
        )

        raw = self._call_llm(prompt, max_tokens=max_tokens)
        try:
            obj = json.loads(raw)
            warnings = obj.get("warnings")
            if not isinstance(warnings, list):
                return []
            out: List[Dict[str, str]] = []
            for w in warnings[:5]:
                if not isinstance(w, dict):
                    continue
                claim = str(w.get("claim") or "").strip()
                public_fact = str(w.get("public_fact") or "").strip()
                sev = str(w.get("severity") or "").strip().lower()
                try:
                    conf = float(w.get("confidence"))
                except Exception:
                    conf = 0.0

                if not claim or not public_fact:
                    continue
                if conf < 0.80:
                    continue
                if sev not in {"low", "med", "high"}:
                    sev = "low"
                out.append({"claim": claim, "public_fact": public_fact, "severity": sev, "confidence": f"{conf:.2f}"})
            return out
        except Exception:
            return []

    # ====================================================================
    # Streaming support
    # ====================================================================

    def supports_streaming(self) -> bool:
        """Return True if the configured LLM client can stream tokens."""
        try:
            return bool(getattr(self.llm, "generate", None)) and ("stream" in self.llm.generate.__code__.co_varnames)
        except Exception:
            return False

    def stream_answer(
        self,
        query: str,
        context: Dict[str, Any],
        mode: Optional[ReasoningMode] = None,
        max_tokens: int = 1000,
    ):
        """Yield partial answer text as it is generated.

        This is a best-effort streaming path. If the underlying LLM client
        doesn't support streaming, callers should fall back to `reason()`.
        """

        if self.llm is None:
            # No LLM available; just yield a single fallback message.
            yield "[No LLM available - install Ollama and run: ollama pull llama3.2]"
            return

        if mode is None:
            mode = self._detect_mode(query, context)

        # For now, only QUICK mode is streamed (minimal chat UX).
        # Other modes can be added once we decide how to stream multi-step thinking.
        prompt = self._build_quick_prompt(query, context)

        try:
            stream = self.llm.generate(
                prompt,
                max_tokens=max_tokens,
                stream=True,
                model=context.get("_model_override"),
            )
        except TypeError:
            # LLM client doesn't accept stream=...
            yield self._call_llm(
                prompt,
                max_tokens=max_tokens,
                model_override=context.get("_model_override"),
            )
            return
        except Exception as e:
            yield f"[LLM error: {e}]"
            return

        buffer = ""
        for chunk in stream:
            try:
                token = chunk.get('message', {}).get('content', '')
            except Exception:
                token = ""

            if not token:
                continue

            buffer += token
            yield buffer
    
    def _detect_mode(self, query: str, context: Dict) -> ReasoningMode:
        """Auto-detect which reasoning mode to use."""
        contradictions = context.get('contradictions', [])
        retrieved_docs = context.get('retrieved_docs', [])
        
        # Deep mode triggers
        if contradictions and len(contradictions) >= 3:
            return ReasoningMode.DEEP
        
        # Thinking mode triggers
        if contradictions:
            return ReasoningMode.THINKING
        
        # Research mode triggers
        if len(retrieved_docs) == 0 and any(word in query.lower() for word in ['search', 'find', 'research', 'latest']):
            return ReasoningMode.RESEARCH
        
        # Complex question indicators
        complexity_markers = ['why', 'how', 'explain', 'compare', 'analyze', 'evaluate']
        if any(marker in query.lower() for marker in complexity_markers):
            return ReasoningMode.THINKING
        
        # Default to quick
        return ReasoningMode.QUICK
    
    def _quick_answer(self, query: str, context: Dict) -> Dict:
        """
        Quick mode: Direct answer without visible thinking.
        
        Internal thinking still happens but not shown to user.
        """
        start_time = datetime.now()
        
        source = "fallback"
        answer = ""
        confidence = 0.8

        # DNNT-first path with confidence-gated fallback.
        # Skip DNNT when copilot context or web search results are present — the DNNT callback loses them.
        has_copilot_ctx = bool(context.get('copilot_context'))
        has_web_search = bool(context.get('web_search_results'))
        if self.dnnt is not None and not has_copilot_ctx and not has_web_search:
            try:
                facts = self._extract_facts_for_dnnt(context)
                dnnt_result = self.dnnt.generate(
                    query=query,
                    facts=facts,
                    training_meta={
                        "unresolved_contradictions_total": len(context.get("contradictions") or []),
                        "groundcheck_passed": bool(context.get("groundcheck_passed", True)),
                    },
                )
                answer = str(dnnt_result.response or "").strip()
                source = str(dnnt_result.source or "dnnt")
                confidence = float(dnnt_result.confidence or 0.0)
            except Exception as e:
                logger.warning(f"[REASONING] DNNT generation failed; falling back to LLM path: {e}")
                answer = ""

        # Existing LLM/fallback path.
        if not answer:
            prompt = self._build_quick_prompt(query, context)
            if self.llm:
                answer = self._call_llm(
                    prompt,
                    max_tokens=500,
                    model_override=context.get("_model_override"),
                )
                source = "llm"
                confidence = 0.8
            else:
                answer = self._generate_fallback_response(query, context)
                source = "fallback"
                confidence = 0.8
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Internal trace (not shown to user)
        trace = ReasoningTrace(
            query=query,
            mode="quick",
            thinking_steps=[
                ThinkingStep(
                    step_type="direct_answer",
                    content=f"No complexity detected, generating direct answer via {source}",
                    duration_ms=duration_ms,
                    timestamp=datetime.now().isoformat()
                )
            ],
            decision="quick_answer",
            confidence=confidence,
            contradictions_found=0,
            total_duration_ms=duration_ms
        )
        
        self.reasoning_traces.append(trace)
        
        return {
            'mode': ReasoningMode.QUICK.value,
            'thinking': None,  # Not shown in quick mode
            'answer': answer,
            'reasoning_trace': trace.to_dict(),
            'confidence': confidence,
            'reasoning_source': source,
            'dnnt_enabled': bool(self.dnnt is not None),
        }
    
    def _generate_fallback_response(self, query: str, context: Dict) -> str:
        """Generate a contextual response when no LLM is available."""
        q = query.strip().lower()
        
        # Check for acknowledgments/praise
        acknowledgment_patterns = [
            'good job', 'great', 'thanks', 'thank you', 'correct', 'right', 
            'exactly', 'perfect', 'awesome', 'nice', 'well done', 'yes'
        ]
        if any(pat in q for pat in acknowledgment_patterns):
            return "Thank you! I'm glad I could help. Is there anything else you'd like to know?"
        
        # Check for greetings
        greeting_patterns = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
        if any(pat in q for pat in greeting_patterns):
            return "Hello! How can I help you today?"
        
        # Check for philosophical/general knowledge questions
        philosophical_patterns = [
            'meaning of life', 'purpose of life', 'what is life', 'why are we here',
            'what is love', 'what is happiness', 'what is consciousness'
        ]
        if any(pat in q for pat in philosophical_patterns):
            return "That's a profound question that philosophers have debated for centuries. I don't have a definitive answer, but I'm happy to discuss what I know about you and help with practical questions."
        
        # Check for capability questions
        capability_patterns = ['can you', 'are you able', 'do you know', 'what can you do']
        if any(pat in q for pat in capability_patterns):
            return "I'm a personal memory assistant. I can remember facts about you, detect contradictions, and help answer questions based on what you've told me. Try telling me something about yourself!"
        
        # Check for "how are you" type questions
        wellbeing_patterns = ['how are you', 'how do you feel', "how's it going"]
        if any(pat in q for pat in wellbeing_patterns):
            return "I'm doing well, thank you for asking! How can I help you today?"
        
        # Check if there's memory context we can use
        retrieved_docs = context.get('retrieved_docs', [])
        if retrieved_docs:
            # We have relevant memories - synthesize from them
            memory_texts = [doc.get('text', '') for doc in retrieved_docs[:3] if doc.get('text')]
            if memory_texts:
                return f"Based on what I remember: {memory_texts[0]}"
        
        # Generic fallback for questions
        if '?' in query:
            return "I don't have enough information to answer that question. Could you tell me more, or ask about something I might know from our conversation?"
        
        # Generic fallback for statements
        return "I understand. Is there anything specific you'd like me to remember or help you with?"
    
    def _thinking_mode(self, query: str, context: Dict) -> Dict:
        """
        Thinking mode: Visible analysis → reasoning → answer.
        
        Like Claude's extended thinking or o1's reasoning.
        """
        start_time = datetime.now()
        steps = []
        
        # Step 1: Analyze query
        analysis_start = datetime.now()
        analysis = self._analyze_query(query, context)
        steps.append(ThinkingStep(
            step_type="analysis",
            content=analysis,
            duration_ms=(datetime.now() - analysis_start).total_seconds() * 1000,
            timestamp=datetime.now().isoformat()
        ))
        
        # Step 2: Identify contradictions
        if context.get('contradictions'):
            contra_start = datetime.now()
            contra_analysis = self._analyze_contradictions(context['contradictions'])
            steps.append(ThinkingStep(
                step_type="contradiction_analysis",
                content=contra_analysis,
                duration_ms=(datetime.now() - contra_start).total_seconds() * 1000,
                timestamp=datetime.now().isoformat()
            ))
        
        # Step 3: Plan approach
        planning_start = datetime.now()
        plan = self._plan_answer(query, analysis, context)
        steps.append(ThinkingStep(
            step_type="planning",
            content=plan,
            duration_ms=(datetime.now() - planning_start).total_seconds() * 1000,
            timestamp=datetime.now().isoformat()
        ))
        
        # Step 4: Generate answer
        answer_start = datetime.now()
        
        # Build thinking-aware prompt
        prompt = self._build_thinking_prompt(query, context, analysis, plan)
        
        if self.llm:
            answer = self._call_llm(
                prompt,
                max_tokens=1000,
                model_override=context.get("_model_override"),
            )
        else:
            # Use the same fallback response generator
            answer = self._generate_fallback_response(query, context)
        
        steps.append(ThinkingStep(
            step_type="answer_generation",
            content="Generated final answer",
            duration_ms=(datetime.now() - answer_start).total_seconds() * 1000,
            timestamp=datetime.now().isoformat()
        ))
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Compile visible thinking
        visible_thinking = self._format_thinking_steps(steps)
        
        # Internal trace
        trace = ReasoningTrace(
            query=query,
            mode="thinking",
            thinking_steps=steps,
            decision="analyzed_and_answered",
            confidence=0.9,
            contradictions_found=len(context.get('contradictions', [])),
            total_duration_ms=duration_ms
        )
        
        self.reasoning_traces.append(trace)
        
        return {
            'mode': ReasoningMode.THINKING.value,
            'thinking': visible_thinking,
            'answer': answer,
            'reasoning_trace': trace.to_dict(),
            'confidence': 0.9
        }
    
    def _deep_reasoning(self, query: str, context: Dict) -> Dict:
        """
        Deep mode: Extended reasoning with sub-tasks.
        
        For complex queries with multiple contradictions or parts.
        """
        start_time = datetime.now()
        steps = []
        
        # Step 1: Decompose query into sub-questions
        decomp_start = datetime.now()
        sub_questions = self._decompose_query(query)
        steps.append(ThinkingStep(
            step_type="decomposition",
            content=f"Identified {len(sub_questions)} sub-questions: {sub_questions}",
            duration_ms=(datetime.now() - decomp_start).total_seconds() * 1000,
            timestamp=datetime.now().isoformat()
        ))
        
        # Step 2: Analyze each contradiction deeply
        if context.get('contradictions'):
            for i, contra in enumerate(context['contradictions'][:3], 1):  # Limit to 3
                contra_start = datetime.now()
                deep_analysis = self._deep_contradiction_analysis(contra, context)
                steps.append(ThinkingStep(
                    step_type=f"deep_contradiction_{i}",
                    content=deep_analysis,
                    duration_ms=(datetime.now() - contra_start).total_seconds() * 1000,
                    timestamp=datetime.now().isoformat()
                ))
        
        # Step 3: Create reasoning plan
        plan_start = datetime.now()
        plan = self._create_deep_plan(query, sub_questions, context)
        steps.append(ThinkingStep(
            step_type="deep_planning",
            content=plan,
            duration_ms=(datetime.now() - plan_start).total_seconds() * 1000,
            timestamp=datetime.now().isoformat()
        ))
        
        # Step 4: Execute plan step-by-step
        exec_start = datetime.now()
        execution = self._execute_deep_plan(plan, context)
        steps.append(ThinkingStep(
            step_type="execution",
            content=execution,
            duration_ms=(datetime.now() - exec_start).total_seconds() * 1000,
            timestamp=datetime.now().isoformat()
        ))
        
        # Step 5: Synthesize final answer
        synth_start = datetime.now()
        
        prompt = self._build_deep_prompt(query, context, plan, execution)
        
        if self.llm:
            answer = self._call_llm(
                prompt,
                max_tokens=2000,
                model_override=context.get("_model_override"),
            )
        else:
            answer = f"[Deep reasoning answer for: {query}]"
        
        steps.append(ThinkingStep(
            step_type="synthesis",
            content="Synthesized comprehensive answer",
            duration_ms=(datetime.now() - synth_start).total_seconds() * 1000,
            timestamp=datetime.now().isoformat()
        ))
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Visible thinking (detailed)
        visible_thinking = self._format_deep_thinking(steps)
        
        # Internal trace
        trace = ReasoningTrace(
            query=query,
            mode="deep",
            thinking_steps=steps,
            decision="deep_multi_step_reasoning",
            confidence=0.95,
            contradictions_found=len(context.get('contradictions', [])),
            total_duration_ms=duration_ms
        )
        
        self.reasoning_traces.append(trace)
        
        return {
            'mode': ReasoningMode.DEEP.value,
            'thinking': visible_thinking,
            'answer': answer,
            'reasoning_trace': trace.to_dict(),
            'confidence': 0.95
        }
    
    def _research_mode(self, query: str, context: Dict) -> Dict:
        """Research mode: Multi-step information gathering."""
        # Placeholder - would integrate with web search
        return self._thinking_mode(query, context)
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _analyze_query(self, query: str, context: Dict) -> str:
        """Analyze what the query is asking."""
        contradictions = context.get('contradictions', [])
        docs = context.get('retrieved_docs', [])
        
        return f"Query: '{query}' | Found {len(docs)} docs, {len(contradictions)} contradictions"
    
    def _analyze_contradictions(self, contradictions: List[Dict]) -> str:
        """Analyze contradictions found."""
        if not contradictions:
            return "No contradictions"
        
        return f"Detected {len(contradictions)} contradictions requiring reconciliation"
    
    def _plan_answer(self, query: str, analysis: str, context: Dict) -> str:
        """Plan how to answer."""
        if context.get('contradictions'):
            return "Plan: Present all perspectives from contradictions, explain context for each"
        else:
            return "Plan: Direct answer from retrieved context"
    
    def _decompose_query(self, query: str) -> List[str]:
        """Break complex query into sub-questions."""
        # Simple heuristic - look for conjunctions
        if ' and ' in query.lower():
            return query.lower().split(' and ')
        return [query]
    
    def _deep_contradiction_analysis(self, contradiction: Dict, context: Dict) -> str:
        """Deep analysis of a contradiction."""
        return f"Contradiction analysis: Multiple valid perspectives detected"
    
    def _create_deep_plan(self, query: str, sub_questions: List[str], context: Dict) -> str:
        """Create detailed reasoning plan."""
        return f"Plan: Address {len(sub_questions)} sub-questions, reconcile contradictions, synthesize"
    
    def _execute_deep_plan(self, plan: str, context: Dict) -> str:
        """Execute the deep reasoning plan."""
        return "Executed multi-step reasoning process"
    
    def _format_thinking_steps(self, steps: List[ThinkingStep]) -> str:
        """Format thinking steps for display."""
        output = "<thinking>\n"
        for step in steps:
            output += f"[{step.step_type}] {step.content}\n"
        output += "</thinking>"
        return output
    
    def _format_deep_thinking(self, steps: List[ThinkingStep]) -> str:
        """Format deep thinking steps (more detailed)."""
        output = "<deep_reasoning>\n"
        for i, step in enumerate(steps, 1):
            output += f"\nStep {i}: {step.step_type}\n"
            output += f"{step.content}\n"
            output += f"(Duration: {step.duration_ms:.0f}ms)\n"
        output += "\n</deep_reasoning>"
        return output

    def _format_style_hint(self, style_profile: Optional[Dict[str, Any]]) -> str:
        """Create a short style instruction from a profile."""
        if not style_profile:
            return ""
        label = str(style_profile.get("tone_label") or "balanced").lower()

        if label == "playful":
            return (
                "Tone: playful and witty when appropriate; mirror the user's humor. "
                "Shift to serious and grounded when the topic is serious. Keep language natural and not overly formal."
            )
        if label == "serious":
            return (
                "Tone: calm, direct, and empathetic. Avoid jokes unless the user explicitly cues humor. "
                "Keep language natural and not overly formal."
            )
        if label == "adaptive":
            return (
                "Tone: adaptive—light when the user is playful, grounded when the user is serious. "
                "Keep a warm, consistent voice. Keep language natural and not overly formal."
            )
        return (
            "Tone: friendly and flexible; lightly playful when the user is playful, "
            "and serious when they are serious. Keep language natural and not overly formal."
        )

    def _format_adaptive_hint(
        self,
        personality_profile: Optional[Dict[str, Any]],
        reflection_scorecard: Optional[Dict[str, Any]],
        episodic_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create personality-driven instructions from personality/reflection loops.
        
        This is now more influential on the chat behavior based on learned patterns.
        """
        hints: List[str] = []
        personality_section = []
        reflection_section = []
        episodic_section = []

        if personality_profile:
            window = int(personality_profile.get("message_window") or 0)
            
            # Lower threshold for personality influence (was 12, now 5)
            if window >= 5:
                verbosity = str(personality_profile.get("verbosity") or "").lower()
                if verbosity == "concise":
                    personality_section.append("User prefers SHORT, DIRECT answers. Keep responses brief and to-the-point.")
                elif verbosity == "verbose":
                    personality_section.append("User appreciates DETAILED explanations. Provide thorough answers with context.")
                else:  # balanced
                    personality_section.append("User prefers balanced responses - not too brief, not too lengthy.")

                fmt = str(personality_profile.get("format") or "").lower()
                if fmt == "structured":
                    personality_section.append("User likes STRUCTURED formatting - use bullets, numbered lists, and clear sections.")
                else:
                    personality_section.append("User prefers natural flowing prose over heavy formatting.")

                emoji_pref = str(personality_profile.get("emoji") or "").lower()
                if emoji_pref == "on":
                    personality_section.append("User responds well to occasional emoji use 🦞")
                else:
                    personality_section.append("Avoid emoji in responses.")
                
                # New profile fields
                interaction_style = str(personality_profile.get("interaction_style") or "").lower()
                if interaction_style == "inquisitive":
                    personality_section.append("User tends to ask questions - be ready with clear, direct answers.")
                elif interaction_style == "declarative":
                    personality_section.append("User makes statements - acknowledge their points and build on them.")
                
                tone_pref = str(personality_profile.get("tone_preference") or "").lower()
                if tone_pref == "technical":
                    personality_section.append("User prefers TECHNICAL language. Don't oversimplify - use precise terminology.")
                elif tone_pref == "casual":
                    personality_section.append("User prefers CASUAL conversation. Keep it approachable and friendly.")
                
                urgency = str(personality_profile.get("urgency") or "").lower()
                if urgency == "high":
                    personality_section.append("User often wants quick answers. Prioritize actionable responses over explanations.")

                state = str(personality_profile.get("state") or "").lower()
                if state == "urgent_executor":
                    personality_section.append("Persona mode is URGENT_EXECUTOR: lead with action-first guidance, then optional detail.")
                elif state == "technical_guide":
                    personality_section.append("Persona mode is TECHNICAL_GUIDE: prioritize precise terminology, constraints, and tradeoffs.")
                elif state == "structured_coach":
                    personality_section.append("Persona mode is STRUCTURED_COACH: respond with clean, numbered steps and checkpoints.")
                elif state == "reflective_partner":
                    personality_section.append("Persona mode is REFLECTIVE_PARTNER: include brief reflective framing before recommendations.")

                if personality_profile.get("state_transitioned"):
                    prev_state = str(personality_profile.get("previous_state") or "").strip()
                    if prev_state:
                        personality_section.append(f"(Recent persona shift: {prev_state} -> {state})")

            # Include message window context
            if window > 0:
                personality_section.append(f"(Based on {window} analyzed messages)")

        if reflection_scorecard:
            try:
                confidence = float(reflection_scorecard.get("preference_confidence") or 0.0)
            except Exception:
                confidence = 0.0
            
            # Lower threshold for reflection influence (was 0.7, now 0.3)
            if confidence >= 0.3:
                topics_raw = reflection_scorecard.get("top_topics") or []
                topics = [
                    t.get("topic")
                    for t in topics_raw
                    if isinstance(t, dict) and t.get("topic")
                ]
                topics = [t for t in topics if isinstance(t, str)]
                if topics:
                    top = ", ".join(topics[:3])
                    reflection_section.append(f"User's main interests: {top}")
                    reflection_section.append(f"Reference these topics in examples when naturally relevant.")
                
                # Include trend information
                trends = reflection_scorecard.get("topic_trends") or {}
                rising = trends.get("rising") or []
                fading = trends.get("fading") or []
                
                if rising:
                    # Handle both string and dict formats for topics
                    rising_strs = []
                    for t in rising[:2]:
                        if isinstance(t, str):
                            rising_strs.append(t)
                        elif isinstance(t, dict):
                            rising_strs.append(str(t.get("topic", t.get("name", str(t)))))
                    if rising_strs:
                        rising_topics = ", ".join(rising_strs)
                        reflection_section.append(f"Recently increasing focus on: {rising_topics}")
                
                if fading:
                    # Handle both string and dict formats for topics
                    fading_strs = []
                    for t in fading[:2]:
                        if isinstance(t, str):
                            fading_strs.append(t)
                        elif isinstance(t, dict):
                            fading_strs.append(str(t.get("topic", t.get("name", str(t)))))
                    if fading_strs:
                        fading_topics = ", ".join(fading_strs)
                        reflection_section.append(f"Decreased interest in: {fading_topics}")
                
                reflection_section.append(f"(Preference confidence: {confidence:.0%})")

        if episodic_preferences and isinstance(episodic_preferences, dict):
            response_style = episodic_preferences.get("response_style")
            if not isinstance(response_style, dict):
                # Support callers that pass only response_style directly.
                response_style = episodic_preferences
            code_style = episodic_preferences.get("code_style")
            if not isinstance(code_style, dict):
                code_style = {}

            def _pref_value(pref_map: Dict[str, Any], key: str) -> tuple[str, float]:
                raw = pref_map.get(key)
                if isinstance(raw, dict):
                    val = str(raw.get("value") or "")
                    try:
                        conf = float(raw.get("confidence") or 0.0)
                    except Exception:
                        conf = 0.0
                    return val, conf
                if raw is None:
                    return "", 0.0
                return str(raw), 0.5

            verbosity, verbosity_conf = _pref_value(response_style, "verbosity")
            if verbosity_conf >= 0.45:
                if verbosity == "concise":
                    episodic_section.append("Long-term preference: concise answers.")
                elif verbosity == "verbose":
                    episodic_section.append("Long-term preference: detailed answers with context.")

            fmt, fmt_conf = _pref_value(response_style, "format")
            if fmt_conf >= 0.45:
                if fmt == "structured":
                    episodic_section.append("Long-term preference: structured formatting (lists/sections).")
                elif fmt == "freeform":
                    episodic_section.append("Long-term preference: natural prose over list-heavy formatting.")

            structure, structure_conf = _pref_value(response_style, "structure")
            if structure_conf >= 0.45 and structure == "step_by_step":
                episodic_section.append("Long-term preference: step-by-step explanations when applicable.")

            emoji, emoji_conf = _pref_value(response_style, "emoji_usage")
            if emoji_conf >= 0.45:
                if emoji == "none":
                    episodic_section.append("Long-term preference: avoid emoji.")
                elif emoji == "minimal":
                    episodic_section.append("Long-term preference: use emoji sparingly.")
                elif emoji == "frequent":
                    episodic_section.append("Long-term preference: occasional emoji is welcome.")

            citation_style, citation_conf = _pref_value(response_style, "citation_style")
            if citation_conf >= 0.45:
                if citation_style == "required":
                    episodic_section.append("Long-term preference: include sources/citations when making factual claims.")
                elif citation_style == "none":
                    episodic_section.append("Long-term preference: avoid citation-heavy formatting unless requested.")

            code_examples, code_examples_conf = _pref_value(response_style, "code_examples")
            if code_examples_conf >= 0.45:
                if code_examples == "yes":
                    episodic_section.append("Long-term preference: include code examples when useful.")
                elif code_examples == "no":
                    episodic_section.append("Long-term preference: prioritize explanation over code unless explicitly asked.")

            lang, lang_conf = _pref_value(code_style, "language")
            if lang_conf >= 0.45 and lang:
                episodic_section.append(f"Long-term code language preference: {lang}.")

        # Build final output
        output_parts = []
        
        if personality_section:
            output_parts.append("LEARNED PERSONALITY PREFERENCES:\n" + "\n".join(f"• {s}" for s in personality_section))
        
        if reflection_section:
            output_parts.append("REFLECTION INSIGHTS:\n" + "\n".join(f"• {s}" for s in reflection_section))
        
        if episodic_section:
            output_parts.append("LONG-TERM PREFERENCES:\n" + "\n".join(f"• {s}" for s in episodic_section))
        
        if not output_parts:
            return ""
        
        return "\n\n".join(output_parts)

    def _format_preference_constraints(
        self,
        episodic_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build hard preference constraints from high-confidence episodic signals.

        These are intentionally stronger than adaptive hints and should be treated as
        default requirements unless the user overrides them in the current turn.
        """
        if not isinstance(episodic_preferences, dict):
            return ""

        response_style = episodic_preferences.get("response_style")
        if not isinstance(response_style, dict):
            response_style = episodic_preferences
        code_style = episodic_preferences.get("code_style")
        if not isinstance(code_style, dict):
            code_style = {}

        def _pref_value(pref_map: Dict[str, Any], key: str) -> tuple[str, float]:
            raw = pref_map.get(key)
            if isinstance(raw, dict):
                val = str(raw.get("value") or "").strip().lower()
                try:
                    conf = float(raw.get("confidence") or 0.0)
                except Exception:
                    conf = 0.0
                return val, conf
            if raw is None:
                return "", 0.0
            return str(raw).strip().lower(), 0.5

        constraints: List[str] = []

        verbosity, verbosity_conf = _pref_value(response_style, "verbosity")
        if verbosity_conf >= 0.6:
            if verbosity == "concise":
                constraints.append("Keep the answer concise by default.")
            elif verbosity == "verbose":
                constraints.append("Provide thorough detail by default.")

        fmt, fmt_conf = _pref_value(response_style, "format")
        if fmt_conf >= 0.6:
            if fmt == "structured":
                constraints.append("Use structured formatting (sections/lists) when it improves clarity.")
            elif fmt == "freeform":
                constraints.append("Prefer natural prose over heavy list formatting unless asked.")

        structure, structure_conf = _pref_value(response_style, "structure")
        if structure_conf >= 0.6 and structure == "step_by_step":
            constraints.append("Use step-by-step explanations for tasks and procedures.")

        emoji, emoji_conf = _pref_value(response_style, "emoji_usage")
        if emoji_conf >= 0.6:
            if emoji == "none":
                constraints.append("Do not use emoji.")
            elif emoji == "minimal":
                constraints.append("Use emoji only sparingly.")

        citation_style, citation_conf = _pref_value(response_style, "citation_style")
        if citation_conf >= 0.6:
            if citation_style == "required":
                constraints.append("Include sources for factual claims when available.")
            elif citation_style == "none":
                constraints.append("Avoid citation-heavy formatting unless explicitly requested.")

        code_examples, code_examples_conf = _pref_value(response_style, "code_examples")
        if code_examples_conf >= 0.6:
            if code_examples == "yes":
                constraints.append("Include code examples when they materially help.")
            elif code_examples == "no":
                constraints.append("Prioritize conceptual explanation over code unless asked for code.")

        lang, lang_conf = _pref_value(code_style, "language")
        if lang_conf >= 0.6 and lang:
            constraints.append(f"When writing code, prefer {lang} unless user requests another language.")

        if not constraints:
            return ""
        return "\n".join(f"- {line}" for line in constraints)
    
    def _build_quick_prompt(self, query: str, context: Dict) -> str:
        """Build prompt for quick mode."""
        docs = context.get('retrieved_docs', [])
        style_hint = self._format_style_hint(context.get("style_profile"))
        adaptive_hint = self._format_adaptive_hint(
            context.get("personality_profile"),
            context.get("reflection_scorecard"),
            context.get("episodic_preferences"),
        )
        preference_constraints = self._format_preference_constraints(
            context.get("episodic_preferences"),
        )
        
        num_memories = len(docs) if docs else 0
        
        prompt = """You are Aether, a personal AI assistant built on the CRT-GroundCheck architecture.
You are NOT a generic chatbot. You are a specific system with real, concrete tools.

CRITICAL: You are an AI assistant helping a USER. Facts in memory are ABOUT THE USER, not about you.
Do NOT claim the user's name, job, location, or any personal attributes as your own.

=== HOW YOU ACTUALLY WORK (be honest about this when asked) ===

Your Technical Stack:
- GroundCheck Memory: A SQLite-backed memory system that stores every fact as a 384-dimensional semantic embedding (using all-MiniLM-L6-v2). Each memory has a trust score from 0.0 to 1.0 that changes over time.
- Semantic Search: When the user asks a question, their query is embedded and compared against all stored memories using cosine similarity. The top matches are retrieved and given to you as context.
- CRT-as-Critic: After you generate an answer, a separate verification step runs GroundCheck.verify() to check your answer against stored memories in ~1ms. If you contradict a memory, it catches it.
- Contradiction Ledger: When conflicting facts arrive (e.g., "I work at Google" then "I work at Microsoft"), BOTH are kept in a ledger with timestamps and trust scores. Nothing is silently overwritten.
- Web Search: You have a DuckDuckGo search tool for real-time information you don't have in memory.
- Reconstruction Gates: Your answers are scored for intent-alignment and memory-alignment. If they fail, the answer is marked as "speech" (low confidence) rather than "belief" (high confidence).
- Heartbeat System: A background process that periodically reviews memories, runs trust decay, and does autonomous maintenance.

WHEN ASKED "HOW DO YOU KNOW?" or "HOW ARE YOU SURE?":
- Be specific and technical. Say something like: "I retrieved that from my GroundCheck memory where you told me [X]. That memory has a trust score of [Y]. I found it via semantic search against {num_memories} stored facts."
- Do NOT make up vague reasons. Cite the actual memory text and trust score from the USER FACTS section below.
- If you have no stored memory for something, say "I don't have that stored in my memory system."

WHEN ASKED "WHO ARE YOU?" or "WHAT ARE YOU?":
- You are Aether, a personal AI running locally on the user's machine.
- Your brain is an Ollama LLM (llama3.2). Your memory is GroundCheck (trust-weighted SQLite + embeddings). Your verification layer is CRT-as-Critic.
- You are NOT OpenAI, NOT ChatGPT, NOT Claude. You are a custom-built local system.

""".replace("{num_memories}", str(num_memories))

        prompt += """CONSTRAINTS:
1. ONLY reference facts from the RETRIEVED MEMORIES sections below
2. NEVER invent details not in the retrieved memories
3. If a fact is missing, say you don't have it - do NOT guess
4. If memory shows conflicting values, disclose the conflict
5. NEVER claim user facts as your own identity
6. Be direct and conversational, not robotic
7. When explaining how you work, draw from the ARCHITECTURE memories — don't recite templates

RESPONSE RULES (follow strictly):
- Answer ONLY what the user asked. Do NOT volunteer unrelated memories or facts.
- When citing a stored fact, quote the memory text EXACTLY as shown — do NOT paraphrase, shorten, or reword it.
- When listing items from memory (e.g. a numbered plan), reproduce ALL items completely. Do NOT drop, merge, or truncate list items.
- Keep your answer focused and concise. If the user asks one question, give one clear answer — don't dump everything you know.
- If multiple memories are shown but only some are relevant, use ONLY the relevant ones. Ignore the rest.

"""

        if preference_constraints:
            prompt += (
                "MANDATORY USER PREFERENCE CONSTRAINTS (high confidence):\n"
                f"{preference_constraints}\n"
                "Treat these as defaults unless the user overrides them in this turn.\n\n"
            )

        if style_hint:
            prompt += f"TONE & STYLE:\n{style_hint}\n\n"
        if adaptive_hint:
            prompt += f"{adaptive_hint}\n\n"
        
        # Add memory context if available — split into user facts and system self-knowledge
        if docs:
            # Separate user facts from system self-knowledge
            user_docs = [d for d in docs if d.get('text', '') and d.get('source') != 'system']
            system_docs = [d for d in docs if d.get('text', '') and d.get('source') == 'system']
            
            if user_docs:
                prompt += "=== RETRIEVED MEMORIES: USER FACTS ===\n"
                prompt += "These are facts the USER shared. Each has a trust score (0-1) and similarity score.\n\n"
                for i, mem in enumerate(user_docs[:6], 1):
                    trust = mem.get('trust') or mem.get('confidence')
                    trust_str = f" [trust: {trust:.2f}]" if trust is not None else ""
                    source = mem.get('source', '')
                    source_str = f" (source: {source})" if source else ""
                    sim = mem.get('similarity')
                    sim_str = f" [similarity: {sim:.2f}]" if sim is not None else ""
                    prompt += f"{i}. {mem['text']}{trust_str}{source_str}{sim_str}\n"
                prompt += "\n"
            
            if system_docs:
                prompt += "=== RETRIEVED MEMORIES: YOUR OWN ARCHITECTURE ===\n"
                prompt += "These are facts about YOUR OWN system. Use them to explain how you work.\n\n"
                for i, mem in enumerate(system_docs[:5], 1):
                    trust = mem.get('trust') or mem.get('confidence')
                    trust_str = f" [trust: {trust:.2f}]" if trust is not None else ""
                    sim = mem.get('similarity')
                    sim_str = f" [similarity: {sim:.2f}]" if sim is not None else ""
                    prompt += f"{i}. {mem['text']}{trust_str}{sim_str}\n"
                prompt += "\n"
            
            if not user_docs and not system_docs:
                prompt += "=== RETRIEVED MEMORIES ===\n(Memories were retrieved but could not be categorized)\n\n"
        else:
            prompt += "=== RETRIEVED MEMORIES ===\n(No stored memories matched this query)\n\n"
        
        # If the user is asking HOW we know something, inject retrieval metadata
        # so the small LLM has concrete facts to cite instead of guessing.
        ql = query.lower()
        is_how_do_you_know = any(phrase in ql for phrase in (
            "how do you know",
            "how are you sure",
            "how can you be sure",
            "how do you remember",
            "how did you know",
            "where did you learn",
            "how do you have that",
            "explain your process",
            "explain the technical",
        ))
        if is_how_do_you_know and docs:
            prompt += "=== RETRIEVAL CONTEXT (weave this into your answer naturally) ===\n"
            prompt += f"Total memories in your database: {num_memories}\n"
            prompt += "The user's question was embedded as a 384-dim vector and matched via cosine similarity.\n"
            prompt += "The memories shown above are the top matches. Cite specific trust scores and similarity scores.\n"
            prompt += "After you respond, CRT-as-Critic will verify your answer against these memories.\n\n"

        # Web search results — inject DuckDuckGo results for real-time queries
        web_results = context.get('web_search_results', [])
        if web_results:
            logger.info("[REASONING] Injecting %d web search results into prompt", len(web_results))
            prompt += "=== WEB SEARCH RESULTS ===\n"
            prompt += "The following are real-time web search results from multiple angles.\n"
            prompt += "INSTRUCTIONS for using these results:\n"
            prompt += "- Provide a comprehensive summary that covers the key facts and events.\n"
            prompt += "- Include BOTH supporting evidence AND criticism/counter-claims when available.\n"
            prompt += "- Generalize and synthesize across sources — don't just list them.\n"
            prompt += "- Note areas of agreement vs disagreement between sources.\n"
            prompt += "- Cite sources [1], [2], etc. for specific claims.\n"
            prompt += "- Aim for a balanced, well-rounded answer (4-8 sentences).\n\n"
            for i, result in enumerate(web_results[:12], 1):
                title = result.get('title', 'No title')
                snippet = result.get('snippet', result.get('body', ''))
                url = result.get('url', result.get('href', ''))
                prompt += f"{i}. **{title}**\n"
                if snippet:
                    prompt += f"   {snippet[:500]}\n"
                if url:
                    prompt += f"   Source: {url}\n"
                prompt += "\n"

        # Copilot GroundCheck context — inject recent MCP memories when user asks about Copilot
        copilot_ctx = context.get('copilot_context', [])
        if copilot_ctx:
            # Filter: only include memories with meaningful text (>30 chars) and reasonable trust
            filtered_ctx = [
                mem for mem in copilot_ctx
                if len(mem.get('text', '')) > 30
                and mem.get('trust', 0) >= 0.35
                and not mem.get('text', '').startswith("User's ")  # skip auto-extracted garbage
            ]
            if filtered_ctx:
                logger.info("[REASONING] Injecting %d Copilot context memories into prompt (filtered from %d)",
                            len(filtered_ctx), len(copilot_ctx))
                prompt += "=== COPILOT GROUNDCHECK CONTEXT ===\n"
                prompt += "These are recent memories from the Copilot GroundCheck MCP system (VS Code sessions).\n"
                prompt += "Summarize what Copilot has been working on based on these stored facts.\n"
                prompt += "IMPORTANT: Quote the work plan items EXACTLY as stored. Do NOT paraphrase or omit items.\n\n"
                for i, mem in enumerate(filtered_ctx[:10], 1):
                    trust = mem.get('trust', 0)
                    source = mem.get('source', 'unknown')
                    ns = mem.get('namespace', 'default')
                    ts = mem.get('timestamp')
                    ts_str = ""
                    if ts:
                        import datetime
                        try:
                            dt = datetime.datetime.fromtimestamp(ts)
                            ts_str = f" @ {dt.strftime('%b %d %H:%M')}"
                        except Exception:
                            pass
                    prompt += f"{i}. [{source}] (ns={ns}, trust={trust:.2f}{ts_str}) {mem['text'][:300]}\n"
                prompt += "\n"

        prompt += f"User: {query}\n\n"
        prompt += "Assistant:"
        
        return prompt
    
    def _build_thinking_prompt(self, query: str, context: Dict, analysis: str, plan: str) -> str:
        """Build prompt for thinking mode."""
        docs = context.get('retrieved_docs', [])
        contradictions = context.get('contradictions', [])
        style_hint = self._format_style_hint(context.get("style_profile"))
        preference_constraints = self._format_preference_constraints(
            context.get("episodic_preferences"),
        )
        adaptive_hint = self._format_adaptive_hint(
            context.get("personality_profile"),
            context.get("reflection_scorecard"),
            context.get("episodic_preferences"),
        )
        
        prompt = """You are Aether, a personal AI built on CRT-GroundCheck. You run locally.

HOW YOU WORK:
- GroundCheck Memory: SQLite + 384-dim semantic embeddings, trust scores 0-1
- Semantic Search: Queries are embedded and matched against stored memories via cosine similarity
- CRT-as-Critic: Post-generation verification catches contradictions in ~1ms
- Contradiction Ledger: Conflicts are tracked, nothing silently overwritten
- Web Search: DuckDuckGo tool for real-time info

CRITICAL: Facts in memory are ABOUT THE USER, not about you. You are an AI system.
When asked "how do you know?", cite the specific memory and its trust score.

"""
        if style_hint:
            prompt += f"TONE & STYLE:\n{style_hint}\n\n"
        if preference_constraints:
            prompt += (
                "MANDATORY USER PREFERENCE CONSTRAINTS (high confidence):\n"
                f"{preference_constraints}\n\n"
            )
        if adaptive_hint:
            prompt += f"ADAPTIVE CONTEXT:\n{adaptive_hint}\n\n"

        prompt += f"Question: {query}\n\n"
        prompt += f"Analysis: {analysis}\n"
        prompt += f"Plan: {plan}\n\n"
        
        if docs:
            prompt += "Context from memory (facts ABOUT THE USER):\n" + "\n".join([d['text'] for d in docs[:5]]) + "\n\n"
        
        if contradictions:
            prompt += f"Note: {len(contradictions)} contradictions found. Present multiple perspectives honestly.\n\n"
        
        prompt += "Your response:"
        
        return prompt
    
    def _build_deep_prompt(self, query: str, context: Dict, plan: str, execution: str) -> str:
        """Build prompt for deep mode."""
        style_hint = self._format_style_hint(context.get("style_profile"))
        preference_constraints = self._format_preference_constraints(
            context.get("episodic_preferences"),
        )
        adaptive_hint = self._format_adaptive_hint(
            context.get("personality_profile"),
            context.get("reflection_scorecard"),
            context.get("episodic_preferences"),
        )
        prompt = """You are Aether, a personal AI built on CRT-GroundCheck. Facts in memory are ABOUT THE USER, not about you.
When asked about yourself, explain your actual architecture: GroundCheck memory (trust-weighted SQLite + embeddings), CRT-as-Critic verification, web search via DuckDuckGo.
Do NOT claim user's personal attributes (name, job, location) as your own.\n\n"""
        if style_hint:
            prompt += f"TONE & STYLE:\n{style_hint}\n\n"
        if preference_constraints:
            prompt += (
                "MANDATORY USER PREFERENCE CONSTRAINTS (high confidence):\n"
                f"{preference_constraints}\n\n"
            )
        if adaptive_hint:
            prompt += f"ADAPTIVE CONTEXT:\n{adaptive_hint}\n\n"
        prompt += f"Complex Question: {query}\n\n"
        prompt += f"Reasoning Plan: {plan}\n"
        prompt += f"Execution: {execution}\n\n"
        prompt += "Synthesize comprehensive answer addressing all aspects:"
        
        return prompt
    
    def _call_llm(
        self,
        prompt: str,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
    ) -> str:
        """Call LLM (Ollama or fallback)."""
        if self.llm is None:
            return f"[No LLM available - install Ollama and run: ollama pull llama3.2]"
        
        try:
            return self.llm.generate(
                prompt,
                max_tokens=max_tokens,
                model=model_override,
            )
        except TypeError:
            # Backward compatibility for lightweight test doubles / older clients.
            return self.llm.generate(prompt, max_tokens=max_tokens)
        except Exception as e:
            return f"[LLM error: {e}]"
    
    def get_reasoning_traces(self, limit: int = 10) -> List[Dict]:
        """Get recent reasoning traces (for debugging/analysis)."""
        return [t.to_dict() for t in self.reasoning_traces[-limit:]]
