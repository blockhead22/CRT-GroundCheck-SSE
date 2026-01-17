"""Generate 80 completely unique queries to reach 200+ examples."""
import requests
import time
import random

# Generate highly specific, unique queries
factual_queries = [
    f"What is my {attr}?" for attr in [
        "middle name", "last name", "nickname", "maiden name", "title",
        "employee ID", "badge number", "office location", "desk number",
        "start date", "hire date", "tenure", "seniority", "rank",
        "department", "division", "unit", "branch", "region",
        "direct report count", "team size", "budget", "quota", "target"
    ]
] + [
    f"Do I {action}?" for action in [
        "work remotely", "travel for work", "have a mentor", "mentor others",
        "attend conferences", "speak publicly", "write blogs", "contribute to open source",
        "volunteer", "donate", "invest", "save", "budget", "track expenses"
    ]
]

conversational_queries = [
    "Top of the morning to you!",
    "Pleasure to meet you!",
    "Delighted to be here!",
    "So nice chatting with you!",
    "I can't thank you enough!",
    "You've been absolutely wonderful!",
    "This has been so helpful!",
    "I'm really enjoying this conversation!",
    "Would you mind assisting me?",
    "Could I trouble you for help?",
    "I'd be grateful for your assistance!",
    "Might you be able to help?",
    "I was hoping you could help!",
    "Do you have a moment?",
    "Got time to chat?",
    "Free to talk?",
    "Available to discuss something?",
    "Can we have a quick word?",
    "Mind if I pick your brain?",
    "May I run something by you?",
]

explanatory_queries = [
    f"{starter} this?" for starter in [
        "Can you break down", "Would you explain", "Could you describe",
        "Mind walking me through", "Care to elaborate on", "Help me grasp"
    ]
] + [
    f"What's the {aspect}?" for aspect in [
        "reasoning behind", "logic in", "rationale for", "thinking on",
        "foundation of", "basis for", "principle behind", "theory of"
    ]
] + [
    f"How {question}?" for question in [
        "should I interpret this", "might this work", "would you approach this",
        "could this be improved", "does this function", "will this impact me",
        "can I leverage this", "do I apply this"
    ]
]

all_queries = factual_queries + conversational_queries + explanatory_queries
random.shuffle(all_queries)

# Take only 80 to avoid timeout issues  
queries = all_queries[:80]

API_BASE = "http://localhost:8123"
THREAD_ID = f"training_final_{int(time.time())}"

print(f"Generating {len(queries)} unique queries...")
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
            if i % 10 == 0:
                print(f"✓ {i}/{len(queries)} processed...")
        else:
            failed += 1
            print(f"✗ {i}/{len(queries)}: HTTP {resp.status_code}")
        time.sleep(0.02)
    except Exception as e:
        failed += 1
        if 'Timeout' in e.__class__.__name__:
            print(f"✗ {i}/{len(queries)}: Timeout")
        else:
            print(f"✗ {i}/{len(queries)}: {e.__class__.__name__}")

print("=" * 60)
print(f"✓ Success: {success}")
print(f"✗ Failed: {failed}")
print(f"\nTotal attempted: {len(queries)}")
