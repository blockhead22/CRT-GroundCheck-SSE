#!/usr/bin/env python3
"""
Phase 1, Step 1: Extract Real Belief Updates from Database

This script extracts belief updates from your existing interaction logs
and contradiction ledger to create the foundation for BeliefRevisionBench.

Run this first to understand what data you have.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths
DB_ACTIVE_LEARNING = Path(__file__).parent.parent.parent / "personal_agent/active_learning.db"
DB_LEDGER = Path(__file__).parent.parent.parent / "personal_agent/crt_ledger.db"
OUTPUT_DIR = Path(__file__).parent.parent / "data"

def extract_interactions_with_slots():
    """Extract interactions that have slot information."""
    print("=" * 60)
    print("STEP 1: Extracting interactions with slot data")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_ACTIVE_LEARNING)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get interactions with slot data
    query = """
    SELECT 
        id,
        query,
        slots_inferred,
        facts_injected,
        response,
        confidence,
        timestamp,
        thread_id
    FROM interaction_logs
    WHERE slots_inferred IS NOT NULL 
        AND slots_inferred != ''
        AND slots_inferred != '{}'
    ORDER BY timestamp
    """
    
    cursor.execute(query)
    interactions = cursor.fetchall()
    
    print(f"\n✓ Found {len(interactions)} interactions with slot data")
    
    # Save raw interactions
    output_file = OUTPUT_DIR / "raw_interactions.json"
    with open(output_file, 'w') as f:
        json.dump([dict(row) for row in interactions], f, indent=2)
    
    print(f"✓ Saved to: {output_file}")
    
    conn.close()
    return interactions

def extract_contradictions():
    """Extract tracked contradictions from ledger."""
    print("\n" + "=" * 60)
    print("STEP 2: Extracting contradictions from ledger")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_LEDGER)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all contradictions
    query = """
    SELECT 
        ledger_id,
        timestamp,
        status,
        contradiction_type,
        memory_id_a,
        memory_id_b,
        drift_mean,
        drift_max
    FROM contradiction_ledger
    ORDER BY timestamp
    """
    
    try:
        cursor.execute(query)
        contradictions = cursor.fetchall()
        
        print(f"\n✓ Found {len(contradictions)} contradictions tracked")
        
        # Count by status
        status_counts = defaultdict(int)
        for c in contradictions:
            status_counts[c['status']] += 1
        
        print("\nBreakdown by status:")
        for status, count in status_counts.items():
            print(f"  - {status}: {count}")
        
        # Save contradictions
        output_file = OUTPUT_DIR / "raw_contradictions.json"
        with open(output_file, 'w') as f:
            json.dump([dict(row) for row in contradictions], f, indent=2)
        
        print(f"\n✓ Saved to: {output_file}")
        
    except sqlite3.OperationalError as e:
        print(f"\n⚠ Error reading contradictions: {e}")
        contradictions = []
    
    conn.close()
    return contradictions

def extract_corrections():
    """Extract user corrections from feedback."""
    print("\n" + "=" * 60)
    print("STEP 3: Extracting user corrections")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_ACTIVE_LEARNING)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get user corrections
    query = """
    SELECT 
        id,
        interaction_id,
        old_value,
        new_value,
        slot,
        correction_type,
        timestamp
    FROM corrections
    ORDER BY timestamp
    """
    
    try:
        cursor.execute(query)
        corrections = cursor.fetchall()
        
        print(f"\n✓ Found {len(corrections)} user corrections")
        
        # Save corrections
        output_file = OUTPUT_DIR / "raw_corrections.json"
        with open(output_file, 'w') as f:
            json.dump([dict(row) for row in corrections], f, indent=2)
        
        print(f"✓ Saved to: {output_file}")
        
    except sqlite3.OperationalError as e:
        print(f"\n⚠ No corrections table found (this is okay if Phase 1 just started)")
        corrections = []
    
    conn.close()
    return corrections

def analyze_potential_belief_updates(interactions, contradictions):
    """Identify potential belief updates from the data."""
    print("\n" + "=" * 60)
    print("STEP 4: Analyzing potential belief updates")
    print("=" * 60)
    
    # Group interactions by thread
    threads = defaultdict(list)
    for interaction in interactions:
        threads[interaction['thread_id']].append(interaction)
    
    print(f"\n✓ Found {len(threads)} conversation threads")
    
    # Find threads with multiple slot updates (potential belief changes)
    belief_updates = []
    
    for thread_id, thread_interactions in threads.items():
        if len(thread_interactions) < 2:
            continue
        
        # Look for slot changes within thread
        for i in range(1, len(thread_interactions)):
            prev = thread_interactions[i-1]
            curr = thread_interactions[i]
            
            try:
                prev_slots = json.loads(prev['slots_inferred']) if prev['slots_inferred'] else {}
                curr_slots = json.loads(curr['slots_inferred']) if curr['slots_inferred'] else {}
            except:
                continue
            
            # Find changed slots
            for slot in set(list(prev_slots.keys()) + list(curr_slots.keys())):
                prev_val = prev_slots.get(slot)
                curr_val = curr_slots.get(slot)
                
                if prev_val and curr_val and prev_val != curr_val:
                    belief_updates.append({
                        'thread_id': thread_id,
                        'slot': slot,
                        'old_value': prev_val,
                        'new_value': curr_val,
                        'old_timestamp': prev['timestamp'],
                        'new_timestamp': curr['timestamp'],
                        'time_delta_days': (curr['timestamp'] - prev['timestamp']) / 86400,
                        'old_query': prev['query'],
                        'new_query': curr['query']
                    })
    
    print(f"\n✓ Identified {len(belief_updates)} potential belief updates")
    
    if belief_updates:
        # Show examples
        print("\nExample belief updates found:")
        for i, update in enumerate(belief_updates[:5]):
            print(f"\n  {i+1}. Slot: {update['slot']}")
            print(f"     Old: {update['old_value']}")
            print(f"     New: {update['new_value']}")
            print(f"     Time delta: {update['time_delta_days']:.1f} days")
    
    # Save potential updates
    output_file = OUTPUT_DIR / "potential_belief_updates.json"
    with open(output_file, 'w') as f:
        json.dump(belief_updates, f, indent=2)
    
    print(f"\n✓ Saved to: {output_file}")
    
    return belief_updates

def generate_summary_report(interactions, contradictions, corrections, belief_updates):
    """Generate summary report of data extraction."""
    print("\n" + "=" * 60)
    print("PHASE 1 DATA EXTRACTION SUMMARY")
    print("=" * 60)
    
    report = f"""
