"""
RAG + Reasoning Engine Demo

Demonstrates:
1. RAG with vector search + SSE contradiction detection
2. Memory fusion tracking (internal hooks)
3. Advanced reasoning modes (like Claude's thinking)
4. Lineage tracking (what memories/facts were used)
"""

from personal_agent.rag import RAGEngine
from personal_agent.reasoning import ReasoningMode
from pathlib import Path
import json


def demo_basic_rag():
    """Demo 1: Basic RAG without reasoning."""
    print("=" * 80)
    print("DEMO 1: Basic RAG (Vector Search + SSE)")
    print("=" * 80)
    
    # Create RAG engine
    rag = RAGEngine()
    
    # Index a document
    doc_path = "sample_sleep.txt"
    if Path(doc_path).exists():
        rag.index_document(doc_path, collection_name="sleep_docs")
    
    # Query (basic)
    result = rag.query(
        user_query="What helps with sleep?",
        collection_name="sleep_docs",
        k=3
    )
    
    print(f"\n📊 Query Results:")
    print(f"  Retrieved Docs: {len(result['retrieved_docs'])}")
    print(f"  Contradictions: {len(result['contradictions'])}")
    print(f"  Fusion ID: {result['fusion_id']}")
    print(f"  Reasoning Required: {result['reasoning_required']}")
    
    if result['retrieved_docs']:
        print(f"\n📄 Top Result:")
        print(f"  {result['retrieved_docs'][0]['text'][:200]}...")
    
    if result['contradictions']:
        print(f"\n⚠️ Contradictions Found:")
        for contra in result['contradictions'][:2]:
            print(f"  - {contra.get('summary', 'Contradiction detected')}")
    
    print()


def demo_reasoning_modes():
    """Demo 2: Different reasoning modes."""
    print("=" * 80)
    print("DEMO 2: Reasoning Modes (Quick, Thinking, Deep)")
    print("=" * 80)
    
    rag = RAGEngine()
    
    # Scenario 1: Simple question → QUICK mode
    print("\n🚀 QUICK MODE (simple question):")
    print("Question: 'What is the capital of France?'")
    
    result = rag.query_with_reasoning(
        user_query="What is the capital of France?",
        mode=ReasoningMode.QUICK
    )
    
    print(f"  Mode: {result['mode']}")
    print(f"  Thinking: {result['thinking']}")
    print(f"  Answer: {result['answer']}")
    print(f"  Confidence: {result['confidence']}")
    
    # Scenario 2: Complex question → THINKING mode
    print("\n🤔 THINKING MODE (complex question):")
    print("Question: 'Why does exercise help with sleep quality?'")
    
    result = rag.query_with_reasoning(
        user_query="Why does exercise help with sleep quality?",
        mode=ReasoningMode.THINKING
    )
    
    print(f"  Mode: {result['mode']}")
    if result['thinking']:
        print(f"  Thinking Process:")
        for line in result['thinking'].split('\n')[:5]:  # Show first 5 lines
            print(f"    {line}")
    print(f"  Answer: {result['answer']}")
    print(f"  Confidence: {result['confidence']}")
    
    # Scenario 3: Contradictions → DEEP mode
    print("\n🧠 DEEP MODE (with contradictions):")
    print("Question: 'Is coffee good or bad for sleep?'")
    
    # Simulate contradictions
    result = rag.query_with_reasoning(
        user_query="Is coffee good or bad for sleep?",
        mode=ReasoningMode.DEEP
    )
    
    print(f"  Mode: {result['mode']}")
    if result['thinking']:
        print(f"  Deep Reasoning:")
        for line in result['thinking'].split('\n')[:8]:  # Show first 8 lines
            print(f"    {line}")
    print(f"  Answer: {result['answer']}")
    print(f"  Confidence: {result['confidence']}")
    
    print()


