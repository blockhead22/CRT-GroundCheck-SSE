"""
CRT-as-Critic: Post-generation verification and revision using GroundCheck.

This is the core differentiator — a 1ms external truth layer that replaces
self-critique (which 7B models are terrible at) with memory-grounded verification.

Flow:
    1. Agent/engine generates a draft answer
    2. CRTCritic.verify_draft() checks it against stored memories via GroundCheck
    3. Based on trust score:
       - PASS  (confidence > 0.7): Ship the answer
       - SOFT  (0.4–0.7): Feed contradictions back, model revises once
       - HARD  (< 0.4): Surface contradiction to user directly
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VerifyVerdict(str, Enum):
    """Result of CRT verification."""
    PASS = "pass"          # confidence > high_threshold — ship it
    SOFT_FAIL = "soft_fail"  # between low and high — revise once
    HARD_FAIL = "hard_fail"  # below low_threshold — surface to user


@dataclass
class CriticResult:
    """Complete result from CRT-as-Critic verification."""
    verdict: VerifyVerdict
    original_answer: str
    final_answer: str
    confidence: float
    contradictions: List[str] = field(default_factory=list)
    hallucinations: List[str] = field(default_factory=list)
    revision_prompt: Optional[str] = None
    was_revised: bool = False
    disclosure_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "contradictions": self.contradictions,
            "hallucinations": self.hallucinations,
            "was_revised": self.was_revised,
            "disclosure_text": self.disclosure_text,
        }


class CRTCritic:
    """
    Post-generation verification layer using GroundCheck.
    
    Replaces LLM self-critique (unreliable on small models) with
    external memory-grounded truth checking at ~1ms cost.
    """

    # Threshold defaults — tune these live via config
    HIGH_THRESHOLD = 0.7   # Above this → ship
    LOW_THRESHOLD = 0.4    # Below this → hard fail (surface to user)

    REVISION_SYSTEM_PROMPT = (
        "You are CRT, a precise AI assistant with persistent memory. "
        "Your previous answer contained factual errors based on what the user "
        "has told you before. Revise your answer using ONLY the corrections below. "
        "Do NOT apologize or explain — just give the correct answer."
    )

    REVISION_TEMPLATE = (
        "Original question: {query}\n\n"
        "Your draft answer: {draft}\n\n"
        "CORRECTIONS from stored memory:\n{corrections}\n\n"
        "Revise your answer to be consistent with those corrections. "
        "Be concise."
    )

    DISCLOSURE_TEMPLATE = (
        "I found a conflict in what I know:\n\n"
        "{conflicts}\n\n"
        "Which one is correct?"
    )

    def __init__(
        self,
        high_threshold: float = HIGH_THRESHOLD,
        low_threshold: float = LOW_THRESHOLD,
    ):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self._gc = None  # Lazy init

    @property
    def gc(self):
        """Lazy-load GroundCheck to avoid import overhead on every request."""
        if self._gc is None:
            try:
                from groundcheck import GroundCheck
                self._gc = GroundCheck()
                logger.info("[CRT-CRITIC] GroundCheck initialized")
            except ImportError:
                logger.warning("[CRT-CRITIC] GroundCheck not installed — critic disabled")
                self._gc = False  # Sentinel: tried and failed
            except Exception as e:
                logger.warning(f"[CRT-CRITIC] GroundCheck init failed: {e}")
                self._gc = False
        return self._gc if self._gc is not False else None

    @staticmethod
    def _normalize_conflict_value(value: Any) -> str:
        txt = str(value or "").strip().lower()
        if not txt:
            return ""
        # Collapse punctuation/whitespace variants (e.g., "Nick  Block" vs "nick block").
        txt = re.sub(r"[^a-z0-9]+", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    @classmethod
    def _dedupe_conflict_values(cls, values: List[Any], trust_scores: List[Any]) -> List[Dict[str, Any]]:
        deduped: Dict[str, Dict[str, Any]] = {}
        for i, raw_val in enumerate(values or []):
            norm = cls._normalize_conflict_value(raw_val)
            if not norm:
                continue
            raw_trust = trust_scores[i] if i < len(trust_scores or []) else 0.0
            try:
                trust = float(raw_trust)
            except Exception:
                trust = 0.0

            existing = deduped.get(norm)
            if existing is None or trust > float(existing.get("trust", 0.0)):
                deduped[norm] = {
                    "display": str(raw_val),
                    "trust": trust,
                    "norm": norm,
                }
        # Stable, deterministic order: highest trust first, then normalized text.
        return sorted(deduped.values(), key=lambda x: (-float(x["trust"]), str(x["norm"])))

    def verify_draft(
        self,
        query: str,
        draft_answer: str,
        retrieved_memories: List[Dict[str, Any]],
        llm_client: Optional[Any] = None,
    ) -> CriticResult:
        """
        Verify a draft answer against stored memories and optionally revise.

        Args:
            query: The user's original question
            draft_answer: The LLM-generated draft answer
            retrieved_memories: List of memory dicts with keys:
                text, trust, memory_id (optional), source (optional)
            llm_client: OllamaClient for revision (optional — if None, can't revise)

        Returns:
            CriticResult with verdict, possibly revised answer, and metadata
        """
        # If no memories to check against, pass through
        if not retrieved_memories or not draft_answer:
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=draft_answer,
                confidence=1.0,
            )

        gc = self.gc
        if gc is None:
            # GroundCheck unavailable — pass through with warning
            logger.debug("[CRT-CRITIC] GroundCheck unavailable, passing draft through")
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=draft_answer,
                confidence=0.5,  # Unknown confidence
            )

        # Convert memory dicts to GroundCheck Memory objects
        try:
            from groundcheck.types import Memory as GCMemory
        except ImportError:
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=draft_answer,
                confidence=0.5,
            )

        gc_memories = []
        for m in retrieved_memories:
            if not isinstance(m, dict) or not m.get("text"):
                continue
            gc_memories.append(GCMemory(
                id=str(m.get("memory_id", m.get("id", "unknown"))),
                text=m["text"],
                trust=float(m.get("trust", 0.5)),
                metadata=m.get("metadata"),
            ))

        if not gc_memories:
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=draft_answer,
                confidence=1.0,
            )

        # Run GroundCheck verification (~1ms)
        try:
            report = gc.verify(
                generated_text=draft_answer,
                retrieved_memories=gc_memories,
                mode="strict",
            )
        except Exception as e:
            logger.warning(f"[CRT-CRITIC] GroundCheck.verify() failed: {e}")
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=draft_answer,
                confidence=0.5,
            )

        confidence = report.confidence
        contradictions = list(report.contradicted_claims or [])
        hallucinations = list(report.hallucinations or [])
        
        _mem_contradictions = len(report.contradiction_details or [])
        logger.info(
            f"[CRT-CRITIC] Confidence: {confidence:.2f} | "
            f"Contradicted claims: {len(contradictions)} | "
            f"Hallucinations: {len(hallucinations)} | "
            f"Memory contradictions: {_mem_contradictions} | "
            f"Passed: {report.passed}"
        )

        # --- PASS: confidence high, no contradictions ---
        if confidence >= self.high_threshold and not contradictions:
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=report.corrected or draft_answer,
                confidence=confidence,
                contradictions=contradictions,
                hallucinations=hallucinations,
            )

        # --- PASS: no verifiable claims in response (conversational/meta text) ---
        # When GroundCheck can't extract meaningful facts from the response,
        # confidence will be very low but that's "no opinion", not "wrong".
        # Only pass if the response doesn't reference any contradicted facts.
        _facts_in_response = len(report.facts_extracted or {}) - len(report.facts_out_of_scope or {})
        if _facts_in_response <= 0 and not contradictions:
            logger.info("[CRT-CRITIC] No verifiable claims in response — passing (no opinion)")
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=draft_answer,
                confidence=1.0,  # No opinion = no problem
                contradictions=[],
                hallucinations=[],
            )

        # --- HARD FAIL: confidence very low AND actual contradictions found ---
        # NOTE: confidence=0.0 with no contradictions means GroundCheck had no
        # opinion (e.g., conversational/meta response). Don't hard-fail on that.
        #
        # IMPORTANT: Only count contradicted_claims (facts the response actually
        # references that conflict with memory). Hallucinations from the regex
        # fact extractor on conversational text are noise, not real errors.
        # Memory-vs-memory contradictions (contradiction_details) should only
        # trigger disclosure if the response uses one of those contradicted facts.
        _has_real_contradictions = len(contradictions) > 0  # contradicted_claims only
        # Hallucinations only count if the response also has grounded facts
        # (i.e., confidence > 0 means GroundCheck actually found verifiable claims).
        # When confidence=0.0 and hallucinations exist, the regex extractor pulled
        # garbage "facts" from conversational text — not real hallucinations.
        if confidence > 0 and len(hallucinations) > 0:
            _has_real_contradictions = True
        if (confidence < self.low_threshold and _has_real_contradictions) or len(contradictions) >= 3:
            # Build disclosure text for the user
            conflict_lines = []
            for detail in (report.contradiction_details or []):
                slot = getattr(detail, "slot", "unknown")
                values = getattr(detail, "values", [])
                trust_scores = getattr(detail, "trust_scores", [])

                if values and len(values) >= 2:
                    # Show the conflicting values with trust scores
                    parts = []
                    deduped = self._dedupe_conflict_values(values, trust_scores)
                    for item in deduped:
                        parts.append(f"\"{item['display']}\" (trust: {float(item['trust']):.1f})")
                    if len(parts) >= 2:
                        conflict_lines.append(f"• Your {slot}: {' vs '.join(parts)}")
                    elif len(parts) == 1:
                        conflict_lines.append(f"• Your {slot}: {parts[0]}")
                elif values:
                    conflict_lines.append(f"• {slot}: {values[0]}")

            if not conflict_lines and contradictions:
                conflict_lines = [f"• {c}" for c in contradictions]
            if not conflict_lines and hallucinations:
                conflict_lines = [f"• I was going to say \"{h}\" but that doesn't match your records" for h in hallucinations]

            disclosure = self.DISCLOSURE_TEMPLATE.format(
                conflicts="\n".join(conflict_lines) if conflict_lines else "Multiple conflicting facts detected."
            )

            return CriticResult(
                verdict=VerifyVerdict.HARD_FAIL,
                original_answer=draft_answer,
                final_answer=disclosure,
                confidence=confidence,
                contradictions=contradictions,
                hallucinations=hallucinations,
                disclosure_text=disclosure,
            )

        # --- SOFT FAIL: in between — try to revise once ---
        # But first: if confidence=0.0 and no contradicted_claims, the response
        # has no verifiable claims that conflict with memory. Don't revise —
        # the "soft fail" is just noise from regex fact extraction on non-factual text.
        if confidence == 0.0 and not contradictions:
            logger.info("[CRT-CRITIC] confidence=0.0 with no contradicted claims — passing (no real issues)")
            return CriticResult(
                verdict=VerifyVerdict.PASS,
                original_answer=draft_answer,
                final_answer=draft_answer,
                confidence=1.0,
                contradictions=[],
                hallucinations=[],
            )

        corrections = []
        if report.corrected and report.corrected != draft_answer:
            corrections.append(f"Corrected version: {report.corrected}")
        for c in contradictions:
            corrections.append(f"Contradiction: {c}")
        for h in hallucinations:
            corrections.append(f"Hallucination: {h}")
        if report.expected_disclosure:
            corrections.append(f"Should disclose: {report.expected_disclosure}")

        correction_text = "\n".join(corrections) if corrections else "Review for factual accuracy."

        # If we have an LLM, attempt revision
        if llm_client is not None and corrections:
            revision_prompt = self.REVISION_TEMPLATE.format(
                query=query,
                draft=draft_answer,
                corrections=correction_text,
            )

            try:
                revised = llm_client.generate(
                    prompt=revision_prompt,
                    system=self.REVISION_SYSTEM_PROMPT,
                    max_tokens=400,
                    temperature=0.3,  # Low temp for precision
                )
                # Handle both string and dict returns
                if isinstance(revised, dict):
                    revised = revised.get("response", "") or revised.get("text", "")
                revised = str(revised).strip()

                leaked_prompt_markers = (
                    "original question:",
                    "your draft answer:",
                    "corrections from stored memory:",
                    "revise your answer",
                )
                if revised and any(marker in revised.lower() for marker in leaked_prompt_markers):
                    logger.warning("[CRT-CRITIC] Discarding leaked revision prompt output")
                    revised = ""

                if revised and len(revised) > 10:
                    logger.info(f"[CRT-CRITIC] Revised answer ({len(draft_answer)} → {len(revised)} chars)")
                    return CriticResult(
                        verdict=VerifyVerdict.SOFT_FAIL,
                        original_answer=draft_answer,
                        final_answer=revised,
                        confidence=confidence,
                        contradictions=contradictions,
                        hallucinations=hallucinations,
                        revision_prompt=revision_prompt,
                        was_revised=True,
                    )
            except Exception as e:
                logger.warning(f"[CRT-CRITIC] Revision failed: {e}")

        # Revision not available or failed — use draft_answer as safe fallback.
        # Don't use report.corrected here: if LLM revision failed (e.g., Ollama down),
        # report.corrected may be None or incomplete. The draft_answer from Claude is
        # always a valid response.
        fallback = draft_answer
        return CriticResult(
            verdict=VerifyVerdict.SOFT_FAIL,
            original_answer=draft_answer,
            final_answer=fallback,
            confidence=confidence,
            contradictions=contradictions,
            hallucinations=hallucinations,
            was_revised=report.corrected is not None and report.corrected != draft_answer,
        )
