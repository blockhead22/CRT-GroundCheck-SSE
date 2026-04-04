import numpy as np
from typing import Dict, List


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def query_index(qv: np.ndarray, index: Dict, emb_vectors: np.ndarray, k: int = 5) -> Dict:
    """Query the index by embedding similarity."""
    clusters = index.get('clusters', [])
    all_claims = index.get('claims', [])
    all_contradictions = index.get('contradictions', [])
    
    # compute similarity to centroids
    centroids = []
    for cl in clusters:
        ids = cl.get('chunk_ids', [])
        idxs = [int(cid[1:]) for cid in ids]
        if not idxs:
            centroids.append(np.zeros(emb_vectors.shape[1] if len(emb_vectors) > 0 else 384, dtype='float32'))
        else:
            vecs = [emb_vectors[idx] for idx in idxs if idx < len(emb_vectors)]
            if vecs:
                centroids.append(np.vstack(vecs).mean(axis=0))
            else:
                centroids.append(np.zeros(emb_vectors.shape[1], dtype='float32'))
    
    sims = [cosine_sim(qv, c) for c in centroids]
    order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
    
    results = []
    for cluster_idx in order:
        cl = clusters[cluster_idx]
        chunk_ids_set = set(cl.get('chunk_ids', []))
        
        # get claims in this cluster
        cluster_claims = [c for c in all_claims if any(q['chunk_id'] in chunk_ids_set for q in c.get('supporting_quotes', []))]
        cluster_claim_ids = set(c['claim_id'] for c in cluster_claims)
        
        # get contradictions involving cluster claims
        cluster_contradictions = [
            x for x in all_contradictions
            if x['pair']['claim_id_a'] in cluster_claim_ids or x['pair']['claim_id_b'] in cluster_claim_ids
        ]
        
        # get open questions from cluster claims
        open_questions = [
            q for c in cluster_claims
            for q in c.get('ambiguity', {}).get('open_questions', [])
        ]
        
        results.append({
            'cluster_id': cl['cluster_id'],
            'similarity': float(sims[cluster_idx]),
            'chunk_ids': cl['chunk_ids'],
            'claims': cluster_claims,
            'contradictions': cluster_contradictions,
            'open_questions': open_questions,
        })
    
    return {'query_results': results, 'total_clusters': len(clusters)}
