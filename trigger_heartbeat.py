"""Trigger a manual heartbeat check to respond to Moltbook posts immediately"""
import sys
sys.path.insert(0, '.')

from personal_agent.db_utils import ThreadSessionDB
from personal_agent.continuous_loops import build_loops

# Initialize database
session_db = ThreadSessionDB()

# Get all threads
threads = session_db.list_threads(limit=10)
print(f"\n📡 MANUAL HEARTBEAT TRIGGER")
print(f"Found {len(threads)} threads\n")

# Build loops (including heartbeat)
reflection_loop, personality_loop, self_reply_loop, heartbeat_loop = build_loops(session_db)

for thread_id in threads:
    print(f"Running heartbeat for thread: {thread_id}")
    
    # Check for mentions
    try:
        mentions = session_db.get_posts_mentioning(agent_name="agent", limit=5)
        aether_mentions = session_db.get_posts_mentioning(agent_name="aether", limit=5)
        all_mentions = mentions + aether_mentions
        
        if all_mentions:
            print(f"  ✅ Found {len(all_mentions)} mentions!")
            for mention in all_mentions:
                print(f"     - '{mention['title']}' by {mention['author']}")
        else:
            print(f"  ℹ️  No mentions found")
    except Exception as e:
        print(f"  ❌ Error checking mentions: {e}")
    
    # Trigger heartbeat
    try:
        result = heartbeat_loop.run_for_thread(thread_id)
        if result:
            print(f"  ✅ Heartbeat executed")
        else:
            print(f"  ℹ️  Heartbeat skipped (not due or disabled)")
    except Exception as e:
        print(f"  ❌ Heartbeat error: {e}")
    
    # Trigger reflection
    try:
        reflection_loop.run_for_thread(thread_id)
        print(f"  ✅ Reflection updated")
    except Exception as e:
        print(f"  ⚠️  Reflection error: {e}")
    
    # Trigger personality
    try:
        personality_loop.run_for_thread(thread_id)
        print(f"  ✅ Personality profile updated")
    except Exception as e:
        print(f"  ⚠️  Personality error: {e}")
    
    print()

print("\n✅ Manual trigger complete!")
print("Check /l/reflections in the frontend for responses\n")
