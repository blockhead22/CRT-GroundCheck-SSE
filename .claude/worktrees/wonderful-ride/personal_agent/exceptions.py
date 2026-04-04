"""
CRT Exception Hierarchy

Centralized exception definitions. Replaces silent `except Exception: pass`
patterns with catchable, loggable error types.
"""

import logging

logger = logging.getLogger(__name__)


class CRTError(Exception):
    """Base exception for all CRT errors."""
    pass


class MemoryError(CRTError):
    """Error in memory storage or retrieval."""
    pass


class LedgerError(CRTError):
    """Error in contradiction ledger operations."""
    pass


class GroundingError(CRTError):
    """Error during grounding/fact-check computation."""
    pass


class ExtractionError(CRTError):
    """Error during fact extraction from text."""
    pass


class TrustComputationError(CRTError):
    """Error during trust score computation."""
    pass


class ReconstructionError(CRTError):
    """Error during memory reconstruction (future Holden integration)."""
    pass


class CompressionError(CRTError):
    """Error during memory compression (future Mirus integration)."""
    pass


class SubsystemInitError(CRTError):
    """A subsystem failed to initialize. Non-fatal but logged."""
    pass


def log_swallowed_exception(context: str, exc: Exception, level: str = "warning"):
    """
    Log an exception that would previously have been silently swallowed.
    
    Use this as a transition tool: replace `except Exception: pass` with
    `except Exception as e: log_swallowed_exception("context", e)`
    
    Args:
        context: Where the exception occurred (e.g., "crt_rag.__init__.classifier")
        exc: The exception instance
        level: Log level - "warning", "error", or "debug"
    """
    msg = f"[CRT] Swallowed exception in {context}: {type(exc).__name__}: {exc}"
    getattr(logger, level, logger.warning)(msg)
