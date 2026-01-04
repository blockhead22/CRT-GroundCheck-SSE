"""
Phase 5 Tests: Lossless Offsets + Multi-Document Provenance

Tests for:
- Lossless chunker (exact reconstruction)
- Strict Invariant VI (equality, not containment)
- Multi-document provenance tracking
- Document registry functionality
"""

import pytest
from sse.chunker import chunk_text
from sse.document_registry import DocumentRegistry
from sse.multi_doc import MultiDocSSE


class TestLosslessChunker:
    """Test that chunker preserves exact character boundaries."""
    
    def test_chunk_reconstruction_exact(self):
        """Chunks must reconstruct exactly from original text."""
        text = "First sentence. Second sentence.\nThird sentence with\nnewlines."
        chunks = chunk_text(text, max_chars=100, doc_id="test")
        
        for chunk in chunks:
            reconstructed = text[chunk["start_char"]:chunk["end_char"]]
            assert reconstructed == chunk["text"], (
                f"Chunk {chunk['chunk_id']} failed exact reconstruction:\n"
                f"  Expected: {repr(chunk['text'])}\n"
                f"  Got:      {repr(reconstructed)}"
            )
    
    def test_whitespace_preservation(self):
        """Newlines, tabs, and spaces must be preserved exactly."""
        text = "Line 1.\n\nLine 3 after blank.\tTab here.  Double space."
        chunks = chunk_text(text, max_chars=100)
        
        # Verify no whitespace normalization
        full_chunked = "".join(c["text"] for c in chunks)
        assert "\n\n" in full_chunked, "Double newline lost"
        assert "\t" in full_chunked, "Tab character lost"
        assert "  " in full_chunked, "Double space lost"
    
    def test_no_stripping_boundaries(self):
        """Leading/trailing whitespace in chunks must be preserved."""
        text = "  Leading spaces. Trailing spaces.  "
        chunks = chunk_text(text, max_chars=100)
        
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk["text"] == text, "Chunk text was stripped"
        assert text[chunk["start_char"]:chunk["end_char"]] == text
    
    def test_doc_id_propagation(self):
        """Chunks must carry doc_id from chunking."""
        text = "Test sentence."
        doc_id = "test_doc_123"
        chunks = chunk_text(text, max_chars=100, doc_id=doc_id)
        
        assert all(c["doc_id"] == doc_id for c in chunks), (
            "doc_id not propagated to all chunks"
        )


class TestStrictInvariantVI:
    """Test that offset reconstruction is exact, not just 'contains'."""
    
    def test_offset_equality_not_containment(self):
        """Offsets must reconstruct with == not just 'in'."""
        from sse.embeddings import EmbeddingStore
        from sse.extractor import extract_claims_from_chunks
        
        text = "Sentence one. Sentence two."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)
        
        for claim in claims:
            for quote in claim["supporting_quotes"]:
                start = quote["start_char"]
                end = quote["end_char"]
                quote_text = quote.get("quote_text") or quote.get("text")
                reconstructed = text[start:end]
                
                # Must be EXACT match, not just contained
                assert reconstructed == quote_text, (
                    f"Strict Invariant VI violated: offset not exact\n"
                    f"  text[{start}:{end}] = {repr(reconstructed)}\n"
                    f"  quote_text = {repr(quote_text)}"
                )


