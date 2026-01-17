"""
Generate diverse test queries for manual correction
"""
import requests
import time

queries = [
    # Factual - simple fact retrieval
    "What is my name?",
    "Where do I work?",
    "What city do I live in?",
    "What is my job title?",
    "When did I graduate?",
    
    # Factual - with question words (tricky)
    "When did I start working?",
    "Where did I go to school?",
    "What degree do I have?",
    "How old am I?",
    
    # Conversational - greetings/acknowledgments
    "Hi there!",
    "Good morning",
    "Thanks so much!",
    "That's really helpful",
    "I appreciate it",
    
    # Conversational - requests
    "Can you help me?",
    "Could you assist with something?",
    "I need your help",
    
    # Explanatory - why/how questions
    "Why did I choose this career?",
    "How does my project work?",
    "Why am I interested in AI?",
    "How did I learn programming?",
    "Explain your memory system",
    
    # Explanatory - complex synthesis
    "Tell me about yourself",
    "What do you know about me?",
    "Give me an overview",
    "Summarize what we've discussed",
    
    # Mixed - interests/preferences
    "What are my hobbies?",
    "What technologies am I into?",
    "What do I like to do?",
    "What are my interests?",
    
    # Edge cases
    "What's my favorite color?",
    "Do I have any pets?",
    "What languages do I speak?",
    "Am I happy with my job?",
]

print(f"Generating {len(queries)} diverse test queries...")

success = 0
failed = 0

for q in queries:
    try:
        resp = requests.post(
            'http://localhost:8123/api/chat/send',
            json={'thread_id': 'manual_correction_test', 'message': q},
            timeout=10
        )
        if resp.ok:
            print(f"  ✓ {q}")
            success += 1
        else:
            print(f"  ✗ {q} (HTTP {resp.status_code})")
            failed += 1
    except Exception as e:
        print(f"  ✗ {q} ({str(e)[:50]})")
        failed += 1
    
    time.sleep(0.1)  # Rate limit

print(f"\n✓ Generated {success} events")
print(f"✗ Failed {failed} events")
print(f"\nRun: python quick_corrections.py")
