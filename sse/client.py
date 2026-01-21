"""
SSE Client Library (Phase 6.2)

Constitutional governor for SSE - makes Phase D+ operations impossible.

This client wraps SSENavigator to expose ONLY permitted Phase A-C operations.
Forbidden operations cannot be called (AttributeError at import time, not runtime).

DESIGN PRINCIPLE: If a method exists on this client, it's permitted.
                  If a method doesn't exist, attempting to call it fails IMMEDIATELY.
                  No getattr() hacks. No reflection. No way around this.
"""

from typing import List, Dict, Optional, Any
from .interaction_layer import SSENavigator, SSEBoundaryViolation
from .coherence import CoherenceTracker


class SSEClient:
    """
    Safe client for SSE indices - prevents Phase 6 boundary violations.
    
    This client provides constitutional enforcement of SSE's boundaries:
    - Exposes only retrieval, search, filter, group, navigate, provenance
    - Forbidden operations literally don't exist as methods
    - Type hints guide IDE autocomplete to only show permitted operations
    - No runtime "maybe this works" - if it compiles, it's permitted
    
    Example:
        >>> client = SSEClient("index.json")
        >>> 
        >>> # These work ✅
        >>> claims = client.get_all_claims()
        >>> contradictions = client.get_contradictions_for_claim("clm0")
        >>> related = client.find_related_claims("clm0")
        >>> 
        >>> # These fail at call time ❌
        >>> client.add_confidence_score(...)        # AttributeError
        >>> client.pick_winner(...)                 # AttributeError
        >>> client.synthesize_answer(...)           # AttributeError
        >>> client.learn_from_feedback(...)         # AttributeError
    """
    
    def __init__(self, index_path: str, embed_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize SSE client.
        
        Args:
            index_path: Path to index.json
            embed_model: Embedding model name (must match what was used during indexing)
        """
        # Wrap the navigator - all methods are proxied through this client
        self._navigator = SSENavigator(index_path, embed_model)
        
        # Expose metadata for inspection
        self.doc_id = self._navigator.doc_id
        self.timestamp = self._navigator.timestamp
    
    # ========================================================================
    # PERMITTED OPERATIONS - Phase A: Observation
    # ========================================================================
    
    def get_all_claims(self) -> List[Dict]:
        """
        Retrieve all claims in the index.
        
        PERMITTED: Retrieval
        
        Returns:
            List of all claims with metadata and provenance
        """
        return self._navigator.get_all_claims()
    
    def get_claim_by_id(self, claim_id: str) -> Optional[Dict]:
        """
        Retrieve a specific claim by ID.
        
        PERMITTED: Retrieval
        
        Args:
            claim_id: Claim identifier (e.g., "clm0", "clm1")
        
        Returns:
            Claim dict with text, quotes, offsets, ambiguity markers
            Returns None if claim not found
        """
        return self._navigator.get_claim_by_id(claim_id)
    
    def get_all_contradictions(self) -> List[Dict]:
        """
        Retrieve all contradictions in the index.
        
        PERMITTED: Retrieval
        
        Returns:
            List of all contradiction pairs (both sides shown in full)
        """
        return self._navigator.get_contradictions()
    
    def get_contradiction_between(self, claim_id_a: str, claim_id_b: str) -> Optional[Dict]:
        """
        Get contradiction relationship between two specific claims.
        
        PERMITTED: Retrieval
        
        Args:
            claim_id_a: First claim ID
            claim_id_b: Second claim ID
        
        Returns:
            Contradiction dict if these claims contradict, None otherwise
        """
        return self._navigator.get_contradiction_by_pair(claim_id_a, claim_id_b)
    
    def get_provenance(self, claim_id: str) -> Dict:
        """
        Get exact source text and byte offsets for a claim.
        
        PERMITTED: Provenance tracking
        
        Args:
            claim_id: Claim to retrieve provenance for
        
        Returns:
            Dict with:
            - claim_text: The extracted claim
            - supporting_quotes: List of quotes with exact offsets
            - Each quote includes: quote_text, chunk_id, start_char, end_char
        
        This enables verification that claims are grounded in source text.
        """
        return self._navigator.get_provenance(claim_id)
    
    # ========================================================================
    # PERMITTED OPERATIONS - Phase B: Search & Filter
    # ========================================================================
    
    def search(self, query: str, k: int = 5, method: str = "semantic") -> List[Dict]:
        """
        Search for claims matching a query.
        
        PERMITTED: Search
        
        Args:
            query: Search query (keyword or semantic)
            k: Number of results to return
            method: "semantic" (embedding-based) or "keyword" (text matching)
        
        Returns:
            List of claims ordered by relevance
        
        Note: This searches existing claims. It does NOT synthesize answers.
        """
        return self._navigator.query(query, k=k, method=method)
    
    def find_contradictions_about(self, topic: str) -> List[Dict]:
        """
        Find all contradictions involving claims about a topic.
        
        PERMITTED: Filtering
        
        Args:
            topic: Topic keyword or phrase
        
        Returns:
            List of contradictions where at least one claim mentions the topic
        """
        return self._navigator.get_contradictions_for_topic(topic)
    
    def find_uncertain_claims(self, min_hedge: float = 0.5) -> List[Dict]:
        """
        Find claims with uncertain language (high hedge scores).
        
        PERMITTED: Filtering by ambiguity metadata
        
        Args:
            min_hedge: Minimum hedge score (0.0 to 1.0)
                      Higher scores = more uncertain language
        
        Returns:
            Claims with hedge_score >= min_hedge, sorted by uncertainty
        
        Note: This EXPOSES uncertainty, does not SOFTEN it.
              Hedge language is preserved, not removed.
        """
        return self._navigator.get_uncertain_claims(min_hedge=min_hedge)
    
    def get_ambiguity_markers(self, claim_id: str) -> Dict:
        """
        Get ambiguity metadata for a specific claim.
        
        PERMITTED: Ambiguity exposure
        
        Args:
            claim_id: Claim to analyze
        
        Returns:
            Dict with:
            - hedge_score: Degree of uncertain language
            - conflict_markers: Markers of internal disagreement
            - open_questions: Questions embedded in the claim
        
        Note: This shows ambiguity as-is. SSE never softens or removes it.
        """
        return self._navigator.get_ambiguity(claim_id)
    
    # ========================================================================
    # PERMITTED OPERATIONS - Phase C: Grouping & Navigation
    # ========================================================================
    
    def get_all_clusters(self) -> List[Dict]:
        """
        Get all semantic clusters.
        
        PERMITTED: Grouping/retrieval
        
        Returns:
            List of clusters (topically similar claims)
        """
        return self._navigator.get_all_clusters()
    
    def get_cluster(self, cluster_id: str) -> Dict:
        """
        Get all claims in a semantic cluster.
        
        PERMITTED: Grouping
        
        Args:
            cluster_id: Cluster identifier
        
        Returns:
            Dict with cluster metadata and all member claims
        """
        return self._navigator.get_cluster(cluster_id)
    
    def find_related_claims(self, claim_id: str) -> List[Dict]:
        """
        Find claims semantically related to a given claim.
        
        PERMITTED: Navigation
        
        Args:
            claim_id: Starting claim
        
        Returns:
            Claims in the same cluster as this claim
        
        Note: This shows topical similarity, NOT truth similarity.
              Related claims may contradict each other.
        """
        claim = self.get_claim_by_id(claim_id)
        if not claim:
            return []
        
        # Find which cluster this claim belongs to
        for cluster in self.get_all_clusters():
            if claim_id in cluster.get("chunk_ids", []):
                return self.get_cluster(cluster["cluster_id"])["claims"]
        
        return []
    
    # ========================================================================
    # PERMITTED OPERATIONS - Coherence Tracking (Observation Only)
    # ========================================================================
    
    def get_disagreement_patterns(self, claim_id: Optional[str] = None) -> List[Dict]:
        """
        Get disagreement relationships in the index.
        
        PERMITTED: Disagreement observation (no resolution)
        
        Args:
            claim_id: Optional - filter to disagreements involving this claim
        
        Returns:
            List of disagreement edges showing how claims relate
        
        CRITICAL: This observes disagreement patterns.
                  It does NOT resolve them or pick winners.
        """
        return self._navigator.get_disagreement_edges(claim_id)
    
    def get_claim_coherence(self, claim_id: str) -> Optional[Dict]:
        """
        Get coherence metadata for a claim.
        
        PERMITTED: Observation
        
        Args:
            claim_id: Claim to analyze
        
        Returns:
            Dict with:
            - total_relationships: How many other claims this relates to
            - contradictions: Count of direct contradictions
            - conflicts: Count of disagreements
            - agreements: Count of aligned claims
        
        CRITICAL: This is metadata about disagreement structure.
                  It does NOT resolve the disagreements.
        """
        return self._navigator.get_claim_coherence(claim_id)
    
    def get_disagreement_clusters(self) -> List[Dict]:
        """
        Get clusters of mutually disagreeing claims.
        
        PERMITTED: Grouping by disagreement patterns
        
        Returns:
            List of disagreement clusters
        
        CRITICAL: Shows disagreement structure without resolving.
        """
        return self._navigator.coherence.get_disagreement_clusters()
    
    # ========================================================================
    # PERMITTED OPERATIONS - Display Formatting
    # ========================================================================
    
    def format_claim(self, claim: Dict, include_provenance: bool = False) -> str:
        """
        Format a claim for human-readable display.
        
        PERMITTED: Display formatting (structural only)
        
        Args:
            claim: Claim dict
            include_provenance: Whether to include source quote details
        
        Returns:
            Formatted string showing claim text and metadata
        
        Note: This is structural formatting only.
              No paraphrasing. Shows claim verbatim.
        """
        return self._navigator.format_claim(claim, include_provenance)
    
    def format_contradiction(self, contradiction: Dict) -> str:
        """
        Format a contradiction for human-readable display.
        
        PERMITTED: Display formatting (structural only)
        
        Args:
            contradiction: Contradiction dict
        
        Returns:
            Formatted string showing both claims in full
        
        Note: Both sides shown. No winner picking. No resolution.
        """
        return self._navigator.format_contradiction(contradiction)
    
    def format_search_results(self, claims: List[Dict], limit: Optional[int] = None) -> str:
        """
        Format search results for display.
        
        PERMITTED: Display formatting
        
        Args:
            claims: List of claims
            limit: Optional limit on number shown
        
        Returns:
            Formatted string of search results
        """
        return self._navigator.format_search_results(claims, limit)
    
    # ========================================================================
    # EXPLICIT DENIALS - These methods don't exist, but we document why
    # ========================================================================
    
    # The following methods DO NOT EXIST and CANNOT BE CALLED.
    # Attempting to call them raises AttributeError immediately.
    #
    # This is intentional. This is the governor. This is the constitutional limit.
    #
    # FORBIDDEN OPERATIONS (Phase D - Outcome Measurement):
    # - add_confidence_score()          ❌ Phase D - would enable ranking
    # - track_user_action()             ❌ Phase D - outcome measurement
    # - measure_engagement()            ❌ Phase D - behavioral tracking
    # - record_recommendation_outcome() ❌ Phase D - learning from results
    # - learn_from_feedback()           ❌ Phase D - model updates
    # - get_recommendation_success()    ❌ Phase D - outcome queries
    #
    # FORBIDDEN OPERATIONS (Phase D/E - Synthesis & Resolution):
    # - synthesize_answer()             ❌ Creates new claims
    # - pick_winner()                   ❌ Resolves contradictions
    # - pick_best_claim()               ❌ Truth ranking
    # - resolve_contradiction()         ❌ Picks sides
    # - merge_claims()                  ❌ Synthesis
    # - paraphrase_claim()              ❌ Modifies source
    #
    # FORBIDDEN OPERATIONS (Phase D/E - Filtering):
    # - filter_high_confidence_only()   ❌ Silent suppression
    # - filter_low_confidence()         ❌ Silent suppression
    # - suppress_contradiction()        ❌ Hiding disagreement
    # - hide_ambiguity()                ❌ Softening uncertainty
    #
    # FORBIDDEN OPERATIONS (Phase D/E - State & Learning):
    # - save_session_state()            ❌ Persistence across queries
    # - remember_preferences()          ❌ User modeling
    # - adapt_to_user()                 ❌ Behavioral learning
    # - personalize_results()           ❌ User-specific optimization
    #
    # IF YOU NEED THESE OPERATIONS, YOU DON'T NEED SSE.
    # You need an agent. SSE is not an agent. SSE is an observation tool.
    #
    # The absence of these methods is not a bug. It's the design.
    # This is the governor. This is where Phase C ends.
    
    def __getattr__(self, name: str) -> Any:
        """
        Intercept attempts to call non-existent methods.
        
        This provides helpful error messages for forbidden operations.
        """
        # Check if this is a known forbidden operation
        forbidden = {
            'add_confidence_score': 'Phase D violation: SSE does not rank claims by confidence',
            'track_user_action': 'Phase D violation: SSE does not measure user behavior',
            'measure_engagement': 'Phase D violation: SSE does not track engagement',
            'record_recommendation_outcome': 'Phase D violation: SSE does not learn from outcomes',
            'learn_from_feedback': 'Phase D violation: SSE does not update models',
            'get_recommendation_success': 'Phase D violation: SSE does not measure success',
            'synthesize_answer': 'Phase E violation: SSE does not generate new claims',
            'pick_winner': 'Phase E violation: SSE does not resolve contradictions',
            'pick_best_claim': 'Phase E violation: SSE does not rank truth',
            'resolve_contradiction': 'Phase E violation: SSE does not pick sides',
            'merge_claims': 'Phase E violation: SSE does not synthesize',
            'paraphrase_claim': 'Phase E violation: SSE preserves source text',
            'filter_high_confidence_only': 'Phase D violation: SSE does not silently filter',
            'filter_low_confidence': 'Phase D violation: SSE does not suppress low-confidence claims',
            'suppress_contradiction': 'Phase D violation: SSE never hides contradictions',
            'hide_ambiguity': 'Phase E violation: SSE never softens uncertainty',
            'save_session_state': 'Phase D violation: SSE is stateless',
            'remember_preferences': 'Phase E violation: SSE does not model users',
            'adapt_to_user': 'Phase E violation: SSE does not learn user patterns',
            'personalize_results': 'Phase E violation: SSE does not customize per user'
        }
        
        if name in forbidden:
            raise AttributeError(
                f"\n{'='*70}\n"
                f"SSE Client Boundary Violation\n"
                f"{'='*70}\n"
                f"Method: {name}()\n"
                f"Reason: {forbidden[name]}\n"
                f"\n"
                f"SSE is an observation tool, not an optimization system.\n"
                f"This operation violates Phase 6 boundaries.\n"
                f"\n"
                f"If you need this operation, you don't need SSE.\n"
                f"You need an agent. SSE is not an agent.\n"
                f"{'='*70}\n"
            )
        
        # Unknown attribute
        raise AttributeError(
            f"SSEClient has no attribute '{name}'. "
            f"See dir(client) for available methods."
        )
    
    def __dir__(self) -> List[str]:
        """
        Expose only permitted methods to IDE autocomplete.
        
        This ensures IDEs only suggest Phase A-C operations.
        """
        return [
            # Metadata
            'doc_id',
            'timestamp',
            # Phase A: Observation
            'get_all_claims',
            'get_claim_by_id',
            'get_all_contradictions',
            'get_contradiction_between',
            'get_provenance',
            # Phase B: Search & Filter
            'search',
            'find_contradictions_about',
            'find_uncertain_claims',
            'get_ambiguity_markers',
            # Phase C: Grouping & Navigation
            'get_all_clusters',
            'get_cluster',
            'find_related_claims',
            # Coherence (observation only)
            'get_disagreement_patterns',
            'get_claim_coherence',
            'get_disagreement_clusters',
            # Display
            'format_claim',
            'format_contradiction',
            'format_search_results'
        ]
