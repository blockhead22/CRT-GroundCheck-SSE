"""Geometric diagnostics, not semantic truth probabilities. No model imports."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class ClusterEvidence:
    clusters: int
    noise_fraction: float
    cluster_entropy_bits: float
    singleton_noise_entropy_bits: float
    support: float


def _entropy(counts):
    p = np.asarray(counts, dtype=float)
    if not len(p) or not p.sum():
        return 0.0
    p = p[p > 0] / p.sum()
    return max(0.0, float(-np.sum(p * np.log2(p))))


def cluster_evidence(labels):
    """Noise is unassigned evidence, never one unanimous semantic cluster.

    support = assigned fraction / (1 + entropy among assigned clusters).
    It is a bounded heuristic, NOT calibrated confidence/correctness. All-noise
    and empty inputs have zero support. Singleton-noise entropy is a separate
    sensitivity diagnostic, not a validated semantic-entropy estimator.
    """
    labels = np.asarray(labels)
    if labels.ndim != 1 or (labels.size and
            (not np.issubdtype(labels.dtype, np.integer) or np.any(labels < -1))):
        raise ValueError('Expected one-dimensional integer DBSCAN labels >= -1')
    n = len(labels)
    counts = [int(np.sum(labels == k)) for k in np.unique(labels) if k >= 0]
    noise = int(np.sum(labels == -1))
    entropy = _entropy(counts)
    fraction = noise / n if n else 1.0
    return ClusterEvidence(len(counts), fraction, entropy,
                           _entropy(counts + [1] * noise),
                           float(np.clip((1.0 - fraction) / (1.0 + entropy), 0., 1.)))


def valid_embeddings(embeddings):
    arr = np.asarray(embeddings)
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] == 0:
        raise ValueError('Expected a nonempty N x D embedding matrix')
    if not np.issubdtype(arr.dtype, np.number) or not np.isfinite(arr).all():
        raise ValueError('Embeddings must be finite numbers')
    if np.any(np.linalg.norm(arr, axis=1) == 0):
        raise ValueError('Zero vectors have undefined cosine direction')
    return arr
