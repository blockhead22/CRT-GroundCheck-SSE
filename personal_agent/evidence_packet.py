"""
Evidence Packet - Provenance tracking for research results.

M3: Web/tool research that doesn't become lying.

Every research fact has a traceable source. If sources conflict,
system records contradiction instead of merging into false consensus.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
import hashlib


@dataclass
class Citation:
    """A single citation from a research source."""
    
    quote_text: str  # Exact quote from source
    source_url: str  # URL or file path
    char_offset: Tuple[int, int]  # (start, end) in original document
    fetched_at: datetime
    confidence: float = 0.8  # How confident the quote extraction is
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "quote_text": self.quote_text,
            "source_url": self.source_url,
            "char_offset": list(self.char_offset),
            "fetched_at": self.fetched_at.isoformat(),
            "confidence": self.confidence,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Citation":
        """Load from dict."""
        return cls(
            quote_text=data["quote_text"],
            source_url=data["source_url"],
            char_offset=tuple(data["char_offset"]),
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            confidence=data.get("confidence", 0.8),
        )


@dataclass
class EvidencePacket:
    """
    A research result with full provenance.
    
    Design:
    - packet_id: Unique identifier for this research query
    - query: Original user question
    - summary: Synthesized answer from sources
    - citations: List of sources supporting the summary
    - trust: Fixed at 0.4 for TOOL sources (quarantined)
    - lane: Always "notes" - never auto-promoted
    """
    
    packet_id: str
    query: str
    summary: str
    citations: List[Citation]
    created_at: datetime
    trust: float = 0.4  # TOOL sources start quarantined
    lane: str = "notes"  # Never goes to belief lane automatically
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "packet_id": self.packet_id,
            "query": self.query,
            "summary": self.summary,
            "citations": [c.to_dict() for c in self.citations],
            "created_at": self.created_at.isoformat(),
            "trust": self.trust,
            "lane": self.lane,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidencePacket":
        """Load from dict."""
        return cls(
            packet_id=data["packet_id"],
            query=data["query"],
            summary=data["summary"],
            citations=[Citation.from_dict(c) for c in data["citations"]],
            created_at=datetime.fromisoformat(data["created_at"]),
            trust=data.get("trust", 0.4),
            lane=data.get("lane", "notes"),
        )
    
    @staticmethod
    def generate_packet_id(query: str) -> str:
        """Generate deterministic packet ID from query."""
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"ep_{timestamp}_{query_hash}"
    
    @classmethod
    def create(
        cls,
        query: str,
        summary: str,
        citations: List[Citation],
    ) -> "EvidencePacket":
        """Create a new evidence packet."""
        return cls(
            packet_id=cls.generate_packet_id(query),
            query=query,
            summary=summary,
            citations=citations,
            created_at=datetime.now(),
            trust=0.4,  # TOOL sources always start quarantined
            lane="notes",
        )
    
    def has_citations(self) -> bool:
        """Check if packet has any citations."""
        return len(self.citations) > 0
    
    def citation_count(self) -> int:
        """Get number of citations."""
        return len(self.citations)
    
    def get_source_urls(self) -> List[str]:
        """Get list of all source URLs."""
        return [c.source_url for c in self.citations]