class TestDocumentRegistry:
    """Test document registry for multi-doc provenance."""
    
    def test_add_document_returns_doc_id(self):
        """Adding document returns unique doc_id."""
        registry = DocumentRegistry()
        doc_id1 = registry.add_document("Text one", filename="file1.txt")
        doc_id2 = registry.add_document("Text two", filename="file2.txt")
        
        assert doc_id1 != doc_id2, "doc_ids must be unique"
        assert "doc0" in doc_id1
        assert "doc1" in doc_id2
    
    def test_get_document_metadata(self):
        """Registry stores and retrieves document metadata."""
        registry = DocumentRegistry()
        text = "Sample document text"
        filename = "sample.txt"
        doc_id = registry.add_document(text, filename=filename)
        
        doc = registry.get_document(doc_id)
        assert doc is not None
        assert doc["doc_id"] == doc_id
        assert doc["filename"] == filename
        assert doc["text"] == text
        assert doc["char_count"] == len(text)
    
    def test_find_by_filename(self):
        """Can lookup doc_id by filename."""
        registry = DocumentRegistry()
        filename = "unique_file.txt"
        doc_id = registry.add_document("Content", filename=filename)
        
        found_id = registry.find_by_filename(filename)
        assert found_id == doc_id
    
    def test_list_documents(self):
        """Can list all registered documents."""
        registry = DocumentRegistry()
        registry.add_document("Text 1", "file1.txt")
        registry.add_document("Text 2", "file2.txt")
        registry.add_document("Text 3", "file3.txt")
        
        docs = registry.list_documents()
        assert len(docs) == 3
        assert all("doc_id" in d for d in docs)
        assert all("filename" in d for d in docs)


class TestMultiDocSSE:
    """Test multi-document SSE pipeline with provenance."""
    
    def test_process_multiple_documents(self):
        """Pipeline processes multiple documents with provenance."""
        pipeline = MultiDocSSE()
        
        doc1_id = pipeline.add_document("The Earth is round.", "earth1.txt")
        doc2_id = pipeline.add_document("The Earth is flat.", "earth2.txt")
        
        pipeline.process_documents(max_chars=200, overlap=50)
        
        # Should have claims from both documents
        assert len(pipeline.claims) >= 2
        
        # Claims should have doc_id
        doc_ids = {c["doc_id"] for c in pipeline.claims}
        assert doc1_id in doc_ids
        assert doc2_id in doc_ids
    
    def test_get_claims_by_document(self):
        """Can filter claims by document."""
        pipeline = MultiDocSSE()
        
        doc1_id = pipeline.add_document("Exercise is good.", "health.txt")
        doc2_id = pipeline.add_document("Water is wet.", "science.txt")
        
        pipeline.process_documents()
        
        doc1_claims = pipeline.get_claims_by_document(doc1_id)
        doc2_claims = pipeline.get_claims_by_document(doc2_id)
        
        assert len(doc1_claims) > 0
        assert len(doc2_claims) > 0
        assert all(c["doc_id"] == doc1_id for c in doc1_claims)
        assert all(c["doc_id"] == doc2_id for c in doc2_claims)
    
    def test_export_index_with_provenance(self):
        """Exported index includes document metadata."""
        pipeline = MultiDocSSE()
        
        pipeline.add_document("Exercise is beneficial for health.", "doc1.txt")
        pipeline.add_document("Water boils at 100 degrees Celsius.", "doc2.txt")
        
        pipeline.process_documents()
        index = pipeline.export_index()
        
        # Index should have documents section
        assert "documents" in index
        assert len(index["documents"]) == 2
        
        # Claims should have doc_id
        assert all("doc_id" in c for c in index["claims"])
        
        # Stats should be present
        assert "stats" in index
        assert index["stats"]["document_count"] == 2
    
    def test_offset_reconstruction_multi_doc(self):
        """Offsets reconstruct correctly across all documents."""
        pipeline = MultiDocSSE()
        
        pipeline.add_document("First document with content.", "doc1.txt")
        pipeline.add_document("Second document with other content.", "doc2.txt")
        
        pipeline.process_documents()
        
        # Validate all offsets across all documents
        for claim in pipeline.claims:
            doc_id = claim["doc_id"]
            doc_text = pipeline.registry.get_text(doc_id)
            
            for quote in claim["supporting_quotes"]:
                start = quote["start_char"]
                end = quote["end_char"]
                quote_text = quote.get("quote_text") or quote.get("text")
                reconstructed = doc_text[start:end]
                
                assert reconstructed == quote_text, (
                    f"Multi-doc offset reconstruction failed for {claim['claim_id']} "
                    f"from {doc_id}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
