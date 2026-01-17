"""
Manual Correction Tool - Interactive Classification
Collect high-quality training data for response type classifier
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path("personal_agent/active_learning.db")

def get_uncorrected_events(limit=50):
    """Get events needing manual correction."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
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
            'question': row[1],
            'predicted': row[2],
            'gates_passed': bool(row[3]),
            'intent': row[4],
            'memory': row[5],
            'grounding': row[6],
        })
    
    conn.close()
    return events

def submit_correction(event_id, corrected_type):
    """Submit manual correction to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE gate_events 
        SET response_type_actual = ?, 
            user_override = 1,
            correction_timestamp = ?
        WHERE event_id = ?
    """, (corrected_type, time.time(), event_id))
    
    conn.commit()
    conn.close()

def count_corrections():
    """Count total corrections."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM gate_events WHERE response_type_actual IS NOT NULL")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def main():
    print("="*80)
    print("MANUAL CORRECTION TOOL")
    print("="*80)
    print("\nClassify each query as:")
    print("  1 = factual      (direct fact: 'What is X?', 'Where is Y?')")
    print("  2 = explanatory  (why/how: 'Why did X?', 'How does Y work?')")
    print("  3 = conversational (greetings, thanks, help requests)")
    print("  s = skip this one")
    print("  q = quit\n")
    
    total = count_corrections()
    print(f"Current corrections: {total}/50")
    
    if total >= 50:
        print("\n✓ Already have 50+ corrections!")
        print("Ready to retrain. Run: python train_classifier.py")
        return
    
    events = get_uncorrected_events(limit=60)
    
    if not events:
        print("\nNo events found needing correction.")
        print("Generate some with: python generate_manual_corrections.py")
        return
    
    print(f"\nFound {len(events)} events to classify\n")
    
    corrections_made = 0
    
    for i, event in enumerate(events, 1):
        print(f"\n{'='*80}")
        print(f"Event {i}/{len(events)} (ID: {event['event_id'][:8]}...)")
        print(f"{'='*80}")
        print(f"\nQuery: {event['question']}")
        print(f"ML Predicted: {event['predicted']}")
        print(f"Gates: {'✓ PASS' if event['gates_passed'] else '✗ FAIL'}")
        print(f"Scores: intent={event['intent']:.2f}, memory={event['memory']:.2f}, grounding={event['grounding']:.2f}")
        
        # Suggest classification
        q = event['question'].lower()
        if any(w in q for w in ['hi', 'hello', 'hey', 'thanks', 'thank you', 'help me', 'appreciate']):
            suggestion = "3 (conversational)"
        elif any(w in q for w in ['why', 'how does', 'how did', 'explain', 'tell me about']):
            suggestion = "2 (explanatory)"
        elif any(w in q for w in ['what is', 'what are', 'when', 'where', 'who']):
            suggestion = "1 (factual)"
        else:
            suggestion = "?"
        
        print(f"Suggestion: {suggestion}")
        
        while True:
            choice = input("\nYour classification (1/2/3/s/q): ").strip().lower()
            
            if choice == 'q':
                print(f"\n✓ Saved {corrections_made} corrections")
                total_now = count_corrections()
                print(f"Total corrections: {total_now}/50")
                if total_now >= 50:
                    print("\n✨ Ready to retrain! Run: python train_classifier.py")
                return
            
            if choice == 's':
                print("⊘ Skipped")
                break
            
            if choice == '1':
                submit_correction(event['event_id'], 'factual')
                print("✓ Saved: factual")
                corrections_made += 1
                break
            elif choice == '2':
                submit_correction(event['event_id'], 'explanatory')
                print("✓ Saved: explanatory")
                corrections_made += 1
                break
            elif choice == '3':
                submit_correction(event['event_id'], 'conversational')
                print("✓ Saved: conversational")
                corrections_made += 1
                break
            else:
                print("Invalid choice. Use 1, 2, 3, s, or q")
        
        # Check if we've hit the goal
        total_now = count_corrections()
        if total_now >= 50:
            print(f"\n{'='*80}")
            print(f"✨ GOAL REACHED: {total_now} corrections!")
            print(f"{'='*80}")
            print("\nReady to retrain. Run: python train_classifier.py")
            return
    
    print(f"\n✓ Completed! Saved {corrections_made} corrections")
    total_now = count_corrections()
    print(f"Total corrections: {total_now}/50")
    
    if total_now >= 50:
        print("\n✨ Ready to retrain! Run: python train_classifier.py")
    else:
        print(f"\nNeed {50 - total_now} more corrections")
        print("Run this script again or generate more events")

if __name__ == "__main__":
    main()
