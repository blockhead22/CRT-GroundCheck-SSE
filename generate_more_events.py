import requests

queries = [
    'What do I study?', 'How am I feeling today?', 'What car do I drive?', 
    'Why did I choose this field?', 'Tell me about my family', 'What are my hobbies?',
    'Where did I go to school?', 'What is my favorite food?', 'How do I spend weekends?',
    'What are my career goals?', 'What skills do I have?', 'Where have I traveled?',
    'What music do I like?', 'What books have I read?', 'Who are my friends?',
    'What sports do I play?', 'What languages do I know?', 'What projects am I working on?',
    'What is my daily routine?', 'What challenges am I facing?', 'What motivates me?',
    'What is my background?', 'What tools do I use?', 'What is my education?',
    'What is my work experience?', 'What are my values?', 'What is important to me?',
    'What do I believe in?', 'What are my strengths?', 'What are my weaknesses?',
    'What is my personality like?', 'What makes me unique?', 'What is my story?',
    'What do I want to achieve?', 'What is my vision?', 'What is my mission?',
    'What is next for me?', 'Where am I headed?', 'What is my purpose?', 'What drives me?'
]

for q in queries:
    try:
        requests.post('http://localhost:8123/api/chat/send', 
                     json={'thread_id': 'test', 'message': q}, timeout=5)
        print(f"✓ {q}")
    except Exception as e:
        print(f"✗ {q}: {e}")
