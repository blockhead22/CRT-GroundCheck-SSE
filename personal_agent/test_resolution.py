#!/usr/bin/env python3
"""
Resolution Policy Testing Script

Tests all 3 contradiction resolution policies:
1. OVERRIDE (job change)
2. PRESERVE (skill refinement)
3. ASK_USER (preference conflict - deferred)

Generates SQL dumps as evidence.
"""

import requests
import sqlite3
import json
import time
from pathlib import Path

BASE_URL = "http://127.0.0.1:5000"

def chat(message):
    """Send message to chatbot."""
    response = requests.post(f"{BASE_URL}/api/chat/send", json={
        "message": message,
        "thread_id": "test_resolution"
    })
    return response.json()

def resolve_contradiction(ledger_id, resolution, chosen_memory_id=None, user_feedback=""):
    """Resolve a contradiction using the new policy endpoint."""
    response = requests.post(f"{BASE_URL}/api/resolve_contradiction", json={
        "thread_id": "test_resolution",
        "ledger_id": ledger_id,
        "resolution": resolution,
        "chosen_memory_id": chosen_memory_id,
        "user_confirmation": user_feedback
    })
    return response.json()

def query_ledger():
    """Query contradiction ledger."""
    conn = sqlite3.connect('personal_agent/crt_ledger_test_resolution.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contradictions ORDER BY timestamp DESC LIMIT 5")
    results = cursor.fetchall()
    conn.close()
    return results

def query_memories(slot):
    """Query memories by slot."""
    conn = sqlite3.connect('personal_agent/crt_memory_test_resolution.db')
    cursor = conn.cursor()
    # Note: Using text search since we don't have a slot column directly
    cursor.execute("""
        SELECT memory_id, text, trust, deprecated, deprecation_reason
        FROM memories
        WHERE text LIKE ?
        ORDER BY timestamp DESC
    """, (f'%{slot}%',))
    results = cursor.fetchall()
    conn.close()
    return results

def export_sql_dumps(suffix=""):
    """Export SQL dumps with timestamp suffix."""
    timestamp = int(time.time())
    
    # Create test_results directory if it doesn't exist
    Path("test_results").mkdir(exist_ok=True)
    
    for db_name in ['crt_memory_test_resolution.db', 'crt_ledger_test_resolution.db', 'active_learning.db']:
        db_path = f'personal_agent/{db_name}'
        if not Path(db_path).exists():
            print(f"⚠ Skipping {db_name} (not found)")
            continue
            
        output_file = f"test_results/{db_name.replace('.db', '')}_{suffix}_{timestamp}.sql"
        
        # Export with UTF-8 encoding (fix for Problem A)
        conn = sqlite3.connect(db_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        conn.close()
        
        print(f"✓ Exported: {output_file}")

print("="*60)
print("RESOLUTION POLICY TEST")
print("="*60)
print("\nNOTE: This test requires the CRT API server to be running")
print(f"at {BASE_URL}\n")

# Test 1: OVERRIDE (Job change)
print("\n### TEST 1: OVERRIDE Policy (Job Change)")
print("-" * 60)

try:
    print("Step 1: Establish Microsoft as employer...")
    resp1 = chat("I work at Microsoft")
    print(f"Response: {resp1.get('answer', 'N/A')[:100]}")

    print("\nStep 2: Create contradiction with Amazon...")
    time.sleep(1)
    resp2 = chat("I work at Amazon now")
    print(f"Response: {resp2.get('answer', 'N/A')[:100]}")

    print("\nStep 3: Trigger clarification...")
    time.sleep(1)
    resp3 = chat("Where do I work?")
    print(f"Response: {resp3.get('answer', 'N/A')[:100]}")
    print(f"Gates passed: {resp3.get('gates_passed', 'N/A')}")

    # Get ledger_id from most recent contradiction
    time.sleep(1)
    ledger_entries = query_ledger()
    if ledger_entries:
        ledger_id = ledger_entries[0][0]  # First column is ledger_id
        print(f"\nLedger ID: {ledger_id}")
        
        # Get memory IDs
        memories = query_memories('Amazon')
        if memories:
            amazon_memory_id = memories[0][0]  # Most recent
            
            print("\nStep 4: Resolve with OVERRIDE (choose Amazon)...")
            resolution = resolve_contradiction(
                ledger_id=ledger_id,
                resolution="OVERRIDE",
                chosen_memory_id=amazon_memory_id,
                user_feedback="Amazon is correct, I switched jobs last month"
            )
            print(f"Resolution result: {resolution}")
            
            print("\nStep 5: Verify Microsoft is deprecated...")
            time.sleep(1)
            memories_after = query_memories('work')
            for mem in memories_after:
                mem_id, text, trust, deprecated, reason = mem
                status = "DEPRECATED" if deprecated else "ACTIVE"
                print(f"  {text[:50]}: {status} (trust={trust:.2f}) {reason or ''}")
        else:
            print("⚠ No memories found for Amazon")
    else:
        print("⚠ No contradictions found in ledger")

    print("\n✓ TEST 1 COMPLETE")
    export_sql_dumps("test1_override")

except Exception as e:
    print(f"✗ TEST 1 FAILED: {e}")
    import traceback
    traceback.print_exc()

# Wait before next test
time.sleep(2)

# Test 2: PRESERVE (Skill refinement)
print("\n### TEST 2: PRESERVE Policy (Skill Refinement)")
print("-" * 60)

try:
    print("Step 1: Establish Python skill...")
    resp4 = chat("I know Python")
    print(f"Response: {resp4.get('answer', 'N/A')[:100]}")

    print("\nStep 2: Add JavaScript (refinement)...")
    time.sleep(1)
    resp5 = chat("I also know JavaScript and TypeScript")
    print(f"Response: {resp5.get('answer', 'N/A')[:100]}")

    # This may create a REFINEMENT contradiction
    time.sleep(1)
    ledger_entries2 = query_ledger()
    if len(ledger_entries2) > len(ledger_entries if 'ledger_entries' in locals() else []):
        new_ledger_id = ledger_entries2[0][0]
        
        print("\nStep 3: Apply PRESERVE policy...")
        resolution2 = resolve_contradiction(
            ledger_id=new_ledger_id,
            resolution="PRESERVE",
            user_feedback="Both are true, I know multiple languages"
        )
        print(f"Resolution result: {resolution2}")

    print("\n✓ TEST 2 COMPLETE")
    export_sql_dumps("test2_preserve")

except Exception as e:
    print(f"✗ TEST 2 FAILED: {e}")
    import traceback
    traceback.print_exc()

# Test 3: ASK_USER deferred
print("\n### TEST 3: ASK_USER Policy (Deferred)")
print("-" * 60)

try:
    print("Step 1: State preference for remote work...")
    resp6 = chat("I prefer working remotely")
    print(f"Response: {resp6.get('answer', 'N/A')[:100]}")

    print("\nStep 2: Contradict with office preference...")
    time.sleep(1)
    resp7 = chat("I don't like working from home")
    print(f"Response: {resp7.get('answer', 'N/A')[:100]}")

    time.sleep(1)
    ledger_entries3 = query_ledger()
    if len(ledger_entries3) > len(ledger_entries2 if 'ledger_entries2' in locals() else []):
        new_ledger_id = ledger_entries3[0][0]
        
        print("\nStep 3: User defers decision...")
        resolution3 = resolve_contradiction(
            ledger_id=new_ledger_id,
            resolution="ASK_USER",
            user_feedback="I'm not sure yet, ask me again later"
        )
        print(f"Resolution result: {resolution3}")

    print("\n✓ TEST 3 COMPLETE")
    export_sql_dumps("test3_askuser")

except Exception as e:
    print(f"✗ TEST 3 FAILED: {e}")
    import traceback
    traceback.print_exc()

# Final summary
print("\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)

try:
    conn = sqlite3.connect('personal_agent/crt_ledger_test_resolution.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ledger_id, status, resolution_method, contradiction_type
        FROM contradictions
        ORDER BY timestamp
    """)
    all_contradictions = cursor.fetchall()

    print(f"\nTotal contradictions tracked: {len(all_contradictions)}")
    for contra in all_contradictions:
        ledger_id, status, resolution, contra_type = contra
        print(f"  {ledger_id}: {status} ({contra_type}) → {resolution or 'N/A'}")

    conn.close()
except Exception as e:
    print(f"⚠ Could not load final summary: {e}")

print("\n✓ All SQL dumps exported to test_results/")
print("✓ Resolution testing complete")
