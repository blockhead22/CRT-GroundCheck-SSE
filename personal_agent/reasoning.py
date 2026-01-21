"""
Reasoning Engine - Advanced Thinking Modes

Like Claude's extended thinking or Copilot's analysis phase.

Supports:
- Quick mode: Direct answer
- Thinking mode: Analyze → Plan → Reason → Answer
- Deep mode: Extended reasoning with sub-tasks
"""

import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


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
        """Initialize reasoning engine."""
        if llm_client is None:
            # Default to Ollama
            try:
                from .ollama_client import get_ollama_client
                llm_client = get_ollama_client()
            except Exception as e:
                print(f"⚠️  Could not initialize Ollama: {e}")
                llm_client = None
        
        self.llm = llm_client
        self.reasoning_traces = []  # Internal log
    
    def reason(
        self,
        query: str,
        context: Dict[str, Any],
        mode: Optional[ReasoningMode] = None
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
            stream = self.llm.generate(prompt, max_tokens=max_tokens, stream=True)
        except TypeError:
            # LLM client doesn't accept stream=...
            yield self._call_llm(prompt, max_tokens=max_tokens)
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
        
        # Simple prompt
        prompt = self._build_quick_prompt(query, context)
        
        # Generate (using LLM if available)
        if self.llm:
            answer = self._call_llm(prompt, max_tokens=500)
        else:
            answer = f"[Quick answer for: {query}]"
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Internal trace (not shown to user)
        trace = ReasoningTrace(
            query=query,
            mode="quick",
            thinking_steps=[
                ThinkingStep(
                    step_type="direct_answer",
                    content="No complexity detected, generating direct answer",
                    duration_ms=duration_ms,
                    timestamp=datetime.now().isoformat()
                )
            ],
            decision="quick_answer",
            confidence=0.8,
            contradictions_found=0,
            total_duration_ms=duration_ms
        )
        
        self.reasoning_traces.append(trace)
        
        return {
            'mode': ReasoningMode.QUICK.value,
            'thinking': None,  # Not shown in quick mode
            'answer': answer,
            'reasoning_trace': trace.to_dict(),
            'confidence': 0.8
        }
    
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
            answer = self._call_llm(prompt, max_tokens=1000)
        else:
            answer = f"[Thinking mode answer for: {query}]"
        
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
            answer = self._call_llm(prompt, max_tokens=2000)
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
    
    def _build_quick_prompt(self, query: str, context: Dict) -> str:
        """Build prompt for quick mode."""
        docs = context.get('retrieved_docs', [])
        
        prompt = """You are CRT (Cognitive-Reflective Transformer), a memory-first AI assistant.

CRITICAL: You are an AI assistant helping a USER. Facts in memory are ABOUT THE USER, not about you.
Do NOT claim the user's name, job, location, or any personal attributes as your own.

YOUR ARCHITECTURE (How you actually work):
- Trust-Weighted Memory: You store memories with trust scores (0-1) that evolve over time
- Belief vs Speech: Answers passing "reconstruction gates" become beliefs (high trust), others are speech (low trust fallback)
- Contradiction Ledger: When you encounter conflicting information, you don't overwrite - you track contradictions and preserve both views
- Coherence Over Time: You prioritize consistency across conversations over single-query accuracy
- Evidence Packets: Your reasoning is backed by provenance chains linking claims to source memories

CRITICAL CONSTRAINTS - MUST FOLLOW:
1. ONLY reference facts that appear in the USER FACTS section below
2. NEVER invent attributes, locations, jobs, or any details not explicitly in the facts
3. If asked to summarize/list facts: ONLY use facts from the USER FACTS section
4. If a fact is NOT in the USER FACTS section, say you don't have that information - do NOT guess
5. Do NOT add "typical" or "likely" attributes based on other facts (e.g., don't assume location from employer)
6. If memory shows conflicting values, acknowledge the conflict - don't pick one arbitrarily
7. NEVER claim user facts as your own identity (e.g., if user's name is "Nick", you are NOT Nick)

Your core principles:
- You ARE an AI assistant having a conversation with a USER
- Use ONLY the USER FACTS below to ground your responses about the user
- Be helpful, direct, and conversational
- When users introduce themselves or share info, acknowledge and remember it
- When explaining "how you work", describe your CRT architecture above, NOT generic transformer/AI concepts
- If asked about YOUR identity: you are CRT, an AI assistant - you do NOT have a human name, job, or location

"""
        
        # Add memory context if available
        if docs:
            prompt += "=== FACTS ABOUT THE USER (from your stored memories) ===\n"
            prompt += "IMPORTANT: These are facts the USER told you about THEMSELVES, NOT facts about you.\n"
            prompt += "You are an AI assistant. The user is a human. Do NOT claim these facts as your own identity.\n\n"
            user_memories = [d for d in docs if d.get('text', '')]
            for i, mem in enumerate(user_memories[:5], 1):
                prompt += f"{i}. {mem['text']}\n"
            prompt += "\n"
        else:
            prompt += "=== FACTS ABOUT THE USER ===\n(No stored facts about this user yet)\n\n"
        
        prompt += f"User: {query}\n\n"
        prompt += "Assistant: Respond using ONLY facts from the USER FACTS section above. These facts describe the USER, not you:"
        
        return prompt
    
    def _build_thinking_prompt(self, query: str, context: Dict, analysis: str, plan: str) -> str:
        """Build prompt for thinking mode."""
        docs = context.get('retrieved_docs', [])
        contradictions = context.get('contradictions', [])
        
        prompt = """You are CRT (Cognitive-Reflective Transformer), a memory-first AI assistant.

YOUR ARCHITECTURE:
- Trust-Weighted Beliefs: Memories have trust scores that evolve with evidence
- Contradiction Preservation: You track conflicts, don't overwrite them
- Reconstruction Gates: Outputs are validated for intent/memory alignment before becoming beliefs
- Coherence Priority: You maintain consistency over time, not just per-query accuracy

You are an AI assistant having a conversation with a USER. 
CRITICAL: Facts in memory are ABOUT THE USER (their name, job, location, etc.), NOT about you.
You do NOT have a human name, occupation, or personal attributes - you are an AI system.

"""
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
        prompt = """You are CRT, an AI assistant. Facts in memory are ABOUT THE USER, not about you.
Do NOT claim user's personal attributes (name, job, location) as your own.\n\n"""
        prompt += f"Complex Question: {query}\n\n"
        prompt += f"Reasoning Plan: {plan}\n"
        prompt += f"Execution: {execution}\n\n"
        prompt += "Synthesize comprehensive answer addressing all aspects:"
        
        return prompt
    
    def _call_llm(self, prompt: str, max_tokens: int = 1000) -> str:
        """Call LLM (Ollama or fallback)."""
        if self.llm is None:
            return f"[No LLM available - install Ollama and run: ollama pull llama3.2]"
        
        try:
            return self.llm.generate(prompt, max_tokens=max_tokens)
        except Exception as e:
            return f"[LLM error: {e}]"
    
    def get_reasoning_traces(self, limit: int = 10) -> List[Dict]:
        """Get recent reasoning traces (for debugging/analysis)."""
        return [t.to_dict() for t in self.reasoning_traces[-limit:]]
