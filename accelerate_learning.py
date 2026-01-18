"""
Active Learning Accelerator: Automated Data Collection System

Generates diverse queries, collects responses, and enables rapid correction.
Goal: Reach 300-500 corrections for ML to beat heuristics.
"""
import requests
import time
import random
import sqlite3
from typing import List, Tuple

API_BASE = "http://localhost:8123"

# High-quality diverse query templates
FACTUAL_TEMPLATES = [
    # Personal info
    "What is my {attr}?",
    "Do I have a {item}?",
    "Where is my {place}?",
    "When did I {action}?",
    "How many {items} do I have?",
    "Which {item} do I prefer?",
    "Who is my {person}?",
    
    # Work/Career
    "What {aspect} do I work on?",
    "Am I {status} at work?",
    "Do I {activity} at my job?",
]

CONVERSATIONAL_TEMPLATES = [
    # Greetings
    "{greeting}!",
    "{greeting}, how are you?",
    "{time_greeting}!",
    
    # Thanks
    "{thanks}!",
    "{thanks} for {service}!",
    "I {appreciation} {action}!",
    
    # Help requests  
    "Can you {help_verb} me?",
    "I need {service}",
    "Could you {help_verb}?",
    
    # Reactions
    "That's {positive_adj}!",
    "{positive_reaction}!",
]

EXPLANATORY_TEMPLATES = [
    # Why/How questions
    "Why {question}?",
    "How {question}?",
    "How come {question}?",
    "What led to {situation}?",
    
    # Explanation requests
    "Explain {topic}",
    "Describe {topic}",
    "Walk me through {topic}",
    "Break down {topic}",
    "Summarize {topic}",
    "Give me an overview of {topic}",
    
    # Context requests
    "What's the story behind {topic}?",
    "How did {situation} happen?",
    "What caused {situation}?",
]

# Fill-in values
FACTUAL_FILLS = {
    'attr': ['email', 'phone number', 'address', 'birthday', 'age', 'height', 'weight'],
    'item': ['car', 'house', 'pet', 'degree', 'certification', 'license'],
    'place': ['office', 'desk', 'home', 'apartment', 'car'],
    'action': ['graduate', 'start working', 'move here', 'get married', 'get promoted'],
    'items': ['cars', 'pets', 'siblings', 'degrees', 'languages', 'skills'],
    'aspect': ['projects', 'technologies', 'tools', 'frameworks', 'languages'],
    'status': ['happy', 'satisfied', 'stressed', 'busy', 'productive'],
    'activity': ['code', 'design', 'manage', 'teach', 'mentor'],
    'person': ['manager', 'mentor', 'partner', 'best friend', 'doctor'],
}

CONVERSATIONAL_FILLS = {
    'greeting': ['Hi', 'Hello', 'Hey', 'Howdy', 'Greetings', 'Yo', 'Sup'],
    'time_greeting': ['Good morning', 'Good afternoon', 'Good evening'],
    'thanks': ['Thanks', 'Thank you', 'Many thanks', 'Much appreciated', 'Cheers'],
    'service': ['the help', 'your time', 'the information', 'your assistance', 'everything'],
    'appreciation': ['appreciate', 'value', 'am grateful for'],
    'action': ['this', 'that', 'your help', 'your support'],
    'help_verb': ['help', 'assist', 'support', 'guide'],
    'positive_adj': ['amazing', 'wonderful', 'fantastic', 'incredible', 'excellent'],
    'positive_reaction': ['Wow', 'Awesome', 'Great', 'Perfect', 'Nice'],
}

EXPLANATORY_FILLS = {
    'question': [
        'did I choose this career', 'do I like this', 'am I interested in this',
        'does this work', 'can I improve', 'should I approach this'
    ],
    'situation': [
        'this decision', 'this change', 'this outcome', 'this situation'
    ],
    'topic': [
        'my background', 'my experience', 'my skills', 'my interests',
        'my career path', 'my education', 'my goals', 'my motivation',
        'this concept', 'your approach', 'your reasoning', 'your memory system'
    ],
}

