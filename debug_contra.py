import sys
sys.path.insert(0, "D:/AI_round2")
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.ollama_client import get_ollama_client
from personal_agent.crt_core import MemorySource

ollama = get_ollama_client()
rag = CRTEnhancedRAG(llm_client=ollama)

print("Testing contradiction detection with detailed output\n")

# Turn 1
result1 = rag.query("I work at Microsoft")
print("Turn 1 complete\n")

# Turn 2 - should contradict
print("Turn 2: I work at Amazon")
# Manually check what previous_user_memories would be
retrieved = rag.retrieve("I work at Amazon", k=5)
user_mems = [mem for mem, _ in retrieved if mem.source == MemorySource.USER]
print(f"Total USER memories in retrieval: {len(user_mems)}")
for i, mem in enumerate(user_mems[:3]):
    print(f"  {i+1}. {mem.text[:60]}... (id={mem.memory_id})")

result2 = rag.query("I work at Amazon")
print(f"\nContradiction detected: {result2.get('contradiction_detected', False)}")
