# SSE Interface Contract (v0.1)

**Version:** 0.1  
**Date:** January 3, 2026  
**Status:** Specification (binding)

This document defines what external systems may and must never do when interacting with SSE. This is not guidance—it is a formal contract. Violations are detectable and testable.

---

## Executive Summary

SSE is a **read-only truth substrate**. Systems that interact with SSE may:
- Query, retrieve, filter, and navigate
- Display claims and contradictions exactly as extracted
- Track disagreement and persistence metadata

Systems must never:
- Synthesize answers or opinions
- Resolve contradictions
- Suppress ambiguity
- Generate new claims
- Weight claims by confidence or consensus
- Paraphrase or restate

---

## Part I: Permitted Operations

### 1. Retrieval Operations

**Definition:** Retrieve claims, contradictions, and metadata from the SSE index without modification.

**Operations:**
```
get_claims_by_topic(topic: str) → List[Claim]
get_claims_by_source(source_id: str) → List[Claim]
get_claims_containing_term(term: str) → List[Claim]
get_contradictions() → List[Contradiction]
get_contradictions_for_claim(claim_id: str) → List[Contradiction]
get_cluster(cluster_id: str) → Cluster
get_all_clusters() → List[Cluster]
```

**Constraints:**
- Results must include complete claim text and supporting quotes
- Byte offsets must be preserved
- Contradictions must be returned as pairs, not evaluated
- No sorting by confidence, consensus, or "importance"
- Results are returned in index order or by explicit sort key (date, source, cluster_id)

**Examples (acceptable):**
```python
# Get all claims about "climate"
claims = sse.get_claims_by_topic("climate")
# Each claim has: claim_text, supporting_quotes[].text, 
#                 supporting_quotes[].start_char, supporting_quotes[].end_char

# Get contradictions involving claim C1
contradictions = sse.get_contradictions_for_claim("clm1")
# Returns: [{"pair": {"claim_id_a": "clm1", "claim_id_b": "clm2"}, 
#            "label": "contradiction", "evidence_quotes": [...]}]

# Get a cluster
cluster = sse.get_cluster("cl0")
# Returns: cluster_id, all member claim_ids, centroid embedding_id
```

### 2. Search Operations

**Definition:** Find claims, contradictions, or clusters by keyword or semantic similarity.

**Operations:**
```
search_claims(query: str, method: "keyword"|"semantic") → List[Claim]
search_clusters(query: str, method: "keyword"|"semantic") → List[Cluster]
search_contradictions(query: str) → List[Contradiction]
```

**Constraints:**
- Semantic search uses embeddings already in SSE; no new embeddings generated
- Results are ranked by similarity or relevance, but ranking is transparent and metadata-visible
- No results are hidden based on confidence threshold
- Contradictions involving any matching claim must be returned
- Ambiguity markers are preserved

**Examples (acceptable):**
```python
# Search for claims semantically similar to "vaccine efficacy"
results = sse.search_claims("vaccine efficacy", method="semantic")
# Returns claims ordered by cosine similarity to query embedding
# Each result includes similarity score (transparent metadata)

# Search for contradictions involving "vaccine"
results = sse.search_contradictions("vaccine")
# Returns all contradiction pairs where either claim mentions "vaccine"
# Both claims shown in full, not just the matching one
```

### 3. Filtering and Grouping

**Definition:** Organize claims and contradictions by metadata without modifying content.

**Operations:**
```
filter_claims(claims: List[Claim], 
              by_source: Optional[str],
              by_time_range: Optional[Tuple[date, date]],
              by_ambiguity_threshold: Optional[float]) → List[Claim]

group_claims_by_cluster(claims: List[Claim]) → Dict[str, List[Claim]]

group_contradictions_by_persistence(contradictions: List[Contradiction]) 
  → Dict[str, List[Contradiction]]
```

**Constraints:**
- Filtering must be transparent (show filter criteria to user)
- Filtered results must still preserve contradictions
- Grouping is structural only; no reordering or ranking by "importance"
- Ambiguity thresholds filter by the metric, not by interpretation
- No implicit filtering (all filtered-out claims remain in the index)