def generate_queries(n: int = 100) -> List[Tuple[str, str]]:
    """Generate n diverse queries with expected labels."""
    queries = []
    
    # Factual queries
    for template in FACTUAL_TEMPLATES * 3:
        if len(queries) >= n // 3:
            break
        filled = template
        for key, values in FACTUAL_FILLS.items():
            if '{' + key + '}' in filled:
                filled = filled.replace('{' + key + '}', random.choice(values))
        queries.append((filled, 'factual'))
    
    # Conversational queries
    for template in CONVERSATIONAL_TEMPLATES * 3:
        if len(queries) >= 2 * n // 3:
            break
        filled = template
        for key, values in CONVERSATIONAL_FILLS.items():
            if '{' + key + '}' in filled:
                filled = filled.replace('{' + key + '}', random.choice(values))
        queries.append((filled, 'conversational'))
    
    # Explanatory queries
    for template in EXPLANATORY_TEMPLATES * 3:
        if len(queries) >= n:
            break
        filled = template
        for key, values in EXPLANATORY_FILLS.items():
            if '{' + key + '}' in filled:
                filled = filled.replace('{' + key + '}', random.choice(values))
        queries.append((filled, 'explanatory'))
    
    random.shuffle(queries)
    return queries[:n]

def send_queries(queries: List[Tuple[str, str]], thread_prefix: str = "data_collection"):
    """Send queries to CRT API and collect responses."""
    thread_id = f"{thread_prefix}_{int(time.time())}"
    
    print(f"Sending {len(queries)} queries to CRT...")
    print("=" * 70)
    
    success = 0
    failed = 0
    
    for i, (query, expected_label) in enumerate(queries, 1):
        try:
            resp = requests.post(
                f"{API_BASE}/api/chat/send",
                json={"thread_id": thread_id, "message": query},
                timeout=15
            )
            if resp.ok:
                success += 1
                if i % 20 == 0:
                    print(f"  ✓ {i}/{len(queries)} sent...")
            else:
                failed += 1
                if failed < 5:
                    print(f"  ✗ Query {i} failed: HTTP {resp.status_code}")
            
            time.sleep(0.03)  # Rate limiting
            
        except Exception as e:
            failed += 1
            if failed < 5:
                print(f"  ✗ Query {i} failed: {e.__class__.__name__}")
    
    print("=" * 70)
    print(f"✓ Success: {success}/{len(queries)}")
    print(f"✗ Failed: {failed}/{len(queries)}")
    
    return success, failed

