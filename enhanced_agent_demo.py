"""
Complete Personal Agent + RAG + Reasoning Integration Example

Shows the full system working together:
- Personal Agent (Phase D+ learning)
- RAG Engine (vector search + SSE)
- Reasoning Engine (thinking modes)
- Memory Fusion Tracking (internal hooks)
"""

from personal_agent.memory import MemorySystem
from personal_agent.rag import RAGEngine
from personal_agent.reasoning import ReasoningMode
from pathlib import Path


class EnhancedPersonalAgent:
    """
    Personal agent with RAG and reasoning capabilities.
    
    Combines:
    - Memory system (learns about you)
    - RAG engine (knowledge retrieval)
    - Reasoning engine (thinking modes)
    - Fusion tracking (observability)
    """
    
    def __init__(self, name: str = "Agent", db_path: str = "personal_agent/agent.db"):
        """Initialize enhanced agent."""
        self.name = name
        
        # Memory system (Phase D+ learning)
        self.memory = MemorySystem(db_path)
        
        # RAG engine (knowledge retrieval + reasoning)
        self.rag = RAGEngine()
        
        print(f"✅ {name} initialized with RAG + Reasoning")
    
    def index_knowledge(self, doc_path: str, collection_name: str = "main"):
        """Index a document for knowledge retrieval."""
        print(f"\n📚 Indexing knowledge: {doc_path}")
        self.rag.index_document(doc_path, collection_name)
        print(f"✅ Knowledge indexed in '{collection_name}'")
    
    def chat(
        self,
        user_message: str,
        collection_name: str = "main",
        show_thinking: bool = True
    ) -> dict:
        """
        Chat with reasoning and memory fusion tracking.
        
        Process:
        1. Retrieve learned memories about user
        2. Search knowledge base (RAG)
        3. Detect contradictions (SSE)
        4. Reason about answer (thinking modes)
        5. Log fusion event (internal tracking)
        6. Store conversation (learning)
        
        Returns full result with answer, thinking, and tracking.
        """
        print(f"\n💬 You: {user_message}")
        
        # 1. Get learned memories about user
        conversations = self.memory.get_recent_conversations(limit=3)
        preferences = self.memory.get_all_preferences()
        
        memory_context = []
        for pref in preferences:
            memory_context.append(f"{pref['preference_type']}: {pref['preference_value']}")
        
        print(f"\n🧠 Using {len(memory_context)} learned memories")
        
        # 2. Query with reasoning
        result = self.rag.query_with_reasoning(
            user_query=user_message,
            collection_name=collection_name,
            memory_context=memory_context,
            mode=None  # Auto-detect
        )
        
        # 3. Show results
        print(f"\n🤖 {self.name} [{result['mode']} mode]:")
        
        if show_thinking and result.get('thinking'):
            print(result['thinking'])
            print()
        
        print(result['answer'])
        print(f"(Confidence: {result['confidence']:.0%})")
        
        # 4. Show what was tracked internally
        lineage = self.rag.get_fusion_lineage(result['fusion_id'])
        print(f"\n📊 Internal Tracking:")
        print(f"  Fusion ID: {result['fusion_id']}")
        print(f"  Memories used: {len(lineage['memories_used'])}")
        print(f"  Facts retrieved: {len(lineage['facts_retrieved'])}")
        print(f"  Contradictions: {len(lineage['contradictions_found'])}")
        
        # 5. Store conversation (learning)
        self.memory.store_conversation(
            user_message=user_message,
            agent_response=result['answer'],
            context={'fusion_id': result['fusion_id'], 'mode': result['mode']}
        )
        
        return result
    
    def learn_preference(self, preference_type: str, value: str):
        """Learn a preference about the user."""
        self.memory.learn_preference(preference_type, value)
        print(f"✅ Learned: {preference_type} = {value}")
    
    def show_memory_stats(self):
        """Show what the agent has learned."""
        print("\n📊 Memory Statistics:")
        print(f"  Conversations: {len(self.memory.get_recent_conversations(limit=100))}")
        print(f"  Preferences: {len(self.memory.get_all_preferences())}")
        
        print("\n🧠 Learned Preferences:")
        for pref in self.memory.get_all_preferences():
            print(f"  • {pref['preference_type']}: {pref['preference_value']}")
    
    def show_fusion_history(self, limit: int = 5):
        """Show recent memory fusion events."""
        print(f"\n🔍 Recent Fusion Events (last {limit}):")
        fusions = self.rag.get_recent_fusions(limit)
        
        for i, fusion in enumerate(fusions, 1):
            print(f"\n  {i}. [{fusion['timestamp']}]")
            print(f"     Query: {fusion['query'][:60]}...")
            print(f"     Mode: {fusion['reasoning_mode']}")
            print(f"     Memories: {len(fusion['memories_used'])}, Facts: {len(fusion['facts_retrieved'])}")
    
    def show_reasoning_traces(self, limit: int = 3):
        """Show recent reasoning traces."""
        print(f"\n🔬 Recent Reasoning Traces (last {limit}):")
        traces = self.rag.get_reasoning_traces(limit)
        
        for i, trace in enumerate(traces, 1):
            print(f"\n  {i}. {trace['query']}")
            print(f"     Mode: {trace['mode']}")
            print(f"     Steps: {len(trace['thinking_steps'])}")
            print(f"     Duration: {trace['total_duration_ms']:.0f}ms")
            print(f"     Confidence: {trace['confidence']}")


