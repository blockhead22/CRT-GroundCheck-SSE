"""
Fast Batch Correction - Apply smart defaults with review
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("personal_agent/active_learning.db")

def smart_classify(query):
    """Apply smart classification rules."""
    q = query.lower().strip()
    
    # Conversational - greetings
    if q in ['hi', 'hello', 'hey', 'hi there', 'good morning', 'good afternoon']:
        return 'conversational', 'greeting'
    
    # Conversational - thanks/acknowledgment
    if any(w in q for w in ['thanks', 'thank you', 'appreciate', "that's helpful", "that's really"]):
        return 'conversational', 'acknowledgment'
    
    # Conversational - help requests
    if any(phrase in q for phrase in ['can you help', 'could you help', 'could you assist', 'i need your help', 'i need help']):
        return 'conversational', 'help request'
    
    # Explanatory - why/how questions
    if q.startswith('why ') or q.startswith('how does') or q.startswith('how did'):
        return 'explanatory', 'why/how question'
    
    # Explanatory - explain/tell me about
    if 'explain' in q or 'tell me about' in q:
        return 'explanatory', 'explanation request'
    
    # Explanatory - give overview/summarize
    if any(w in q for w in ['summarize', 'overview', 'give me an overview']):
        return 'explanatory', 'summary request'
    
    # Factual - simple what/where/when questions
    if q.startswith(('what is', 'what are', 'where is', 'where do', 'when did', 'when do', 'who is', 'who are')):
        return 'factual', 'simple fact query'
    
    # Factual - what/where without verb (likely simple)
    if q.startswith('what ') and any(w in q for w in ['my ', 'your ', 'the ']):
        return 'factual', 'what query'
    
    # Default to factual for unclear cases
    return 'factual', 'default'

def batch_correct():
    """Apply smart corrections with confirmation."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get uncorrected events
    cursor.execute("""
        SELECT event_id, question
        FROM gate_events
        WHERE response_type_actual IS NULL
        ORDER BY timestamp DESC
        LIMIT 60
    """)
    
    events = cursor.fetchall()
    print(f"Found {len(events)} events to classify\n")
    
    corrections = []
    
    for event_id, question in events:
        classification, reason = smart_classify(question)
        corrections.append((event_id, question, classification, reason))
    
    # Show summary
    print("SMART CLASSIFICATION SUMMARY")
    print("="*80)
    print(f"{'Query':<45} {'Type':<15} {'Reason':<20}")
    print("-"*80)
    
    by_type = {'factual': 0, 'explanatory': 0, 'conversational': 0}
    
    for _, q, ctype, reason in corrections:
        print(f"{q[:43]:<45} {ctype:<15} {reason:<20}")
        by_type[ctype] += 1
    
    print("-"*80)
    print(f"Factual: {by_type['factual']}, Explanatory: {by_type['explanatory']}, Conversational: {by_type['conversational']}")
    print()
    
    confirm = input("Apply these corrections? (y/n): ").strip().lower()
    
    if confirm == 'y':
        timestamp = time.time()
        for event_id, _, ctype, _ in corrections:
            cursor.execute("""
                UPDATE gate_events
                SET response_type_actual = ?,
                    user_override = 1,
                    correction_timestamp = ?
                WHERE event_id = ?
            """, (ctype, timestamp, event_id))
        
        conn.commit()
        print(f"\n✓ Applied {len(corrections)} corrections")
        
        # Check total
        cursor.execute("SELECT COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL")
        total = cursor.fetchone()[0]
        print(f"Total corrections: {total}")
        
        if total >= 50:
            print("\n✨ Ready to retrain! Run: python train_classifier.py")
    else:
        print("\n✗ Cancelled")
    
    conn.close()

if __name__ == "__main__":
    batch_correct()
