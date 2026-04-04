import requests
import time
import json

API_URL = 'http://127.0.0.1:8123/api/chat/send'

contradictions = [
    ('I work at Microsoft', 'I work at Amazon'),
    ('I am 25 years old', 'I am 30 years old'),
    ('I live in Seattle', 'I live in New York'),
    ('I prefer coffee', 'I hate coffee'),
    ('I like dogs', 'I am allergic to dogs'),
    ('I am a vegetarian', 'I love steak'),
    ('I speak English', 'I only speak Spanish'),
    ('I am single', 'I am married'),
    ('I drive a Tesla', 'I do not own a car'),
    ('I wake up at 6am', 'I never wake up before noon'),
    ('I love winter', 'I hate cold weather'),
    ('I am an introvert', 'I am extremely extroverted'),
    ('I hate flying', 'I love airplanes'),
    ('I am a night owl', 'I am a morning person'),
    ('I live alone', 'I have 5 roommates'),
    ('I am allergic to peanuts', 'I eat peanut butter daily'),
    ('I am left-handed', 'I am right-handed'),
    ('I hate sports', 'I play basketball every day'),
    ('I am a minimalist', 'I am a hoarder'),
    ('I never drink alcohol', 'I drink wine every night')
]

thread_id = f'full_retest_{int(time.time())}'
results = {'detected': 0, 'missed': 0, 'errors': [], 'details': []}

print('FULL CONTRADICTION DETECTION TEST (20 pairs)')
print('=' * 70)

for i, (old, new) in enumerate(contradictions, 1):
    print(f'[{i}/20] {old[:25]}... -> {new[:25]}...', end=' ')
    
    try:
        r1 = requests.post(API_URL, json={'thread_id': thread_id, 'message': old}, timeout=60)
        time.sleep(0.5)
        r2 = requests.post(API_URL, json={'thread_id': thread_id, 'message': new}, timeout=60)
        data = r2.json()
        metadata = data.get('metadata', {})
        detected = metadata.get('contradiction_detected', False)
        
        if detected:
            print('DETECTED')
            results['detected'] += 1
            results['details'].append({'pair': i, 'old': old, 'new': new, 'detected': True, 'category': metadata.get('category')})
        else:
            print('MISSED')
            results['missed'] += 1
            results['details'].append({'pair': i, 'old': old, 'new': new, 'detected': False, 'metadata': metadata})
    except Exception as e:
        print(f'ERROR: {e}')
        results['errors'].append(str(e))
        results['missed'] += 1

total = results['detected'] + results['missed']
rate = (results['detected'] / total * 100) if total > 0 else 0

print('=' * 70)
print(f'DETECTION RATE: {results["detected"]}/{total} ({rate:.1f}%)')
if rate >= 75:
    print('SUCCESS: Detection rate meets target (>=75%)')
elif rate >= 60:
    print('PARTIAL: Detection improved but below target')
else:
    print('FAILURE: Detection rate still too low')

with open('retest_detection_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Saved to retest_detection_results.json')