**Examples (acceptable):**
```python
# Filter claims to only those mentioning "COVID" from 2020-2021
filtered = sse.filter_claims(
    claims,
    by_source=None,
    by_time_range=("2020-01-01", "2021-12-31"),
    by_ambiguity_threshold=None
)
# Returns claims matching the filter
# If any claim matches, its contradictions are also shown

# Group all claims by cluster
grouped = sse.group_claims_by_cluster(all_claims)
# Returns: {"cl0": [clm1, clm3, clm5], "cl1": [...], ...}
```

### 4. Provenance Tracking

**Definition:** Retrieve the source, offset, and quote for any claim.

**Operations:**
```
get_claim_provenance(claim_id: str) 
  → {claim_text, supporting_quotes[{quote_text, start_char, end_char, source_chunk_id}]}

get_quote_from_source(source_id: str, start_char: int, end_char: int) 
  → str

trace_claim_to_source(claim_id: str) → {source_document, chunk_id, offsets}
```

**Constraints:**
- Offsets must enable exact reconstruction: `source[start:end] == quote`
- Provenance is always retrievable
- No loss of fidelity in provenance tracking
- Tracing preserves the full chain: claim → quote → chunk → document

**Examples (acceptable):**
```python
# Get full provenance for a claim
prov = sse.get_claim_provenance("clm7")
# Returns:
# {
#   "claim_id": "clm7",
#   "claim_text": "The process requires attention.",
#   "supporting_quotes": [
#     {"quote_text": "requires attention",
#      "chunk_id": "c2",
#      "start_char": 142,
#      "end_char": 158}
#   ]
# }

# Reconstruct the quote from source
quote = sse.get_quote_from_source("doc1.txt", 142, 158)
# Returns: "requires attention"
# Proof: source[142:158] == quote
```

### 5. Ambiguity Exposure

**Definition:** Retrieve and display ambiguity metadata without interpreting it.

**Operations:**
```
get_ambiguity_for_claim(claim_id: str) 
  → {hedge_score, contains_conflict_markers, open_questions}

filter_by_ambiguity(claims: List[Claim], min_hedge: float, max_hedge: float)
  → List[Claim]

highlight_uncertain_claims(claims: List[Claim]) → List[Claim]
```

**Constraints:**
- Ambiguity metadata is descriptive, not prescriptive
- High hedge score does not mean the claim is "weak" or "unreliable"—it means the source uses uncertain language
- Ambiguity is displayed alongside the claim, never used to suppress it
- Filtering by ambiguity threshold is explicit and reversible
- Uncertainty markers are preserved in all operations

**Examples (acceptable):**
```python
# Get ambiguity for a claim
ambig = sse.get_ambiguity_for_claim("clm3")
# Returns: {"hedge_score": 0.7, "contains_conflict_markers": true, 
#           "open_questions": ["What does 'effective' mean?"]}
# This is information about the source, not a judgment

# Filter to uncertain claims only
uncertain = sse.filter_by_ambiguity(claims, min_hedge=0.5, max_hedge=1.0)
# Returns claims with high hedge scores
# User sees: "These claims use uncertain language in the source"
```

### 6. Display and Navigation

**Definition:** Render SSE data in human-readable form without synthesis.

**Operations:**
```
render_claim(claim: Claim, format: "json"|"markdown"|"text") → str

render_contradiction_pair(pair: Contradiction, format: str) → str

render_cluster(cluster: Cluster, format: str) → str

paginate_results(results: List, page_size: int, page_num: int) 
  → {page, total_pages, results}
```

**Constraints:**
- Rendering is structural: reordering, indenting, formatting only
- No paraphrasing of claim text
- Quotes always appear verbatim with offsets
- Contradictions are presented as side-by-side pairs, not resolved
- Pagination preserves all results; no hidden items
- Format options (JSON, markdown, text) must preserve content fidelity

