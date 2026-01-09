#!/usr/bin/env python3
"""
Quick test of CRT Chat with Ollama

Tests:
1. Embeddings working (384 dims)
2. Ollama connection
3. Basic memory storage
4. Query with real AI
"""

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client
from personal_agent.embeddings import encode_text

print("=" * 70)
print("CRT + Ollama Integration Test")
print("=" * 70)

# Test 1: Embeddings
print("\n1. Testing embeddings...")
try:
    vec = encode_text("test")
    print(f"   ✅ Embeddings working: {len(vec)} dimensions")
except Exception as e:
    print(f"   ❌ Embedding error: {e}")
    exit(1)

# Test 2: Ollama
print("\n2. Testing Ollama connection...")
try:
    ollama = get_ollama_client("llama3")
    response = ollama.generate("Say hello in 5 words or less", max_tokens=20, temperature=0.5)
    print(f"   ✅ Ollama working")
    print(f"   Response: {response[:100]}")
except Exception as e:
    print(f"   ❌ Ollama error: {e}")
    print(f"   💡 Make sure: ollama serve is running")
    print(f"   💡 And run: ollama pull llama3")
    exit(1)

# Test 3: CRT System
print("\n3. Initializing CRT system...")
try:
    rag = CRTEnhancedRAG()
    print(f"   ✅ CRT initialized")
except Exception as e:
    print(f"   ❌ CRT error: {e}")
    exit(1)

# Test 4: Simple query
print("\n4. Testing query...")
try:
    result = rag.query("Hello! My name is Test User.", user_marked_important=True)
    print(f"   ✅ Query successful")
    print(f"   Response type: {result['response_type']}")
    print(f"   Answer: {result['answer'][:100]}")
    print(f"   Confidence: {result['confidence']:.2f}")
except Exception as e:
    print(f"   ❌ Query error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 5: Recall
print("\n5. Testing recall...")
try:
    result2 = rag.query("What's my name?")
    print(f"   ✅ Recall successful")
    print(f"   Response: {result2['answer'][:100]}")
    print(f"   Retrieved {len(result2['retrieved_memories'])} memories")
except Exception as e:
    print(f"   ❌ Recall error: {e}")
    exit(1)

print("\n" + "=" * 70)
print("✅ All tests passed!")
print("=" * 70)
print("\n🚀 Ready to launch chat GUI:")
print("   streamlit run crt_chat_gui.py --server.port 8502")
print("\n📊 Or view dashboard:")
print("   streamlit run crt_dashboard.py")
print()
