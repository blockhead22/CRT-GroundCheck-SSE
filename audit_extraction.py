"""
Diagnostic: Check what claim extraction is actually producing.
"""

import json

# Load the index
idx = json.load(open('output_index/index.json'))

# Reconstruct full text
full_text = ''.join([c['text'] for c in idx['chunks']])

print("CLAIM EXTRACTION AUDIT")
print("="*70)

for claim in idx['claims'][:2]:
    print(f"\nClaim ID: {claim['claim_id']}")
    print(f"Claim Text: {claim['claim_text'][:60]}...")
    
    for quote in claim['supporting_quotes']:
        start = quote['start_char']
        end = quote['end_char']
        stored_text = quote['quote_text']
        chunk_id = quote['chunk_id']
        
        # Get actual text from offsets
        actual_text = full_text[start:end]
        
        print(f"\n  Supporting Quote from {chunk_id}:")
        print(f"    Offsets: [{start}:{end}]")
        print(f"    Stored text: \"{stored_text[:70]}...\"")
        print(f"    Actual text: \"{actual_text[:70]}...\"")
        print(f"    Match: {stored_text == actual_text}")
        print(f"    Stored len: {len(stored_text)}, Actual len: {len(actual_text)}")
