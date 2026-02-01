from personal_agent.db_utils import ThreadSessionDB

db = ThreadSessionDB()
comments = db._get_connection().execute(
    'SELECT id, post_id, content, author, created_at FROM molt_comments ORDER BY created_at DESC LIMIT 5'
).fetchall()

print('\n📝 Recent Comments:\n')
if comments:
    for c in comments:
        print(f'Comment #{c[0]}: On post #{c[1]} by "{c[3]}"')
        print(f'Content: {c[2]}\n')
else:
    print('  No comments yet')