**Examples (acceptable):**

Rendering a contradiction:
```markdown
## Contradiction: Claim C1 vs Claim C2

### Claim C1: "Exercise is healthy."
**Source:** Document A, lines 5-8
**Quote:** "Exercise is healthy and strengthens the body."
**Offsets:** [142:195]
**Ambiguity:** Hedge score 0.1 (low uncertainty)

### Claim C2: "Exercise damages joints."
**Source:** Document B, line 23
**Quote:** "Some people find that exercise damages joints."
**Offsets:** [340:390]
**Ambiguity:** Hedge score 0.6 (high uncertainty in source)

---
**No interpretation. Both claims shown in full. User decides.**
```

---

## Part II: Forbidden Operations

### 1. Synthesis

**Definition:** Generating new claims, summaries, or interpretations.

**Forbidden:**
```python
# ❌ No synthesis across contradictions
synthesize_into_answer(contradiction_pair) → str

# ❌ No "balanced" conclusions
create_balanced_summary(contradictions) → str

# ❌ No inferring the "real" meaning
infer_underlying_truth(claims) → str

# ❌ No generating answers to questions
answer_question(question: str) → str
```

**Why:** Synthesis invents claims SSE did not extract. This violates the Non-Fabrication Invariant and the Contradiction Preservation Invariant.

**Example violation:**
```python
# Given:
claims = [
  "The vaccine is safe.",
  "The vaccine causes serious side effects."
]

# ❌ FORBIDDEN:
result = sse.synthesize_into_answer(claims)
# This would generate something like:
# "The vaccine is safe for most people but causes side effects in rare cases."
# SSE never extracted that claim. The interface fabricated it.
```

### 2. Truth Picking

**Definition:** Selecting one side of a contradiction as "correct" or "better."

**Forbidden:**
```python
# ❌ No confidence scoring
rank_claims_by_confidence(claims) → List[Claim]

# ❌ No consensus-based filtering
filter_claims_by_consensus(claims, threshold=0.7) → List[Claim]

# ❌ No "best answer" logic
get_best_answer(contradiction) → Claim

# ❌ No weighting by source quality or document importance
weight_claims_by_source_credibility(claims) → List[Weighted[Claim]]
```

**Why:** Picking winners suppresses the Contradiction Preservation Invariant. It also introduces subjective judgment into what should be an objective data structure.

**Example violation:**
```python
# Given contradictions:
contradictions = [
  {"claim_a": "Vaccines are safe", "claim_b": "Vaccines are dangerous"},
]

# ❌ FORBIDDEN:
best = sse.get_best_answer(contradictions[0])
# This would return only one side, hiding the other.
```

### 3. Ambiguity Softening

**Definition:** Reducing, hiding, or interpreting uncertainty markers.

**Forbidden:**
```python
# ❌ No removing hedges to make claims sound certain
remove_hedging_language(claim) → Claim

# ❌ No suppressing ambiguity markers
hide_ambiguity_if_minor(claim, threshold=0.3) → Claim

# ❌ No interpreting hedges as "weakness"
downgrade_claim_by_ambiguity(claim) → Claim

# ❌ No softening contradictions to sound like nuance
reframe_contradiction_as_spectrum(contradiction) → str
```

**Why:** Ambiguity is information. Softening it removes information and misleads the user about what the source actually said.

**Example violation:**
```python
# Given:
claim = {
  "text": "Exercise may possibly be helpful in some cases.",
  "ambiguity": {"hedge_score": 0.9}
}

# ❌ FORBIDDEN:
cleaned = sse.remove_hedging_language(claim)
# This would produce: "Exercise is helpful."
# The source's uncertainty is now hidden.
```

### 4. Paraphrasing or Restating

**Definition:** Rewriting claims in different language.

**Forbidden:**
```python
# ❌ No rephrasing
rephrase_claim(claim: Claim) → str

# ❌ No simplifying language
simplify_claim_for_children(claim: Claim) → str

# ❌ No translating (unless preserving the exact same meaning with provenance)
translate_claim(claim: Claim, language: str) → str

# ❌ No elaborating beyond what's in the quote
elaborate_on_claim(claim: Claim) → str
```

