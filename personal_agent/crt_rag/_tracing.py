from __future__ import annotations
import logging
import time
from typing import TYPE_CHECKING, Dict, List, Any, Optional
if TYPE_CHECKING:
    from ._engine import CRTEnhancedRAG

logger = logging.getLogger(__name__)


def trace_step(engine: "CRTEnhancedRAG", phase: str, message: str, data: Optional[Dict] = None):
    """
    Log an orchestration step for debugging/transparency.

    Args:
        phase: Step type (e.g., INTENT, FACTSTORE, CRT, RESPOND)
        message: Human-readable description
        data: Optional structured data for this step
    """
    step = {
        "phase": phase,
        "message": message,
        "timestamp": time.time(),
        "data": data or {}
    }
    engine._react_trace.append(step)

    if engine.react_tracing_enabled:
        logger.info(f"[{phase}] {message}")


def enable_tracing(engine: "CRTEnhancedRAG", enabled: bool = True):
    """Enable or disable step tracing."""
    engine.react_tracing_enabled = enabled
    logger.info(f"Tracing {'enabled' if enabled else 'disabled'}")


def get_trace(engine: "CRTEnhancedRAG") -> List[Dict[str, Any]]:
    """Get the trace from the last query."""
    return list(engine._react_trace)


def clear_trace(engine: "CRTEnhancedRAG"):
    """Clear the trace buffer."""
    engine._react_trace.clear()


def get_crt_status(engine: "CRTEnhancedRAG") -> Dict:
    """Get CRT system health and statistics."""
    return {
        'belief_speech_ratio': engine.memory.get_belief_speech_ratio(),
        'contradiction_stats': engine.ledger.get_contradiction_stats(),
        'pending_reflections': len(engine.ledger.get_reflection_queue()),
        'memory_count': len(engine.memory._load_all_memories()),
        'session_id': engine.session_id
    }


def get_open_contradictions(engine: "CRTEnhancedRAG") -> List[Dict]:
    """Get unresolved contradictions requiring reflection."""
    entries = engine.ledger.get_open_contradictions()
    return [e.to_dict() for e in entries]


def get_reflection_queue(engine: "CRTEnhancedRAG") -> List[Dict]:
    """Get pending reflections."""
    return engine.ledger.get_reflection_queue()
