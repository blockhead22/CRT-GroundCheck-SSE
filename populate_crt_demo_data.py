"""
Populate CRT System with Demo Data

Creates sample memories, contradictions, and interactions to demonstrate
the dashboard functionality.
"""

import time
import numpy as np
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import MemorySource

def populate_demo_data():
    """Populate the CRT system with demo data."""
    
    print("🧠 Initializing CRT system...")
    rag = CRTEnhancedRAG()
    
    # Sample queries and statements
    demo_interactions = [
        {
            "query": "What is my favorite color?",
            "context": "User stated their favorite color is blue",
            "important": True
        },
        {
            "query": "What's the weather like?",
            "context": "Simple weather query - low importance",
            "important": False
        },
        {
            "query": "Remember that I work at TechCorp",
            "context": "User sharing employment information",
            "important": True
        },
        {
            "query": "My dog's name is Max",
            "context": "User sharing personal information",
            "important": True
        },
        {
            "query": "What time is it?",
            "context": "Time query - not memorable",
            "important": False
        },
        {
            "query": "I prefer working in the morning",
            "context": "User preference",
            "important": True
        },
        {
            "query": "Actually, my favorite color is green now",
            "context": "Contradicts earlier statement about blue",
            "important": True
        },
        {
            "query": "I've been promoted to Senior Engineer at TechCorp",
            "context": "Update to employment info",
            "important": True
        },
        {
            "query": "What's 2+2?",
            "context": "Simple math query",
            "important": False
        },
        {
            "query": "I actually prefer working in the evening",
            "context": "Contradicts earlier preference",
            "important": True
        },
    ]
    
    print(f"\n📝 Adding {len(demo_interactions)} interactions...")
    
    for i, interaction in enumerate(demo_interactions):
        print(f"  [{i+1}/{len(demo_interactions)}] Processing: {interaction['query'][:50]}...")
        
        try:
            result = rag.query(
                user_query=interaction['query'],
                user_marked_important=interaction['important']
            )
            
            is_belief = result['response_type'] == 'belief'
            print(f"      ✓ Is belief: {is_belief}")
            print(f"      ✓ Gates passed: {result['gates_passed']}")
            print(f"      ✓ Contradiction: {result['contradiction_detected']}")
            
        except Exception as e:
            print(f"      ✗ Error: {e}")
        
        # Small delay to spread out timestamps
        time.sleep(0.1)
    
    # Add some standalone memories
    print("\n💾 Adding standalone memories...")
    
    standalone_memories = [
        "I graduated from MIT in 2018",
        "I love hiking in the mountains",
        "My birthday is March 15th",
        "I'm learning to play guitar",
        "I have a cat named Luna"
    ]
    
    for memory_text in standalone_memories:
        try:
            # Store as high-confidence user memory
            memory = rag.memory.store_memory(
                text=memory_text,
                confidence=0.9,
                source=MemorySource.USER,
                context={"type": "standalone", "verified": True},
                user_marked_important=True
            )
            print(f"  ✓ Stored: {memory_text}")
        except Exception as e:
            print(f"  ✗ Error storing '{memory_text}': {e}")
    
    # Get statistics
    print("\n📊 CRT System Statistics:")
    
    try:
        memories = rag.memory._load_all_memories()
        print(f"  Total memories: {len(memories)}")
        
        if memories:
            trust_scores = [m.trust for m in memories]
            print(f"  Average trust: {np.mean(trust_scores):.3f}")
            print(f"  High trust (>0.7): {sum(1 for t in trust_scores if t > 0.7)}")
            print(f"  Low trust (<0.3): {sum(1 for t in trust_scores if t < 0.3)}")
    except Exception as e:
        print(f"  Error getting statistics: {e}")
    
    try:
        open_contradictions = rag.ledger.get_open_contradictions()
        reflection_queue = rag.ledger.get_reflection_queue()
        print(f"  Open contradictions: {len(open_contradictions)}")
        print(f"  Pending reflections: {len(reflection_queue)}")
    except Exception as e:
        print(f"  Error getting contradictions: {e}")
    
    print("\n✅ Demo data population complete!")
    print("\n🚀 Launch the dashboard with:")
    print("   streamlit run crt_dashboard.py")


if __name__ == "__main__":
    populate_demo_data()