**Why:** Paraphrasing introduces interpretive drift. The original language is the truth. Everything else is a shadow.

**Example violation:**
```python
# Given:
claim = {
  "text": "The process requires careful attention.",
  "supporting_quote": "requires careful attention"
}

# ❌ FORBIDDEN:
simplified = sse.simplify_claim_for_children(claim)
# Returns: "You have to be very careful."
# This is a paraphrase, not the original claim.

# ✅ ALLOWED:
display = sse.render_claim(claim, format="markdown")
# Returns the claim and quote exactly, in markdown format.
```

### 5. Opinion or Interpretation

**Definition:** Adding judgment, context, or meta-commentary not in the source or SSE metadata.

**Forbidden:**
```python
# ❌ No editorial framing
add_editorial_context(claim) → str

# ❌ No belief statements
state_belief_about_claim(claim: Claim) → str

# ❌ No "in my opinion" or equivalent
generate_commentary(claim: Claim) → str

# ❌ No probabilistic truth scoring
assign_probability_to_claim(claim: Claim) → float
```

**Why:** Opinions are not part of the contract between SSE and the consumer. They belong in downstream systems explicitly marked as opinion, not embedded in SSE results.

**Example violation:**
```python
# Given:
claim = "The vaccine has side effects."

# ❌ FORBIDDEN:
response = sse.generate_commentary(claim)
# Returns: "While the vaccine has side effects, they are generally mild and rare."
# This adds editorial judgment not in SSE.
```

### 6. Suppression or Hiding

**Definition:** Removing claims, contradictions, or metadata from display.

**Forbidden:**
```python
# ❌ No silent filtering
suppress_low_confidence_claims(claims) → List[Claim]

# ❌ No hiding contradictions for coherence
remove_contradictions_if_minor(contradictions) → List[Contradiction]

# ❌ No truncating results below a threshold
truncate_results_below_confidence(results, threshold=0.5) → List

# ❌ No hiding ambiguity unless explicitly requested
display_claims_without_ambiguity_markers(claims) → str
```

**Why:** Hiding information is a form of lying. If SSE extracted it, it should be visible. If filtering is necessary, the filter must be explicit and reversible.

**Example violation:**
```python
# Given all claims and contradictions from SSE:
all_claims = [clm1, clm2, clm3]
all_contradictions = [contra_1_2, contra_2_3]

# ❌ FORBIDDEN:
filtered = sse.remove_contradictions_if_minor(all_contradictions)
# This silently hides contradictions if the system judges them "minor".
# The user is never told they were removed.

# ✅ ALLOWED:
filtered = sse.filter_claims(all_claims, by_source="EPA")
# This explicitly filters by source.
# The filter is transparent: user sees "Filtered by source: EPA"
# Removed items are known to be removed.
```

---

## Part III: Error Handling and Boundary Violations

### What Happens When a Boundary is Violated

If an interface tries to perform a forbidden operation, the SSE layer responds with a clear error:

```python
class SSEBoundaryViolation(Exception):
    """
    Raised when an interface tries to perform a forbidden operation.
    """
    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        
    def __str__(self):
        return (
            f"SSE Boundary Violation: {self.operation}\n"
            f"Reason: {self.reason}\n"
            f"SSE permits only: retrieval, filtering, grouping, provenance tracking, "
            f"ambiguity exposure, display, and navigation.\n"
            f"SSE forbids: synthesis, truth picking, ambiguity softening, paraphrasing, "
            f"opinion, and suppression."
        )
```

**Examples:**