def demo_scenario_1():
    """Scenario 1: Learning about user over time."""
    print("=" * 80)
    print("SCENARIO 1: Learning Over Time")
    print("=" * 80)
    
    agent = EnhancedPersonalAgent(name="SleepCoach")
    
    # Index knowledge
    if Path("sample_sleep.txt").exists():
        agent.index_knowledge("sample_sleep.txt", collection_name="sleep")
    
    # First interaction - agent learns
    agent.learn_preference("wake_time", "6:00 AM")
    agent.learn_preference("bedtime", "11:00 PM")
    agent.learn_preference("coffee_cutoff", "5:00 PM")
    
    # Chat 1 - Simple question
    agent.chat(
        "What helps with sleep?",
        collection_name="sleep",
        show_thinking=True
    )
    
    # Chat 2 - Uses learned context
    agent.chat(
        "What time should I stop drinking coffee?",
        collection_name="sleep",
        show_thinking=True
    )
    
    # Show what was learned
    agent.show_memory_stats()
    agent.show_fusion_history(limit=2)


def demo_scenario_2():
    """Scenario 2: Complex question with deep reasoning."""
    print("\n" + "=" * 80)
    print("SCENARIO 2: Complex Question → Deep Reasoning")
    print("=" * 80)
    
    agent = EnhancedPersonalAgent(name="HealthAdvisor")
    
    # User context
    agent.learn_preference("stress_level", "high")
    agent.learn_preference("exercise_time", "morning")
    agent.learn_preference("screen_time", "before bed")
    
    # Complex multi-part question
    result = agent.chat(
        "I wake up at 3 AM and can't fall back asleep. Why does this happen and what can I do about it?",
        show_thinking=True
    )
    
    # Show reasoning details
    agent.show_reasoning_traces(limit=1)


def demo_scenario_3():
    """Scenario 3: Tracking what context was used."""
    print("\n" + "=" * 80)
    print("SCENARIO 3: Memory Fusion Tracking")
    print("=" * 80)
    
    agent = EnhancedPersonalAgent(name="Tracker")
    
    # Learn multiple preferences
    agent.learn_preference("age", "35")
    agent.learn_preference("fitness_level", "moderate")
    agent.learn_preference("sleep_quality", "poor")
    agent.learn_preference("caffeine_sensitivity", "high")
    
    # Ask question that uses multiple memories
    result = agent.chat(
        "Should I exercise in the morning or evening for better sleep?",
        show_thinking=True
    )
    
    # Show exactly what was used
    print("\n🔍 Detailed Fusion Analysis:")
    lineage = agent.rag.get_fusion_lineage(result['fusion_id'])
    
    print(f"\n  Memories Used ({len(lineage['memories_used'])}):")
    for mem in lineage['memories_used']:
        print(f"    • {mem}")
    
    print(f"\n  Facts Retrieved ({len(lineage['facts_retrieved'])}):")
    for fact in lineage['facts_retrieved'][:3]:
        print(f"    • {fact['text'][:80]}...")
        print(f"      Source: {fact['source']}")


