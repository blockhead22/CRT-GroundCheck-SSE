"""Shared helpers for baseline systems."""

from __future__ import annotations

from typing import Any, Dict, Optional


def blank_response(
    answer: str = "",
    response_type: str = "speech",
    gates_passed: bool = False,
    gate_reason: str = "",
    contradiction_detected: bool = False,
    confidence: float = 0.0,
    intent_alignment: float = 0.0,
    memory_alignment: float = 0.0,
    best_prior_trust: Optional[float] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Return a minimal EvalSystem-compatible response dict."""
    d: Dict[str, Any] = {
        "answer": answer,
        "response_type": response_type,
        "gates_passed": gates_passed,
        "gate_reason": gate_reason,
        "contradiction_detected": contradiction_detected,
        "confidence": confidence,
        "intent_alignment": intent_alignment,
        "memory_alignment": memory_alignment,
        "best_prior_trust": best_prior_trust,
    }
    d.update(extra)
    return d
