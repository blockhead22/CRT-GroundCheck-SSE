#!/usr/bin/env python3
"""
CRT-GroundCheck-SSE Demo with ReAct Orchestration
Run: python rag-demo.py

Architecture (ReAct Pattern):
  1. THINK   - IntentRouter classifies user intent
  2. ACT     - Call appropriate tool (FactStore, CRT, LLM)
  3. OBSERVE - Get tool result
  4. THINK   - Validate result, decide if complete
  5. RESPOND - Return final answer to user
  
Tools:
  - FactStore: Structured slot-based memory (store/lookup)
  - CRT: Trust-weighted memory with contradiction tracking
  - LLM: Generation for code, explanations, chat
  - Templates: Fallback responses when no LLM
  
PROD extension points:
- Add GroundCheck validation on LLM responses  
- Add SSE compression for long-term memory
- Add multi-step reasoning chains
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


# Verbose mode for showing orchestration steps
VERBOSE = True


def log_step(phase: str, message: str):
    """Log orchestration step if verbose mode is on."""
    if VERBOSE:
        print(f"  [{phase}] {message}")


def llm_generate(prompt: str, system: str = None) -> str:
    """Generate response using Ollama if available."""
    if not OLLAMA_AVAILABLE:
        return None
    try:
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        
        log_step("ACT", "Calling LLM...")
        response = ollama.chat(model='llama3.2', messages=messages)
        result = response['message']['content']
        log_step("OBSERVE", f"LLM returned {len(result)} chars")
        return result
    except Exception as e:
        log_step("OBSERVE", f"LLM failed: {e}")
        return None


def main():
    print("=" * 60)
    print("CRT + FactStore + ReAct Orchestration Demo")
    print("=" * 60)
    print()
    print("Commands: quit | facts | memory | history <slot> | clear | verbose")
    print(f"LLM: {'Available (Ollama)' if OLLAMA_AVAILABLE else 'Unavailable (templates only)'}")
    print()
    
    # Initialize systems
    print("Initializing...")
    fact_store = FactStore(db_path="demo_facts.db")
    router = IntentRouter()
    crt = CRTEnhancedRAG(memory_db="demo_crt_memory.db", ledger_db="demo_crt_ledger.db")
    print("Ready.\n")
    
    global VERBOSE
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        
        if not user_input:
            continue
        
        # Commands
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye.")
            break
        
        if user_input.lower() == 'verbose':
            VERBOSE = not VERBOSE
            print(f"Verbose mode: {'ON' if VERBOSE else 'OFF'}\n")
            continue
        
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
            print("Cleared.\n")
            continue
        
        # ========== ReAct ORCHESTRATION ==========
        
        # STEP 1: THINK - Classify intent
        log_step("THINK", f"Classifying intent...")
        routed = router.classify(user_input)
        intent = routed.intent
        log_step("THINK", f"Intent = {intent.value} (confidence: {routed.confidence:.2f})")
        
        # STEP 2-4: ACT + OBSERVE + THINK (varies by intent)
        response = None
        
        # --- FACT HANDLERS ---
        if intent in [Intent.FACT_STATEMENT, Intent.FACT_CORRECTION]:
            log_step("ACT", "Calling FactStore.process_input()...")
            result = fact_store.process_input(user_input)
            log_step("OBSERVE", f"Extracted: {len(result['extracted'])}, Updated: {len(result['updated'])}")
            
            # THINK: Format response
            if result["extracted"]:
                f = result["extracted"][0]
                slot_name = f['slot'].split('.')[-1].replace('_', ' ')
                response = f"Got it. I'll remember your {slot_name} is {f['value']}."
            elif result["updated"]:
                u = result["updated"][0]
                slot_name = u['slot'].split('.')[-1].replace('_', ' ')
                response = f"Updated. Your {slot_name} is now {u['to']} (was {u['from']})."
            else:
                log_step("THINK", "No fact extracted, will acknowledge")
                response = "I heard you, but I couldn't extract a specific fact. Try: 'My name is X' or 'My favorite color is Y'."
        
        elif intent == Intent.FACT_QUESTION:
            log_step("ACT", "Calling FactStore.answer()...")
            answer = fact_store.answer(user_input)
            log_step("OBSERVE", f"FactStore returned: {answer or 'None'}")
            
            if answer:
                response = answer
            else:
                # THINK: Need to try fallback
                log_step("THINK", "No fact found, trying CRT fallback...")
                log_step("ACT", "Calling CRT.query()...")
                crt_result = crt.query(user_query=user_input)
                crt_answer = crt_result.get('answer', '')
                log_step("OBSERVE", f"CRT returned: {crt_answer[:50] if crt_answer else 'None'}...")
                
                if crt_answer and not crt_answer.startswith('['):
                    response = crt_answer
                else:
                    response = "I don't know that yet. Tell me!"
        
        elif intent == Intent.META_MEMORY:
            log_step("ACT", "Calling FactStore.get_all_facts()...")
            facts = fact_store.get_all_facts()
            log_step("OBSERVE", f"Found {len(facts)} facts")
            
            if facts:
                lines = ["Here's what I know about you:"]
                for slot, f in facts.items():
                    slot_name = slot.split('.')[-1].replace('_', ' ')
                    lines.append(f"  - {slot_name}: {f['value']}")
                response = "\n".join(lines)
            else:
                response = "I don't know anything about you yet. Tell me something."
        
        # --- TASK HANDLERS ---
        elif intent == Intent.TASK_CODE:
            log_step("THINK", "Code task detected, need LLM")
            if OLLAMA_AVAILABLE:
                lang = routed.extracted.get('language', 'the requested language')
                response = llm_generate(
                    user_input,
                    system=f"You are a helpful coding assistant. Write clean, commented code in {lang}. Keep responses concise. Output code in markdown code blocks."
                )
            else:
                log_step("THINK", "No LLM available, using template")
                response = get_template_response(routed)
                if not response:
                    response = "I can write code, but I need Ollama for complex requests. Install with: pip install ollama"
        
        elif intent == Intent.TASK_EXPLAIN:
            log_step("THINK", "Explanation task, gathering context...")
            if OLLAMA_AVAILABLE:
                log_step("ACT", "Calling FactStore.get_all_facts() for context...")
                facts = fact_store.get_all_facts()
                facts_context = "\n".join([f"- {s}: {f['value']}" for s, f in facts.items()]) if facts else "None"
                log_step("OBSERVE", f"Got {len(facts)} facts for context")
                
                response = llm_generate(
                    f"User facts:\n{facts_context}\n\nQuestion: {user_input}",
                    system="You are a helpful assistant. Explain clearly and concisely. If the question is about the user, use the provided facts."
                )
            else:
                response = "I need Ollama to explain things. Install it with: pip install ollama"
        
        elif intent == Intent.TASK_SUMMARIZE:
            response = "Summarize mode. But I'd need something to summarize. What would you like me to shorten?"
        
        elif intent == Intent.TASK_GENERAL:
            log_step("THINK", "General task, trying LLM...")
            if OLLAMA_AVAILABLE:
                response = llm_generate(user_input, system="You are a helpful assistant. Be concise and practical.")
            else:
                response = "I'd love to help. What specifically do you need? I'm best at remembering facts about you and simple code tasks."
        
        # --- KNOWLEDGE HANDLERS ---
        elif intent in [Intent.KNOWLEDGE_QUERY, Intent.KNOWLEDGE_OPINION]:
            log_step("THINK", "Knowledge query, need LLM...")
            if OLLAMA_AVAILABLE:
                response = llm_generate(
                    user_input,
                    system="You are a knowledgeable assistant. Answer accurately and concisely. If unsure, say so."
                )
            else:
                response = get_template_response(routed) or "I need Ollama to answer general knowledge questions."
        
        # --- CHAT HANDLERS ---
        elif intent == Intent.CHAT_GREETING:
            log_step("THINK", "Greeting detected, using template")
            response = get_template_response(routed)
        
        elif intent == Intent.CHAT_FAREWELL:
            log_step("THINK", "Farewell detected, using template")
            response = get_template_response(routed)
        
        elif intent == Intent.CHAT_SMALLTALK:
            log_step("THINK", "Smalltalk, personalizing with facts...")
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
            log_step("THINK", "Emotional content, responding empathetically...")
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

- FactStore: Structured facts (name, color, job)
- CRT: Trust-weighted memory for complex info  
- IntentRouter: Routes your input to the right handler
- GroundCheck: Validates responses are factual

Try: "My name is X" then "What is my name?" then "facts" """
        
        # --- FALLBACK ---
        elif intent == Intent.UNKNOWN:
            log_step("THINK", "Unknown intent, trying LLM as fallback...")
            if OLLAMA_AVAILABLE:
                facts = fact_store.get_all_facts()
                facts_context = "\n".join([f"- {s}: {f['value']}" for s, f in facts.items()]) if facts else "None"
                response = llm_generate(
                    f"User facts:\n{facts_context}\n\nUser: {user_input}",
                    system="You are a helpful assistant with memory. Use the user facts if relevant. Be concise."
                )
            else:
                response = get_template_response(routed)
        
        # STEP 5: RESPOND
        log_step("RESPOND", "Delivering final answer")
        if response:
            print(f"\nAssistant: {response}\n")
        else:
            print(f"\nAssistant: I'm not sure how to respond to that.\n")


def show_facts(fact_store):
    print("\n" + "=" * 50)
    print("CURRENT FACTS")
    print("=" * 50)
    facts = fact_store.get_all_facts()
    if not facts:
        print("  (none yet)")
    else:
        for slot, f in facts.items():
            bar = "#" * int(f['trust'] * 10) + "." * (10 - int(f['trust'] * 10))
            print(f"\n  {slot}")
            print(f"    Value: {f['value']}")
            print(f"    Trust: [{bar}] {f['trust']:.2f} | Source: {f['source']}")
    print()


def show_memory(crt):
    print("\n" + "=" * 50)
    print("CRT RAW MEMORIES (last 5)")
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
    
    print(f"\nHistory for {slot}:")
    history = fact_store.get_history(slot)
    if not history:
        print("  (no history)")
    else:
        for h in history:
            current = "<- current" if h['is_current'] else ""
            print(f"  {h['timestamp'][:19]} | {h['value']} ({h['source']}) {current}")
    print()
    print()


if __name__ == "__main__":
    main()