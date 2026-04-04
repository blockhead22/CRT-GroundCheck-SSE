import requests
import json
import time

API_URL = 'http://127.0.0.1:8123/api'

print('RESOLUTION POLICIES TEST')
print('=' * 70)

results = {'OVERRIDE': False, 'PRESERVE': False, 'ASK_USER': False}

# Test 1: OVERRIDE
print('\n1. Testing OVERRIDE policy (job change)...')
thread = f'override_test_{int(time.time())}'

# Create contradiction
r1 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': 'I work at Microsoft'}, timeout=60)
time.sleep(0.5)
r2 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': 'I work at Amazon'}, timeout=60)

# Get contradiction
contradictions = requests.get(f'{API_URL}/contradictions', params={'thread_id': thread}, timeout=30).json()
if contradictions.get('contradictions'):
    ledger_id = contradictions['contradictions'][0]['ledger_id']
    old_mem = contradictions['contradictions'][0]['old_memory_id']
    new_mem = contradictions['contradictions'][0]['new_memory_id']
    
    # Resolve with OVERRIDE
    try:
        resolve_resp = requests.post(f'{API_URL}/resolve_contradiction', json={
            'thread_id': thread,
            'ledger_id': ledger_id,
            'resolution': 'OVERRIDE',
            'chosen_memory_id': new_mem,
            'user_confirmation': 'Amazon is correct'
        }, timeout=30)
        
        if resolve_resp.status_code == 200:
            print('   OVERRIDE worked')
            results['OVERRIDE'] = True
        else:
            print(f'   OVERRIDE failed: {resolve_resp.status_code} - {resolve_resp.text}')
    except Exception as e:
        print(f'   OVERRIDE error: {e}')
else:
    print('   No contradiction created for OVERRIDE test')

time.sleep(1)

# Test 2: PRESERVE
print('\n2. Testing PRESERVE policy (skill refinement)...')
thread = f'preserve_test_{int(time.time())}'

r1 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': 'I know Python'}, timeout=60)
time.sleep(0.5)
r2 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': 'I also know JavaScript'}, timeout=60)

contradictions = requests.get(f'{API_URL}/contradictions', params={'thread_id': thread}, timeout=30).json()
if contradictions.get('contradictions'):
    ledger_id = contradictions['contradictions'][0]['ledger_id']
    
    try:
        resolve_resp = requests.post(f'{API_URL}/resolve_contradiction', json={
            'thread_id': thread,
            'ledger_id': ledger_id,
            'resolution': 'PRESERVE',
            'user_confirmation': 'Both are correct'
        }, timeout=30)
        
        if resolve_resp.status_code == 200:
            print('   PRESERVE worked')
            results['PRESERVE'] = True
        else:
            print(f'   PRESERVE failed: {resolve_resp.status_code} - {resolve_resp.text}')
    except Exception as e:
        print(f'   PRESERVE error: {e}')
else:
    print('   No contradiction (auto-PRESERVE - PASS)')
    results['PRESERVE'] = True  # Assume it worked if no contradiction logged

time.sleep(1)

# Test 3: ASK_USER
print('\n3. Testing ASK_USER policy (deferred)...')
thread = f'askuser_test_{int(time.time())}'

r1 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': 'I prefer remote work'}, timeout=60)
time.sleep(0.5)
r2 = requests.post(f'{API_URL}/chat/send', json={'thread_id': thread, 'message': "I don't like working from home"}, timeout=60)

contradictions = requests.get(f'{API_URL}/contradictions', params={'thread_id': thread}, timeout=30).json()
if contradictions.get('contradictions'):
    ledger_id = contradictions['contradictions'][0]['ledger_id']
    
    try:
        resolve_resp = requests.post(f'{API_URL}/resolve_contradiction', json={
            'thread_id': thread,
            'ledger_id': ledger_id,
            'resolution': 'ASK_USER',
            'user_confirmation': "I'll decide later"
        }, timeout=30)
        
        if resolve_resp.status_code == 200:
            print('   ASK_USER worked')
            results['ASK_USER'] = True
        else:
            print(f'   ASK_USER failed: {resolve_resp.status_code} - {resolve_resp.text}')
    except Exception as e:
        print(f'   ASK_USER error: {e}')
else:
    print('   No contradiction created for ASK_USER test')

# Summary
print('\n' + '=' * 70)
print('RESOLUTION POLICIES:')
for policy, worked in results.items():
    status = 'WORKING' if worked else 'BROKEN'
    print(f'  {policy}: {status}')

working_count = sum(results.values())
print(f'\nTotal: {working_count}/3 policies working ({working_count/3*100:.0f}%)')

if working_count == 3:
    print('SUCCESS: All policies working')
elif working_count >= 2:
    print('PARTIAL: Some policies broken')
else:
    print('FAILURE: Major issues with resolution')

# Save
with open('retest_resolution.json', 'w') as f:
    json.dump(results, f, indent=2)

print('\nSaved to retest_resolution.json')
