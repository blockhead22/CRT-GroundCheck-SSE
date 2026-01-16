#!/usr/bin/env python3
"""
Seed CRT Memory with Project Profile

Seeds the system with basic information about CRT itself:
- What is CRT
- Who is building it
- Core principles
- Architecture
"""

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import MemorySource

def seed_crt_profile():
    """Seed CRT memory with foundational project information."""
    rag = CRTEnhancedRAG(
        memory_db="personal_agent/crt_memory.db",
        ledger_db="personal_agent/crt_ledger.db"
    )
    
    print("🌱 Seeding CRT Profile...")
    print("=" * 70)
    
    # Project identity
    facts = [
        {
            "text": "CRT (Cognitive-Reflective Transformer) is a memory-first AI assistant that prioritizes coherence over time.",
            "confidence": 1.0,
            "important": True
        },
        {
            "text": "CRT's core principle: 'The mouth must never outweigh the self' - responses must be grounded in verified memory.",
            "confidence": 1.0,
            "important": True
        },
        {
            "text": "CRT was created by Nick Block, a software architect exploring truthful personal AI systems.",
            "confidence": 1.0,
            "important": True
        },
        {
            "text": "CRT uses trust-weighted memory retrieval where memories have trust scores (0-1) that evolve with evidence.",
            "confidence": 1.0,
            "important": False
        },
        {
            "text": "CRT separates belief (high-trust, gate-passed outputs) from speech (low-trust fallback responses).",
            "confidence": 1.0,
            "important": False
        },
        {
            "text": "CRT maintains a contradiction ledger that preserves conflicting information instead of silently overwriting.",
            "confidence": 1.0,
            "important": False
        },
        {
            "text": "CRT implements reconstruction gates that validate responses for intent alignment and memory grounding before accepting as beliefs.",
            "confidence": 1.0,
            "important": False
        },
        {
            "text": "CRT was built in January 2026 as an exploration of memory-first AI architecture.",
            "confidence": 1.0,
            "important": False
        },
        {
            "text": "CRT's architecture includes: trust-weighted retrieval, drift detection, SSE compression, contradiction tracking, and evidence packets.",
            "confidence": 1.0,
            "important": False
        },
        {
            "text": "CRT is designed for coherence over time rather than optimizing single-query accuracy.",
            "confidence": 1.0,
            "important": True
        }
    ]
    
    for i, fact in enumerate(facts, 1):
        mem = rag.memory.store_memory(
            text=fact["text"],
            confidence=fact["confidence"],
            source=MemorySource.SYSTEM,
            context={"type": "project_profile", "category": "foundational"},
            user_marked_important=fact["important"]
        )
        
        status = "⭐" if fact["important"] else "  "
        print(f"{status} [{i:2d}] {fact['text'][:60]}...")
    
    print("=" * 70)
    print(f"✅ Seeded {len(facts)} foundational facts about CRT")
    print(f"📊 Memory system ready for use")
    
    # Verify
    retrieved = rag.retrieve("What is CRT?", k=3)
    print(f"\n🔍 Test retrieval: Found {len(retrieved)} memories")
    if retrieved:
        top = retrieved[0][0]
        print(f"   Top result: {top.text[:80]}...")
        print(f"   Trust: {top.trust:.3f}, Score: {retrieved[0][1]:.3f}")

if __name__ == "__main__":
    seed_crt_profile()
