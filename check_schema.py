import sqlite3

conn = sqlite3.connect("d:/AI_round2/personal_agent/crt_user_profile.db")
cursor = conn.cursor()

# Get table schema
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_profile_multi'")
schema = cursor.fetchone()
print("Table schema:")
print(schema[0])

conn.close()
