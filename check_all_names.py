import sqlite3

conn = sqlite3.connect("d:/AI_round2/personal_agent/crt_user_profile.db")
cursor = conn.cursor()

# Check ALL name facts, including inactive ones
cursor.execute("SELECT id, value, normalized, active, timestamp, source_thread FROM user_profile_multi WHERE slot = 'name' ORDER BY timestamp DESC")
all_names = cursor.fetchall()

print(f"Found {len(all_names)} name facts (including inactive):")
for row in all_names:
    id_val, value, norm, active, ts, thread = row
    status = "ACTIVE" if active else "INACTIVE"
    print(f"  [{status}] id={id_val}: '{value}' (normalized: '{norm}') from thread '{thread}'")

conn.close()