def demo_scenario_4():
    """Scenario 4: Different reasoning modes."""
    print("\n" + "=" * 80)
    print("SCENARIO 4: Reasoning Modes in Action")
    print("=" * 80)
    
    agent = EnhancedPersonalAgent(name="ReasoningDemo")
    
    questions = [
        ("What time is it?", "QUICK mode expected"),
        ("Why do we need sleep?", "THINKING mode expected"),
        ("Compare different sleep stages, explain their purposes, and analyze how they interact", "DEEP mode expected")
    ]
    
    for question, expected in questions:
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"Expected: {expected}")
        print("="*60)
        
        result = agent.chat(question, show_thinking=True)
        
        print(f"\n✓ Actual mode: {result['mode']}")


def demo_full_integration():
    """Complete integration demo."""
    print("\n" + "=" * 80)
    print("COMPLETE INTEGRATION DEMO")
    print("=" * 80)
    
    agent = EnhancedPersonalAgent(name="Assistant")
    
    # Index knowledge
    print("\n📚 Step 1: Index Knowledge Base")
    if Path("sample_sleep.txt").exists():
        agent.index_knowledge("sample_sleep.txt")
    
    # Learn about user
    print("\n🧠 Step 2: Learn User Preferences")
    preferences = {
        "wake_time": "6:00 AM",
        "bedtime": "10:30 PM",
        "exercise_preference": "morning workouts",
        "diet": "low caffeine",
        "work_schedule": "remote, flexible hours",
        "stress_level": "moderate"
    }
    
    for pref_type, value in preferences.items():
        agent.learn_preference(pref_type, value)
    
    # Chat session
    print("\n💬 Step 3: Chat Session")
    
    questions = [
        "What's a good sleep routine for me?",
        "Why do I sometimes wake up in the middle of the night?",
        "How can I improve my deep sleep?"
    ]
    
    for q in questions:
        agent.chat(q, show_thinking=True)
    
    # Show analytics
    print("\n📊 Step 4: Analytics")
    agent.show_memory_stats()
    agent.show_fusion_history(limit=3)
    agent.show_reasoning_traces(limit=3)


def main():
    """Run all scenarios."""
    print("\n" + "=" * 80)
    print("ENHANCED PERSONAL AGENT DEMO")
    print("RAG + Reasoning + Memory Fusion Tracking")
    print("=" * 80)
    
    scenarios = [
        ("Learning Over Time", demo_scenario_1),
        ("Deep Reasoning", demo_scenario_2),
        ("Fusion Tracking", demo_scenario_3),
        ("Reasoning Modes", demo_scenario_4),
        ("Full Integration", demo_full_integration)
    ]
    
    for name, scenario in scenarios:
        try:
            scenario()
        except Exception as e:
            print(f"\n⚠️ Scenario '{name}' failed: {e}")
            import traceback
            traceback.print_exc()
        
        input("\n\nPress Enter to continue to next scenario...")
    
    print("\n" + "=" * 80)
    print("✅ All scenarios complete!")
    print("\nKey Takeaways:")
    print("  • RAG combines vector search + SSE + memory context")
    print("  • Reasoning engine thinks before answering (QUICK/THINKING/DEEP)")
    print("  • Memory fusion tracking logs what was used when (internal)")
    print("  • Complete observability for debugging/auditing")
    print("=" * 80)


if __name__ == "__main__":
    main()
