from sse.extractor import extract_claims_from_chunks, is_assertive, normalize_claim_text
from sse.chunker import chunk_text
from sse.embeddings import EmbeddingStore
import numpy as np


def test_assertive_filtering():
    assert is_assertive("The sky is blue.") is True
    assert is_assertive("What is the sky?") is False
    assert is_assertive("Note: something.") is False
    assert is_assertive("Hi") is False


def test_normalize_claim():
    assert normalize_claim_text("  hello   world  ") == "hello world"


def test_claim_extraction():
    txt = "The sun is hot. The moon is bright. Is the sky blue?"
    chunks = chunk_text(txt, max_chars=50)
    embs = np.random.randn(len(chunks), 384).astype('float32')
    # normalize
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    embs = embs / norms
    claims = extract_claims_from_chunks(chunks, embs)
    assert len(claims) > 0
    for c in claims:
        assert 'claim_id' in c
        assert 'claim_text' in c
        assert len(c.get('supporting_quotes', [])) > 0
