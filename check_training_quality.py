import sqlite3

conn = sqlite3.connect('personal_agent/active_learning.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT question, response_type_predicted, response_type_actual 
    FROM gate_events 
    WHERE response_type_actual IS NOT NULL 
    LIMIT 50
''')

print('Training data quality - heuristic labels:')
print(f"{'Query':<50} {'Heuristic Label':<20}")
print('-'*75)

misclass_count = 0
for q, pred, actual in cursor.fetchall():
    # Our auto-classifier used heuristics, but some are wrong
    if actual == 'conversational' and 'help' not in q.lower() and 'thank' not in q.lower() and 'hi' not in q.lower():
        print(f'{q[:48]:<50} {actual:<20} ← WRONG')
        misclass_count += 1
    elif actual == 'factual' and any(w in q.lower() for w in ['why', 'how does', 'explain']):
        print(f'{q[:48]:<50} {actual:<20} ← SHOULD BE explanatory')
        misclass_count += 1

print(f"\nPotential mislabels: {misclass_count}")
conn.close()
