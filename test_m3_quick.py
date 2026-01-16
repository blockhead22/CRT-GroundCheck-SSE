"""Quick test of M3 research functionality"""

from pathlib import Path
from personal_agent.research_engine import ResearchEngine
from personal_agent.evidence_packet import EvidencePacket

# Test 1: Create research engine
print("Test 1: Creating research engine...")
workspace_root = str(Path.cwd())
engine = ResearchEngine(workspace_root=workspace_root)
print(f"[OK] Research engine created with workspace: {workspace_root}")

# Test 2: Execute research query
print("\nTest 2: Executing research query...")
try:
    packet = engine.research(
        query="What is CRT?",
        max_sources=2,
        search_local=True,
        search_web=False,
    )
    print(f"[OK] Research completed!")
    print(f"  - Packet ID: {packet.packet_id}")
    print(f"  - Summary length: {len(packet.summary)} chars")
    print(f"  - Citations: {packet.citation_count()}")
    
    for i, citation in enumerate(packet.citations, 1):
        print(f"\n  Citation {i}:")
        print(f"    - Source: {citation.source_url}")
        print(f"    - Quote: {citation.quote_text[:100]}...")
        print(f"    - Offset: {citation.char_offset}")
        
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n[OK] M3 backend test complete!")
