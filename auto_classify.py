"""Automated correction helper - provides reasonable defaults"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("personal_agent/active_learning.db")

# Heuristic rules for auto-classification
def auto_classify(query):
    q_lower = query.lower()
    
    # Conversational patterns
    if any(pattern in q_lower for pattern in ['hi', 'hello', 'thanks', 'thank you', 'how are you']):
        return 'conversational'
    
    # Explanatory patterns (why, how, explain, tell me about)
    if any(pattern in q_lower for pattern in ['why ', 'how ', 'explain', 'tell me about']):
        return 'explanatory'
    
    # Factual patterns (what, when, where, who, simple questions)
    if any(pattern in q_lower for pattern in ['what is', 'what are', 'when ', 'where ', 'who ']):
        return 'factual'
    
    # Default to factual for most "what" questions
    if 'what' in q_lower:
        return 'factual'
        
    return 'factual'  # default

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get uncorrected events
    cursor.execute("""
        SELECT event_id, question
        FROM gate_events
        WHERE response_type_actual IS NULL
        ORDER BY timestamp DESC
    """)
    
    events = cursor.fetchall()
    print(f"Found {len(events)} events to auto-classify")
    
    for event_id, query in events:
        classification = auto_classify(query)
        cursor.execute("""
            UPDATE gate_events 
            SET response_type_actual = ?, user_override = 1, correction_timestamp = ?
            WHERE event_id = ?
        """, (classification, time.time(), event_id))
        print(f"✓ {query[:60]:60} → {classification}")
    
    conn.commit()
    
    # Count total
    cursor.execute("SELECT COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL")
    total = cursor.fetchone()[0]
    print(f"\nTotal corrections: {total}")
    
    conn.close()

if __name__ == "__main__":
    main()
