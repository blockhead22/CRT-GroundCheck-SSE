"""
Phase 4.2: Adapters for EvidencePacket consumption

These adapters consume EvidencePacket format and are architecturally
prevented from corrupting the data through schema validation.

All adapters:
- Must accept EvidencePacket as input
- Must preserve all claims and contradictions
- Must validate output before returning
- Must log events to audit trail
"""

from .rag_adapter import RAGAdapter
from .search_adapter import SearchAdapter

__all__ = ["RAGAdapter", "SearchAdapter"]
