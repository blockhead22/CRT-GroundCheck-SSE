"""
CRT System Demo - Cognitive-Reflective Transformer in Action

Demonstrates:
1. Trust-weighted retrieval (not just similarity)
2. Belief vs speech separation
3. Contradiction ledgers (no silent overwrites)
4. Trust evolution over time
5. Reconstruction gates (Holden constraints)
6. Reflection triggers

Philosophy:
- Memory first, honesty over performance
- Coherence over time > single-query accuracy
- "The mouth must never outweigh the self"
"""

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import MemorySource
import time


def demo_1_trust_weighted_retrieval():
    """
    Demo 1: Trust-Weighted Retrieval
    
    Shows how CRT retrieves based on trust + confidence + recency,
    not just similarity.
    """
    print("=" * 80)
    print("DEMO 1: Trust-Weighted Retrieval")
    print("Retrieval Score: R_i = similarity · recency · belief_weight")
    print("where belief_weight = α·trust + (1-α)·confidence")
    print("=" * 80)
    
    rag = CRTEnhancedRAG()
    
    # Store memories with different trust levels
    print("\n📝 Storing memories with varying trust...")
    
    # High trust memory (from system)
    rag.memory.store_memory(
        text="The sky is blue during the day",
        confidence=0.9,
        source=MemorySource.SYSTEM,
        context={'verified': True}
    )
    print("  ✓ Stored: 'Sky is blue' (System source, will have higher trust)")
    
    # Low trust memory (from fallback)
    rag.memory.store_memory(
        text="The sky is green during the day",
        confidence=0.8,
        source=MemorySource.FALLBACK,
        context={'verified': False}
    )
    print("  ✓ Stored: 'Sky is green' (Fallback source, capped at lower trust)")
    
    # Query
    print("\n❓ Query: 'What color is the sky?'")
    retrieved = rag.retrieve("What color is the sky?", k=2)
    
    print("\n📊 Retrieved (trust-weighted):")
    for i, (mem, score) in enumerate(retrieved, 1):
        print(f"\n  {i}. Score: {score:.4f}")
        print(f"     Text: {mem.text}")
        print(f"     Trust: {mem.trust:.3f}")
        print(f"     Confidence: {mem.confidence:.3f}")
        print(f"     Source: {mem.source.value}")
    
    print("\n💡 Notice: Higher-trust memory ranked first, even if similarity is similar")
    print()


def demo_2_belief_vs_speech():
    """
    Demo 2: Belief vs Speech Separation
    
    Shows how responses passing gates become "beliefs" (high trust),
    while those failing gates become "speech" (low trust fallback).
    """
    print("=" * 80)
    print("DEMO 2: Belief vs Speech Separation")
    print("Gates: Intent alignment ≥ θ AND Memory alignment ≥ θ")
    print("=" * 80)
    
    rag = CRTEnhancedRAG()
    
    # Store some base knowledge
    rag.memory.store_memory(
        text="Exercise improves sleep quality by regulating circadian rhythm",
        confidence=0.9,
        source=MemorySource.USER
    )
    
    # Query 1: Aligned with memory → Belief
    print("\n🔵 Query 1 (aligned): 'How does exercise help sleep?'")
    result1 = rag.query("How does exercise help sleep?")
    
    print(f"  Response Type: {result1['response_type']}")
    print(f"  Gates Passed: {result1['gates_passed']}")
    print(f"  Intent Alignment: {result1['intent_alignment']:.3f}")
    print(f"  Memory Alignment: {result1['memory_alignment']:.3f}")
    
    if result1['response_type'] == 'belief':
        print("  ✅ Stored as BELIEF (high trust)")
    
    # Check belief/speech ratio
    print("\n📊 Belief vs Speech Stats:")
    stats = rag.memory.get_belief_speech_ratio()
    print(f"  Beliefs: {stats['belief_count']}")
    print(f"  Speech: {stats['speech_count']}")
    print(f"  Belief Ratio: {stats['belief_ratio']:.1%}")
    
    print("\n💡 Principle: Only gate-passing responses become beliefs")
    print()