```python
# Attempt to synthesize an answer:
try:
    answer = sse.answer_question("What is the truth about vaccines?")
except SSEBoundaryViolation as e:
    print(e)
    # Output:
    # SSE Boundary Violation: answer_question
    # Reason: SSE does not generate answers. It exposes contradictions.
    # Use: sse.get_contradictions_by_topic("vaccines") instead.

# Attempt to hide contradictions:
try:
    display = sse.render_claims_without_contradictions(claims)
except SSEBoundaryViolation as e:
    print(e)
    # Output:
    # SSE Boundary Violation: render_claims_without_contradictions
    # Reason: Contradictions are core information. They cannot be hidden.
    # Use: sse.render_contradiction_pairs(contradictions) instead.
```

### Testable Boundaries

Every forbidden operation has a corresponding test:

```python
def test_synthesis_is_forbidden():
    """Verify that synthesis operations raise SSEBoundaryViolation."""
    sse = SSEIndex(...)
    claims = [c1, c2]  # Contradictory claims
    
    with pytest.raises(SSEBoundaryViolation):
        sse.synthesize_into_answer(claims)

def test_truth_picking_is_forbidden():
    """Verify that picking winners raises SSEBoundaryViolation."""
    sse = SSEIndex(...)
    contradictions = [contra1, contra2]
    
    with pytest.raises(SSEBoundaryViolation):
        sse.rank_claims_by_confidence(contradictions)

def test_ambiguity_softening_is_forbidden():
    """Verify that softening ambiguity raises SSEBoundaryViolation."""
    sse = SSEIndex(...)
    claim = get_claim_with_high_ambiguity()
    
    with pytest.raises(SSEBoundaryViolation):
        sse.remove_hedging_language(claim)
```

---

## Part IV: Compliant Implementation Signature

Any system implementing SSE as a dependency must:

1. **Declare Compliance**
   ```python
   class MySystem(SSECompliant):
       """This system interacts with SSE only through permitted operations."""
       
       sse_version = "0.1"
       permitted_operations = [
           "retrieve", "search", "filter", "group",
           "provenance", "ambiguity_exposure", "display", "navigate"
       ]
   ```

2. **Expose Boundaries to Users**
   ```
   When a user asks for a forbidden operation (e.g., "What does the text really mean?"):
   
   MySystem responds:
   "I can show you claims and contradictions from the source.
    I can navigate by topic. I can expose ambiguities.
    But I won't synthesize an answer. That's your job."
   ```

3. **Test Against the Contract**
   ```python
   def test_my_system_only_uses_permitted_operations():
       """Verify that MySystem never calls forbidden SSE operations."""
       system = MySystem(sse_index)
       operations = introspect_system_calls(system)
       
       for op in operations:
           assert op in PERMITTED_OPERATIONS
   ```

4. **Document Limitations**
   ```
   In help/docs, clearly state:
   - What SSE provides (claims, contradictions, offsets, ambiguity)
   - What SSE does NOT provide (answers, truth scores, synthesis)
   - What the system does beyond SSE (if anything)
   - Where the user's judgment is required
   ```

---

## Part V: Usage Examples

### Example 1: Compliant Chat Interface

```python
class SSECompliantChat:
    """A chat interface that respects SSE boundaries."""
    
    def __init__(self, sse_index):
        self.sse = sse_index
    
    def handle_user_query(self, query: str):
        """Process a user query while respecting SSE boundaries."""
        
        # ✅ ALLOWED: Search for related claims
        claims = self.sse.search_claims(query, method="semantic")
        
        if not claims:
            return f"I found no claims about '{query}' in the source."
        
        # ✅ ALLOWED: Get contradictions
        contradictions = self.sse.get_contradictions()
        involved = [c for c in contradictions 
                   if any(claim.id in [c.claim_id_a, c.claim_id_b] 
                         for claim in claims)]
        
        # ✅ ALLOWED: Display claims and contradictions
        response = f"I found {len(claims)} claims about '{query}':\n\n"
        for claim in claims:
            response += f"- {claim.text}\n"
            response += f"  Source: {claim.supporting_quotes[0].quote_text}\n"
        
        if involved:
            response += f"\nThese claims have contradictions:\n"
            for contra in involved:
                response += f"- Claim A: {contra.claim_a_text}\n"
                response += f"- Claim B: {contra.claim_b_text}\n"
        
        # ❌ NOT ALLOWED: Generate an answer
        # response += f"\nBased on the above, the answer is...\n"  # FORBIDDEN
        
        # ✅ ALLOWED: Ask the user to decide
        response += "\nWhat do you make of these claims?"
        
        return response
```

