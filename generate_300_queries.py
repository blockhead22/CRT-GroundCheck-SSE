"""Generate 100 more diverse queries to definitely reach 200+ training examples."""
import requests
import time

queries = [
    # More factual queries (40)
    "What year was I born?",
    "What month is my birthday?",
    "What day is my birthday?",
    "What school did I attend?",
    "What university did I go to?",
    "What did I study?",
    "What field am I in?",
    "What industry do I work in?",
    "What position do I hold?",
    "What level am I at?",
    "What skills do I have?",
    "What tools do I use?",
    "What programming languages do I know?",
    "What frameworks am I familiar with?",
    "What projects have I worked on?",
    "What accomplishments do I have?",
    "What awards have I won?",
    "What recognition have I received?",
    "What goals do I have?",
    "What ambitions do I have?",
    "What dreams do I have?",
    "What fears do I have?",
    "What strengths do I have?",
    "What weaknesses do I have?",
    "What values do I hold?",
    "What beliefs do I have?",
    "What opinions do I have?",
    "What preferences do I have?",
    "What dislikes do I have?",
    "What allergies do I have?",
    "What medications do I take?",
    "What health conditions do I have?",
    "What dietary restrictions do I have?",
    "What exercise do I do?",
    "What music do I like?",
    "What genres do I prefer?",
    "What artists do I follow?",
    "What shows do I watch?",
    "What games do I play?",
    "What apps do I use?",
    
    # More conversational queries (30)
    "Greetings!",
    "Salutations!",
    "Howdy!",
    "Yo!",
    "Sup!",
    "How are things?",
    "How have you been?",
    "What's new?",
    "What's happening?",
    "How's your day?",
    "Glad to be here",
    "Happy to chat",
    "Excited to talk",
    "Looking forward to this",
    "This is wonderful",
    "That's fantastic",
    "That's incredible",
    "I'm impressed",
    "Well done",
    "Excellent work",
    "Much appreciated",
    "Many thanks",
    "Thanks a lot",
    "Thanks a bunch",
    "Cheers",
    "I owe you one",
    "You're a lifesaver",
    "You're the best",
    "Can you give me a hand?",
    "Mind helping out?",
    
    # More explanatory queries (30)
    "How come I chose this path?",
    "What led me to this decision?",
    "Why did I make that choice?",
    "How did that happen?",
    "What caused this?",
    "How does this connect?",
    "What's the relationship between these?",
    "How are these related?",
    "What links these together?",
    "How do these fit together?",
    "Explain the connection",
    "Describe the pattern",
    "What's the story here?",
    "How did this develop?",
    "What's the progression?",
    "How did this evolve?",
    "What's the timeline?",
    "Walk through the steps",
    "Break it down for me",
    "Simplify this",
    "Make it clearer",
    "Help me understand",
    "Clarify this point",
    "Elaborate on that",
    "Expand on this idea",
    "Give more details",
    "Provide more context",
    "What's the background?",
    "What's the bigger picture?",
    "How does everything connect?",
]

API_BASE = "http://localhost:8123"
THREAD_ID = "training_data_generation_300"

print(f"Generating {len(queries)} more queries...")
print("=" * 60)

success = 0
failed = 0

for i, query in enumerate(queries, 1):
    try:
        resp = requests.post(
            f"{API_BASE}/api/chat/send",
            json={"thread_id": THREAD_ID, "message": query},
            timeout=20
        )
        if resp.ok:
            success += 1
            print(f"✓ {i}/{len(queries)}: {query[:50]}")
        else:
            failed += 1
            print(f"✗ {i}/{len(queries)}: {query[:50]} (HTTP {resp.status_code})")
        time.sleep(0.03)
    except Exception as e:
        failed += 1
        print(f"✗ {i}/{len(queries)}: {query[:50]} ({e.__class__.__name__})")

print("=" * 60)
print(f"✓ Success: {success}")
print(f"✗ Failed: {failed}")
