#!/usr/bin/env python3
"""
CRT-GroundCheck-SSE Demo
Run: python rag-demo.py

A simple chat interface demonstrating:
- CRT: Memory with trust scores, contradiction detection, belief/speech separation
- GroundCheck: Verifies responses are grounded in context (no hallucinations)
- SSE: Semantic compression modes and contradiction heuristics

Architecture notes for generative expansion:
- CRT provides the "truth layer" - what facts we know and their trust scores
- GroundCheck validates that any generated text stays grounded in those facts
- SSE provides semantic compression and contradiction detection
- An LLM (Ollama) can expand the facts into natural language responses
- The flow: User Input → CRT (retrieve + detect contradictions) → LLM (expand) → GroundCheck (validate) → Response
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "groundcheck"))

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.crt_core import SSEMode, MemorySource

# Optional: GroundCheck for verification
try:
    from groundcheck import GroundCheck, Memory as GCMemory
    GROUNDCHECK_AVAILABLE = True
except ImportError:
    GROUNDCHECK_AVAILABLE = False

# Optional: SSE contradiction detection
try:
    from sse.contradictions import heuristic_contradiction
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False

# Optional: Ollama for generative expansion
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def demo_groundcheck(response_text, memories):
    """Demonstrate GroundCheck verification."""
    if not GROUNDCHECK_AVAILABLE or not memories:
        return None
    try:
        verifier = GroundCheck()
        gc_memories = [GCMemory(id=f"m{i}", text=m.get('text', '')) for i, m in enumerate(memories)]
        result = verifier.verify(response_text, gc_memories)
        return {'passed': result.passed, 'hallucinations': getattr(result, 'hallucinations', [])}
    except Exception as e:
        return {'error': str(e)}


def demo_sse_contradiction(text_a, text_b):
    """Demonstrate SSE heuristic contradiction detection."""
    if not SSE_AVAILABLE:
        return None
    try:
        return heuristic_contradiction(text_a, text_b)
    except Exception:
        return None


def expand_with_llm(crt_answer, user_input, retrieved_memories, contradiction_detected):
    """
    Use LLM to expand CRT's factual answer into natural language.
    
    This is where the 'generative layer' comes in:
    - CRT provides the facts and trust scores (the 'truth')
    - LLM expands those facts into helpful, natural responses
    - GroundCheck can then validate the expansion stays grounded
    """
    if not OLLAMA_AVAILABLE:
        return crt_answer  # Fall back to raw CRT answer
    
    # Build context from retrieved memories
    memory_context = "\n".join([
        f"- {m.get('text', '')} (trust: {m.get('trust', 0):.2f})"
        for m in retrieved_memories[:5]
    ]) if retrieved_memories else "No prior context."
    
    # Build system prompt that enforces grounding
    system_prompt = """You are a helpful assistant with memory. You MUST:
1. Only state facts that appear in the provided context
2. If you're unsure, say so - don't make things up
3. If there's a contradiction in context, acknowledge it
4. Keep responses concise and natural"""

    # Build user message with context
    user_message = f"""Context from memory:
{memory_context}

CRT system answer: {crt_answer}
{"⚠️ CONTRADICTION DETECTED - please acknowledge conflicting information" if contradiction_detected else ""}

User question: {user_input}

