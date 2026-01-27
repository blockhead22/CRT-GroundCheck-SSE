#!/usr/bin/env python3
"""
CRT-GroundCheck-SSE Demo with Intent Router
Run: python rag-demo.py

Architecture:
  User Input → IntentRouter → Handler → Response
  
Handlers:
  - fact_statement/correction → FactStore (store)
  - fact_question → FactStore (lookup) → CRT fallback
  - task_* → Templates or LLM
  - chat_* → Templates or LLM
  - knowledge_* → LLM or punt
  
PROD extension points:
- Add LLM expansion layer for all handlers
- Add GroundCheck validation on LLM responses  
- Add SSE compression for long-term memory
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "groundcheck"))

from personal_agent.fact_store import FactStore
from personal_agent.intent_router import IntentRouter, Intent, get_template_response
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


def llm_generate(prompt: str, system: str = None) -> str:
    """Generate response using Ollama if available."""
    if not OLLAMA_AVAILABLE:
        return None
    try:
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        
        response = ollama.chat(model='llama3.2', messages=messages)
        return response['message']['content']
    except Exception:
        return None


def main():
    print("=" * 60)
    print("CRT + FactStore + Intent Router Demo")
    print("=" * 60)
    print()
    print("Commands: quit | facts | memory | history <slot> | clear")
    print(f"LLM: {'✅ Ollama' if OLLAMA_AVAILABLE else '❌ Templates only'}")
    print()
    
    # Initialize systems
    print("🔧 Initializing...")
    fact_store = FactStore(db_path="demo_facts.db")
    router = IntentRouter()
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
        
        # ========== ROUTE & HANDLE ==========
        
        # 1. Classify intent
        routed = router.classify(user_input)
        intent = routed.intent
        
        # Debug: show intent (can remove later)
        print(f"[{intent.value}]")
        
        # 2. Handle based on intent
        response = None
        
        # --- FACT HANDLERS ---
        if intent in [Intent.FACT_STATEMENT, Intent.FACT_CORRECTION]:
            result = fact_store.process_input(user_input)
            
            if result["extracted"]:
                f = result["extracted"][0]
                slot_name = f['slot'].split('.')[-1].replace('_', ' ')
                response = f"Got it! I'll remember your {slot_name} is {f['value']}."
            elif result["updated"]:
                u = result["updated"][0]
                slot_name = u['slot'].split('.')[-1].replace('_', ' ')
                response = f"Updated! Your {slot_name} is now {u['to']} (was {u['from']})."
            else:
                response = "I heard you, but I couldn't extract a specific fact. Try: 'My name is X' or 'My favorite color is Y'."
        
        elif intent == Intent.FACT_QUESTION:
            answer = fact_store.answer(user_input)
            if answer:
                response = answer
            else:
                # Fallback to CRT
                crt_result = crt.query(user_query=user_input)
                crt_answer = crt_result.get('answer', '')
                if crt_answer and not crt_answer.startswith('['):
                    response = crt_answer
                else:
                    response = "I don't know that yet. Tell me!"
        
        elif intent == Intent.META_MEMORY:
            facts = fact_store.get_all_facts()
            if facts:
                lines = ["Here's what I know about you:"]
                for slot, f in facts.items():
                    slot_name = slot.split('.')[-1].replace('_', ' ')
                    lines.append(f"  • {slot_name}: {f['value']}")
                response = "\n".join(lines)
            else:
                response = "I don't know anything about you yet. Tell me something!"
        
        # --- TASK HANDLERS ---
        elif intent == Intent.TASK_CODE:
            # Always try LLM first for code tasks
            if OLLAMA_AVAILABLE:
                lang = routed.extracted.get('language', 'the requested language')
                response = llm_generate(
                    user_input,
                    system=f"You are a helpful coding assistant. Write clean, commented code in {lang}. Keep responses concise. Output code in markdown code blocks."
                )
            else:
                # Fall back to template
                response = get_template_response(routed)
                if not response:
                    response = "I can write code, but I need Ollama for complex requests. Install with: pip install ollama"
        
        elif intent == Intent.TASK_EXPLAIN:
            if OLLAMA_AVAILABLE:
                # Get facts for context
                facts = fact_store.get_all_facts()
                facts_context = "\n".join([f"- {s}: {f['value']}" for s, f in facts.items()]) if facts else "None"
                
                response = llm_generate(
                    f"User facts:\n{facts_context}\n\nQuestion: {user_input}",
                    system="You are a helpful assistant. Explain clearly and concisely. If the question is about the user, use the provided facts."
                )
            else:
                response = "I need Ollama to explain things. Install it with: pip install ollama"
        
        elif intent == Intent.TASK_SUMMARIZE:
            response = "TL;DR mode! But I'd need something to summarize. What would you like me to shorten?"
        
        elif intent == Intent.TASK_GENERAL:
            if OLLAMA_AVAILABLE:
                response = llm_generate(user_input, system="You are a helpful assistant. Be concise and practical.")
            else:
                response = "I'd love to help! What specifically do you need? I'm best at remembering facts about you and simple code tasks."
        
        # --- KNOWLEDGE HANDLERS ---
        elif intent in [Intent.KNOWLEDGE_QUERY, Intent.KNOWLEDGE_OPINION]:
            if OLLAMA_AVAILABLE:
                response = llm_generate(
                    user_input,
                    system="You are a knowledgeable assistant. Answer accurately and concisely. If unsure, say so."
                )
            else:
                response = get_template_response(routed) or "I need Ollama to answer general knowledge questions."
        
        # --- CHAT HANDLERS ---
        elif intent == Intent.CHAT_GREETING:
            response = get_template_response(routed)
        
        elif intent == Intent.CHAT_FAREWELL:
            response = get_template_response(routed)
        
        elif intent == Intent.CHAT_SMALLTALK:
            if OLLAMA_AVAILABLE:
                facts = fact_store.get_all_facts()
                name = facts.get('user.name', {}).get('value', 'friend')
                response = llm_generate(
                    user_input,
                    system=f"You are a friendly assistant chatting with {name}. Keep it brief and warm."
                )
            else:
                response = get_template_response(routed)
        
        elif intent == Intent.CHAT_EMOTION:
            if OLLAMA_AVAILABLE:
                facts = fact_store.get_all_facts()
                name = facts.get('user.name', {}).get('value', '')
                name_part = f" {name}" if name else ""
                response = llm_generate(
                    user_input,
                    system=f"The user{name_part} is sharing their feelings. Be empathetic but brief. Don't say 'I'm here for you' or similar cliches."
                )
            else:
                response = get_template_response(routed)
        
        # --- META HANDLERS ---
        elif intent == Intent.META_SYSTEM:
            response = """I'm a memory-focused AI with these components:

📋 **FactStore** - Structured facts (name, color, job)
🧠 **CRT** - Trust-weighted memory for complex info  
🎯 **IntentRouter** - Routes your input to the right handler
🔬 **GroundCheck** - Validates responses are factual

Try: "My name is X" → "What is my name?" → "facts" """
        
        # --- FALLBACK ---
        elif intent == Intent.UNKNOWN:
            if OLLAMA_AVAILABLE:
                # Let LLM try to handle it
                facts = fact_store.get_all_facts()
                facts_context = "\n".join([f"- {s}: {f['value']}" for s, f in facts.items()]) if facts else "None"
                response = llm_generate(
                    f"User facts:\n{facts_context}\n\nUser: {user_input}",
                    system="You are a helpful assistant with memory. Use the user facts if relevant. Be concise."
                )
            else:
                response = get_template_response(routed)
        
        # Output response
        if response:
            print(f"\n🤖 {response}\n")
        else:
            print(f"\n🤖 I'm not sure how to respond to that.\n")


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