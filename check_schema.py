import sqlite3
conn = sqlite3.connect('personal_agent/active_learning.db')
cursor = conn.cursor()
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table"')
for row in cursor.fetchall():
    print(row[0])
    print()