def demo_memory_fusion_tracking():
    """Demo 3: Memory fusion tracking (internal hooks)."""
    print("=" * 80)
    print("DEMO 3: Memory Fusion Tracking (Internal Hooks)")
    print("=" * 80)
    
    rag = RAGEngine()
    
    # Simulate queries with memory context
    print("\n📝 Query 1: Without memory context")
    result1 = rag.query_with_reasoning(
        user_query="What's the best sleep schedule?",
        memory_context=None
    )
    fusion_id_1 = result1['fusion_id']
    print(f"  Fusion ID: {fusion_id_1}")
    print(f"  Memories Used: 0")
    print(f"  Facts Retrieved: {len(result1['retrieved_docs'])}")
    
    # Query with learned memories
    print("\n📝 Query 2: With learned memory context")
    learned_memories = [
        "User prefers waking up at 6 AM",
        "User has trouble falling asleep after 11 PM",
        "User is sensitive to caffeine"
    ]
    
    result2 = rag.query_with_reasoning(
        user_query="What time should I stop drinking coffee?",
        memory_context=learned_memories
    )
    fusion_id_2 = result2['fusion_id']
    print(f"  Fusion ID: {fusion_id_2}")
    print(f"  Memories Used: {len(learned_memories)}")
    print(f"  Facts Retrieved: {len(result2['retrieved_docs'])}")
    
    # Show fusion lineage
    print("\n🔍 Fusion Lineage Details:")
    lineage = rag.get_fusion_lineage(fusion_id_2)
    if lineage:
        print(f"  Query: {lineage['query']}")
        print(f"  Session ID: {lineage['session_id']}")
        print(f"  Reasoning Mode: {lineage['reasoning_mode']}")
        print(f"  Memories Used: {len(lineage['memories_used'])}")
        for i, mem in enumerate(lineage['memories_used'], 1):
            print(f"    {i}. {mem}")
        print(f"  Facts Retrieved: {len(lineage['facts_retrieved'])}")
    
    # Show recent fusions
    print("\n📊 Recent Fusion Events:")
    recent = rag.get_recent_fusions(limit=5)
    for event in recent:
        print(f"  [{event['timestamp']}] {event['query'][:50]}...")
        print(f"    → Mode: {event['reasoning_mode']}, Memories: {len(event['memories_used'])}")
    
    print()


def demo_reasoning_traces():
    """Demo 4: Reasoning traces (internal observability)."""
    print("=" * 80)
    print("DEMO 4: Reasoning Traces (Internal Observability)")
    print("=" * 80)
    
    rag = RAGEngine()
    
    # Execute several queries with different complexity
    queries = [
        ("What time is it?", ReasoningMode.QUICK),
        ("How does sleep affect memory?", ReasoningMode.THINKING),
        ("Compare REM vs deep sleep benefits", ReasoningMode.DEEP)
    ]
    
    for query, mode in queries:
        rag.query_with_reasoning(query, mode=mode)
    
    # Show reasoning traces
    print("\n🔬 Reasoning Traces (last 3 queries):")
    traces = rag.get_reasoning_traces(limit=3)
    
    for i, trace in enumerate(traces, 1):
        print(f"\n  Trace {i}:")
        print(f"    Query: {trace['query']}")
        print(f"    Mode: {trace['mode']}")
        print(f"    Steps: {len(trace['thinking_steps'])}")
        for step in trace['thinking_steps']:
            print(f"      - [{step['step_type']}] {step['content'][:60]}...")
            print(f"        Duration: {step['duration_ms']:.0f}ms")
        print(f"    Confidence: {trace['confidence']}")
        print(f"    Total Duration: {trace['total_duration_ms']:.0f}ms")
    
    print()


