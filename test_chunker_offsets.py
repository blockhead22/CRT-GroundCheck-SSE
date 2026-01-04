"""Test current chunker offset behavior"""
text = 'First sentence. Second sentence.\nThird sentence.'
print(f"Original text: {repr(text)}")
print(f"Length: {len(text)}")

from sse.chunker import chunk_text
chunks = chunk_text(text, max_chars=100)

print(f"\nChunks: {len(chunks)}")
for c in chunks:
    reconstructed = text[c["start_char"]:c["end_char"]]
    match = reconstructed == c["text"]
    print(f"\n{c['chunk_id']}: [{c['start_char']}:{c['end_char']}]")
    print(f"  Stored:        {repr(c['text'])}")
    print(f"  Reconstructed: {repr(reconstructed)}")
    print(f"  Match: {match}")
