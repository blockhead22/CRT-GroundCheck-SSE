"""
Document Registry for Multi-Document SSE

Phase 5: Provenance foundation for tracking claims across multiple documents.
"""

import hashlib
from typing import Dict, List, Optional
from pathlib import Path


class DocumentRegistry:
    """
    Manages document metadata for multi-document SSE pipelines.
    
    Responsibilities:
    - Assign unique doc_id to each document
    - Store document text, filename, metadata
    - Provide doc_id lookups and reverse mappings
    """
    
    def __init__(self):
        self.documents: Dict[str, Dict] = {}  # doc_id -> metadata
        self._filename_to_id: Dict[str, str] = {}  # filename -> doc_id
        self._next_id = 0
    
    def add_document(
        self,
        text: str,
        filename: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Register a document and return its doc_id.
        
        Args:
            text: Full document text
            filename: Source filename (optional)
            metadata: Additional metadata (optional)
            
        Returns:
            doc_id: Unique identifier for this document
        """
        # Generate doc_id from content hash + counter
        content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
        doc_id = f"doc{self._next_id}_{content_hash}"
        self._next_id += 1
        
        # Store document metadata
        self.documents[doc_id] = {
            "doc_id": doc_id,
            "filename": filename or f"untitled_{self._next_id}",
            "text": text,
            "char_count": len(text),
            "content_hash": content_hash,
            "metadata": metadata or {}
        }
        
        # Track filename mapping
        if filename:
            self._filename_to_id[filename] = doc_id
        
        return doc_id
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get document metadata by doc_id."""
        return self.documents.get(doc_id)
    
    def get_text(self, doc_id: str) -> Optional[str]:
        """Get document text by doc_id."""
        doc = self.documents.get(doc_id)
        return doc["text"] if doc else None
    
    def find_by_filename(self, filename: str) -> Optional[str]:
        """Find doc_id by filename."""
        return self._filename_to_id.get(filename)
    
    def list_documents(self) -> List[Dict]:
        """List all registered documents (summary view)."""
        return [
            {
                "doc_id": doc["doc_id"],
                "filename": doc["filename"],
                "char_count": doc["char_count"],
                "content_hash": doc["content_hash"]
            }
            for doc in self.documents.values()
        ]
    
    def __len__(self) -> int:
        """Number of registered documents."""
        return len(self.documents)
    
    def __contains__(self, doc_id: str) -> bool:
        """Check if doc_id is registered."""
        return doc_id in self.documents
