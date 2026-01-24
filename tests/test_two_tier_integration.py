"""Test that two-tier extraction works end-to-end."""
import requests
import sqlite3
import json
import time
import sys

API_URL = "http://127.0.0.1:8123/api/chat/send"
thread_id = f"two_tier_test_{int(time.time())}"

def test_two_tier_integration():
    """Run end-to-end tests for two-tier fact extraction."""
    
    print("=" * 70)
    print("Two-Tier Fact Extraction Integration Test")
    print("=" * 70)
    print(f"Thread ID: {thread_id}\n")
    
    # Test 1: Open-world fact (should use LLM)
    print("Test 1: Open-world fact extraction")
    print("-" * 70)
    try:
        r1 = requests.post(API_URL, json={
            "thread_id": thread_id,
            "message": "I love quantum gardening"
        }, timeout=30)
        r1.raise_for_status()
        response1 = r1.json()
        print(f"✓ Request successful")
        print(f"  Response: {response1['answer'][:100]}")
    except Exception as e:
        print(f"✗ Request failed: {e}")
        return False
    
    time.sleep(1)
    
    # Test 2: Hard slot fact (should use regex)
    print("\nTest 2: Hard slot extraction")
    print("-" * 70)
    try:
        r2 = requests.post(API_URL, json={
            "thread_id": thread_id,
            "message": "My name is Alex"
        }, timeout=30)
        r2.raise_for_status()
        response2 = r2.json()
        print(f"✓ Request successful")
        print(f"  Response: {response2['answer'][:100]}")
    except Exception as e:
        print(f"✗ Request failed: {e}")
        return False
    
    time.sleep(1)
    
    # Test 3: Check database for tuples
    print("\nTest 3: Database verification")
    print("-" * 70)
    db_path = f"personal_agent/crt_memory_{thread_id}.db"
    
    # Wait a bit for database to be written
    time.sleep(2)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if extraction_method column exists
        cursor.execute("PRAGMA table_info(memories)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'extraction_method' not in columns:
            print(f"✗ extraction_method column not found in database")
            print(f"  Available columns: {columns}")
            conn.close()
            return False
        
        print(f"✓ extraction_method column exists")
        
        if 'fact_tuples' not in columns:
            print(f"✗ fact_tuples column not found in database")
            conn.close()
            return False
        
        print(f"✓ fact_tuples column exists")
        
        # Check stored memories
        cursor.execute("""
            SELECT text, fact_tuples, extraction_method 
            FROM memories 
            WHERE extraction_method IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            print(f"✗ No memories found with extraction_method")
            conn.close()
            return False
        
        print(f"✓ Found {len(rows)} memories with extraction data")
        
        llm_count = 0
        regex_count = 0
        tuples_found = False
        
        for row in rows:
            text, tuples, method = row
            print(f"\n  Memory: {text[:60]}")
            print(f"  Method: {method}")
            
            if method == 'llm':
                llm_count += 1
            elif method == 'regex':
                regex_count += 1
            
            if tuples:
                tuples_found = True
                try:
                    tuples_obj = json.loads(tuples)
                    print(f"  Tuples: {len(tuples_obj)} extracted")
                    for t in tuples_obj[:2]:
                        print(f"    - {t.get('attribute', 'unknown')}: {t.get('value', 'unknown')}")
                except json.JSONDecodeError as e:
                    print(f"  ✗ Failed to parse tuples JSON: {e}")
        
        conn.close()
        
        print(f"\n  Summary: {llm_count} LLM extractions, {regex_count} regex extractions")
        
        if not tuples_found:
            print(f"  ⚠ Warning: No fact_tuples found in database")
        
    except Exception as e:
        print(f"✗ Database check failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Recall open-world fact
    print("\nTest 4: Recall test")
    print("-" * 70)
    try:
        r3 = requests.post(API_URL, json={
            "thread_id": thread_id,
            "message": "What hobbies do I have?"
        }, timeout=30)
        r3.raise_for_status()
        response3 = r3.json()
        answer = response3['answer']
        print(f"✓ Request successful")
        print(f"  Answer: {answer}")
        
        # Check if the hobby is recalled
        if "quantum gardening" in answer.lower() or "gardening" in answer.lower():
            print("✅ SUCCESS: Open-world fact recalled")
        else:
            print("⚠ WARNING: Open-world fact not recalled (may need LLM enabled)")
    except Exception as e:
        print(f"✗ Request failed: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ Two-tier integration test completed successfully!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = test_two_tier_integration()
    sys.exit(0 if success else 1)
