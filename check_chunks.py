import json
with open("canonical_demo/chunks.json") as f:
    chunks = json.load(f)

with open("canonical_demo/input.txt") as f:
    text = f.read()

print(f"Total text length: {len(text)}")
print()

for chunk in chunks[:3]:
    cid = chunk["chunk_id"]
    start = chunk["start_char"]
    end = chunk["end_char"]
    chunk_text = chunk["text"]
    reconstructed = text[start:end]
    
    print(f"{cid}: [{start}:{end}]")
    print(f"  Stored: {repr(chunk_text[:60])}")
    print(f"  Recon:  {repr(reconstructed[:60])}")
    print(f"  Match: {chunk_text == reconstructed}")
    print()
