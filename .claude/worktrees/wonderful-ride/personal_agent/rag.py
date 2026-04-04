"""
RAG Engine with Memory Lineage Tracking

Combines vector search + SSE + internal observability.

Features:
- Semantic search over documents
- SSE contradiction detection
- Memory fusion tracking (invisible background hooks)
- Lineage logging (what memories + facts were combined when)
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any, Set
from pathlib import Path
import numpy as np

from sse import SSEClient
from .reasoning import ReasoningEngine, ReasoningMode


class MemoryLineage:
    """
    Internal tracking of what information was used where.
    
    This is invisible to the user but logged for debugging/auditing.
    Tracks: "At timestamp X, we combined memory Y with retrieved fact Z"
    """
    
    def __init__(self, lineage_db_path: str = "personal_agent/lineage.jsonl"):
        self.lineage_db_path = lineage_db_path
        Path(lineage_db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def log_fusion(
        self,
        query: str,
        memories_used: List[str],
        facts_retrieved: List[Dict],
        contradictions_found: List[Dict],
        reasoning_mode: str,
        session_id: str
    ) -> str:
        """
        Log a memory+fact fusion event.
        
        Returns fusion_id for tracing.
        """
        fusion_id = str(uuid.uuid4())[:8]
        
        event = {
            'fusion_id': fusion_id,
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'query': query,
            'reasoning_mode': reasoning_mode,
            'memories_used': memories_used,
            'facts_retrieved': [
                {
                    'source': f.get('source', 'unknown'),
                    'text_snippet': f.get('text', '')[:100],
                    'relevance_score': f.get('score', 0.0)
                }
                for f in facts_retrieved
            ],
            'contradictions_found': len(contradictions_found),
            'contradiction_details': [
                {
                    'claim_a': c.get('pair', {}).get('claim_id_a', ''),
                    'claim_b': c.get('pair', {}).get('claim_id_b', '')
                }
                for c in contradictions_found
            ]
        }
        
        # Append to JSONL
        with open(self.lineage_db_path, 'a') as f:
            f.write(json.dumps(event) + '\n')
        
        return fusion_id
    
    def get_lineage(self, fusion_id: str) -> Optional[Dict]:
        """Retrieve lineage for a specific fusion event."""
        if not Path(self.lineage_db_path).exists():
            return None
        
        with open(self.lineage_db_path, 'r') as f:
            for line in f:
                event = json.loads(line)
                if event['fusion_id'] == fusion_id:
                    return event
        return None
    
    def get_recent_fusions(self, limit: int = 10) -> List[Dict]:
        """Get recent fusion events."""
        if not Path(self.lineage_db_path).exists():
            return []
        
        events = []
        with open(self.lineage_db_path, 'r') as f:
            for line in f:
                events.append(json.loads(line))
        
        return events[-limit:]


class RAGEngine:
    """
    Retrieval-Augmented Generation with SSE and memory tracking.
    
    Architecture:
    1. User query → Vector search finds relevant docs
    2. SSE checks retrieved docs for contradictions
    3. Memory system adds learned context
    4. INTERNAL: Log what was combined (lineage tracking)
    5. Return context + contradictions + fusion_id
    """
    
    def __init__(
        self,
        vector_db_path: str = "personal_agent/vector_db",
        sse_indices_path: str = "personal_agent/indices",
        llm_client=None
    ):
        """Initialize RAG engine."""
        self.vector_db_path = vector_db_path
        self.sse_indices_path = sse_indices_path
        
        # Vector DB (ChromaDB)
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.chroma_client = chromadb.PersistentClient(
                path=vector_db_path,
                settings=Settings(anonymized_telemetry=False)
            )
            self.vector_db_available = True
        except ImportError:
            print("Warning: ChromaDB not installed. Install: pip install chromadb")
            self.chroma_client = None
            self.vector_db_available = False
        
        # Collections (one per knowledge base)
        self.collections = {}
        
        # SSE clients for contradiction detection
        self.sse_clients: Dict[str, SSEClient] = {}
        
        # Memory lineage tracker (background/invisible)
        self.lineage = MemoryLineage()
        
        # Reasoning engine (thinking modes)
        self.reasoning_engine = ReasoningEngine(llm_client=llm_client)
        
        # Session ID (for tracing)
        self.session_id = str(uuid.uuid4())[:8]
    
    def index_document(
        self,
        doc_path: str,
        collection_name: str = "main",
        chunk_size: int = 500
    ):
        """
        Index a document for RAG + SSE.
        
        Creates both:
        1. Vector embeddings (for semantic search)
        2. SSE index (for contradiction detection)
        """
        print(f"📚 Indexing {doc_path} into '{collection_name}'...")
        
        # Read document
        with open(doc_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Chunk document
        chunks = self._chunk_text(text, chunk_size)
        
        # 1. Vector indexing
        if self.vector_db_available:
            collection = self._get_or_create_collection(collection_name)
            
            # Add chunks to ChromaDB
            ids = [f"{collection_name}_{i}" for i in range(len(chunks))]
            collection.add(
                documents=chunks,
                ids=ids,
                metadatas=[{'source': doc_path, 'chunk_id': i} for i in range(len(chunks))]
            )
            
            print(f"  ✓ Vector indexed {len(chunks)} chunks")
        
        # 2. SSE indexing (contradiction detection)
        sse_output_dir = f"{self.sse_indices_path}/{collection_name}"
        Path(sse_output_dir).mkdir(parents=True, exist_ok=True)
        
        import os
        os.system(f'python -m sse.cli compress --input "{doc_path}" --out "{sse_output_dir}"')
        
        sse_index_path = f"{sse_output_dir}/index.json"
        if Path(sse_index_path).exists():
            self.sse_clients[collection_name] = SSEClient(sse_index_path)
            print(f"  ✓ SSE indexed with contradiction detection")
        
        print(f"✓ Indexing complete: {collection_name}")
    
    def query(
        self,
        user_query: str,
        collection_name: str = "main",
        k: int = 5,
        memory_context: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        RAG query with memory fusion and lineage tracking.
        
        Args:
            user_query: User's question
            collection_name: Which knowledge base to search
            k: Number of results to retrieve
            memory_context: Learned memories to include
        
        Returns:
            {
                'retrieved_docs': [...],      # Vector search results
                'contradictions': [...],      # SSE detected contradictions
                'memory_context': [...],      # Learned context used
                'fusion_id': '...',           # Internal tracking ID
                'reasoning_required': bool    # Whether deep thinking needed
            }
        """
        # Vector search
        retrieved_docs = self._vector_search(user_query, collection_name, k)
        
        # SSE contradiction check
        contradictions = self._check_contradictions(user_query, collection_name)
        
        # Determine if reasoning required
        reasoning_required = self._needs_reasoning(
            query=user_query,
            contradictions=contradictions,
            doc_count=len(retrieved_docs)
        )
        
        # INTERNAL: Log memory fusion (invisible to user)
        fusion_id = self.lineage.log_fusion(
            query=user_query,
            memories_used=memory_context or [],
            facts_retrieved=retrieved_docs,
            contradictions_found=contradictions,
            reasoning_mode="deep" if reasoning_required else "quick",
            session_id=self.session_id
        )
        
        return {
            'retrieved_docs': retrieved_docs,
            'contradictions': contradictions,
            'memory_context': memory_context or [],
            'fusion_id': fusion_id,  # For internal tracking
            'reasoning_required': reasoning_required
        }
    
    def _vector_search(
        self,
        query: str,
        collection_name: str,
        k: int
    ) -> List[Dict]:
        """Semantic search using vector embeddings."""
        if not self.vector_db_available:
            return []
        
        collection = self._get_or_create_collection(collection_name)
        
        if collection.count() == 0:
            return []
        
        results = collection.query(
            query_texts=[query],
            n_results=min(k, collection.count())
        )
        
        docs = []
        for i in range(len(results['documents'][0])):
            docs.append({
                'text': results['documents'][0][i],
                'source': results['metadatas'][0][i].get('source', 'unknown'),
                'score': results['distances'][0][i] if 'distances' in results else 1.0,
                'id': results['ids'][0][i]
            })
        
        return docs
    
    def _check_contradictions(
        self,
        query: str,
        collection_name: str
    ) -> List[Dict]:
        """Use SSE to find contradictions in retrieved context."""
        if collection_name not in self.sse_clients:
            return []
        
        client = self.sse_clients[collection_name]
        return client.find_contradictions_about(query)
    
    def _needs_reasoning(
        self,
        query: str,
        contradictions: List[Dict],
        doc_count: int
    ) -> bool:
        """
        Determine if query needs deep reasoning vs quick answer.
        
        Triggers deep reasoning if:
        - Contradictions found
        - Complex question (multiple sub-questions)
        - Low doc count (need to reason from limited info)
        """
        # Contradictions require reasoning
        if contradictions:
            return True
        
        # Complex queries (multiple "and", "or", "but")
        complexity_markers = ['and', 'but', 'however', 'although', 'or']
        if sum(query.lower().count(m) for m in complexity_markers) >= 2:
            return True
        
        # Few docs means need to reason more
        if doc_count < 2:
            return True
        
        # Question words suggest need for reasoning
        reasoning_words = ['why', 'how', 'explain', 'compare', 'analyze']
        if any(word in query.lower() for word in reasoning_words):
            return True
        
        return False
    
    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks for indexing."""
        # Simple chunking by sentences
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _get_or_create_collection(self, name: str):
        """Get or create ChromaDB collection."""
        if name not in self.collections:
            self.collections[name] = self.chroma_client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
        return self.collections[name]
    
    def get_fusion_lineage(self, fusion_id: str) -> Optional[Dict]:
        """
        Get lineage for a specific fusion event.
        
        Shows what memories/facts were combined.
        """
        return self.lineage.get_lineage(fusion_id)
    
    def get_recent_fusions(self, limit: int = 10) -> List[Dict]:
        """Get recent memory fusion events."""
        return self.lineage.get_recent_fusions(limit)
    
    def query_with_reasoning(
        self,
        user_query: str,
        collection_name: str = "main",
        k: int = 5,
        memory_context: Optional[List[str]] = None,
        mode: Optional[ReasoningMode] = None
    ) -> Dict[str, Any]:
        """
        Complete RAG query with reasoning engine.
        
        This is the main entry point combining:
        1. Vector search
        2. SSE contradiction detection
        3. Memory fusion tracking (internal)
        4. Advanced reasoning (thinking modes)
        
        Args:
            user_query: User's question
            collection_name: Knowledge base to search
            k: Number of results
            memory_context: Learned memories to include
            mode: Reasoning mode (auto-detected if None)
        
        Returns:
            {
                'answer': str,                 # Final answer
                'thinking': Optional[str],     # Visible thinking process
                'retrieved_docs': [...],       # Context used
                'contradictions': [...],       # Contradictions found
                'fusion_id': str,              # Internal tracking
                'reasoning_trace': {...},      # Internal reasoning trace
                'confidence': float,
                'mode': str                    # Reasoning mode used
            }
        """
        # Step 1: RAG query (retrieval + contradiction detection)
        rag_result = self.query(
            user_query=user_query,
            collection_name=collection_name,
            k=k,
            memory_context=memory_context
        )
        
        # Step 2: Reasoning (analyze + think + answer)
        reasoning_context = {
            'retrieved_docs': rag_result['retrieved_docs'],
            'contradictions': rag_result['contradictions'],
            'memory_context': rag_result['memory_context']
        }
        
        reasoning_result = self.reasoning_engine.reason(
            query=user_query,
            context=reasoning_context,
            mode=mode
        )
        
        # Step 3: Combine results
        return {
            **reasoning_result,
            'retrieved_docs': rag_result['retrieved_docs'],
            'contradictions': rag_result['contradictions'],
            'fusion_id': rag_result['fusion_id']
        }
    
    def get_reasoning_traces(self, limit: int = 10) -> List[Dict]:
        """Get recent reasoning traces (for analysis/debugging)."""
        return self.reasoning_engine.get_reasoning_traces(limit)
