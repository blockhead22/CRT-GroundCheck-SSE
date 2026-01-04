"""
SSE Interaction Layer (Phase 6, D2)

Read-only navigation of SSE indices. No synthesis, no decisions.

Enables querying, filtering, and exploring SSE data while respecting the Interface Contract.
- Permitted: Retrieve, search, filter, group, navigate, expose provenance
- Forbidden: Synthesize, pick winners, soften ambiguity, suppress information
"""

import json
import numpy as np
from typing import List, Dict, Optional, Any
from .embeddings import EmbeddingStore


class SSEBoundaryViolation(Exception):
    """Raised when an operation violates the SSE Interface Contract."""
    
    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(
            f"SSE Boundary Violation: {operation}\n"
            f"Reason: {reason}\n"
            f"SSE permits only: retrieval, search, filter, group, navigate, provenance, ambiguity exposure.\n"
            f"SSE forbids: synthesis, truth picking, ambiguity softening, paraphrasing, opinion, suppression."
        )


class SSENavigator:
    """
    Read-only navigator for SSE indices.
    
    Enables querying, filtering, and exploring claims and contradictions
    without synthesis, decision-making, or ambiguity softening.
    """
    
    def __init__(self, index_path: str, embed_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize the navigator with an SSE index.
        
        Args:
            index_path: Path to index.json
            embed_model: Embedding model for semantic search (must match original)
        """
        with open(index_path, "r", encoding="utf-8") as f:
            self.index = json.load(f)
        
        self.doc_id = self.index.get("doc_id", "unknown")
        self.timestamp = self.index.get("timestamp", "unknown")
        self.chunks = self.index.get("chunks", [])
        self.clusters = self.index.get("clusters", [])
        self.claims = self.index.get("claims", [])
        self.contradictions = self.index.get("contradictions", [])
        
        # Try to load embeddings if available (same directory as index)
        self.embeddings = None
        self.embed_store = None
        try:
            import os
            embed_path = os.path.join(os.path.dirname(index_path), "embeddings.npy")
            if os.path.exists(embed_path):
                self.embeddings = np.load(embed_path)
                self.embed_store = EmbeddingStore(embed_model)
        except Exception:
            pass  # Embeddings not available, semantic search will fail gracefully
    
    # ===== PERMITTED OPERATIONS =====
    
    def query(self, query_text: str, k: int = 5, method: str = "semantic") -> List[Dict]:
        """
        Search for claims matching a query.
        
        PERMITTED OPERATION: Retrieval + search
        
        Args:
            query_text: Query string (topic, keyword, or claim fragment)
            k: Number of results to return
            method: "semantic" (requires embeddings) or "keyword"
        
        Returns:
            List of claims with metadata, ordered by relevance
        """
        if method == "semantic":
            return self._semantic_search(query_text, k)
        elif method == "keyword":
            return self._keyword_search(query_text, k)
        else:
            raise ValueError(f"Unknown search method: {method}")
    
    def get_contradictions_for_topic(self, topic: str) -> List[Dict]:
        """
        Find all contradictions involving claims about a topic.
        
        PERMITTED OPERATION: Retrieval + filtering
        
        Args:
            topic: Topic keyword
        
        Returns:
            List of contradictions where at least one claim mentions the topic
        """
        # Find claims mentioning the topic
        relevant_claims = self._keyword_search(topic, k=len(self.claims))
        relevant_claim_ids = {c["claim_id"] for c in relevant_claims}
        
        # Find contradictions involving these claims
        result = []
        for contra in self.contradictions:
            claim_a_id = contra.get("pair", {}).get("claim_id_a")
            claim_b_id = contra.get("pair", {}).get("claim_id_b")
            
            if claim_a_id in relevant_claim_ids or claim_b_id in relevant_claim_ids:
                result.append(contra)
        
        return result
    
    def get_claim_by_id(self, claim_id: str) -> Optional[Dict]:
        """
        Retrieve a single claim by ID.
        
        PERMITTED OPERATION: Retrieval
        """
        for claim in self.claims:
            if claim.get("claim_id") == claim_id:
                return claim
        return None
    
    def get_provenance(self, claim_id: str) -> Dict:
        """
        Get the exact source text and offsets for a claim.
        
        PERMITTED OPERATION: Provenance tracking
        
        Args:
            claim_id: ID of the claim
        
        Returns:
            Dict with claim text, supporting quotes, and byte offsets
        """
        claim = self.get_claim_by_id(claim_id)
        if not claim:
            raise ValueError(f"Claim not found: {claim_id}")
        
        result = {
            "claim_id": claim_id,
            "claim_text": claim.get("claim_text"),
            "supporting_quotes": []
        }
        
        for quote in claim.get("supporting_quotes", []):
            chunk_id = quote.get("chunk_id")
            start = quote.get("start_char")
            end = quote.get("end_char")
            
            # Reconstruct from full text (concatenated chunks) for validation
            try:
                full_text = ''.join([c.get("text", "") for c in self.chunks])
                reconstructed = full_text[start:end]
            except Exception:
                reconstructed = None
            
            result["supporting_quotes"].append({
                "quote_text": quote.get("quote_text"),
                "reconstructed_text": reconstructed,
                "chunk_id": chunk_id,
                "start_char": start,
                "end_char": end,
                "char_count": end - start,
                "valid": reconstructed == quote.get("quote_text") if reconstructed else False
            })
        
        return result
    
    def get_ambiguity(self, claim_id: str) -> Dict:
        """
        Get ambiguity markers for a claim.
        
        PERMITTED OPERATION: Ambiguity exposure (display as-is, no softening)
        
        Args:
            claim_id: ID of the claim
        
        Returns:
            Dict with hedge score, conflict markers, open questions
        """
        claim = self.get_claim_by_id(claim_id)
        if not claim:
            raise ValueError(f"Claim not found: {claim_id}")
        
        return {
            "claim_id": claim_id,
            "claim_text": claim.get("claim_text"),
            "ambiguity": claim.get("ambiguity", {})
        }
    
    def get_cluster(self, cluster_id: str) -> Dict:
        """
        Get all claims in a semantic cluster.
        
        PERMITTED OPERATION: Retrieval + grouping
        
        Args:
            cluster_id: ID of the cluster
        
        Returns:
            Dict with cluster info and all member claims
        """
        cluster = next((c for c in self.clusters if c.get("cluster_id") == cluster_id), None)
        if not cluster:
            raise ValueError(f"Cluster not found: {cluster_id}")
        
        member_claims = []
        for claim_id in cluster.get("chunk_ids", []):
            claim = self.get_claim_by_id(claim_id)
            if claim:
                member_claims.append(claim)
        
        return {
            "cluster_id": cluster_id,
            "num_claims": len(member_claims),
            "claims": member_claims
        }
    
    def get_uncertain_claims(self, min_hedge: float = 0.5) -> List[Dict]:
        """
        Find claims with high hedge scores (uncertain language).
        
        PERMITTED OPERATION: Filtering by ambiguity metadata
        
        Args:
            min_hedge: Minimum hedge score threshold (0.0 to 1.0)
        
        Returns:
            List of claims where hedge_score >= min_hedge
        """
        result = []
        for claim in self.claims:
            hedge_score = claim.get("ambiguity", {}).get("hedge_score", 0.0)
            if hedge_score >= min_hedge:
                result.append(claim)
        
        return sorted(result, key=lambda c: c.get("ambiguity", {}).get("hedge_score", 0.0), reverse=True)
    
    def get_contradictions(self) -> List[Dict]:
        """
        Get all contradictions in the index.
        
        PERMITTED OPERATION: Retrieval
        
        Returns:
            List of all contradiction pairs
        """
        return self.contradictions
    
    def get_contradiction_by_pair(self, claim_id_a: str, claim_id_b: str) -> Optional[Dict]:
        """
        Get a specific contradiction by its claim pair.
        
        PERMITTED OPERATION: Retrieval
        """
        for contra in self.contradictions:
            pair = contra.get("pair", {})
            if ((pair.get("claim_id_a") == claim_id_a and pair.get("claim_id_b") == claim_id_b) or
                (pair.get("claim_id_a") == claim_id_b and pair.get("claim_id_b") == claim_id_a)):
                return contra
        return None
    
    def get_all_claims(self) -> List[Dict]:
        """
        Get all claims in the index.
        
        PERMITTED OPERATION: Retrieval
        """
        return self.claims
    
    def get_all_clusters(self) -> List[Dict]:
        """
        Get all clusters in the index.
        
        PERMITTED OPERATION: Retrieval
        """
        return self.clusters
    
    # ===== FORBIDDEN OPERATIONS (raise SSEBoundaryViolation) =====
    
    def synthesize_answer(self, *args, **kwargs):
        """FORBIDDEN: Synthesis of new claims."""
        raise SSEBoundaryViolation(
            "synthesize_answer",
            "SSE does not synthesize or generate answers. It exposes what is already extracted."
        )
    
    def answer_question(self, *args, **kwargs):
        """FORBIDDEN: QA-style answering."""
        raise SSEBoundaryViolation(
            "answer_question",
            "SSE is not a QA system. Use query() to find related claims instead."
        )
    
    def pick_best_claim(self, *args, **kwargs):
        """FORBIDDEN: Truth picking or confidence scoring."""
        raise SSEBoundaryViolation(
            "pick_best_claim",
            "SSE does not pick winners. All claims are preserved equally."
        )
    
    def resolve_contradiction(self, *args, **kwargs):
        """FORBIDDEN: Resolving contradictions."""
        raise SSEBoundaryViolation(
            "resolve_contradiction",
            "SSE does not resolve contradictions. Both sides are preserved."
        )
    
    def soften_ambiguity(self, *args, **kwargs):
        """FORBIDDEN: Removing or hiding uncertainty markers."""
        raise SSEBoundaryViolation(
            "soften_ambiguity",
            "SSE never softens ambiguity. Uncertainty is preserved and exposed."
        )
    
    def remove_hedge_language(self, *args, **kwargs):
        """FORBIDDEN: Removing uncertainty language."""
        raise SSEBoundaryViolation(
            "remove_hedge_language",
            "SSE preserves hedge language. It is information about the source."
        )
    
    def suppress_contradiction(self, *args, **kwargs):
        """FORBIDDEN: Hiding contradictions."""
        raise SSEBoundaryViolation(
            "suppress_contradiction",
            "SSE never suppresses contradictions. Both sides must always be shown."
        )
    
    def filter_low_confidence(self, *args, **kwargs):
        """FORBIDDEN: Silent filtering by confidence."""
        raise SSEBoundaryViolation(
            "filter_low_confidence",
            "SSE does not silently filter claims. If you filter, make it explicit."
        )
    
    # ===== DISPLAY FORMATTING (structural only) =====
    
    def format_claim(self, claim: Dict, include_provenance: bool = False) -> str:
        """
        Format a claim for display.
        
        PERMITTED OPERATION: Display (structural formatting only)
        
        No paraphrasing. Shows claim text and quote verbatim.
        """
        lines = []
        lines.append(f"Claim: {claim.get('claim_text')}")
        
        for quote in claim.get("supporting_quotes", []):
            lines.append(f"  Quote: \"{quote.get('quote_text')}\"")
            lines.append(f"  Offsets: [{quote.get('start_char')}:{quote.get('end_char')}]")
        
        ambiguity = claim.get("ambiguity", {})
        hedge = ambiguity.get("hedge_score", 0.0)
        if hedge > 0.0:
            lines.append(f"  Ambiguity: Hedge score {hedge:.2f} (source uses uncertain language)")
        
        if include_provenance:
            prov = self.get_provenance(claim.get("claim_id"))
            lines.append(f"  Supporting quotes: {len(prov.get('supporting_quotes', []))}")
        
        return "\n".join(lines)
    
    def format_contradiction(self, contradiction: Dict) -> str:
        """
        Format a contradiction for display.
        
        PERMITTED OPERATION: Display (structural formatting only)
        
        Shows both sides in full. No picking winners.
        """
        pair = contradiction.get("pair", {})
        claim_a_id = pair.get("claim_id_a")
        claim_b_id = pair.get("claim_id_b")
        
        claim_a = self.get_claim_by_id(claim_a_id)
        claim_b = self.get_claim_by_id(claim_b_id)
        
        lines = []
        lines.append("=" * 60)
        lines.append("CONTRADICTION DETECTED")
        lines.append("=" * 60)
        
        if claim_a:
            lines.append("\n[CLAIM A]")
            lines.append(self.format_claim(claim_a))
        
        if claim_b:
            lines.append("\n[CLAIM B]")
            lines.append(self.format_claim(claim_b))
        
        lines.append(f"\nLabel: {contradiction.get('label', 'contradiction')}")
        lines.append("\n⚠️  Both claims are shown in full.")
        lines.append("No interpretation is provided. You decide what this means.")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def format_search_results(self, claims: List[Dict], limit: int = None) -> str:
        """
        Format search results for display.
        
        PERMITTED OPERATION: Display (structural formatting only)
        """
        if limit:
            claims = claims[:limit]
        
        lines = []
        lines.append(f"Found {len(claims)} claims:\n")
        
        for i, claim in enumerate(claims, 1):
            lines.append(f"{i}. {claim.get('claim_text')}")
            for quote in claim.get("supporting_quotes", []):
                lines.append(f"   Quote: \"{quote.get('quote_text')}\"")
            lines.append("")
        
        return "\n".join(lines)
    
    # ===== INTERNAL SEARCH METHODS =====
    
    def _keyword_search(self, query: str, k: int) -> List[Dict]:
        """Search claims by keyword matching."""
        query_lower = query.lower()
        
        scored = []
        for claim in self.claims:
            claim_text = claim.get("claim_text", "").lower()
            quote_texts = " ".join([q.get("quote_text", "").lower() 
                                   for q in claim.get("supporting_quotes", [])])
            
            combined = f"{claim_text} {quote_texts}"
            
            # Simple scoring: count keyword matches
            score = combined.count(query_lower)
            if score > 0:
                scored.append((score, claim))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [claim for _, claim in scored[:k]]
    
    def _semantic_search(self, query: str, k: int) -> List[Dict]:
        """Search claims by semantic similarity (requires embeddings)."""
        if self.embeddings is None or self.embed_store is None:
            raise RuntimeError(
                "Semantic search requires embeddings. "
                "Embeddings not found in index directory."
            )
        
        # Embed the query
        query_embedding = self.embed_store.embed_texts([query])[0]
        
        # Compute similarity to all claims
        scored = []
        for i, claim in enumerate(self.claims):
            if i < len(self.embeddings):
                similarity = np.dot(query_embedding, self.embeddings[i])
                scored.append((similarity, claim))
        
        # Sort by similarity descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [claim for _, claim in scored[:k]]
    
    # ===== INDEX INFO =====
    
    def info(self) -> Dict:
        """Get basic information about the index."""
        return {
            "doc_id": self.doc_id,
            "timestamp": self.timestamp,
            "num_chunks": len(self.chunks),
            "num_claims": len(self.claims),
            "num_clusters": len(self.clusters),
            "num_contradictions": len(self.contradictions),
            "num_claims_with_ambiguity": sum(
                1 for c in self.claims 
                if c.get("ambiguity", {}).get("hedge_score", 0) > 0
            ),
            "has_embeddings": self.embeddings is not None
        }
