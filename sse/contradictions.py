from typing import List, Dict, Optional
import numpy as np
from hashlib import md5


# Cache for NLI results (claim_pair_hash -> label)
_NLI_CACHE = {}


def _cache_key(text_a: str, text_b: str) -> str:
    """Generate cache key for claim pair (order-independent)."""
    pair = tuple(sorted([text_a, text_b]))
    return md5(f"{pair[0]}|||{pair[1]}".encode()).hexdigest()


def heuristic_contradiction(a: str, b: str) -> str:
    """
    Heuristic pre-filter for contradictions.
    Looks for negation patterns and opposing concepts.
    Returns 'contradiction' only if negation mismatch or explicit opposition words detected.
    """
    a_lower = a.lower()
    b_lower = b.lower()
    
    # Check for negation mismatch
    neg_words = {'not ', "n't ", 'no ', 'never ', 'cannot ', "can't "}
    a_has_neg = any(w in a_lower for w in neg_words)
    b_has_neg = any(w in b_lower for w in neg_words)
    
    # Negation mismatch is a strong signal
    if a_has_neg != b_has_neg:
        return 'contradiction'
    
    # Check for explicit opposition words
    opposition_pairs = [
        ('round', 'flat'),
        ('beneficial', 'harmful'),
        ('beneficial', 'dangerous'),
        ('safe', 'dangerous'),
        ('effective', 'ineffective'),
        ('real', 'hoax'),
        ('true', 'false'),
        ('healthy', 'unhealthy'),
        ('improves', 'damages'),
        ('helps', 'hurts'),
        ('agree', 'disagree'),
    ]
    
    for word_a, word_b in opposition_pairs:
        if (word_a in a_lower and word_b in b_lower) or \
           (word_b in a_lower and word_a in b_lower):
            return 'contradiction'
    
    return 'unrelated'


def query_ollama_nli(premise: str, hypothesis: str, ollama_client=None, model: str = "mistral") -> Optional[str]:
    """
    Query local Ollama instance for NLI classification (cached).
    Uses OllamaClient if provided, otherwise tries requests.
    Returns: 'contradiction' | 'entailment' | 'neutral' | None
    """
    # Check cache first
    cache_key = _cache_key(premise, hypothesis)
    if cache_key in _NLI_CACHE:
        return _NLI_CACHE[cache_key]
    
    result = None
    
    # Try OllamaClient if available
    if ollama_client is not None:
        try:
            prompt = f"""Given a premise and hypothesis, classify the relationship as one of: contradiction, entailment, or neutral.

Premise: {premise}
Hypothesis: {hypothesis}

Respond with ONLY the label (contradiction, entailment, or neutral)."""
            
            response_text = ollama_client.generate(model, prompt)
            if response_text:
                text_lower = response_text.lower().strip()
                if 'contradiction' in text_lower:
                    result = 'contradiction'
                elif 'entail' in text_lower:
                    result = 'entailment'
                elif 'neutral' in text_lower:
                    result = 'neutral'
        except Exception:
            pass
    
    # Fallback to requests if OllamaClient didn't work
    if result is None:
        try:
            import requests
            prompt = f"""Given a premise and hypothesis, classify the relationship as one of: contradiction, entailment, or neutral.

Premise: {premise}
Hypothesis: {hypothesis}

Respond with ONLY the label."""
            
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=5
            )
            if resp.status_code == 200:
                text = resp.json().get('response', '').lower()
                if 'contradiction' in text:
                    result = 'contradiction'
                elif 'entail' in text:
                    result = 'entailment'
                elif 'neutral' in text:
                    result = 'neutral'
        except Exception:
            pass
    
    # Cache the result
    _NLI_CACHE[cache_key] = result
    return result


def clear_nli_cache():
    """Clear NLI cache (useful for testing)."""
    global _NLI_CACHE
    _NLI_CACHE = {}


def detect_contradictions(
    claims: List[Dict], 
    embeddings: np.ndarray = None, 
    use_ollama: bool = False,
    ollama_client=None,
    ollama_model: str = "mistral"
) -> List[Dict]:
    """
    Detect contradictions between claims.
    
    Strategy:
    1. Use embedding similarity as pre-filter (only compare semantically related claims)
    2. Use LLM NLI as primary classification (cached) when available
    3. Use heuristic negation rules only as fallback
    4. Deduplicate contradiction pairs
    
    Args:
        claims: List of claims with 'claim_text' and 'claim_id'
        embeddings: Embedding matrix (used for similarity pre-filtering)
        use_ollama: (deprecated) if True, tries to use Ollama
        ollama_client: OllamaClient instance (preferred way to pass Ollama)
        ollama_model: Model name for Ollama
    """
    cons = []
    if len(claims) < 2:
        return cons
    
    # Determine if we should try LLM
    try_llm = use_ollama or (ollama_client is not None)
    
    # Get embeddings for pre-filtering
    claim_embs = None
    if embeddings is not None:
        emb = np.asarray(embeddings, dtype='float32')
        claim_embs = []
        for c in claims:
            if c.get('supporting_quotes'):
                idx = int(c['supporting_quotes'][0]['chunk_id'][1:])
            else:
                idx = 0
            if idx < len(emb):
                claim_embs.append(emb[idx])
            else:
                claim_embs.append(np.zeros(emb.shape[1], dtype='float32'))
        claim_embs = np.vstack(claim_embs) if claim_embs else None
    
    n = len(claims)
    seen_pairs = set()  # For deduplication
    
    for i in range(n):
        for j in range(i+1, n):
            # Avoid duplicate pairs
            pair_key = (min(claims[i]['claim_id'], claims[j]['claim_id']), 
                       max(claims[i]['claim_id'], claims[j]['claim_id']))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            
            # Pre-filter by similarity (lower threshold to catch opposite statements)
            if claim_embs is not None:
                sim = float(np.dot(claim_embs[i], claim_embs[j]))
                # Lower threshold to 0.2 to include semantically related but opposite claims
                # (e.g., "Earth is round" vs "Earth is flat" should be caught)
                if sim < 0.2:
                    continue
            
            # Classify using LLM (primary) or heuristic (fallback)
            label = None
            if try_llm:
                label = query_ollama_nli(
                    claims[i]['claim_text'],
                    claims[j]['claim_text'],
                    ollama_client=ollama_client,
                    model=ollama_model
                )
            
            if label is None:
                # Fallback to heuristic
                label = heuristic_contradiction(claims[i]['claim_text'], claims[j]['claim_text'])
            
            # Only record actual contradictions
            if label == 'contradiction':
                # Get quotes for evidence
                quote_a = claims[i].get('supporting_quotes', [{}])[0]
                quote_b = claims[j].get('supporting_quotes', [{}])[0]
                
                cons.append({
                    'pair': {
                        'claim_id_a': claims[i]['claim_id'],
                        'claim_id_b': claims[j]['claim_id']
                    },
                    'label': 'contradiction',
                    'evidence_quotes': [quote_a, quote_b]
                })
    
    return cons