# Phase 1 Data Extraction Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Data Collected

### Interactions with Slots
- **Total interactions:** {len(interactions)}
- **Output:** raw_interactions.json

### Contradictions Tracked
- **Total contradictions:** {len(contradictions)}
- **Output:** raw_contradictions.json

### User Corrections
- **Total corrections:** {len(corrections)}
- **Output:** raw_corrections.json

### Potential Belief Updates
- **Total identified:** {len(belief_updates)}
- **Output:** potential_belief_updates.json

## Next Steps

### ✅ What You Have
You successfully extracted {len(belief_updates)} potential belief updates from your logs.

### 📋 What To Do Next (Phase 1, Day 1 continued)

1. **Manual Labeling (2-3 hours)**
   - Open: belief_revision/data/potential_belief_updates.json
   - Label first 50 examples with categories:
     * REFINEMENT: "I like Python" → "I like Python and JavaScript"
     * REVISION: "I work at Microsoft" → "I work at Amazon"
     * TEMPORAL: "I'm 25" → "I'm 26"
     * CONFLICT: Contradictory without clear intent
   - Save as: labeled_examples_manual.json

2. **Generate Synthetic Data (Today/Tomorrow)**
   - Run: python scripts/phase1_generate_synthetic.py
   - This will create 600 synthetic examples using templates
   - Cost: Free (template-based, no API calls initially)

3. **Annotation Setup (End of Week 1)**
   - Prepare for Amazon MTurk annotation
   - Goal: 800 total labeled examples (200 real + 600 synthetic)

### 📊 Phase 1 Progress
- [x] Step 1: Extract real data ({len(belief_updates)} examples found)
- [ ] Step 2: Manual labeling (50 examples)
- [ ] Step 3: Generate synthetic data (600 examples)
- [ ] Step 4: MTurk annotation (800 examples total)
- [ ] Step 5: Upload to HuggingFace

**Timeline:** You should finish Steps 1-2 today, Step 3 tomorrow.

### 🎯 Week 1 Goal
By end of Week 1, you should have 200+ labeled real examples extracted and ready.

---
See START_HERE.md for detailed guidance on each step.
"""
    
    # Save report
    output_file = OUTPUT_DIR / "extraction_report.md"
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(report)
    print(f"\n✓ Full report saved to: {output_file}")

def main():
    """Run Phase 1 data extraction."""
    print("\n" + "🚀" * 30)
    print("PHASE 1: DATA EXTRACTION")
    print("Belief Revision Bench - Week 1, Day 1")
    print("🚀" * 30 + "\n")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Extract all data
    interactions = extract_interactions_with_slots()
    contradictions = extract_contradictions()
    corrections = extract_corrections()
    belief_updates = analyze_potential_belief_updates(interactions, contradictions)
    
    # Generate summary
    generate_summary_report(interactions, contradictions, corrections, belief_updates)
    
    print("\n" + "✅" * 30)
    print("DATA EXTRACTION COMPLETE!")
    print("✅" * 30 + "\n")
    
    print("Next: Read belief_revision/data/extraction_report.md")
    print("Then: Start manual labeling of potential_belief_updates.json\n")

if __name__ == "__main__":
    main()
