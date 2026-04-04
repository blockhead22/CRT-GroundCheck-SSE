"""
Real Embeddings for CRT

Uses sentence-transformers for semantic embeddings.
Replaces placeholder hash-based vectors with real AI embeddings.
"""

import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer


class EmbeddingEngine:
    """Handles text encoding to semantic vectors."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding model.
        
        Models:
        - all-MiniLM-L6-v2: Fast, 384 dims, good quality (default)
        - all-mpnet-base-v2: Slower, 768 dims, better quality
        - paraphrase-MiniLM-L6-v2: Good for similarity
        """
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Lazy load the model."""
        if self.model is None:
            print(f"Loading embedding model: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            print(f"Model loaded ({self.model.get_sentence_embedding_dimension()} dimensions)")
    
    def encode(self, text: str) -> np.ndarray:
        """
        Encode text to semantic vector.
        
        Returns:
            Normalized numpy array of embeddings
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(self.model.get_sentence_embedding_dimension())
        
        # Get embedding
        embedding = self.model.encode(text, convert_to_numpy=True)
        
        # Ensure it's normalized
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def encode_batch(self, texts: list) -> np.ndarray:
        """Encode multiple texts efficiently."""
        if not texts:
            return np.array([])
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        
        # Normalize each
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        embeddings = embeddings / norms
        
        return embeddings
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self.model.get_sentence_embedding_dimension()


# Global instance (lazy loaded)
_global_encoder: Optional[EmbeddingEngine] = None


def get_encoder(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingEngine:
    """Get or create global encoder instance."""
    global _global_encoder
    if _global_encoder is None or _global_encoder.model_name != model_name:
        _global_encoder = EmbeddingEngine(model_name)
    return _global_encoder


def encode_text(text: str) -> np.ndarray:
    """
    Convenience function to encode text.
    
    Uses global encoder instance.
    """
    encoder = get_encoder()
    return encoder.encode(text)
