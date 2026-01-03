from typing import Dict, List


def render_index(
    index_data: Dict,
    style: str = "natural",
    max_claims_per_cluster: int = 15
) -> str:
    """
    Render an index back to readable text using ONLY stored claims + quotes.
    Never hallucinate or add information.
    
    Styles:
    - "natural": prose-like narrative from claims
    - "bullet": bullet list of claims with quotes
    - "conflict": highlight contradictions first
    """
    claims_by_id = {c["claim_id"]: c for c in index_data.get("claims", [])}
    contradictions = index_data.get("contradictions", [])
    
    # Build contradiction map
    contradiction_pairs = set()
    for cont in contradictions:
        if cont.get("label") == "contradiction":
            a, b = cont["pair"]["claim_id_a"], cont["pair"]["claim_id_b"]
            contradiction_pairs.add((min(a, b), max(a, b)))
    
    output = []
    
    if style == "conflict":
        output.append("=" * 70)
        output.append("EXPLICIT CONTRADICTIONS")
        output.append("=" * 70)
        
        for cont in contradictions:
            if cont.get("label") != "contradiction":
                continue
            claim_a_id = cont["pair"]["claim_id_a"]
            claim_b_id = cont["pair"]["claim_id_b"]
            claim_a = claims_by_id.get(claim_a_id)
            claim_b = claims_by_id.get(claim_b_id)
            
            if claim_a and claim_b:
                output.append("")
                output.append("[CONTRADICTION]")
                output.append(f"  X {claim_a['claim_text']}")
                if claim_a.get("supporting_quotes"):
                    quote = claim_a["supporting_quotes"][0]
                    output.append(f"    -> \"{quote['quote_text'][:100]}...\"")
                output.append(f"  X {claim_b['claim_text']}")
                if claim_b.get("supporting_quotes"):
                    quote = claim_b["supporting_quotes"][0]
                    output.append(f"    -> \"{quote['quote_text'][:100]}...\"")
    
    # Render claims grouped by cluster
    output.append("\n" + "=" * 70)
    if style == "conflict":
        output.append("KEY CLAIMS")
    else:
        output.append("DOCUMENT SUMMARY")
    output.append("=" * 70)
    
    clusters = index_data.get("clusters", [])
    for cluster in clusters:
        # Get claims in this cluster
        chunk_ids_in_cluster = set(cluster.get("chunk_ids", []))
        cluster_claims = [
            c for c in index_data.get("claims", [])
            if any(q["chunk_id"] in chunk_ids_in_cluster for q in c.get("supporting_quotes", []))
        ]
        
        if not cluster_claims:
            continue
        
        output.append(f"\n[Cluster {cluster['cluster_id']}]")
        
        for i, claim in enumerate(cluster_claims[:max_claims_per_cluster]):
            if not claim.get("claim_text"):
                continue
            
            # Mark uncertain claims
            is_uncertain = claim.get("ambiguity", {}).get("hedge_score", 0) > 0.5
            has_conflicts = any(
                claim["claim_id"] in pair
                for pair in contradiction_pairs
            )
            
            prefix = ""
            if is_uncertain:
                prefix = "[uncertain] "
            if has_conflicts:
                prefix += "[conflicts] "
            
            if style == "bullet":
                output.append(f"  * {prefix}{claim['claim_text']}")
                for quote in claim.get("supporting_quotes", [])[:1]:
                    output.append(f"    >> \"{quote['quote_text'][:80]}...\"")
            else:
                # natural style: prose-like
                output.append(f"  {i+1}. {prefix}{claim['claim_text']}")
    
    # List open questions
    open_questions = [
        c for c in index_data.get("claims", [])
        if c.get("ambiguity", {}).get("open_questions")
    ]
    
    if open_questions:
        output.append("\n" + "=" * 70)
        output.append("OPEN QUESTIONS")
        output.append("=" * 70)
        for claim in open_questions:
            for q in claim.get("ambiguity", {}).get("open_questions", []):
                output.append(f"  ? {q}")
    
    output.append("\n" + "=" * 70)
    output.append(f"Total: {len(index_data.get('claims', []))} claims | "
                  f"{len(contradictions)} contradictions | "
                  f"{len(open_questions)} open questions")
    output.append("=" * 70)
    
    return "\n".join(output)
