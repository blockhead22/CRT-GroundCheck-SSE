import json
import numpy as np
from .embeddings import EmbeddingStore


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def evaluate_index(input_txt_path: str, index_path: str) -> dict:
    with open(input_txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    idx = json.load(open(index_path, 'r', encoding='utf-8'))
    # compression ratio
    orig_tokens = estimate_tokens(text)
    compressed_tokens = estimate_tokens(json.dumps(idx))
    compression_ratio = compressed_tokens / orig_tokens
    # semantic coverage
    chunks = idx.get('chunks', [])
    claims = idx.get('claims', [])
    emb_store = EmbeddingStore()
    if chunks:
        chunk_texts = [c['text'] for c in chunks]
        chunk_embs = emb_store.embed_texts(chunk_texts)
        doc_emb = chunk_embs.mean(axis=0)
    else:
        doc_emb = None
    if claims:
        claim_texts = [c['claim_text'] for c in claims]
        claim_embs = emb_store.embed_texts(claim_texts)
        comp_emb = claim_embs.mean(axis=0)
    else:
        comp_emb = None
    semantic_coverage = None
    if doc_emb is not None and comp_emb is not None:
        semantic_coverage = float(np.dot(doc_emb, comp_emb))
    quote_retention = sum(len(c.get('supporting_quotes', [])) for c in claims) / max(1, len(chunks))
    contradiction_count = len(idx.get('contradictions', []))
    report = {
        'compression_ratio': compression_ratio,
        'semantic_coverage': semantic_coverage,
        'quote_retention_rate': quote_retention,
        'contradiction_count': contradiction_count,
    }
    # write report.json next to index
    return report