def demo_3_contradiction_ledger():
    """
    Demo 3: Contradiction Ledger (No Silent Overwrites)
    
    Shows how contradictions create ledger entries instead of
    silently replacing memories.
    """
    print("=" * 80)
    print("DEMO 3: Contradiction Ledger - No Silent Overwrites")
    print("When beliefs diverge: Create ledger entry, preserve both")
    print("=" * 80)
    
    rag = CRTEnhancedRAG()
    
    # Store initial belief
    print("\n📝 Initial belief:")
    rag.memory.store_memory(
        text="Coffee is bad for sleep because caffeine is a stimulant",
        confidence=0.85,
        source=MemorySource.SYSTEM
    )
    print("  ✓ Stored: 'Coffee is bad for sleep'")
    
    time.sleep(0.1)  # Small delay
    
    # Contradicting belief
    print("\n📝 New information (contradicts):")
    result = rag.query("Is coffee good for afternoon sleep?")
    
    if result['contradiction_detected']:
        print("  ⚠️ CONTRADICTION DETECTED")
        print(f"  Drift: {result['contradiction_entry']['drift_mean']:.3f}")
        print(f"  Summary: {result['contradiction_entry']['summary']}")
        print("\n  ✓ Created ledger entry (NO DELETION)")
        print("  ✓ Both memories preserved")
        print(f"  ✓ Old memory trust: degraded")
    
    # Show open contradictions
    print("\n📊 Open Contradictions:")
    contradictions = rag.get_open_contradictions()
    for contra in contradictions[:3]:
        print(f"  • {contra['summary']}")
        print(f"    Drift: {contra['drift_mean']:.3f}")
        print(f"    Status: {contra['status']}")
    
    print("\n💡 Principle: Contradictions are signals, not bugs")
    print("   History preserved, tension recorded, reflection queued")
    print()


def demo_4_trust_evolution():
    """
    Demo 4: Trust Evolution
    
    Shows how trust scores evolve based on alignment/contradiction.
    """
    print("=" * 80)
    print("DEMO 4: Trust Evolution Over Time")
    print("τ_new = f(τ_old, drift, alignment)")
    print("=" * 80)
    
    rag = CRTEnhancedRAG()
    
    # Store memory
    mem = rag.memory.store_memory(
        text="Regular sleep schedule improves health",
        confidence=0.8,
        source=MemorySource.SYSTEM
    )
    
    print(f"\n📝 Initial Memory:")
    print(f"  Text: {mem.text}")
    print(f"  Initial Trust: {mem.trust:.3f}")
    print(f"  Confidence: {mem.confidence:.3f}")
    
    # Simulate aligned query (should increase trust)
    print("\n🔵 Query (aligned): 'Why is sleep schedule important?'")
    result1 = rag.query("Why is sleep schedule important?")
    
    # Check trust after
    mem_after = rag.memory._load_all_memories()[0]
    print(f"  Trust after: {mem_after.trust:.3f}")
    if mem_after.trust > mem.trust:
        print(f"  ✓ Trust INCREASED (alignment)")
    
    # Simulate contradicting query (should decrease trust)
    print("\n🔴 Query (contradicts): 'Sleep schedule doesn't matter'")
    result2 = rag.query("Why doesn't sleep schedule matter?")
    
    # Show trust history
    print("\n📊 Trust Evolution History:")
    history = rag.memory.get_trust_history(mem.memory_id)
    for entry in history[:5]:
        print(f"  • {entry['reason']}")
        print(f"    {entry['old_trust']:.3f} → {entry['new_trust']:.3f}")
        if entry['drift']:
            print(f"    Drift: {entry['drift']:.3f}")
    
    print("\n💡 Principle: Trust evolves slowly, based on evidence")
    print()


def demo_5_reconstruction_gates():
    """
    Demo 5: Reconstruction Gates (Holden Constraints)
    
    Shows how intent/memory alignment gates prevent
    "sounding good while drifting".
    """
    print("=" * 80)
    print("DEMO 5: Reconstruction Gates (Holden Constraints)")
    print("Prevent: 'Mouth outweighing self'")
    print("=" * 80)
    
    rag = CRTEnhancedRAG()
    
    # Store knowledge base
    rag.memory.store_memory(
        text="Meditation reduces stress and improves focus",
        confidence=0.9,
        source=MemorySource.USER
    )
    
    # Query aligned with memory
    print("\n✅ Aligned Query: 'How does meditation help focus?'")
    result1 = rag.query("How does meditation help focus?")
    
    print(f"  Intent Alignment: {result1['intent_alignment']:.3f}")
    print(f"  Memory Alignment: {result1['memory_alignment']:.3f}")
    print(f"  Gates: {'PASSED' if result1['gates_passed'] else 'FAILED'}")
    print(f"  Result: {result1['response_type'].upper()}")
    
    print("\n📊 Gate Thresholds:")
    print(f"  θ_intent: {rag.config.theta_intent}")
    print(f"  θ_mem: {rag.config.theta_mem}")
    
    print("\n💡 Principle: Output must align with both intent AND memory")
    print("   Otherwise: marked as low-trust speech, not belief")
    print()


