"""
Diagnostic: Understand the offset structure in the index.
"""

import json

idx = json.load(open('output_index/index.json'))

print("CHUNK STRUCTURE")
print("="*70)
for c in idx['chunks']:
    print(f"Chunk {c['chunk_id']}: absolute offsets [{c['start_char']}:{c['end_char']}]")
    text_sample = c['text'][:50].replace('\n', '\\n')
    print(f"  Text: {text_sample}...")

print("\n" + "="*70)
print("CLAIM QUOTES (first claim)")
print("="*70)
for q in idx['claims'][0]['supporting_quotes']:
    print(f"Quote: [{q['start_char']}:{q['end_char']}]")
    print(f"  Text: {q['quote_text'][:60]}...")
    chunk_id = q['chunk_id']
    chunk = next(c for c in idx['chunks'] if c['chunk_id'] == chunk_id)
    print(f"  From chunk {chunk_id}: absolute [{chunk['start_char']}:{chunk['end_char']}]")
    
    # Try to extract from chunk text using different methods
    chunk_text = chunk['text']
    
    # Method 1: Direct indexing into chunk text (assuming quote offsets are relative)
    method1 = chunk_text[q['start_char'] - chunk['start_char']:q['end_char'] - chunk['start_char']]
    
    # Method 2: Assume offsets are absolute, need to get from original text
    # (We don't have it here, but we can show the problem)
    
    print(f"\n  Reconstruction attempt (treating offsets as relative to chunk):")
    print(f"    {method1[:60]}...")
    print(f"    Matches stored quote: {method1 == q['quote_text']}")
