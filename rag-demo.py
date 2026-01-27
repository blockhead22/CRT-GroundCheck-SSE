#!/usr/bin/env python3
"""
CRT-GroundCheck-SSE Demo with Structured Fact Store
Run: python rag-demo.py

Architecture:
  User Input → FactStore (extract/store) → Answer from slots OR fallback to CRT
  
PROD extension points:
- Add LLM expansion layer between FactStore and response
- Add GroundCheck validation on LLM responses  
- Add SSE compression for long-term memory
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "groundcheck"))

from personal_agent.fact_store import FactStore
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import MemorySource

# Optional components
try:
    from groundcheck import GroundCheck, Memory as GCMemory
    GROUNDCHECK_AVAILABLE = True
except ImportError:
    GROUNDCHECK_AVAILABLE = False

try:
    from sse.contradictions import heuristic_contradiction
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def main():
    print("=" * 60)
    print("CRT + FactStore Demo")
    print("=" * 60)
    print()
    print("Commands: quit | facts | memory | history <slot> | clear")
    print(f"Components: FactStore ✅ | CRT ✅ | GroundCheck {'✅' if GROUNDCHECK_AVAILABLE else '❌'} | SSE {'✅' if SSE_AVAILABLE else '❌'}")
    print()
    
    # Initialize
    print("🔧 Initializing...")
    fact_store = FactStore(db_path="demo_facts.db")
    crt = CRTEnhancedRAG(memory_db="demo_crt_memory.db", ledger_db="demo_crt_ledger.db")
    print("✅ Ready!\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        # Commands
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if user_input.lower() == 'facts':
            show_facts(fact_store)
            continue
        
        if user_input.lower() == 'memory':
            show_memory(crt)
            continue
        
        if user_input.lower().startswith('history '):
            slot = user_input[8:].strip()
            show_history(fact_store, slot)
            continue
        
        if user_input.lower() == 'clear':
            import os
            for f in ["demo_facts.db", "demo_crt_memory.db", "demo_crt_ledger.db"]:
                if os.path.exists(f):
                    os.remove(f)
            fact_store = FactStore(db_path="demo_facts.db")
            crt = CRTEnhancedRAG(memory_db="demo_crt_memory.db", ledger_db="demo_crt_ledger.db")
            print("✅ Cleared!\n")
            continue
        
        # ========== PROCESS INPUT ==========
        
        # 1. Extract structured facts
        result = fact_store.process_input(user_input)
        
        # Show what we extracted/updated
        if result["extracted"]:
            for f in result["extracted"]:
                slot_name = f['slot'].split('.')[-1].replace('_', ' ')
                print(f"📝 Stored: {slot_name} = {f['value']}")
        
        if result["contradictions"]:
            for c in result["contradictions"]:
                slot_name = c['slot'].split('.')[-1].replace('_', ' ')
                print(f"⚠️  Updated {slot_name}: '{c['old']}' → '{c['new']}'")
        
        # 2. Detect if question
        is_question = _is_question(user_input)
        
        if is_question:
            # Try FactStore first
            answer = fact_store.answer(user_input)
            if answer:
                print(f"\n🤖 Assistant: {answer}\n")
                continue
            
            # Fallback to CRT for complex queries
            # PROD: Add LLM reasoning here
            print("(No fact found, checking CRT...)")
            crt_result = crt.query(user_query=user_input)
            crt_answer = crt_result.get('answer', '')
            
            if crt_answer and not crt_answer.startswith('['):
                print(f"\n🤖 Assistant: {crt_answer}\n")
            else:
                print(f"\n🤖 Assistant: I don't know that yet. Tell me!\n")
        else:
            # Statement - acknowledge
            if result["updated"]:
                u = result["updated"][0]
                slot_name = u['slot'].split('.')[-1].replace('_', ' ')
                print(f"\n🤖 Assistant: Got it! Updated your {slot_name} to {u['to']}.\n")
            elif result["extracted"]:
                f = result["extracted"][0]
                slot_name = f['slot'].split('.')[-1].replace('_', ' ')
                print(f"\n🤖 Assistant: Nice! I'll remember your {slot_name} is {f['value']}.\n")
            else:
                # No structured fact extracted - store in CRT as raw memory
                # PROD: Try LLM extraction here
                print(f"\n🤖 Assistant: Noted!\n")


def _is_question(text: str) -> bool:
    t = text.lower().strip()
    if t.endswith('?'):
        return True
    q_words = ['what', 'who', 'where', 'when', 'why', 'how', 'is my', 'do i', 'am i', 'whats', "what's"]
    return any(t.startswith(w) for w in q_words)


def show_facts(fact_store):
    print("\n" + "=" * 50)
    print("📋 CURRENT FACTS")
    print("=" * 50)
    facts = fact_store.get_all_facts()
    if not facts:
        print("  (none yet)")
    else:
        for slot, f in facts.items():
            bar = "█" * int(f['trust'] * 10) + "░" * (10 - int(f['trust'] * 10))
            print(f"\n  {slot}")
            print(f"    → {f['value']}")
            print(f"    Trust: [{bar}] {f['trust']:.2f} | Source: {f['source']}")
    print()


def show_memory(crt):
    print("\n" + "=" * 50)
    print("📚 CRT RAW MEMORIES (last 5)")
    print("=" * 50)
    memories = crt.memory._load_all_memories()
    if not memories:
        print("  (none)")
    else:
        for mem in memories[-5:]:
            print(f"  [{mem.trust:.2f}] {mem.text[:60]}...")
    print()


def show_history(fact_store, slot):
    # Auto-prefix if needed
    if not slot.startswith("user."):
        slot = f"user.{slot}"
    
    print(f"\n📜 History for {slot}:")
    history = fact_store.get_history(slot)
    if not history:
        print("  (no history)")
    else:
        for h in history:
            current = "← current" if h['is_current'] else ""
            print(f"  {h['timestamp'][:19]} | {h['value']} ({h['source']}) {current}")
    print()


if __name__ == "__main__":
    main()