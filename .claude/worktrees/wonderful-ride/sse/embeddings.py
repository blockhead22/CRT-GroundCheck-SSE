import numpy as np
from typing import List, Callable


class EmbeddingStore:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", embed_fn: Callable = None):
        self.model_name = model_name
        self.embed_fn = embed_fn
        self._model = None
        if embed_fn is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(model_name)
                self.embed_fn = lambda texts: self._model.encode(list(texts), show_progress_bar=False)
            except Exception:
                from sklearn.feature_extraction.text import TfidfVectorizer
                self._tfidf = TfidfVectorizer(max_features=512)
                def fit_and_embed(texts):
                    X = self._tfidf.fit_transform(texts).toarray()
                    return X.astype("float32")
                self.embed_fn = fit_and_embed

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        vecs = self.embed_fn(texts)
        arr = np.asarray(vecs, dtype="float32")
        # normalize
        norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
        return arr / norms

    def save(self, path: str, vectors: np.ndarray):
        np.save(path, vectors.astype("float32"))

    def load(self, path: str) -> np.ndarray:
        return np.load(path)