def demo_auto_mode_detection():
    """Demo 5: Automatic reasoning mode detection."""
    print("=" * 80)
    print("DEMO 5: Auto Mode Detection")
    print("=" * 80)
    
    rag = RAGEngine()
    
    test_queries = [
        "What's 2+2?",  # Simple → QUICK
        "Why is the sky blue?",  # Why question → THINKING
        "Compare and contrast sleep stages and explain how they affect memory consolidation",  # Complex → DEEP
    ]
    
    print("\n🎯 Auto-detecting reasoning modes:")
    for query in test_queries:
        result = rag.query_with_reasoning(
            user_query=query,
            mode=None  # Auto-detect
        )
        print(f"\n  Query: '{query}'")
        print(f"  Auto-detected Mode: {result['mode']}")
        print(f"  Reasoning Required: {'Yes' if result.get('reasoning_required') else 'No'}")
        print(f"  Confidence: {result['confidence']}")
    
    print()


def demo_full_workflow():
    """Demo 6: Complete workflow with all features."""
    print("=" * 80)
    print("DEMO 6: Complete Workflow")
    print("=" * 80)
    
    rag = RAGEngine()
    
    # Scenario: User asks complex question about sleep
    user_query = "I wake up at 3 AM and can't fall back asleep. Why does this happen and what can I do?"
    
    print(f"\n❓ User Question:")
    print(f"  {user_query}")
    
    # Add memory context (user's learned preferences)
    memories = [
        "User goes to bed around 11 PM",
        "User drinks coffee until 5 PM",
        "User exercises in the morning",
        "User has high stress job"
    ]
    
    print(f"\n🧠 Memory Context ({len(memories)} memories):")
    for mem in memories:
        print(f"  - {mem}")
    
    # Execute query with reasoning
    result = rag.query_with_reasoning(
        user_query=user_query,
        memory_context=memories,
        mode=None  # Auto-detect
    )
    
    print(f"\n🔍 Processing:")
    print(f"  Reasoning Mode: {result['mode']}")
    print(f"  Retrieved Docs: {len(result['retrieved_docs'])}")
    print(f"  Contradictions: {len(result['contradictions'])}")
    print(f"  Fusion ID: {result['fusion_id']}")
    
    if result['thinking']:
        print(f"\n💭 Thinking Process:")
        print(result['thinking'])
    
    print(f"\n✅ Answer:")
    print(f"  {result['answer']}")
    print(f"  Confidence: {result['confidence']}")
    
    # Show what was tracked internally
    print(f"\n📊 Internal Tracking (Fusion Lineage):")
    lineage = rag.get_fusion_lineage(result['fusion_id'])
    if lineage:
        print(f"  Timestamp: {lineage['timestamp']}")
        print(f"  Session: {lineage['session_id']}")
        print(f"  Memories Used: {len(lineage['memories_used'])}")
        print(f"  Facts Retrieved: {len(lineage['facts_retrieved'])}")
        print(f"  Contradictions: {len(lineage['contradictions_found'])}")
        print(f"  Mode: {lineage['reasoning_mode']}")
    
    # Show reasoning trace
    traces = rag.get_reasoning_traces(limit=1)
    if traces:
        trace = traces[0]
        print(f"\n🔬 Reasoning Trace:")
        print(f"  Steps: {len(trace['thinking_steps'])}")
        print(f"  Total Time: {trace['total_duration_ms']:.0f}ms")
        for step in trace['thinking_steps']:
            print(f"    [{step['step_type']}] {step['duration_ms']:.0f}ms")
    
    print()


def main():
    """Run all demos."""
    print("\n" + "=" * 80)
    print("RAG + REASONING ENGINE DEMOS")
    print("Demonstrating internal hooks, memory tracking, and thinking modes")
    print("=" * 80 + "\n")
    
    demos = [
        ("Basic RAG", demo_basic_rag),
        ("Reasoning Modes", demo_reasoning_modes),
        ("Memory Fusion Tracking", demo_memory_fusion_tracking),
        ("Reasoning Traces", demo_reasoning_traces),
        ("Auto Mode Detection", demo_auto_mode_detection),
        ("Complete Workflow", demo_full_workflow)
    ]
    
    for name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            print(f"⚠️ Demo '{name}' failed: {e}")
            import traceback
            traceback.print_exc()
        
        input("\nPress Enter to continue to next demo...")
    
    print("\n" + "=" * 80)
    print("✅ All demos complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
