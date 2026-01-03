import numpy as np
from sse.clustering import cluster_embeddings

def test_clustering_runs():
    rng = np.random.RandomState(42)
    vecs = rng.randn(10, 32).astype('float32')
    clusters = cluster_embeddings(vecs, method='kmeans')
    assert isinstance(clusters, list)
