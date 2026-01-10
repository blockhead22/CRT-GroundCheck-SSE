#!/usr/bin/env python3
"""
CRT Chat Interface

Simple command-line chat with the CRT (Cognitive-Reflective Transformer) system.

Current Status:
- ✅ CRT memory system with trust-weighted retrieval
- ✅ Contradiction detection and ledger
- ✅ Belief vs speech separation
- ✅ Optional local LLM via Ollama (if available)

Usage:
    python crt_chat.py [--model llama3.2:latest]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import MemorySource
try:
    from personal_agent.ollama_client import get_ollama_client
except Exception:
    get_ollama_client = None


def print_banner(llm_status_line: str):
    """Print welcome banner."""
    print("\n" + "=" * 70)
    print("  🧠 CRT CHAT - Cognitive-Reflective Transformer")
    print("  Memory-First AI with Trust-Weighted Beliefs")
    print("=" * 70)
    print("\n  Philosophy:")
    print("    • Memory first, honesty over performance")
    print("    • Coherence over time > single-query accuracy")
    print("    • Trust evolves slowly with evidence")
    print("    • Contradictions preserved, not overwritten")
    print("\n  Status:")
    print("    ✅ CRT memory system active")
    print("    ✅ Contradiction ledger enabled")
    print(f"    {llm_status_line}")
    print("\n  Commands:")
    print("    chat       - Interactive chat mode")
    print("    store      - Store a memory directly")
    print("    recall     - Search memories")
    print("    status     - System health")
    print("    contradictions - View open contradictions")
    print("    exit       - Quit")
    print("=" * 70 + "\n")


def print_response(result: dict, show_metadata: bool = True):
    """Print CRT response with formatting."""
    print(f"\n🤖 {result['answer']}")
    
    if show_metadata:
        print(f"\n📊 Metadata:")
        print(f"   Type: {result['response_type'].upper()}")
        
        if result['response_type'] == 'belief':
            print(f"   ✓ Gates passed - speaking from memory")
        else:
            print(f"   ⚠️  Fallback response - gates failed")
            print(f"   Reason: {result['gate_reason']}")
        
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Mode: {result['mode']}")
        
        if result['contradiction_detected']:
            print(f"   ⚠️  Contradiction detected!")
            entry = result['contradiction_entry']
            print(f"      Drift: {entry['drift_mean']:.3f}")
            print(f"      Summary: {entry['summary']}")
        
        if result['retrieved_memories']:
            print(f"\n🧠 Retrieved {len(result['retrieved_memories'])} memories:")
            for i, mem in enumerate(result['retrieved_memories'][:3], 1):
                print(f"   {i}. [{mem['source']}] Trust: {mem['trust']:.2f} | {mem['text'][:60]}...")


def cmd_chat(rag: CRTEnhancedRAG, show_metadata: bool = True):
    """Interactive chat mode."""
    print("\n💬 Chat Mode (type 'exit' to quit, 'help' for commands)")
    print("   Type '!meta' to toggle metadata display\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            
            if user_input.lower() == '!meta':
                show_metadata = not show_metadata
                status = "ON" if show_metadata else "OFF"
                print(f"\n✓ Metadata display: {status}\n")
                continue
            
            if user_input.lower() == 'help':
                print("\n📚 Chat Commands:")
                print("   exit / quit / q    - Exit chat")
                print("   !meta              - Toggle metadata display")
                print("   !important         - Mark next query as important")
                print("   help               - Show this help")
                print()
                continue
            
            # Check for importance marker
            important = False
            if user_input.startswith('!important'):
                important = True
                user_input = user_input.replace('!important', '').strip()
                print("   ℹ️  Marked as important")
            
            # Query CRT system
            result = rag.query(user_input, user_marked_important=important)
            
            # Display response
            print_response(result, show_metadata)
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


def cmd_store(rag: CRTEnhancedRAG):
    """Store a memory directly."""
    print("\n💾 Store Memory")
    
    text = input("Memory text: ").strip()
    if not text:
        print("❌ Empty text")
        return
    
    confidence = input("Confidence (0.0-1.0, default 0.8): ").strip()
    confidence = float(confidence) if confidence else 0.8
    
    important = input("Important? (y/n, default n): ").strip().lower() == 'y'
    
    memory = rag.memory.store_memory(
        text=text,
        confidence=confidence,
        source=MemorySource.USER,
        context={'manual_entry': True},
        user_marked_important=important
    )
    
    print(f"\n✓ Stored memory: {memory.memory_id}")
    print(f"  Trust: {memory.trust:.3f}")
    print(f"  SSE Mode: {memory.sse_mode.value}")
    print()


def cmd_recall(rag: CRTEnhancedRAG):
    """Search memories."""
    print("\n🔍 Recall Memories")
    
    query = input("Search query: ").strip()
    if not query:
        print("❌ Empty query")
        return
    
    k = input("Number of results (default 5): ").strip()
    k = int(k) if k else 5
    
    results = rag.retrieve(query, k=k)
    
    if not results:
        print("\n❌ No memories found")
        return
    
    print(f"\n📚 Found {len(results)} memories:\n")
    for i, (memory, score) in enumerate(results, 1):
        print(f"{i}. [Score: {score:.3f}] Trust: {memory.trust:.2f} | {memory.source.value}")
        print(f"   {memory.text}")
        print(f"   Created: {datetime.fromtimestamp(memory.timestamp).strftime('%Y-%m-%d %H:%M')}")
        print()


def cmd_status(rag: CRTEnhancedRAG, llm_status_line: str):
    """Show system status."""
    print("\n🏥 System Status")
    
    status = rag.get_crt_status()
    
    print(f"\n📊 Metrics:")
    print(f"   Memories: {status['memory_count']}")
    print(f"   Pending Reflections: {status['pending_reflections']}")
    print(f"   Session: {status['session_id']}")
    
    # Contradiction stats
    c_stats = status['contradiction_stats']
    print(f"\n⚠️  Contradictions:")
    print(f"   Open: {c_stats.get('open', 0)}")
    print(f"   Resolved: {c_stats.get('resolved', 0)}")
    print(f"   Total: {c_stats.get('total', 0)}")
    
    # Belief/speech ratio
    bs_ratio = status['belief_speech_ratio']
    print(f"\n💭 Belief vs Speech:")
    print(f"   Beliefs: {bs_ratio.get('beliefs', 0)}")
    print(f"   Speeches: {bs_ratio.get('speeches', 0)}")
    ratio = bs_ratio.get('ratio', 0)
    print(f"   Ratio: {ratio:.1%}")

    print(f"\n🤖 LLM:")
    print(f"   {llm_status_line.strip()}")
    
    print()


def cmd_contradictions(rag: CRTEnhancedRAG):
    """View open contradictions."""
    print("\n⚠️  Open Contradictions")
    
    contradictions = rag.get_open_contradictions()
    
    if not contradictions:
        print("\n✅ No open contradictions")
        return
    
    print(f"\n📋 {len(contradictions)} open contradictions:\n")
    
    for i, c in enumerate(contradictions[:10], 1):
        print(f"{i}. [{c['ledger_id'][-12:]}]")
        print(f"   Drift: {c['drift_mean']:.3f}")
        print(f"   Summary: {c['summary']}")
        print(f"   Old: {c['old_memory_id'][-12:]}")
        print(f"   New: {c['new_memory_id'][-12:]}")
        if c['query']:
            print(f"   Query: {c['query']}")
        print()


def main():
    """Main CLI loop."""

    parser = argparse.ArgumentParser(description="CRT interactive chat")
    parser.add_argument("--model", default="llama3.2:latest", help="Ollama model name")
    parser.add_argument(
        "--no-ollama",
        action="store_true",
        help="Disable Ollama even if available (forces placeholder behavior)",
    )
    args = parser.parse_args()

    llm_client = None
    if args.no_ollama:
        llm_status_line = "⚠️  LLM: placeholder (--no-ollama)"
    elif get_ollama_client is None:
        llm_status_line = "⚠️  LLM: placeholder (Ollama client not available)"
    else:
        llm_client = get_ollama_client(args.model)
        llm_status_line = f"✅ LLM: Ollama ({args.model})"

    print_banner(llm_status_line)
    
    # Initialize CRT system
    print("🔄 Initializing CRT system...")
    try:
        rag = CRTEnhancedRAG(llm_client=llm_client)
        print("✅ CRT system ready\n")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    # Main command loop
    while True:
        try:
            cmd = input("CRT> ").strip().lower()
            
            if not cmd:
                continue
            
            if cmd in ['exit', 'quit', 'q']:
                print("\n👋 Goodbye!\n")
                break
            
            elif cmd == 'chat':
                cmd_chat(rag)
            
            elif cmd == 'store':
                cmd_store(rag)
            
            elif cmd == 'recall':
                cmd_recall(rag)
            
            elif cmd == 'status':
                cmd_status(rag, llm_status_line)
            
            elif cmd == 'contradictions':
                cmd_contradictions(rag)
            
            elif cmd == 'help':
                print_banner(llm_status_line)
            
            else:
                print(f"❌ Unknown command: {cmd}")
                print("   Type 'help' for commands\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
