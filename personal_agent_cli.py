"""
Personal Agent - Simple CLI

Quick command-line interface for the personal learning agent.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from personal_agent import PersonalAgent


def print_banner():
    print("\n" + "=" * 70)
    print("  PERSONAL LEARNING AGENT")
    print("  Phase D+ Experimental System")
    print("=" * 70)
    print("\n  SSE Layer: Honest contradiction detection (Phase C)")
    print("  Agent Layer: Learning and adaptation (Phase D+)")
    print("\n  Commands:")
    print("    chat       - Interactive chat")
    print("    index      - Index a document")
    print("    stats      - Show memory stats")
    print("    export     - Export memory")
    print("=" * 70 + "\n")


def cmd_chat(agent: PersonalAgent):
    """Interactive chat mode."""
    print("\n🤖 Chat Mode (type 'exit' to quit, 'help' for commands)\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'exit':
                break
            
            if user_input.lower() == 'help':
                print("\nCommands in chat:")
                print("  exit               - Exit chat")
                print("  contradictions     - Show contradictions about topic")
                print("  stats              - Memory statistics")
                print("  helpful / not      - Give feedback on last response")
                print()
                continue
            
            if user_input.lower() == 'stats':
                stats = agent.get_memory_stats()
                print(f"\n📊 Memory: {stats['conversations']} convs, "
                      f"{stats['preferences_learned']} prefs, "
                      f"{stats['contradictions_resolved']} contradictions\n")
                continue
            
            if user_input.lower() == 'contradictions':
                topic = input("Topic: ").strip()
                result = agent.show_contradictions(topic, index_name="main")
                print(f"\n{result}\n")
                continue
            
            if user_input.lower() in ['helpful', 'not']:
                was_helpful = user_input.lower() == 'helpful'
                agent.learn_from_feedback(was_helpful)
                print(f"✓ Feedback recorded\n")
                continue
            
            # Normal chat
            response = agent.chat(user_input, index_name="main")
            print(f"\nAgent: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
    
    stats = agent.get_memory_stats()
    print(f"\n✓ Chat ended. Total conversations: {stats['conversations']}\n")


def cmd_index(agent: PersonalAgent, file_path: str):
    """Index a document."""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"\n📄 Indexing {file_path}...")
    agent.index_knowledge(file_path, index_name="main")
    print("✓ Done\n")


def cmd_stats(agent: PersonalAgent):
    """Show memory statistics."""
    stats = agent.get_memory_stats()
    print("\n📊 Memory Statistics:")
    print(f"  Conversations: {stats['conversations']}")
    print(f"  Preferences learned: {stats['preferences_learned']}")
    print(f"  Strategies recorded: {stats['strategies_recorded']}")
    print(f"  Contradictions resolved: {stats['contradictions_resolved']}")
    print()


def cmd_export(agent: PersonalAgent, output_path: str = "agent_memory.json"):
    """Export memory to JSON."""
    print(f"\n💾 Exporting memory to {output_path}...")
    agent.export_memory(output_path)
    print("✓ Done\n")


def main():
    """Main CLI entry point."""
    print_banner()
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  Warning: No API key found in environment")
        print("   Set OPENAI_API_KEY or ANTHROPIC_API_KEY\n")
        provider = input("Use without LLM? (y/n): ").strip().lower()
        if provider != 'y':
            return
    
    # Initialize agent
    provider = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
    print(f"🔧 Initializing agent (provider: {provider})...")
    
    agent = PersonalAgent(llm_provider=provider)
    print("✓ Agent ready\n")
    
    # Parse command
    if len(sys.argv) < 2:
        cmd = "chat"
    else:
        cmd = sys.argv[1].lower()
    
    if cmd == "chat":
        cmd_chat(agent)
    
    elif cmd == "index":
        if len(sys.argv) < 3:
            file_path = input("File path: ").strip()
        else:
            file_path = sys.argv[2]
        cmd_index(agent, file_path)
    
    elif cmd == "stats":
        cmd_stats(agent)
    
    elif cmd == "export":
        output = sys.argv[2] if len(sys.argv) > 2 else "agent_memory.json"
        cmd_export(agent, output)
    
    else:
        print(f"❌ Unknown command: {cmd}")
        print("\nUsage:")
        print("  python personal_agent_cli.py chat")
        print("  python personal_agent_cli.py index <file>")
        print("  python personal_agent_cli.py stats")
        print("  python personal_agent_cli.py export [output.json]")
        print()



if __name__ == "__main__":
    main()
