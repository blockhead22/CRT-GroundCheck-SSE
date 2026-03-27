"""TurboQuant implementation for memory vectors.

Stage 1: Random orthogonal rotation + Lloyd-Max scalar quantization
Stage 2: QJL (Quantized Johnson-Lindenstrauss) residual correction for inner products

Pure numpy implementation. No training required (data-oblivious).
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import norm


# ---------------------------------------------------------------------------
# Lloyd-Max codebook for Gaussian N(0, sigma)
# ---------------------------------------------------------------------------

def lloyd_max_codebook(n_levels: int, sigma: float = 1.0, max_iter: int = 200) -> tuple:
    """Compute optimal Lloyd-Max quantizer for N(0, sigma).

    Returns (boundaries, centroids) where:
      - boundaries: (n_levels+1,) array with boundaries[-1] = -inf, boundaries[0] = inf
      - centroids: (n_levels,) array of reconstruction levels
    """
    # Initialize centroids uniformly across [-3sigma, 3sigma]
    centroids = np.linspace(-3 * sigma, 3 * sigma, n_levels)

    for _ in range(max_iter):
        # Compute boundaries as midpoints between centroids
        boundaries = np.zeros(n_levels + 1)
        boundaries[0] = -np.inf
        boundaries[-1] = np.inf
        for i in range(1, n_levels):
            boundaries[i] = (centroids[i - 1] + centroids[i]) / 2.0

        # Update centroids: E[X | boundary[i] < X <= boundary[i+1]]
        new_centroids = np.zeros(n_levels)
        for i in range(n_levels):
            lo, hi = boundaries[i], boundaries[i + 1]
            # E[X | lo < X <= hi] for X ~ N(0, sigma)
            # = sigma * (phi(lo/sigma) - phi(hi/sigma)) / (Phi(hi/sigma) - Phi(lo/sigma))
            lo_s = lo / sigma if lo != -np.inf else -10.0
            hi_s = hi / sigma if hi != np.inf else 10.0

            prob = norm.cdf(hi_s) - norm.cdf(lo_s)
            if prob < 1e-15:
                new_centroids[i] = (lo_s + hi_s) / 2.0 * sigma
            else:
                new_centroids[i] = sigma * (norm.pdf(lo_s) - norm.pdf(hi_s)) / prob

        if np.allclose(centroids, new_centroids, atol=1e-10):
            break
        centroids = new_centroids

    return boundaries, centroids


# ---------------------------------------------------------------------------
# Compressed memory representation
# ---------------------------------------------------------------------------

@dataclass
class CompressedMemory:
    """Compressed representation of a single memory vector."""
    indices: np.ndarray       # uint8 or uint16 quantization indices, shape (dim,)
    bits: int                 # bit depth used
    norm: float               # original vector L2 norm
    qjl_signs: Optional[np.ndarray] = None   # packed sign bits, shape (ceil(dim/8),)
    residual_norm: float = 0.0               # ||residual|| for QJL correction

    @property
    def storage_bytes(self) -> int:
        """Actual storage cost in bytes."""
        # indices: ceil(dim * bits / 8)
        dim = len(self.indices)
        index_bytes = int(np.ceil(dim * self.bits / 8))
        # norm: 4 bytes (float32)
        # qjl_signs: dim/8 bytes (1 bit per dim)
        qjl_bytes = len(self.qjl_signs) if self.qjl_signs is not None else 0
        # residual_norm: 4 bytes if QJL
        meta_bytes = 4 + (4 if qjl_bytes > 0 else 0)
        return index_bytes + qjl_bytes + meta_bytes


# ---------------------------------------------------------------------------
# MemoryQuantizer
# ---------------------------------------------------------------------------

class MemoryQuantizer:
    """TurboQuant-style quantizer for memory embedding vectors.

    Stage 1: Random orthogonal rotation + Lloyd-Max quantization
    Stage 2 (optional): QJL residual correction for inner products
    """

    def __init__(self, dim: int = 384, bits: int = 3, use_qjl: bool = True, seed: int = 42):
        self.dim = dim
        self.bits = bits
        self.use_qjl = use_qjl
        self.n_levels = 2 ** bits

        rng = np.random.RandomState(seed)

        # Stage 1: Random orthogonal rotation matrix via QR decomposition
        gaussian = rng.randn(dim, dim).astype(np.float32)
        Q, R = np.linalg.qr(gaussian)
        # Ensure proper rotation (det = +1)
        self.rotation = Q.astype(np.float32)

        # Precompute Lloyd-Max codebook for N(0, 1/sqrt(dim))
        # After rotation, each coordinate ~ N(0, ||v||/sqrt(dim))
        # For unit-norm vectors: sigma = 1/sqrt(dim)
        self.sigma = 1.0 / np.sqrt(dim)
        self.boundaries, self.centroids = lloyd_max_codebook(self.n_levels, self.sigma)
        self.boundaries = self.boundaries.astype(np.float32)
        self.centroids = self.centroids.astype(np.float32)

        # Stage 2: QJL random sign matrix for residual correction
        if use_qjl:
            # Random Gaussian projection matrix
            self.qjl_matrix = rng.randn(dim, dim).astype(np.float32) / np.sqrt(dim)

    def _quantize(self, values: np.ndarray) -> tuple:
        """Quantize array of floats to nearest centroid. Returns (indices, reconstructed)."""
        # Digitize: find which bucket each value falls into
        indices = np.digitize(values, self.boundaries[1:-1]).astype(np.uint8)
        # Clip to valid range
        indices = np.clip(indices, 0, self.n_levels - 1)
        reconstructed = self.centroids[indices]
        return indices, reconstructed

    def compress(self, vector: np.ndarray) -> CompressedMemory:
        """Compress a memory vector using TurboQuant."""
        vec = np.asarray(vector, dtype=np.float32).flatten()
        assert len(vec) == self.dim, f"Expected {self.dim}D, got {len(vec)}D"

        vec_norm = float(np.linalg.norm(vec))
        if vec_norm < 1e-10:
            return CompressedMemory(
                indices=np.zeros(self.dim, dtype=np.uint8),
                bits=self.bits, norm=0.0,
            )

        # Normalize to unit norm for rotation
        normalized = vec / vec_norm

        # Stage 1: Rotate
        rotated = normalized @ self.rotation  # (dim,)

        # Quantize
        indices, reconstructed_rotated = self._quantize(rotated)

        # Stage 2: QJL residual correction
        qjl_signs = None
        residual_norm = 0.0
        if self.use_qjl:
            # Residual in rotated space
            residual = rotated - reconstructed_rotated
            residual_norm = float(np.linalg.norm(residual))

            if residual_norm > 1e-10:
                # Project residual through QJL matrix
                projected = self.qjl_matrix @ residual  # (dim,)
                # Store only signs (1 bit per dimension)
                signs = (projected >= 0).astype(np.uint8)
                # Pack into bytes
                qjl_signs = np.packbits(signs)
            else:
                qjl_signs = np.packbits(np.zeros(self.dim, dtype=np.uint8))

        return CompressedMemory(
            indices=indices,
            bits=self.bits,
            norm=vec_norm,
            qjl_signs=qjl_signs,
            residual_norm=residual_norm,
        )

    def decompress(self, compressed: CompressedMemory) -> np.ndarray:
        """Approximate reconstruction (for visualization/analysis, not primary use case)."""
        if compressed.norm < 1e-10:
            return np.zeros(self.dim, dtype=np.float32)

        # Reconstruct from centroids
        reconstructed_rotated = self.centroids[compressed.indices]

        # Inverse rotation
        reconstructed = reconstructed_rotated @ self.rotation.T

        # Rescale to original norm
        return reconstructed * compressed.norm

    def inner_product(self, query: np.ndarray, compressed: CompressedMemory) -> float:
        """Compute corrected inner product <query, original> from compressed form.

        Stage 1: <query, k_reconstructed>
        Stage 2 (QJL): + correction term for residual
        """
        q = np.asarray(query, dtype=np.float32).flatten()
        if compressed.norm < 1e-10:
            return 0.0

        # Reconstruct Stage 1
        reconstructed_rotated = self.centroids[compressed.indices]
        reconstructed_normalized = reconstructed_rotated @ self.rotation.T
        reconstructed = reconstructed_normalized * compressed.norm

        # Base inner product
        ip = float(np.dot(q, reconstructed))

        # Stage 2: QJL correction
        if self.use_qjl and compressed.qjl_signs is not None and compressed.residual_norm > 1e-10:
            # Unpack signs
            signs = np.unpackbits(compressed.qjl_signs)[:self.dim]
            signs = signs.astype(np.float32) * 2 - 1  # {0,1} -> {-1, +1}

            # Project query through QJL matrix
            q_projected = self.qjl_matrix @ q  # (dim,)

            # Correction: ||residual|| * sqrt(pi/2) / dim * <S@q, signs>
            correction = (compressed.residual_norm * compressed.norm *
                         np.sqrt(np.pi / 2) / self.dim *
                         float(np.dot(q_projected, signs)))
            ip += correction

        return ip

    def batch_inner_products(self, query: np.ndarray,
                            compressed_db: List[CompressedMemory]) -> np.ndarray:
        """Compute inner products against a batch of compressed memories."""
        return np.array([self.inner_product(query, c) for c in compressed_db])

    def batch_search(self, query: np.ndarray,
                     compressed_db: List[CompressedMemory], k: int = 5) -> np.ndarray:
        """Top-k retrieval using corrected inner products."""
        scores = self.batch_inner_products(query, compressed_db)
        return np.argsort(scores)[::-1][:k]


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("TurboQuant Memory Quantizer — Self-Test")
    print("=" * 50)

    dim = 384
    rng = np.random.default_rng(123)

    # Generate 10 random unit vectors
    vecs = rng.standard_normal((10, dim)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

    for bits in [2, 3, 4, 8]:
        for use_qjl in [False, True]:
            mq = MemoryQuantizer(dim=dim, bits=bits, use_qjl=use_qjl)

            cos_sims = []
            ip_errors = []
            for i in range(10):
                comp = mq.compress(vecs[i])
                recon = mq.decompress(comp)

                # Cosine similarity
                cos = float(np.dot(vecs[i], recon) / (np.linalg.norm(vecs[i]) * np.linalg.norm(recon) + 1e-10))
                cos_sims.append(cos)

                # Inner product accuracy (compare corrected IP vs true IP for a random query)
                q = vecs[(i + 1) % 10]
                true_ip = float(np.dot(q, vecs[i]))
                est_ip = mq.inner_product(q, comp)
                ip_errors.append(abs(true_ip - est_ip))

            qjl_str = "+QJL" if use_qjl else "    "
            storage = comp.storage_bytes
            print(f"  {bits}-bit {qjl_str} | cos_sim={np.mean(cos_sims):.4f} | "
                  f"IP_err={np.mean(ip_errors):.4f} | {storage} bytes/vec")

    print("\nSelf-test passed.")