### Example 2: Compliant RAG System

```python
class SSECompliantRAG:
    """A RAG system that consults SSE without overriding it."""
    
    def __init__(self, sse_index, knowledge_base):
        self.sse = sse_index
        self.kb = knowledge_base
    
    def answer_query(self, query: str):
        """Answer a query, but respect SSE authority."""
        
        # Step 1: Check SSE
        sse_claims = self.sse.search_claims(query, method="semantic")
        sse_contradictions = self.sse.get_contradictions_involving_any(sse_claims)
        
        # Step 2: If SSE has contradictions, report them
        if sse_contradictions:
            return {
                "source": "SSE",
                "status": "contradiction_detected",
                "claims": sse_claims,
                "contradictions": sse_contradictions,
                "message": "The source contains conflicting claims. See above."
            }
        
        # Step 3: If SSE has consensus, cite it
        if sse_claims and not sse_contradictions:
            return {
                "source": "SSE",
                "status": "consensus",
                "claims": sse_claims,
                "message": "These claims are from the source."
            }
        
        # Step 4: If SSE has no opinion, use knowledge base
        if not sse_claims:
            kb_answer = self.kb.query(query)
            return {
                "source": "Knowledge Base",
                "status": "no_sse_claims",
                "answer": kb_answer,
                "message": "SSE has no claims about this. See knowledge base above."
            }
```

---

## Conclusion

This contract is binding.

**Every interface to SSE must:**
- ✅ Stay within permitted operations
- ✅ Never perform forbidden operations
- ✅ Expose boundaries to users
- ✅ Preserve contradictions
- ✅ Preserve ambiguity
- ✅ Maintain provenance
- ✅ Never synthesize or decide

**Every system that violates this contract is not actually using SSE—it is misrepresenting SSE as a truth source when it is only a data structure.**

Compliance is testable. Violations raise errors. The boundary is clear.

---

## Appendix: Summary Table

| Operation | Category | Status | Example |
|-----------|----------|--------|---------|
| Retrieval | Get claims by topic, source, term | ✅ Allowed | `get_claims_by_topic("vaccines")` |
| Search | Find claims, clusters, contradictions | ✅ Allowed | `search_claims("vaccine safety", method="semantic")` |
| Filter | Select claims by metadata | ✅ Allowed | `filter_claims(claims, by_time_range=(2020, 2021))` |
| Group | Organize by cluster, contradiction, source | ✅ Allowed | `group_claims_by_cluster(claims)` |
| Provenance | Trace claim to source with offsets | ✅ Allowed | `get_claim_provenance("clm1")` |
| Ambiguity | Expose hedge scores and uncertainty | ✅ Allowed | `get_ambiguity_for_claim("clm1")` |
| Display | Render in JSON, markdown, text | ✅ Allowed | `render_claim(claim, format="markdown")` |
| Navigate | Pagination, history, suggestions | ✅ Allowed | `paginate_results(results, page_size=10, page=1)` |
| Synthesis | Generate answers or summaries | ❌ Forbidden | `synthesize_into_answer(claims)` |
| Truth Picking | Rank, weight, or score claims | ❌ Forbidden | `rank_claims_by_confidence(claims)` |
| Ambiguity Softening | Remove hedges or hide uncertainty | ❌ Forbidden | `remove_hedging_language(claim)` |
| Paraphrasing | Rephrase or restate claims | ❌ Forbidden | `rephrase_claim(claim)` |
| Opinion | Add judgment or interpretation | ❌ Forbidden | `generate_commentary(claim)` |
| Suppression | Hide claims or contradictions | ❌ Forbidden | `hide_contradictions_if_minor(contradictions)` |

