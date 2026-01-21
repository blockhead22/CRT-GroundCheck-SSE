"""
Multi-Document SSE Pipeline

Phase 5: Orchestrates SSE processing across multiple documents with provenance tracking.
"""

from typing import List, Dict, Optional
from pathlib import Path
import numpy as np

from .document_registry import DocumentRegistry
from .chunker import chunk_text
from .embeddings import EmbeddingStore
from .extractor import extract_claims_from_chunks
from .contradictions import detect_contradictions
from .clustering import cluster_embeddings
from .ambiguity import analyze_ambiguity_for_claims


class MultiDocSSE:
    """
    Multi-document SSE pipeline with provenance tracking.
    
    Features:
    - Process multiple documents in one index
    - Track doc_id for all claims/contradictions/clusters
    - Support within-document and (future) cross-document contradictions
    """
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.registry = DocumentRegistry()
        self.emb_store = EmbeddingStore(embedding_model)
        
        # Pipeline artifacts (across all documents)
        self.chunks: List[Dict] = []
        self.claims: List[Dict] = []
        self.contradictions: List[Dict] = []
        self.clusters: List[Dict] = []
        
        # Embeddings
        self.chunk_embeddings: Optional[np.ndarray] = None
        self.claim_embeddings: Optional[np.ndarray] = None
    
    def add_document(self, text: str, filename: Optional[str] = None) -> str:
        """Register a document. Returns doc_id."""
        return self.registry.add_document(text, filename)
    
    def add_document_from_file(self, filepath: str) -> str:
        """Load and register a document from file."""
        path = Path(filepath)
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        return self.add_document(text, filename=path.name)
    
    def process_documents(
        self,
        max_chars: int = 500,
        overlap: int = 100,
        use_ollama: bool = False
    ):
        """
        Run full SSE pipeline on all registered documents.
        
        Steps:
        1. Chunk all documents (preserving doc_id)
        2. Embed chunks
        3. Extract claims (preserving doc_id)
        4. Embed claims
        5. Detect contradictions (within-doc only in Phase 5)
        6. Cluster claims
        7. Analyze ambiguity
        """
        if len(self.registry) == 0:
            raise ValueError("No documents registered. Use add_document() first.")
        
        # Step 1: Chunk all documents
        self.chunks = []
        for doc_id, doc_meta in self.registry.documents.items():
            doc_chunks = chunk_text(
                doc_meta["text"],
                max_chars=max_chars,
                overlap=overlap,
                doc_id=doc_id
            )
            self.chunks.extend(doc_chunks)
        
        # Step 2: Embed chunks
        chunk_texts = [c["text"] for c in self.chunks]
        self.chunk_embeddings = self.emb_store.embed_texts(chunk_texts)
        
        # Step 3: Extract claims
        self.claims = extract_claims_from_chunks(self.chunks, self.chunk_embeddings)
        
        # Step 4: Embed claims
        claim_texts = [c["claim_text"] for c in self.claims]
        self.claim_embeddings = self.emb_store.embed_texts(claim_texts)
        
        # Step 5: Detect contradictions (within-doc only for Phase 5)
        # Future: add cross_document=True flag for cross-doc contradictions
        self.contradictions = detect_contradictions(
            self.claims,
            self.claim_embeddings,
            use_ollama=use_ollama
        )
        
        # Step 6: Cluster claims
        self.clusters = cluster_embeddings(
            self.claim_embeddings,
            method="hdbscan",
            min_cluster_size=2
        )
        
        # Step 7: Analyze ambiguity
        self.claims = analyze_ambiguity_for_claims(self.claims)
    
    def export_index(self) -> Dict:
        """
        Export complete SSE index with provenance metadata.
        
        Returns:
            Full index containing documents, chunks, claims, contradictions, clusters
        """
        return {
            "documents": self.registry.list_documents(),
            "chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "doc_id": c["doc_id"],
                    "start_char": c["start_char"],
                    "end_char": c["end_char"],
                    "char_count": len(c["text"])
                }
                for c in self.chunks
            ],
            "claims": [
                {
                    "claim_id": c["claim_id"],
                    "claim_text": c["claim_text"],
                    "doc_id": c["doc_id"],
                    "supporting_quotes": c["supporting_quotes"],
                    "ambiguity": c.get("ambiguity", {})
                }
                for c in self.claims
            ],
            "contradictions": self.contradictions,
            "clusters": self.clusters,
            "stats": {
                "document_count": len(self.registry),
                "chunk_count": len(self.chunks),
                "claim_count": len(self.claims),
                "contradiction_count": len(self.contradictions),
                "cluster_count": len(self.clusters)
            }
        }
    
    def get_claims_by_document(self, doc_id: str) -> List[Dict]:
        """Get all claims from a specific document."""
        return [c for c in self.claims if c.get("doc_id") == doc_id]
    
    def get_contradictions_by_document(self, doc_id: str) -> List[Dict]:
        """Get contradictions where at least one claim is from this document."""
        doc_claim_ids = {c["claim_id"] for c in self.get_claims_by_document(doc_id)}
        return [
            cont for cont in self.contradictions
            if cont["pair"]["claim_id_a"] in doc_claim_ids
            or cont["pair"]["claim_id_b"] in doc_claim_ids
        ]
