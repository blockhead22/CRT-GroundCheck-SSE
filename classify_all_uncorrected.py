"""Wait for API processing to complete, then classify all uncorrected events."""
import sqlite3
import time

print("Waiting for API to finish processing events...")
print("=" * 60)

last_count = 0
stable_count = 0

while True:
    try:
        conn = sqlite3.connect('personal_agent/active_learning.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM gate_events')
        current_count = c.fetchone()[0]
        conn.close()
        
        if current_count == last_count:
            stable_count += 1
            if stable_count >= 3:
                print(f"\n✓ Stable at {current_count} events")
                break
        else:
            stable_count = 0
            print(f"Events: {current_count} (+{current_count - last_count})")
            last_count = current_count
        
        time.sleep(2)
    except sqlite3.OperationalError:
        print(".", end="", flush=True)
        time.sleep(1)

print("\nClassifying uncorrected events...")
print("=" * 60)

conn = sqlite3.connect('personal_agent/active_learning.db')
c = conn.cursor()

c.execute('SELECT event_id, question FROM gate_events WHERE response_type_actual IS NULL')
events = c.fetchall()

print(f"Found {len(events)} uncorrected events")

if len(events) == 0:
    print("No events to classify!")
    conn.close()
    exit(0)

# Enhanced classification rules
rules = {
    'conversational': [
        # Greetings
        'hi$', '^hi ', 'hello', 'hey', 'howdy', 'yo$', 'sup$', 'greetings', 'salutations',
        # Time-based greetings  
        'good morning', 'good afternoon', 'good evening',
        # Thanks
        'thanks', 'thank you', 'appreciate', 'grateful', 'cheers', 'owe you',
        # Positive reactions
        'amazing', 'wonderful', 'fantastic', 'incredible', 'impressed', 'well done', 'excellent',
        # Help requests
        'help me', 'can you help', 'could you help', 'please help', 'give me a hand', 'mind helping',
        'can i ask', 'may i ask', 'i have a question', 'i need',
        # Social
        'nice to', 'great to', 'glad to', 'happy to', 'excited to', 'looking forward',
        'how are', 'hows', 'whats up', 'whats new', 'whats happening', 'how have you',
        'youre the best', 'lifesaver', 'you are'
    ],
    'explanatory': [
        # Why/How questions
        '^why ', 'why do', 'why did', 'why am', 'why is', 'why are', 'how come',
        '^how ', 'how do', 'how did', 'how can', 'how does', 'how is', 'how are',
        # Explanation requests
        'explain', 'describe', 'summarize', 'overview', 'clarify', 'elaborate', 'expand on',
        # Context requests
        'what led', 'what caused', 'walk through', 'break down', 'break it down',
        'simplify', 'make it clearer', 'help me understand',
        'give more details', 'provide more context',
        # Pattern/relationship questions  
        'whats the relationship', 'how are these', 'what links', 'how do these',
        'whats the story', 'how did this', 'whats the progression', 'whats the timeline',
        'whats the background', 'whats the bigger', 'how does everything',
        # Motivation
        'what drives', 'what motivates'
    ],
    'factual': [
        # Question words
        '^what is my', '^where ', '^when ', '^who ', '^which ',
        # Personal facts
        'my name', 'my email', 'my phone', 'my address', 'my birthday', 'my age',
        'my hometown', 'my job', 'my role', 'my team', 'my degree', 'my major',
        # Work/Career
        'what school', 'what university', 'what did i study', 'what field',
        'what industry', 'what position', 'what level', 'what company',
        # Skills/Experience
        'what skills', 'what tools', 'what programming', 'what frameworks',
        'what projects', 'what accomplishments', 'what awards', 'what recognition',
        # Interests/Preferences
        'my favorite', 'what sports', 'what instruments', 'what pets', 'my hobbies',
        'what car', 'what city', 'what neighborhood', 'what music', 'what genres',
        'what artists', 'what shows', 'what games', 'what apps',
        # Personal attributes
        'what goals', 'what ambitions', 'what dreams', 'what fears',
        'what strengths', 'what weaknesses', 'what values', 'what beliefs',
        'what opinions', 'what preferences', 'what dislikes',
        # Health
        'what allergies', 'what medications', 'what health', 'dietary restrictions',
        'what exercise',
        # Existence questions
        'do i have', 'am i ', 'are you', 'how many', 'how old',
        # Temporal
        'where do i', 'where did i', 'when did i', 'what year', 'what month', 'what day',
        # Collections
        'what languages', 'what are my', 'certifications', 'relationship status'
    ]
}

ts = time.time()
applied = 0

for event_id, question in events:
    # Find matching category
    category = 'factual'  # default
    for cat, patterns in rules.items():
        for pattern in patterns:
            q_lower = question.lower()
            # Check pattern match
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
    print(f"  ✓ {question[:60]:60} -> {category}")

conn.commit()

print("=" * 60)
print(f"Applied {applied} corrections")

c.execute('SELECT COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL')
total = c.fetchone()[0]
print(f"Total corrected: {total}")

c.execute('SELECT response_type_actual, COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL GROUP BY response_type_actual')
dist = c.fetchall()

print("\nDistribution:")
for category, count in dist:
    print(f"  {category}: {count}")

conn.close()

print(f"\nReady to retrain! ({total} examples)")
