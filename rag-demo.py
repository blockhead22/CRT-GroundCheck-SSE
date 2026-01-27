#!/usr/bin/env python3
"""
CRT-Enhanced RAG Demo
Run: python crt_rag_demo.py

This uses the full CRT-GroundCheck-SSE system with a simple chat interface.
"""

import ollama
import sys
from pathlib import Path

# Add parent directory to path to import personal_agent
sys.path.insert(0, str(Path(__file__).parent))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import SSEMode

def main():
    print("=" * 60)
    print("CRT-Enhanced RAG Chat Demo")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the conversation")
    print("Type 'memory' to see stored facts")
    print("Type 'trust' to see trust scores")
    print("Type 'ledger' to see contradiction history\n")
    
    # Initialize CRT system
    print("🔧 Initializing CRT system...")
    rag = CRTEnhancedRAG(
        memory_db_path="./demo_memory.db",
        ledger_db_path="./demo_ledger.db",
        feature_flags={
            "self_questioning_enabled": True,
            "caveat_injection_enabled": True,
            "domain_detection_enabled": True,
            "temporal_tracking_enabled": True,
            "denial_detection_enabled": True
        }
    )
    print("✅ CRT system ready!\n")
    
    conversation_history = []
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        # Special commands
        if user_input.lower() == 'memory':
            show_memory(rag)
            continue
        
        if user_input.lower() == 'trust':
            show_trust_scores(rag)
            continue
        
        if user_input.lower() == 'ledger':
            show_ledger(rag)
            continue
        
        if not user_input:
            continue
        
        try:
            # Process through CRT system
            print("\n🔍 Processing with CRT...", end=" ")
            
            result = rag.process_user_input(
                user_query=user_input,
                conversation_history=conversation_history,
                session_id="demo_session"
            )
            
            # Display CRT metadata
            if result.get("contradiction_detected"):
                print("⚠️  Contradiction detected!")
            elif result.get("denial_detected"):
                print("🔄 Denial detected!")
            elif result.get("retraction_detected"):
                print("↩️  Retraction detected!")
            else:
                print("✓")
            
            # Show SSE mode
            sse_mode = result.get("sse_mode", SSEMode.LOSSLESS)
            mode_emoji = {
                SSEMode.LOSSLESS: "🔒",
                SSEMode.LOSSY: "⚡",
                SSEMode.RADICAL: "🔥"
            }
            print(f"{mode_emoji.get(sse_mode, '🔒')} Mode: {sse_mode.value}")
            
            # Get enhanced context
            context = result.get("context", "")
            
            # Build prompt with CRT context
            messages = []
            
            # System prompt
            messages.append({
                'role': 'system',
                'content': 'You are a helpful assistant with memory. Use the provided context to answer accurately.'
            })
            
            # Add conversation history
            for msg in conversation_history[-6:]:  # Last 3 turns
                messages.append(msg)
            
            # Add current query with context
            user_message = user_input
            if context:
                user_message = f"[Context from memory]\n{context}\n\n[User question]\n{user_input}"
            
            messages.append({
                'role': 'user',
                'content': user_message
            })
            
            # Get LLM response
            print("🤖 Generating response...\n")
            response = ollama.chat(
                model='llama3.2',
                messages=messages
            )
            
            assistant_message = response['message']['content']
            
            # Inject caveats if needed
            caveats = result.get("caveats", [])
            if caveats:
                caveat_text = "\n\n⚠️ " + " ".join(caveats)
                assistant_message = assistant_message + caveat_text
            
            # Update conversation history
            conversation_history.append({
                'role': 'user',
                'content': user_input
            })
            conversation_history.append({
                'role': 'assistant',
                'content': assistant_message
            })
            
            print(f"Assistant: {assistant_message}\n")
            
            # Show provenance
            if result.get("retrieved_memories"):
                print(f"📚 Retrieved {len(result['retrieved_memories'])} memories")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            break

def show_memory(rag):
    """Display all stored memories"""
    print("\n📝 Stored Memories:")
    memories = rag.memory._load_all_memories()
    
    if not memories:
        print("  (none yet)")
    else:
        for mem in memories:
            print(f"\n  ID: {mem.memory_id}")
            print(f"  Text: {mem.text[:100]}...")
            print(f"  Trust: {mem.trust:.2f}")
            if mem.domain_tags:
                print(f"  Domains: {', '.join(mem.domain_tags)}")
            if mem.temporal_status:
                print(f"  Status: {mem.temporal_status}")
    print()

def show_trust_scores(rag):
    """Display trust scores for all facts"""
    print("\n🎯 Trust Scores:")
    memories = rag.memory._load_all_memories()
    
    if not memories:
        print("  (no facts stored yet)")
    else:
        for mem in memories:
            bar = "█" * int(mem.trust * 10) + "░" * (10 - int(mem.trust * 10))
            print(f"  [{bar}] {mem.trust:.2f} - {mem.text[:50]}...")
    print()

def show_ledger(rag):
    """Display contradiction ledger"""
    print("\n📊 Contradiction Ledger:")
    
    try:
        ledger = rag.ledger
        entries = ledger.get_all_contradictions()
        
        if not entries:
            print("  (no contradictions detected yet)")
        else:
            for entry in entries[-10:]:  # Last 10
                print(f"\n  Turn: {entry.turn}")
                print(f"  Type: {entry.contradiction_type}")
                print(f"  Slot: {entry.slot}")
                print(f"  Prior: {entry.prior_value} → New: {entry.new_value}")
                print(f"  Drift: {entry.drift:.2f}")
    except Exception as e:
        print(f"  Error reading ledger: {e}")
    
    print()

if __name__ == "__main__":
    main()