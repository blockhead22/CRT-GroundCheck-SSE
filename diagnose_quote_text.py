"""
Diagnostic: Compare stored quote with actual text at offsets.
"""

import json

idx = json.load(open('output_index/index.json'))

# Reconstruct the full original text from chunks
original_text = ''.join([c['text'] for c in idx['chunks']])

print("CHECKING QUOTE RECONSTRUCTION")
print("="*70)

for claim_idx, claim in enumerate(idx['claims'][:1]):
    print(f"Claim {claim['claim_id']}: {claim['claim_text'][:50]}...")
    
    for quote in claim['supporting_quotes']:
        start = quote['start_char']
        end = quote['end_char']
        stored_quote = quote['quote_text']
        
        # Extract from full text
        extracted = original_text[start:end]
        
        print(f"\nQuote offsets: [{start}:{end}]")
        print(f"Length: {end - start} chars")
        print(f"Stored quote text:")
        print(f"  \"{stored_quote}\"")
        print(f"Extracted from document:")
        print(f"  \"{extracted}\"")
        print(f"Match: {stored_quote == extracted}")
        
        # Check for whitespace/line ending differences
        if stored_quote != extracted:
            print(f"\nDifferences:")
            print(f"  Stored length: {len(stored_quote)}")
            print(f"  Extracted length: {len(extracted)}")
            print(f"  Stored ends with: {repr(stored_quote[-20:])}")
            print(f"  Extracted ends with: {repr(extracted[-20:])}")