Respond naturally based on the context. If CRT already gave a good answer, you can expand on it slightly. If the context is insufficient, say so."""

    try:
        response = ollama.chat(
            model='llama3.2',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message}
            ]
        )
        return response['message']['content']
    except Exception as e:
        return f"{crt_answer}\n\n(LLM expansion failed: {e})"


def main():
    print("=" * 60)
    print("CRT-GroundCheck-SSE Demo")
    print("=" * 60)
    print()
    print("Commands: quit | memory | trust | ledger | clear")
    print(f"Components: CRT ✅ | GroundCheck {'✅' if GROUNDCHECK_AVAILABLE else '❌'} | SSE {'✅' if SSE_AVAILABLE else '❌'} | Ollama {'✅' if OLLAMA_AVAILABLE else '❌'}")
    print()
    
    # Initialize CRT system with demo databases
    print("🔧 Initializing CRT system...")
    rag = CRTEnhancedRAG(
        memory_db="demo_crt_memory.db",
        ledger_db="demo_crt_ledger.db"
    )
    print("✅ CRT system ready!\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if user_input.lower() == 'memory':
            show_memory(rag)
            continue
        
        if user_input.lower() == 'trust':
            show_trust_scores(rag)
            continue
        
        if user_input.lower() == 'ledger':
            show_ledger(rag)
            continue
        
        if user_input.lower() == 'clear':
            import os
            for db in ["demo_crt_memory.db", "demo_crt_ledger.db"]:
                if os.path.exists(db):
                    os.remove(db)
            rag = CRTEnhancedRAG(memory_db="demo_crt_memory.db", ledger_db="demo_crt_ledger.db")
            print("✅ Demo databases cleared\n")
            continue
        
        if not user_input:
            continue
        
        try:
            print("\n🔍 Processing with CRT...")
            
            # Query CRT system (correct signature - no conversation_history)
            result = rag.query(user_query=user_input)
            
            # Extract CRT results
            answer = result.get('answer', '(no response)')
            confidence = result.get('confidence', 0.0)
            response_type = result.get('response_type', 'unknown')
            gates_passed = result.get('gates_passed', False)
            contradiction_detected = result.get('contradiction_detected', False)
            retrieved_memories = result.get('retrieved_memories', [])
            unresolved_hard = result.get('unresolved_hard_conflicts', 0)
            
            # Display CRT status
            print(f"\n┌─ CRT Status ─────────────────────────────────")
            print(f"│ Confidence: {confidence:.0%}")
            print(f"│ Response Type: {response_type}")
            print(f"│ Gates Passed: {'✅' if gates_passed else '❌'}")
            if contradiction_detected:
                print(f"│ ⚠️  CONTRADICTION DETECTED")
            if unresolved_hard > 0:
                print(f"│ 🔴 Unresolved conflicts: {unresolved_hard}")
            print(f"│ Retrieved: {len(retrieved_memories)} memories")
            print(f"└───────────────────────────────────────────────")
            
            # Show retrieved memories
            if retrieved_memories:
                print("\n📚 Top Retrieved Memories:")
                for i, mem in enumerate(retrieved_memories[:3], 1):
                    trust = mem.get('trust', 0)
                    text = mem.get('text', '')[:60]
                    print(f"   {i}. [Trust: {trust:.2f}] {text}...")
            
            # GroundCheck verification on CRT answer
            if GROUNDCHECK_AVAILABLE and retrieved_memories and answer:
                gc_result = demo_groundcheck(answer, retrieved_memories)
                if gc_result and 'error' not in gc_result:
                    status = "✅ GROUNDED" if gc_result['passed'] else "⚠️ UNGROUNDED"
                    print(f"\n🔬 GroundCheck: {status}")
            
            # SSE heuristic check
            if SSE_AVAILABLE and retrieved_memories:
                prior = retrieved_memories[0].get('text', '')
                if prior:
                    sse_result = demo_sse_contradiction(prior, user_input)
                    if sse_result == 'contradiction':
                        print(f"🔥 SSE Heuristic: Contradiction with prior memory")
            
            # Expand with LLM if available (generative layer)
            if OLLAMA_AVAILABLE:
                print("\n💭 Expanding with LLM...")
                expanded_answer = expand_with_llm(
                    answer, user_input, retrieved_memories, contradiction_detected
                )
                
                # Validate expanded answer with GroundCheck
                if GROUNDCHECK_AVAILABLE and retrieved_memories:
                    gc_expanded = demo_groundcheck(expanded_answer, retrieved_memories)
                    if gc_expanded and 'error' not in gc_expanded:
                        if not gc_expanded['passed']:
                            print(f"⚠️ LLM response may contain ungrounded claims")
                            if gc_expanded.get('hallucinations'):
                                print(f"   Potential hallucinations: {gc_expanded['hallucinations'][:3]}")
                
                print(f"\n🤖 Assistant: {expanded_answer}\n")
            else:
                # No LLM - just show CRT's raw answer
                print(f"\n🤖 Assistant: {answer}\n")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print()


def show_memory(rag):
    """Display stored memories with trust scores."""
    print("\n" + "=" * 50)
    print("📚 STORED MEMORIES")
    print("=" * 50)
    
    memories = rag.memory._load_all_memories()
    if not memories:
        print("  (no memories stored yet)")
    else:
        for mem in memories[-10:]:  # Last 10
            trust_bar = "█" * int(mem.trust * 10) + "░" * (10 - int(mem.trust * 10))
            # Map source to emoji (only use sources that actually exist in MemorySource enum)
            source_emoji = {
                MemorySource.USER: "👤",
                MemorySource.SYSTEM: "🤖",
                MemorySource.FALLBACK: "💭",
                MemorySource.EXTERNAL: "🌐",
                MemorySource.REFLECTION: "🔮",
                MemorySource.LLM_OUTPUT: "🧠",
            }
            emoji = source_emoji.get(mem.source, "❓")
            print(f"\n  {emoji} [{trust_bar}] Trust: {mem.trust:.2f}")
            print(f"     {mem.text[:80]}{'...' if len(mem.text) > 80 else ''}")
    print()


def show_trust_scores(rag):
    """Display trust scores for all facts."""
    print("\n" + "=" * 50)
    print("🎯 TRUST SCORES")
    print("=" * 50)
    
    memories = rag.memory._load_all_memories()
    if not memories:
        print("  (no facts stored yet)")
    else:
        for mem in memories[-10:]:
            bar = "█" * int(mem.trust * 10) + "░" * (10 - int(mem.trust * 10))
            print(f"  [{bar}] {mem.trust:.2f} - {mem.text[:50]}...")
    print()


def show_ledger(rag):
    """Display contradiction ledger."""
    print("\n" + "=" * 50)
    print("⚖️ CONTRADICTION LEDGER")
    print("=" * 50)
    
    try:
        entries = rag.ledger.get_unresolved_contradictions()
        if not entries:
            print("  (no contradictions detected)")
        else:
            for entry in entries[:10]:
                print(f"\n  📍 Type: {entry.contradiction_type.value}")
                print(f"     Slot: {entry.slot}")
                print(f"     Old: {entry.old_value}")
                print(f"     New: {entry.new_value}")
                print(f"     Status: {entry.resolution_status.value}")
    except Exception as e:
        print(f"  Error reading ledger: {e}")
    print()


if __name__ == "__main__":
    main()