def auto_label_new_events():
    """Automatically label uncorrected events with smart rules."""
    # Wait for API to finish
    print("Waiting for database to be available...")
    max_retries = 10
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect('personal_agent/active_learning.db', timeout=10.0)
            c = conn.cursor()
            c.execute('SELECT event_id, question FROM gate_events WHERE response_type_actual IS NULL')
            events = c.fetchall()
            break
        except sqlite3.OperationalError:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print("Database still locked after retries. Try again later.")
                return 0
    
    if not events:
        print("No new events to label!")
        conn.close()
        return 0
    
    print(f"\nAuto-labeling {len(events)} new events...")
    
    # Enhanced classification rules
    rules = {
        'conversational': [
            '^hi$', '^hi ', 'hello', 'hey', 'howdy', '^yo$', '^sup$', 'greetings', 'salutations',
            'good morning', 'good afternoon', 'good evening',
            'thanks', 'thank you', 'appreciate', 'grateful', 'cheers',
            'amazing', 'wonderful', 'fantastic', 'incredible', 'excellent', 'awesome', 'great', 'perfect', 'nice',
            'help me', 'can you help', 'could you help', 'assist', 'guide', 'support me',
            'can i ask', 'may i ask', 'i have a question', 'i need',
            'nice to', 'glad to', 'happy to', 'excited to',
            'how are', 'hows', 'whats up', 'whats new', 'how have you',
            'wow$', 'wow ', "that's"
        ],
        'explanatory': [
            '^why ', 'why do', 'why did', 'why am', 'why is', 'how come',
            '^how ', 'how do', 'how did', 'how can', 'how does', 'how should',
            'explain', 'describe', 'summarize', 'overview', 'walk me through', 'break down',
            'what led', 'what caused', 'whats the story', 'how did this',
            'clarify', 'elaborate', 'expand on', 'give more details',
            'whats the background', 'whats the bigger', 'what motivates', 'what drives'
        ],
        'factual': [
            '^what is my', '^where ', '^when ', '^who ', '^which ',
            'do i have', 'am i ', 'how many', 'how old',
            'my name', 'my email', 'my phone', 'my address', 'my birthday',
            'my job', 'my role', 'my team', 'my manager', 'my office',
            'what school', 'what university', 'what degree', 'what major',
            'what skills', 'what tools', 'what projects', 'what languages',
            'where do i', 'when did i', 'who is my'
        ]
    }
    
    ts = time.time()
    applied = 0
    
    for event_id, question in events:
        category = 'factual'  # default
        q_lower = question.lower()
        
        for cat, patterns in rules.items():
            for pattern in patterns:
                if pattern.endswith('$'):
                    if q_lower == pattern[:-1]:
                        category = cat
                        break
                elif pattern.startswith('^'):
                    if q_lower.startswith(pattern[1:]):
                        category = cat
                        break
                else:
                    if pattern in q_lower:
                        category = cat
                        break
            if category != 'factual':
                break
        
        c.execute(
            'UPDATE gate_events SET response_type_actual=?, user_override=1, correction_timestamp=? WHERE event_id=?',
            (category, ts, event_id)
        )
        applied += 1
    
    conn.commit()
    conn.close()
    
    print(f"✓ Labeled {applied} events")
    return applied

def check_progress():
    """Check progress toward ML readiness."""
    conn = sqlite3.connect('personal_agent/active_learning.db')
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM gate_events')
    total = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL')
    corrected = c.fetchone()[0]
    
    c.execute('SELECT response_type_actual, COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL GROUP BY response_type_actual')
    dist = c.fetchall()
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("📊 ACTIVE LEARNING PROGRESS")
    print("=" * 70)
    print(f"Total events: {total}")
    print(f"Corrected: {corrected}")
    print(f"Uncorrected: {total - corrected}")
    print(f"\nDistribution:")
    for cat, count in dist:
        print(f"  {cat}: {count} ({count/corrected*100:.1f}%)")
    
    print(f"\n🎯 Progress to ML readiness:")
    print(f"  Current: {corrected}/500 corrections")
    progress_bar = '█' * (corrected // 10) + '░' * (50 - corrected // 10)
    print(f"  [{progress_bar}] {corrected/500*100:.1f}%")
    
    if corrected >= 300:
        print(f"\n🚀 READY! You have {corrected} corrections - ML should beat heuristics now!")
    elif corrected >= 200:
        print(f"\n⚡ ALMOST THERE! {300 - corrected} more corrections to ML readiness")
    else:
        print(f"\n📈 Keep going! {300 - corrected} more corrections needed")
    
    print("=" * 70)

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 ACTIVE LEARNING DATA COLLECTION ACCELERATOR")
    print("=" * 70)
    
    # Generate diverse queries
    print("\n1. Generating 150 diverse queries...")
    queries = generate_queries(150)
    print(f"✓ Generated {len(queries)} queries")
    
    # Send to API
    print("\n2. Sending queries to CRT...")
    success, failed = send_queries(queries)
    
    # Wait for API to finish processing
    print("\n3. Waiting for API to process...")
    time.sleep(5)
    
    # Auto-label
    print("\n4. Auto-labeling new events...")
    labeled = auto_label_new_events()
    
    # Check progress
    check_progress()
    
    print("\n✅ Data collection complete!")
    print("   Run again to collect more data")
    print("   Run train_classifier.py when ready to retrain")
