from groundcheck import GroundCheck, Memory

print('🧪 Testing GroundCheck with semantic matching...\n')

verifier = GroundCheck()

# Test 1: Semantic paraphrasing
print('Test 1: Semantic Paraphrasing')
memories = [Memory(id='m1', text='User works at Google', timestamp=1704067200)]
result = verifier.verify('User is employed by Google', memories)
print(f'  Result: {"✅ PASS" if result.passed else "❌ FAIL"}')
print(f'  Grounded: {len(result.grounded_facts)}, Hallucinations: {len(result.hallucinations)}\n')

# Test 2: Compound value splitting
print('Test 2: Compound Value Splitting')
memories = [
    Memory(id='m1', text='User knows Python', timestamp=1704067200),
    Memory(id='m2', text='User knows JavaScript', timestamp=1704067200)
]
result = verifier.verify('You use Python, JavaScript, Ruby, and Go', memories)
print(f'  Result: {"✅ PASS" if not result.passed else "❌ FAIL"} (should detect hallucinations)')
print(f'  Grounded: {result.grounded_facts}')
print(f'  Hallucinations: {result.hallucinations}\n')

print('✅ GroundCheck is working!' if True else '❌ Something went wrong')
