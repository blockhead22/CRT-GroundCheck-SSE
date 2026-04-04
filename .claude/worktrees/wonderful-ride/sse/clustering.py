import numpy as np
from typing import Dict, List


def cluster_embeddings(vectors: np.ndarray, method: str = "hdbscan", min_cluster_size: int = 2) -> List[Dict]:
    n, d = vectors.shape
    clusters = []
    if method == "hdbscan":
        try:
            import hdbscan
            clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric='euclidean')
            labels = clusterer.fit_predict(vectors)
        except Exception:
            method = "agg"
    if method == "agg":
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics.pairwise import cosine_distances
        # Agglomerative on cosine distances using average linkage
        if n <= 1:
            labels = np.zeros(n, dtype=int)
        else:
            # affinity must be in ['cityblock', 'cosine', 'euclidean', 'l1', 'l2', 'manhattan']
            model = AgglomerativeClustering(n_clusters=None, distance_threshold=0.5, linkage='average', metric='cosine')
            labels = model.fit_predict(vectors)
    if method == "kmeans":
        from sklearn.cluster import KMeans
        k = max(2, int(max(2, n // 10)))
        km = KMeans(n_clusters=k, random_state=42)
        labels = km.fit_predict(vectors)
    # assemble clusters
    unique = sorted(set(int(x) for x in labels if x >= 0))
    for uid in unique:
        idxs = [i for i, l in enumerate(labels) if l == uid]
        centroid = vectors[idxs].mean(axis=0)
        clusters.append({
            "cluster_id": f"cl{uid}",
            "chunk_ids": [f"c{i}" for i in idxs],
            "centroid_embedding_id": f"cent{uid}",
        })
    # noise/unassigned ignored
    return clusters
