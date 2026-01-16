"""
M3 Evidence Packets - Unit Tests

Tests the research engine, evidence packets, and memory storage.
"""

import pytest
from pathlib import Path
from datetime import datetime

from personal_agent.evidence_packet import Citation, EvidencePacket
from personal_agent.research_engine import ResearchEngine
from personal_agent.crt_memory import CRTMemorySystem, MemorySource
from personal_agent.crt_core import CRTConfig


def test_citation_creation():
    """Test creating a citation with provenance."""
    citation = Citation(
        quote_text="This is a test quote",
        source_url="https://example.com/doc",
        char_offset=(100, 200),
        fetched_at=datetime.now(),
        confidence=0.8,
    )
    
    assert citation.quote_text == "This is a test quote"
    assert citation.source_url == "https://example.com/doc"
    assert citation.char_offset == (100, 200)
    assert citation.confidence == 0.8


def test_citation_serialization():
    """Test citation to_dict and from_dict."""
    original = Citation(
        quote_text="Test quote",
        source_url="file://test.md",
        char_offset=(0, 10),
        fetched_at=datetime(2026, 1, 15, 12, 0, 0),
        confidence=0.9,
    )
    
    data = original.to_dict()
    restored = Citation.from_dict(data)
    
    assert restored.quote_text == original.quote_text
    assert restored.source_url == original.source_url
    assert restored.char_offset == original.char_offset
    assert restored.confidence == original.confidence


def test_evidence_packet_creation():
    """Test creating an evidence packet."""
    citations = [
        Citation(
            quote_text="Quote 1",
            source_url="source1.md",
            char_offset=(0, 10),
            fetched_at=datetime.now(),
        ),
        Citation(
            quote_text="Quote 2",
            source_url="source2.md",
            char_offset=(50, 60),
            fetched_at=datetime.now(),
        ),
    ]
    
    packet = EvidencePacket.create(
        query="What is CRT?",
        summary="CRT is a memory system...",
        citations=citations,
    )
    
    assert packet.query == "What is CRT?"
    assert packet.summary == "CRT is a memory system..."
    assert packet.citation_count() == 2
    assert packet.trust == 0.4  # TOOL sources quarantined
    assert packet.lane == "notes"
    assert packet.has_citations()


def test_evidence_packet_serialization():
    """Test evidence packet to_dict and from_dict."""
    citations = [
        Citation(
            quote_text="Test",
            source_url="test.md",
            char_offset=(0, 4),
            fetched_at=datetime(2026, 1, 15, 12, 0, 0),
        )
    ]
    
    original = EvidencePacket.create(
        query="test query",
        summary="test summary",
        citations=citations,
    )
    
    data = original.to_dict()
    restored = EvidencePacket.from_dict(data)
    
    assert restored.query == original.query
    assert restored.summary == original.summary
    assert restored.citation_count() == original.citation_count()
    assert restored.trust == original.trust


def test_research_engine_local_search():
    """Test research engine with local document search."""
    workspace_root = str(Path.cwd())
    engine = ResearchEngine(workspace_root=workspace_root)
    
    # Search for something that should exist in our docs
    packet = engine.research(
        query="CRT memory system",
        max_sources=2,
        search_local=True,
        search_web=False,
    )
    
    assert packet.packet_id.startswith("ep_")
    assert packet.query == "CRT memory system"
    assert len(packet.summary) > 0
    assert packet.trust == 0.4
    assert packet.lane == "notes"


def test_research_storage_in_memory(tmp_path):
    """Test storing research results in CRT memory."""
    db_path = tmp_path / "test_memory.db"
    config = CRTConfig()
    memory = CRTMemorySystem(db_path=str(db_path), config=config)
    
    # Create evidence packet
    citations = [
        Citation(
            quote_text="CRT uses trust-weighted memory",
            source_url="docs/crt.md",
            char_offset=(100, 131),
            fetched_at=datetime.now(),
        )
    ]
    
    packet = EvidencePacket.create(
        query="How does CRT work?",
        summary="CRT uses trust-weighted memory for reliability.",
        citations=citations,
    )
    
    # Store research result
    memory_id = memory.store_research_result(
        query="How does CRT work?",
        evidence_packet=packet,
    )
    
    assert memory_id is not None
    assert memory_id.startswith("mem_")
    
    # Retrieve and verify
    stored = memory.retrieve_by_id(memory_id)
    assert stored is not None
    assert stored.text == packet.summary
    assert stored.source == MemorySource.EXTERNAL
    assert stored.trust == 0.4  # Quarantined
    
    # Check provenance
    assert stored.context is not None
    assert "provenance" in stored.context
    assert stored.context["provenance"]["tool"] == "research_engine"


def test_research_citations_retrieval(tmp_path):
    """Test retrieving citations from stored research."""
    db_path = tmp_path / "test_memory.db"
    config = CRTConfig()
    memory = CRTMemorySystem(db_path=str(db_path), config=config)
    
    # Store research with citations
    citations = [
        Citation(
            quote_text="Quote 1",
            source_url="source1.md",
            char_offset=(0, 10),
            fetched_at=datetime.now(),
        ),
        Citation(
            quote_text="Quote 2",
            source_url="source2.md",
            char_offset=(20, 30),
            fetched_at=datetime.now(),
        ),
    ]
    
    packet = EvidencePacket.create(
        query="test",
        summary="summary",
        citations=citations,
    )
    
    memory_id = memory.store_research_result("test", packet)
    
    # Retrieve citations
    retrieved_citations = memory.get_research_citations(memory_id)
    
    assert len(retrieved_citations) == 2
    assert retrieved_citations[0]["quote_text"] == "Quote 1"
    assert retrieved_citations[1]["quote_text"] == "Quote 2"


def test_research_promotion_to_belief(tmp_path):
    """Test promoting research from notes to belief lane."""
    db_path = tmp_path / "test_memory.db"
    config = CRTConfig()
    memory = CRTMemorySystem(db_path=str(db_path), config=config)
    
    # Store research
    packet = EvidencePacket.create(
        query="test",
        summary="test summary",
        citations=[],
    )
    
    memory_id = memory.store_research_result("test", packet)
    
    # Check initial trust (should be 0.4)
    stored = memory.retrieve_by_id(memory_id)
    assert stored.trust == 0.4
    
    # Promote to belief lane
    promoted = memory.promote_to_belief(memory_id, user_confirmed=True)
    assert promoted is True
    
    # Check trust increased
    promoted_memory = memory.retrieve_by_id(memory_id)
    assert promoted_memory.trust == 0.8  # Belief threshold


def test_promotion_requires_user_confirmation(tmp_path):
    """Test that promotion requires explicit user confirmation."""
    db_path = tmp_path / "test_memory.db"
    config = CRTConfig()
    memory = CRTMemorySystem(db_path=str(db_path), config=config)
    
    packet = EvidencePacket.create(
        query="test",
        summary="test",
        citations=[],
    )
    
    memory_id = memory.store_research_result("test", packet)
    
    # Try to promote without confirmation
    promoted = memory.promote_to_belief(memory_id, user_confirmed=False)
    assert promoted is False
    
    # Trust should not change
    memory_after = memory.retrieve_by_id(memory_id)
    assert memory_after.trust == 0.4


def test_evidence_packet_no_auto_promotion():
    """Test that evidence packets are always quarantined."""
    packet = EvidencePacket.create(
        query="test",
        summary="test",
        citations=[],
    )
    
    # Trust should be fixed at 0.4
    assert packet.trust == 0.4
    
    # Lane should be notes (quarantined)
    assert packet.lane == "notes"
