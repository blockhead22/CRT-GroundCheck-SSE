import requests
import json
import time

API_URL = 'http://127.0.0.1:8123/api'

print('GATE BLOCKING TEST')
print('=' * 70)

# Create fresh thread
thread_id = f'gate_test_{int(time.time())}'

# Step 1: Create contradiction
print('\n1. Creating contradiction (Microsoft -> Amazon)...')
r1 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread_id, 'message': 'I work at Microsoft'}, timeout=60)
print(f'   Response 1: {r1.json()["answer"][:60]}')

time.sleep(0.5)

r2 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread_id, 'message': 'I work at Amazon'}, timeout=60)
data2 = r2.json()
meta2 = data2.get('metadata', {})
print(f'   Response 2: {data2["answer"][:60]}')
print(f'   Contradiction detected: {meta2.get("contradiction_detected", False)}')

time.sleep(0.5)

# Step 2: Query about contradicted fact (GATE SHOULD BLOCK)
print('\n2. Querying contradicted fact: "Where do I work?"')
r3 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread_id, 'message': 'Where do I work?'}, timeout=60)
data3 = r3.json()

print(f'\n   Answer: {data3["answer"]}')
print(f'   Gates passed: {data3.get("gates_passed", True)}')
print(f'   Response type: {data3.get("response_type", "N/A")}')

# Validate gate blocking
if data3.get('gates_passed') == False:
    print('\n   RESULT: Gate blocked correctly')
    gate_result = 'WORKING'
elif 'conflicting' in data3['answer'].lower() or 'which is correct' in data3['answer'].lower():
    print('\n   RESULT: Gate blocked (clarification requested)')
    gate_result = 'WORKING'
else:
    print(f'\n   RESULT: Gate did NOT block. Returned confident answer.')
    gate_result = 'BROKEN'

# Test multiple contradicted queries
print('\n' + '=' * 70)
print('Testing 3 more contradicted queries...')

test_queries = [
    ('location', 'I live in Seattle', 'I live in Tokyo', 'Where do I live?'),
    ('age', "I'm 25", "I'm 35", 'How old am I?'),
    ('preference', 'I love coffee', 'I hate coffee', 'Do I like coffee?')
]

blocked_count = 0

for slot, old, new, query in test_queries:
    thread = f'gate_{slot}_{int(time.time())}'
    
    # Setup contradiction
    requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': old}, timeout=60)
    time.sleep(0.3)
    requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': new}, timeout=60)
    time.sleep(0.3)
    
    # Query
    r = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': query}, timeout=60)
    data = r.json()
    
    gates_passed = data.get('gates_passed', True)
    answer_lower = data['answer'].lower()
    
    is_blocked = (
        gates_passed == False or 
        'conflicting' in answer_lower or 
        'which is correct' in answer_lower or
        'contradiction' in answer_lower
    )
    
    if is_blocked:
        print(f'  {slot}: BLOCKED')
        blocked_count += 1
    else:
        print(f'  {slot}: NOT BLOCKED ("{data["answer"][:50]}...")')

total_tests = 4  # Initial + 3 more
total_blocked = (1 if gate_result == 'WORKING' else 0) + blocked_count
block_rate = (total_blocked / total_tests * 100)

print('\n' + '=' * 70)
print(f'GATE BLOCKING RATE: {total_blocked}/{total_tests} ({block_rate:.0f}%)')

if block_rate >= 75:
    print('SUCCESS: Gate blocking working')
elif block_rate >= 50:
    print('PARTIAL: Gate blocking inconsistent')
else:
    print('FAILURE: Gate blocking broken')

# Save evidence
evidence = {
    'gate_blocking_rate': block_rate,
    'tests_passed': total_blocked,
    'tests_total': total_tests,
    'status': 'WORKING' if block_rate >= 75 else 'BROKEN'
}

with open('retest_gate_blocking.json', 'w') as f:
    json.dump(evidence, f, indent=2)

print('\nSaved to retest_gate_blocking.json')
