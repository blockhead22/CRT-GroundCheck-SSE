"""
Personal Agent - Example Usage

Shows how to use the learning agent with SSE.
"""

from personal_agent import PersonalAgent

def main():
    """
    Example: Personal learning agent that uses SSE for contradiction detection.
    
    This agent:
    - Learns your preferences
    - Remembers conversations
    - Uses contradictions to offer different approaches
    - Grows with you over time
    """
    
    print("=" * 70)
    print("PERSONAL LEARNING AGENT")
    print("=" * 70)
    print("\nThis is Phase D+ experimental system.")
    print("It learns, remembers, and adapts to you.")
    print("SSE provides the honest contradiction layer.\n")
    
    # Initialize agent (set your API key or use env variable)
    # Get API key from: https://platform.openai.com/api-keys
    agent = PersonalAgent(
        llm_provider="openai",  # or "anthropic" for Claude
        llm_api_key=None  # Will use OPENAI_API_KEY from environment
    )
    
    # Index your knowledge
    print("Step 1: Indexing knowledge with SSE...")
    agent.index_knowledge("sample_sleep.txt", index_name="sleep_knowledge")
    
    print("\nStep 2: Chat with memory and learning")
    print("-" * 70)
    
    # First conversation
    response = agent.chat("What do you know about sleep?")
    print(f"\nAgent: {response}\n")
    
    # Check for contradictions
    print("\nStep 3: Showing contradictions (SSE honest layer)")
    print("-" * 70)
    contradictions = agent.show_contradictions("sleep", index_name="sleep_knowledge")
    print(contradictions)
    
    # Continue conversation (agent remembers)
    print("\nStep 4: Follow-up (agent remembers context)")
    print("-" * 70)
    response = agent.chat("Which approach makes more sense?")
    print(f"\nAgent: {response}\n")
    
    # Provide feedback (agent learns)
    print("\nStep 5: Feedback loop (agent learns)")
    print("-" * 70)
    agent.learn_from_feedback(was_helpful=True, aspect="detailed_explanations")
    print("✓ Agent learned you prefer detailed explanations\n")
    
    # Show what agent has learned
    print("\nStep 6: Memory stats")
    print("-" * 70)
    stats = agent.get_memory_stats()
    print(f"Conversations: {stats['conversations']}")
    print(f"Preferences learned: {stats['preferences_learned']}")
    print(f"Strategies recorded: {stats['strategies_recorded']}")
    print(f"Contradictions resolved: {stats['contradictions_resolved']}")
    
    # Interactive loop
    print("\n" + "=" * 70)
    print("INTERACTIVE MODE")
    print("=" * 70)
    print("Type your messages. Type 'quit' to exit, 'stats' for memory stats.\n")
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() == 'quit':
            break
        
        if user_input.lower() == 'stats':
            stats = agent.get_memory_stats()
            print(f"\nMemory Stats: {stats}")
            continue
        
        if user_input.lower() == 'contradictions':
            topic = input("Topic to check: ").strip()
            result = agent.show_contradictions(topic, index_name="sleep_knowledge")
            print(f"\n{result}")
            continue
        
        if user_input.lower().startswith('index '):
            file_path = user_input[6:].strip()
            agent.index_knowledge(file_path, index_name="custom")
            continue
        
        if not user_input:
            continue
        
        response = agent.chat(user_input, index_name="sleep_knowledge")
        print(f"\nAgent: {response}")
        
        # Ask for feedback
        feedback = input("\nWas this helpful? (y/n/skip): ").strip().lower()
        if feedback == 'y':
            agent.learn_from_feedback(was_helpful=True)
        elif feedback == 'n':
            agent.learn_from_feedback(was_helpful=False)
    
    print("\n✓ Conversation ended. Memory persisted.")
    print(f"Total conversations: {agent.get_memory_stats()['conversations']}")


if __name__ == "__main__":
    main()
