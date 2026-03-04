"""Wipe all shared/global DBs for clean eval. Preserves nothing."""
import sqlite3
import os

dbs_to_wipe = {
    # Main memory + facts
    "personal_agent/crt_memory.db": ["memories", "trust_log", "belief_speech", "reasoning_traces"],
    "personal_agent/crt_facts.db": ["facts"],
    "data/crt_memory.db": ["memories", "trust_log", "belief_speech", "reasoning_traces", "contradictions",
                           "reflection_queue", "contradiction_worklog", "conflict_resolutions", "contradiction_lifecycle"],
    # Shared memory + ledger
    "personal_agent/crt_memory_shared.db": ["memories", "trust_log", "belief_speech", "reasoning_traces", "reflection_traces"],
    "personal_agent/crt_ledger_shared.db": ["contradictions", "reflection_queue", "contradiction_worklog",
                                            "conflict_resolutions", "contradiction_lifecycle"],
    # User profile
    "personal_agent/crt_user_profile.db": ["user_profile_multi"],
    # Episodic
    "personal_agent/crt_episodic.db": ["session_summaries", "user_preferences", "interaction_patterns",
                                       "concept_nodes", "concept_aliases", "interaction_log"],
    # Thread sessions (selective — keep structure, wipe data)
    "personal_agent/crt_thread_sessions.db": ["thread_sessions", "recent_queries", "reflection_scorecards",
                                              "personality_profiles", "reflection_journal_entries",
                                              "heartbeat_history", "molt_posts", "molt_comments", "molt_votes",
                                              "heartbeat_news_cache", "reflection_scorecard_history",
                                              "personality_profile_history", "outbound_notifications"],
}

total_cleared = 0
for db_path, tables in dbs_to_wipe.items():
    if not os.path.exists(db_path):
        print(f"SKIP (not found): {db_path}")
        continue
    try:
        db = sqlite3.connect(db_path)
        existing = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for tbl in tables:
            if tbl in existing:
                cnt = db.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
                if cnt > 0:
                    db.execute(f"DELETE FROM [{tbl}]")
                    total_cleared += cnt
                    print(f"  {db_path} / {tbl}: cleared {cnt} rows")
        db.commit()
        db.close()
    except Exception as e:
        print(f"ERROR {db_path}: {e}")

print(f"\nTotal rows cleared: {total_cleared}")
print("All DBs clean.")
