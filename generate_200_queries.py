"""Generate 60 more diverse queries to reach 200+ training examples."""
import requests
import time

queries = [
    # Factual queries (20)
    "What is my birthday?",
    "What is my age?",
    "What is my hometown?",
    "Where did I go to school?",
    "What is my degree?",
    "What is my major?",
    "What is my favorite food?",
    "What is my favorite movie?",
    "What is my favorite book?",
    "What sports do I play?",
    "What instruments do I play?",
    "What pets do I have?",
    "What are my hobbies?",
    "What car do I drive?",
    "What city do I live in?",
    "What neighborhood am I in?",
    "What is my relationship status?",
    "Do I have kids?",
    "What languages do I know?",
    "What certifications do I have?",
    
    # Conversational queries (20)
    "Good evening!",
    "Hey there!",
    "How's it going?",
    "What's up?",
    "Nice to meet you!",
    "Great to chat with you!",
    "I really appreciate this",
    "You've been so helpful",
    "This is amazing",
    "Wow that's great",
    "I'm so grateful",
    "Could you please assist me?",
    "I'd like some help",
    "Can I get your help?",
    "I need assistance",
    "Please help with this",
    "I have a quick question",
    "May I ask something?",
    "Can we talk about something?",
    "I'd love to discuss this",
    
    # Explanatory queries (20)
    "Why do I like this?",
    "How can I improve?",
    "What motivates my decisions?",
    "Explain my career path",
    "How did I get here?",
    "Why is this important to me?",
    "Walk me through my experience",
    "Break down my skills",
    "Describe my background",
    "Summarize my education",
    "Give me an overview of my work",
    "Tell me about my achievements",
    "How do I spend my time?",
    "What drives me?",
    "Why am I interested in this field?",
    "How does my memory work?",
    "Explain your reasoning",
    "How do you remember things?",
    "What is your approach?",
    "Describe how you think",
]

API_BASE = "http://localhost:8123"
THREAD_ID = "training_data_generation_200"

print(f"Generating {len(queries)} queries...")
print("=" * 60)

success = 0
failed = 0

for i, query in enumerate(queries, 1):
    try:
        resp = requests.post(
            f"{API_BASE}/api/chat/send",
            json={"thread_id": THREAD_ID, "message": query},
            timeout=15
        )
        if resp.ok:
            success += 1
            print(f"✓ {i}/{len(queries)}: {query[:50]}")
        else:
            failed += 1
            print(f"✗ {i}/{len(queries)}: {query[:50]} (HTTP {resp.status_code})")
        time.sleep(0.02)  # Small delay to avoid overwhelming API
    except Exception as e:
        failed += 1
        print(f"✗ {i}/{len(queries)}: {query[:50]} ({e.__class__.__name__})")

print("=" * 60)
print(f"✓ Success: {success}")
print(f"✗ Failed: {failed}")
print(f"\nRun: python -c \"import sqlite3; conn=sqlite3.connect('personal_agent/active_learning.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM gate_events'); print(f'Total events: {{c.fetchone()[0]}}'); conn.close()\"")
