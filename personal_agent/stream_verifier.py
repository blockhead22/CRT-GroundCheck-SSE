"""
Mid-stream verification for CRT streaming responses.

Runs lightweight checks on buffered tokens during streaming:
  1. Think tag leak detection (regex, near-zero cost)
  2. Fact contradiction check against retrieved memories (string matching)
  3. Repetition detection (sentence dedup)

Modeled after the validated test harness at tests/cloud_providers/test_stream_pause.py,
adapted for the production chunked-streaming architecture.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CheckpointResult:
    """Result of a single mid-stream checkpoint."""
    token_count: int
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    action: str = "continue"  # "continue", "strip", "stop", "regenerate"
    stripped_content: Optional[str] = None
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_count": self.token_count,
            "passed": self.checks_passed,
            "failed": self.checks_failed,
            "warnings": self.warnings,
            "action": self.action,
            "detail": self.detail,
        }


class StreamVerifier:
    """Runs mid-stream verification checks on buffered response content.

    Usage:
        verifier = StreamVerifier(retrieved_memories=[...])
        for chunk in response_chunks:
            buffer += chunk
            # yield chunk to client
            if verifier.should_checkpoint(buffer):
                result = verifier.run_checkpoint(buffer)
                if result.action == "stop":
                    break
    """

    def __init__(
        self,
        retrieved_memories: Optional[List[Dict[str, Any]]] = None,
        checkpoint_interval: int = 150,
    ):
        self.retrieved_memories = retrieved_memories or []
        self.checkpoint_interval = checkpoint_interval
        self._next_checkpoint = checkpoint_interval
        self._char_count = 0
        self.checkpoints: List[CheckpointResult] = []

    def should_checkpoint(self, buffer: str) -> bool:
        """Check if we've accumulated enough visible tokens for a checkpoint.

        Uses character-based approximation: ~4 chars per token.
        """
        approx_tokens = len(buffer) // 4
        return approx_tokens >= self._next_checkpoint

    def run_checkpoint(self, buffer: str) -> CheckpointResult:
        """Run all verification checks on the current buffer."""
        approx_tokens = len(buffer) // 4
        result = CheckpointResult(token_count=approx_tokens)

        # Check 1: Think tag leak detection
        think_result = self._check_think_leak(buffer)
        if think_result == "leak":
            result.checks_failed.append("think_tag_leak")
            result.action = "strip"
            result.stripped_content = self._strip_think_tags(buffer)
            result.detail = "Think tags detected in visible response — stripped"
        else:
            result.checks_passed.append("no_think_leak")

        # Check 2: Fact contradiction against retrieved memories
        contradiction = self._check_fact_contradiction(buffer)
        if contradiction:
            result.checks_failed.append("fact_contradiction")
            if result.action != "strip":
                result.action = "stop"
            result.detail = contradiction
        else:
            result.checks_passed.append("no_fact_contradiction")

        # Check 3: Repetition detection
        repetition = self._check_repetition(buffer)
        if repetition:
            result.checks_failed.append("repetition_detected")
            if result.action == "continue":
                result.action = "stop"
            if not result.detail:
                result.detail = repetition
        else:
            result.checks_passed.append("no_repetition")

        self._next_checkpoint += self.checkpoint_interval
        self.checkpoints.append(result)
        logger.info(
            "[STREAM_VERIFY] Checkpoint @ ~%d tokens: %d passed, %d failed, action=%s",
            approx_tokens,
            len(result.checks_passed),
            len(result.checks_failed),
            result.action,
        )
        return result

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_think_leak(self, buffer: str) -> str:
        """Detect <think> tags leaking into visible response.

        Note: For Ollama qwen3, thinking comes in a separate 'thinking' field
        and should never appear in the 'response' field. This check catches
        cases where think content leaks into visible output via any path.
        """
        # Check for explicit <think> tags
        if re.search(r"<think>", buffer, re.IGNORECASE):
            return "leak"
        # Check for partial think tags at the end of buffer
        if buffer.rstrip().endswith("<think") or buffer.rstrip().endswith("<thin"):
            return "leak"
        return "ok"

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think>...</think> blocks from text."""
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Also strip incomplete think blocks at the end
        cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        return cleaned.strip()

    def _check_fact_contradiction(self, buffer: str) -> Optional[str]:
        """Check if the response contradicts known facts from retrieved memories.

        Uses simple keyword matching against memory slot values.
        Returns a description of the contradiction, or None.
        """
        if not self.retrieved_memories:
            return None

        buffer_lower = buffer.lower()

        # Extract fact-like entries from retrieved memories
        for mem in self.retrieved_memories:
            if not isinstance(mem, dict):
                continue
            text = str(mem.get("text") or "").strip()
            trust = float(mem.get("trust") or mem.get("confidence") or 0)

            # Only check high-trust facts
            if trust < 0.7 or not text:
                continue

            # Look for FACT: slot = value pattern
            fact_match = re.search(
                r"(?:FACT|PREF):\s*([A-Za-z0-9_ ]+)\s*=\s*(.+)",
                text, re.IGNORECASE,
            )
            if not fact_match:
                continue

            slot_name = fact_match.group(1).strip().lower()
            known_value = fact_match.group(2).strip().lower()

            # Check if the response mentions this slot with a different value
            # Only for exclusive slots where contradiction matters
            if slot_name in buffer_lower:
                # The slot is mentioned — check if the known value is present
                # Simple heuristic: if the slot name is in the response but
                # the known value is NOT, it might be wrong
                # (but we only flag if an alternative value IS present)
                if known_value not in buffer_lower and len(known_value) > 2:
                    # Potential contradiction — but be conservative
                    # Only flag if it looks like the model stated a different value
                    # in proximity to the slot name
                    slot_idx = buffer_lower.find(slot_name)
                    nearby = buffer_lower[max(0, slot_idx - 50):slot_idx + len(slot_name) + 100]
                    # Look for "is", ":", "=" patterns near the slot name
                    if any(w in nearby for w in (" is ", " are ", ": ", "= ")):
                        return (
                            f"Response mentions '{slot_name}' but known value "
                            f"'{known_value}' not found (trust={trust:.2f})"
                        )

        return None

    def _check_repetition(self, buffer: str) -> Optional[str]:
        """Detect sentence-level repetition in the response."""
        # Split into sentences (rough)
        sentences = [s.strip() for s in re.split(r'[.!?]\s+', buffer) if len(s.strip()) > 20]
        if len(sentences) < 3:
            return None

        # Normalize and check for duplicates
        normalized = [re.sub(r'\s+', ' ', s.lower().strip()) for s in sentences]
        seen = set()
        for s in normalized:
            if s in seen:
                return f"Repeated sentence detected: '{s[:60]}...'"
            seen.add(s)

        # Also check for near-duplicates (same first 30 chars)
        prefixes = [s[:30] for s in normalized if len(s) >= 30]
        prefix_seen = set()
        for p in prefixes:
            if p in prefix_seen:
                return f"Near-duplicate sentence prefix: '{p}...'"
            prefix_seen.add(p)

        return None

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of all checkpoints run."""
        total_passed = sum(len(c.checks_passed) for c in self.checkpoints)
        total_failed = sum(len(c.checks_failed) for c in self.checkpoints)
        return {
            "checkpoints_run": len(self.checkpoints),
            "total_passed": total_passed,
            "total_failed": total_failed,
            "actions_taken": [c.action for c in self.checkpoints if c.action != "continue"],
            "details": [c.to_dict() for c in self.checkpoints],
        }
