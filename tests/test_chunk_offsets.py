from sse.chunker import chunk_text


def test_offsets_integrity():
    txt = "This is a sentence. Another one here! And a question? Final sentence."
    chunks = chunk_text(txt, max_chars=50, overlap=10)
    for c in chunks:
        start = c['start_char']
        end = c['end_char']
        assert txt[start:end].strip() in c['text']
