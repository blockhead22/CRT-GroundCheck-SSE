"""Generate some test events to correct."""
import requests

API = "http://localhost:8123"
THREAD = "correction_test"

queries = [
    "What is my name?",
    "When did I graduate?",
    "How many languages do I speak?",
    "Hi, how are you?",
    "Thanks for helping!",
    "Why am I working on this project?",
    "Where do I live?",
    "Can you explain what you know about me?",
    "What technologies am I interested in?",
    "How does CRT work?",
]

print("Generating test events...")
for query in queries:
    print(f"  {query}")
    try:
        response = requests.post(
            f"{API}/api/chat/send",
            json={"thread_id": THREAD, "message": query},
            timeout=10
        )
        if response.status_code == 200:
            print(f"    ✓")
        else:
            print(f"    ✗ {response.status_code}")
    except Exception as e:
        print(f"    ✗ {e}")

print(f"\n✓ Generated {len(queries)} events for correction")
