from sse.contradictions import heuristic_contradiction, detect_contradictions
import numpy as np


def test_heuristic_contradiction():
    result = heuristic_contradiction("The sky is blue.", "The sky is not blue.")
    assert result == 'contradiction'
    
    result = heuristic_contradiction("The sky is blue.", "The sky is bright.")
    assert result == 'unrelated'


def test_contradiction_detection():
    claims = [
        {"claim_id": "c1", "claim_text": "The sun is hot.", "supporting_quotes": [{"chunk_id": "c0"}]},
        {"claim_id": "c2", "claim_text": "The sun is not hot.", "supporting_quotes": [{"chunk_id": "c1"}]},
    ]
    embs = np.random.randn(2, 384).astype('float32')
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12
    embs = embs / norms
    cons = detect_contradictions(claims, embs)
    assert isinstance(cons, list)
