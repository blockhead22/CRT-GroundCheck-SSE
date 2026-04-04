"""
SSE (Semantic String Engine) - Phase 6 Boundary-Enforced API

Primary Entry Point: SSEClient (Phase 6.2)
    Safe, boundary-enforced client for SSE indices.
    Prevents Phase D+ operations at call time.

Advanced: SSENavigator (Phase 6.1)
    Full navigator with boundary violations explicitly raised.
    Use only if you need lower-level access.

Recommended: Always use SSEClient for production code.
"""

__version__ = "0.2.0"  # Phase 6.2 complete

# Primary API - Safe client (recommended)
from .client import SSEClient

# Advanced API - Full navigator (use with caution)
from .interaction_layer import SSENavigator, SSEBoundaryViolation

# Coherence tracking
from .coherence import CoherenceTracker, CoherenceBoundaryViolation

# Core components (for internal use)
from .evidence_packet import EvidencePacket

__all__ = [
    # Recommended
    'SSEClient',
    
    # Advanced
    'SSENavigator',
    'SSEBoundaryViolation',
    'CoherenceTracker',
    'CoherenceBoundaryViolation',
    
    # Core
    'EvidencePacket',
]
