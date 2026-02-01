"""Check what's in the ledger feed"""
from personal_agent.db_utils import ThreadSessionDB
from personal_agent.heartbeat_executor import HeartbeatLLMExecutor

session_db = ThreadSessionDB()
executor = HeartbeatLLMExecutor(session_db=session_db)

# Get threads
threads = session_db.list_threads(limit=1)
thread_id = threads[0]

# Get context
context = executor.gather_context(thread_id)

print("\n📬 LEDGER FEED:\n")
for i, post in enumerate(context.ledger_feed[:10], 1):
    print(f"{i}. Post #{post.get('id')}: \"{post.get('title')}\"")
    print(f"   Author: {post.get('author')}")
    print(f"   Content: {post.get('content')[:100]}...")
    
    # Check for mentions
    content_lower = post.get('content', '').lower()
    title_lower = post.get('title', '').lower()
    
    has_aether = 'aether' in content_lower or 'aether' in title_lower
    has_agent = 'agent' in content_lower or '@agent' in content_lower
    
    print(f"   Has 'aether': {has_aether}")
    print(f"   Has 'agent': {has_agent}")
    print()
