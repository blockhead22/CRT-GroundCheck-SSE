from sse.chunker import chunk_text


def test_chunk_overlap_behavior():
    txt = "".join([f"Sentence {i}. " for i in range(20)])
    chunks = chunk_text(txt, max_chars=60, overlap=20)
    assert len(chunks) >= 2
    for a, b in zip(chunks, chunks[1:]):
        # next chunk should start before previous chunk ends when overlap requested
        assert b['start_char'] < a['end_char']
        # and start_char within bounds of the text
        assert 0 <= b['start_char'] < b['end_char'] <= len(txt)
