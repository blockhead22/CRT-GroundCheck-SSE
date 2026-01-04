"""
Fix tool: Correct quote_text to match actual byte offsets in index.

The offsets appear correct, but the stored quote_text doesn't match.
This tool reconstructs quote_text from the actual bytes.
"""

import json
import sys

def fix_index(index_path):
    """Load index, fix all quote_text to match offsets, save back."""
    
    with open(index_path, 'r', encoding='utf-8') as f:
        idx = json.load(f)
    
    # Reconstruct full text from chunks
    full_text = ''.join([c['text'] for c in idx['chunks']])
    
    print(f"Full text length: {len(full_text)} chars")
    print(f"Processing {len(idx['claims'])} claims...")
    
    fixed_count = 0
    
    for claim_idx, claim in enumerate(idx['claims']):
        for quote_idx, quote in enumerate(claim['supporting_quotes']):
            start = quote['start_char']
            end = quote['end_char']
            
            # Extract the actual text at these offsets
            actual_text = full_text[start:end]
            stored_text = quote['quote_text']
            
            if actual_text != stored_text:
                print(f"\nClaim {claim_idx} ({claim['claim_id']}) Quote {quote_idx}:")
                print(f"  Old: {stored_text[:50]}... (len={len(stored_text)})")
                print(f"  New: {actual_text[:50]}... (len={len(actual_text)})")
                
                # Update the quote_text to match actual offsets
                idx['claims'][claim_idx]['supporting_quotes'][quote_idx]['quote_text'] = actual_text
                fixed_count += 1
    
    if fixed_count > 0:
        print(f"\nFixed {fixed_count} quote texts")
        
        # Save back to index
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
        
        print(f"Saved fixed index to {index_path}")
        return True
    else:
        print("No quotes needed fixing")
        return False

if __name__ == "__main__":
    index_path = 'output_index/index.json'
    if len(sys.argv) > 1:
        index_path = sys.argv[1]
    
    fix_index(index_path)
