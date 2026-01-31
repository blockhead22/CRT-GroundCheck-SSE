"""Quick script to clear Moltbook entries"""
from personal_agent.db_utils import get_thread_session_db

db = get_thread_session_db()
result = db.clear_moltbook_entries()
print(f"Cleared {result['deleted_posts']} posts from {result['submolt']}")
print("Moltbook is now empty.")
