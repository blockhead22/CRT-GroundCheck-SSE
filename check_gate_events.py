import sqlite3

conn = sqlite3.connect('personal_agent/active_learning.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT question, response_type_predicted, gates_passed, 
           intent_align, memory_align, grounding_score 
    FROM gate_events 
    ORDER BY timestamp DESC 
    LIMIT 20
''')

print("\nRecent gate events from validation:")
print(f"{'Query':<45} {'Type':<15} {'Pass':<6} {'Intent':<7} {'Memory':<7} {'Ground':<7}")
print('-'*100)

for q, t, gp, ia, ma, gs in cursor.fetchall():
    status = "✓" if gp else "✗"
    print(f'{q[:43]:<45} {t:<15} {status:<6} {ia:.3f}   {ma:.3f}   {gs:.3f}')

conn.close()
