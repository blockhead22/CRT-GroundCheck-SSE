"""Debug age gate blocking"""
import requests
import time

API_URL = "http://127.0.0.1:8123/api/chat/send"

thread_id = f"age_debug_{int(time.time())}"

print("Testing age gate blocking...")

# Setup contradiction
r1 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I am 25 years old"}, timeout=30)
print(f"1. {r1.json()['answer'][:80]}")

time.sleep(0.5)

r2 = requests.post(API_URL, json={"thread_id": thread_id, "message": "I am 30 years old"}, timeout=30)
data2 = r2.json()
print(f"2. {data2['answer'][:80]}")
print(f"   contradiction_detected: {data2.get('contradiction_detected')}")

time.sleep(0.5)

# Query
r3 = requests.post(API_URL, json={"thread_id": thread_id, "message": "How old am I?"}, timeout=30)
data3 = r3.json()

print(f"3. Query response:")
print(f"   gates_passed: {data3.get('gates_passed')}")
print(f"   answer: {data3.get('answer')}")
print(f"   unresolved_contradictions_total: {data3.get('unresolved_contradictions_total')}")

# Check contradictions endpoint
r_contra = requests.get("http://127.0.0.1:8123/api/contradictions", params={"thread_id": thread_id})
contradictions = r_contra.json().get("contradictions", [])
print(f"\n4. Open contradictions: {len(contradictions)}")
for c in contradictions:
    print(f"   - {c.get('summary', 'N/A')[:60]}")
