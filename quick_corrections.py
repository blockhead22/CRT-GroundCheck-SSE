"""
Quick correction tool - reads directly from SQLite, minimal API calls.
"""

import sqlite3
import requests
import time
from pathlib import Path

DB_PATH = Path("personal_agent/active_learning.db")
API_BASE = "http://localhost:8123"

def get_uncorrected_events(limit=20):
    """Get events needing correction directly from DB."""
    if not DB_PATH.exists():
        print("No active_learning.db found")
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT event_id, question, response_type_predicted, gates_passed, 
               intent_align, memory_align, grounding_score
        FROM gate_events
        WHERE response_type_actual IS NULL
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    events = []
    for row in cursor.fetchall():
        events.append({
            'event_id': row[0],
            'query': row[1],
            'predicted': row[2],
            'passed': bool(row[3]),
            'intent': row[4],
            'memory': row[5],
            'grounding': row[6]
        })
    
    conn.close()
    return events

def count_corrections():
    """Count how many corrections we have."""
    if not DB_PATH.exists():
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def submit_correction_db(event_id, corrected_type):
    """Submit correction directly to DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE gate_events 
        SET response_type_actual = ?, user_override = 1, correction_timestamp = ?
        WHERE event_id = ?
    """, (corrected_type, time.time(), event_id))
    conn.commit()
    conn.close()

def main():
    print("="*80)
    print("QUICK CORRECTION TOOL")
    print("="*80)
    
    corrections = count_corrections()
    print(f"\nCurrent corrections: {corrections}/50")
    print(f"Need {50 - corrections} more to trigger auto-retrain\n")
    
    events = get_uncorrected_events(20)
    
    if not events:
        print("No uncorrected events found!")
        return
    
    print(f"Found {len(events)} events needing correction\n")
    
    corrected_count = 0
    
    for i, event in enumerate(events, 1):
        print(f"\n{'='*80}")
        print(f"Event {i}/{len(events)} (ID: {event['event_id']})")
        print(f"{'='*80}")
        print(f"Query: {event['query']}")
        print(f"Predicted: {event['predicted']}")
        print(f"Gates: {'PASS ✓' if event['passed'] else 'FAIL ✗'}")
        print(f"Scores: intent={event['intent']:.2f}, memory={event['memory']:.2f}, grounding={event['grounding']:.2f}")
        print()
        print("Correct type:")
        print("  1 = factual")
        print("  2 = explanatory") 
        print("  3 = conversational")
        print("  s = skip")
        print("  q = quit")
        
        choice = input("\nYour choice: ").strip().lower()
        
        if choice == 'q':
            break
        elif choice == 's':
            continue
        elif choice in ['1', '2', '3']:
            type_map = {'1': 'factual', '2': 'explanatory', '3': 'conversational'}
            corrected_type = type_map[choice]
            
            submit_correction_db(event['event_id'], corrected_type)
            corrected_count += 1
            print(f"✓ Saved: {corrected_type}")
    
    total = corrections + corrected_count
    print(f"\n{'='*80}")
    print(f"Session complete!")
    print(f"Corrected this session: {corrected_count}")
    print(f"Total corrections: {total}/50")
    
    if total >= 50:
        print("\n🎉 50 corrections reached! Triggering retrain...")
        try:
            response = requests.post(f"{API_BASE}/api/learning/retrain", timeout=30)
            if response.status_code == 200:
                print("✓ Retrain triggered successfully!")
            else:
                print(f"✗ Retrain failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Error triggering retrain: {e}")
    else:
        print(f"Need {50 - total} more corrections to trigger retrain")

if __name__ == "__main__":
    main()
