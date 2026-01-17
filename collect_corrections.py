"""
Interactive correction collection tool for active learning.

Reviews gate events and lets you correct misclassifications.
Triggers auto-retrain at 50 corrections.
"""

import requests
import json
from typing import List, Dict, Optional

API_BASE = "http://localhost:8123"

def get_learning_stats() -> Dict:
    """Get current learning statistics."""
    response = requests.get(f"{API_BASE}/api/learning/stats", timeout=10)
    if response.status_code == 200:
        return response.json()
    return {}

def get_events_needing_correction(limit: int = 50) -> List[Dict]:
    """Get gate events that need user correction."""
    response = requests.get(
        f"{API_BASE}/api/learning/events",
        params={"limit": limit},
        timeout=10
    )
    if response.status_code == 200:
        return response.json()
    return []

def submit_correction(event_id: int, corrected_type: str) -> bool:
    """Submit a correction for a gate event."""
    response = requests.post(
        f"{API_BASE}/api/learning/correct/{event_id}",
        json={"corrected_type": corrected_type},
        timeout=10
    )
    return response.status_code == 200

def classify_query_interactive(query: str, predicted: str, gates_passed: bool) -> Optional[str]:
    """Interactive classification UI."""
    print(f"\n{'='*80}")
    print(f"QUERY: {query}")
    print(f"{'='*80}")
    print(f"Predicted type: {predicted}")
    print(f"Gates passed: {'✓' if gates_passed else '✗'}")
    print()
    print("What type should this be?")
    print("  1. factual     - Direct fact queries (What is X?)")
    print("  2. explanatory - Synthesis/reasoning (When/Why/How?)")
    print("  3. conversational - Chat/greetings (Hi, Thanks)")
    print("  s. skip")
    print("  q. quit")
    print()
    
    choice = input("Choice [1/2/3/s/q]: ").strip().lower()
    
    if choice == 'q':
        return None
    elif choice == 's':
        return "skip"
    elif choice == '1':
        return "factual"
    elif choice == '2':
        return "explanatory"
    elif choice == '3':
        return "conversational"
    else:
        print("Invalid choice, skipping...")
        return "skip"

def review_gate_events():
    """Main correction collection loop."""
    print("="*80)
    print("ACTIVE LEARNING: Correction Collection")
    print("="*80)
    
    # Get current stats
    stats = get_learning_stats()
    print(f"\nCurrent stats:")
    print(f"  Total events: {stats.get('total_events', 0)}")
    print(f"  Corrections: {stats.get('num_corrections', 0)}/50 (need 50 to auto-retrain)")
    print(f"  Model loaded: {stats.get('model_loaded', False)}")
    
    if stats.get('num_corrections', 0) >= 50:
        print(f"\n✨ AUTO-RETRAIN THRESHOLD REACHED!")
        print(f"   The system will retrain automatically on next correction.")
    
    # Get recent events
    print(f"\nFetching recent gate events...")
    events = get_events_needing_correction(limit=100)
    
    if not events:
        print("No correction events found. Try running some queries first.")
        return
    
    print(f"Found {len(events)} events to review.\n")
    
    corrected = 0
    skipped = 0
    
    for i, event in enumerate(events):
        query = event.get('question', '')
        predicted = event.get('response_type_predicted', 'unknown')
        gates_passed = event.get('gates_passed', False)
        event_id = event.get('event_id', 0)
        
        actual_type = classify_query_interactive(query, predicted, gates_passed)
        
        if actual_type is None:
            print("\nQuitting...")
            break
        elif actual_type == "skip":
            skipped += 1
            continue
        elif actual_type == predicted:
            print(f"✓ Prediction was correct, marking as confirmed...")
        else:
            print(f"✓ Correcting: {predicted} → {actual_type}")
        
        # Submit correction
        if submit_correction(event_id, actual_type):
            corrected += 1
            print(f"   Saved! ({corrected} corrections submitted)")
            
            # Check if we hit threshold
            current_stats = get_learning_stats()
            current_corrections = current_stats.get('num_corrections', 0)
            
            if current_corrections >= 50:
                print(f"\n🎉 THRESHOLD REACHED: {current_corrections} corrections!")
                print(f"   Auto-retrain will trigger on next event.")
                
                choice = input("\nContinue collecting more? [y/n]: ").strip().lower()
                if choice != 'y':
                    break
        else:
            print(f"   ✗ Failed to save correction")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Corrections submitted: {corrected}")
    print(f"Skipped: {skipped}")
    
    # Final stats
    final_stats = get_learning_stats()
    print(f"\nFinal stats:")
    print(f"  Total corrections: {final_stats.get('num_corrections', 0)}/50")
    print(f"  Model version: {final_stats.get('model_version', 'none')}")
    
    if final_stats.get('num_corrections', 0) >= 50:
        print(f"\n✨ Ready for auto-retrain!")
        print(f"   Next gate event will trigger retraining.")
        print(f"   Run comprehensive_validation.py to trigger it.")

def main():
    print("\nStarting correction collection...")
    print(f"API: {API_BASE}\n")
    
    try:
        review_gate_events()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