def demo_6_reflection_triggers():
    """
    Demo 6: Reflection Triggers
    
    Shows how volatility triggers reflection queuing.
    """
    print("=" * 80)
    print("DEMO 6: Reflection Triggers")
    print("V = β₁·drift + β₂·(1-alignment) + β₃·contradiction + β₄·fallback")
    print("=" * 80)
    
    rag = CRTEnhancedRAG()
    
    # Store belief
    rag.memory.store_memory(
        text="Consistent bedtime improves sleep quality",
        confidence=0.9,
        source=MemorySource.SYSTEM
    )
    
    # Create contradiction (high drift)
    print("\n🔴 High-drift query:")
    result = rag.query("Why is irregular bedtime better for sleep?")
    
    if result['contradiction_detected']:
        print("  ⚠️ Contradiction detected")
        print(f"  Drift: {result['contradiction_entry']['drift_mean']:.3f}")
        
        # Check reflection queue
        queue = rag.get_reflection_queue()
        if queue:
            print(f"\n📋 Reflection Queued:")
            for item in queue[:3]:
                print(f"  • Priority: {item['priority']}")
                print(f"    Volatility: {item['volatility']:.3f}")
                print(f"    Ledger ID: {item['ledger_id']}")
    
    print("\n💡 Principle: High volatility → reflection, not silent overwrite")
    print()


def demo_7_crt_health_monitoring():
    """
    Demo 7: CRT System Health
    
    Shows overall system statistics and health.
    """
    print("=" * 80)
    print("DEMO 7: CRT System Health & Statistics")
    print("=" * 80)
    
    rag = CRTEnhancedRAG()
    
    # Do some operations
    rag.query("What is cognitive coherence?")
    rag.query("Why does memory matter?")
    rag.query("How does trust evolve?")
    
    # Get status
    status = rag.get_crt_status()
    
    print("\n📊 CRT System Status:")
    print(f"\n  Belief vs Speech:")
    print(f"    Beliefs: {status['belief_speech_ratio']['belief_count']}")
    print(f"    Speech: {status['belief_speech_ratio']['speech_count']}")
    print(f"    Belief Ratio: {status['belief_speech_ratio']['belief_ratio']:.1%}")
    
    print(f"\n  Contradictions:")
    print(f"    Total: {status['contradiction_stats']['total_contradictions']}")
    print(f"    Open: {status['contradiction_stats']['open']}")
    print(f"    Resolved: {status['contradiction_stats']['resolved']}")
    print(f"    Avg Drift: {status['contradiction_stats']['average_drift']:.3f}")
    
    print(f"\n  Reflections:")
    print(f"    Pending: {status['pending_reflections']}")
    
    print(f"\n  Memory:")
    print(f"    Total Items: {status['memory_count']}")
    
    print("\n💡 CRT maintains coherence over time, not just accuracy per query")
    print()


def main():
    """Run all CRT demos."""
    print("\n" + "=" * 80)
    print("CRT (Cognitive-Reflective Transformer) SYSTEM DEMOS")
    print("Memory First. Honesty Over Performance.")
    print("=" * 80 + "\n")
    
    demos = [
        ("Trust-Weighted Retrieval", demo_1_trust_weighted_retrieval),
        ("Belief vs Speech", demo_2_belief_vs_speech),
        ("Contradiction Ledger", demo_3_contradiction_ledger),
        ("Trust Evolution", demo_4_trust_evolution),
        ("Reconstruction Gates", demo_5_reconstruction_gates),
        ("Reflection Triggers", demo_6_reflection_triggers),
        ("System Health", demo_7_crt_health_monitoring)
    ]
    
    for name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            print(f"⚠️ Demo '{name}' failed: {e}")
            import traceback
            traceback.print_exc()
        
        input("\nPress Enter for next demo...")
    
    print("\n" + "=" * 80)
    print("✅ CRT DEMOS COMPLETE")
    print("\nKey Principles Demonstrated:")
    print("  1. Trust-weighted retrieval (not just similarity)")
    print("  2. Belief vs speech separation (gates prevent drift)")
    print("  3. Contradiction ledgers (no silent overwrites)")
    print("  4. Trust evolution (evidence-based, gradual)")
    print("  5. Reconstruction constraints (coherence checks)")
    print("  6. Reflection triggers (volatility-based)")
    print("\nCRT Philosophy:")
    print("  • Memory first, honesty over performance")
    print("  • Coherence over time > single-query accuracy")
    print("  • Contradictions are signals, not bugs")
    print("  • 'The mouth must never outweigh the self'")
    print("=" * 80)


if __name__ == "__main__":
    main()
