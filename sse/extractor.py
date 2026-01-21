import re
import json
from typing import List, Dict, Optional
from difflib import SequenceMatcher
import numpy as np

FILLER_PHRASES = set([
    "note:", "fyi", "example", "e.g", "i.e", "etc.", "by the way",
    "in other words", "that is", "as mentioned", "as stated",
])

HEDGE_WORDS = set([
    "may", "might", "could", "seems", "suggests", "possible", "unclear", "likely",
    "appears", "arguably", "apparently", "perhaps", "tend",
])


def string_similarity(s1: str, s2: str) -> float:
    """Compute string similarity (0.0 to 1.0)."""
    return SequenceMatcher(None, s1, s2).ratio()


def is_assertive(sentence: str) -> bool:
    s = sentence.strip()
    if s.endswith('?'):
        return False
    if len(s.split()) < 3:
        return False
    if any(f in s.lower() for f in FILLER_PHRASES):
        return False
    return True


def normalize_claim_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def has_negation_word(text: str) -> bool:
    """
    Check if text contains negation keywords or patterns.
    
    This prevents deduplication of opposite claims like:
    - "The statement is true" vs "The statement is not true"
    - "System complies" vs "System fails to comply"
    - "Valid with approval" vs "Valid without approval"
    
    Phase 4 Fix #1: Addresses Invariant III violation.
    Phase 4c expansion: Added "fails to", "lack", "without" patterns.
    """
    # Simple negation words
    negation_words = {
        'not', 'no', 'never', 'neither', 'nor', 'nobody', 'nothing', 'nowhere',
        "doesn't", "don't", "didn't", "isn't", "aren't", "wasn't", "weren't",
        "haven't", "hasn't", "hadn't", "won't", "wouldn't", "shouldn't",
        "can't", "couldn't", "cannot", "mustn't", "mightn't", "needn't"
    }
    
    # Multi-word negation patterns
    negation_patterns = [
        'fails to', 'failed to', 'lack', 'lacks', 'lacking',
        'without', 'absence of', 'devoid of', 'free from',
        'unable to', 'incapable of', 'insufficient'
    ]
    
    text_lower = text.lower()
    words = set(text_lower.split())
    
    # Check simple negation words
    if negation_words & words:
        return True
    
    # Check multi-word patterns
    for pattern in negation_patterns:
        if pattern in text_lower:
            return True
    
    return False


def dedupe_claims(claim_indices: List[int], claim_texts: List[str], embeddings: np.ndarray, thresh: float = 0.85) -> List[int]:
    """
    Deduplicate claims based on embedding similarity.
    But preserve semantically opposite claims (e.g., contradictions) by also checking text distance.
    
    Phase 4 improvement: Now detects negation to prevent deduplication of opposite claims.
    """
    keep = []
    for i in claim_indices:
        vec = embeddings[i]
        dup = False
        for j in keep:
            emb_sim = float(np.dot(vec, embeddings[j]))
            
            # High embedding similarity (above threshold) is concerning
            if emb_sim > thresh:
                # Phase 4 Fix #1: Check if one has negation and the other doesn't
                # If negation differs, they're likely opposites - preserve both
                has_neg_i = has_negation_word(claim_texts[i])
                has_neg_j = has_negation_word(claim_texts[j])
                
                if has_neg_i != has_neg_j:
                    # One is negated, one isn't - they're opposites, not duplicates
                    continue  # Keep both claims
                
                # Both have same negation status, so check text similarity
                text_sim = string_similarity(claim_texts[i], claim_texts[j])
                # Only treat as duplicate if both embedding and text are highly similar
                # This preserves contradictions like "Earth is round" vs "Earth is flat"
                if text_sim > 0.8:  # Text must also be very similar (not just about same topic)
                    dup = True
                    break
        if not dup:
            keep.append(i)
    return keep


def extract_claims_from_chunks(chunks: List[Dict], embeddings: np.ndarray) -> List[Dict]:
    """
    Extract claims from chunks with precise sentence-level offsets.
    
    Phase 4 Fix #2: Now stores exact sentence boundaries instead of chunk boundaries.
    Phase 5: Preserves doc_id provenance from chunks.
    This improves Invariant VI (Source Traceability) precision.
    """
    claims = []
    claim_texts = []
    claim_support = []
    emb = np.asarray(embeddings, dtype='float32')
    
    for cidx, c in enumerate(chunks):
        chunk_text = c['text']
        chunk_start = c['start_char']  # Document-level offset of chunk
        doc_id = c.get('doc_id', 'doc0')  # Phase 5: Preserve document provenance
        
        # Split into sentences
        sents = re.split(r'(?<=[.!?])\s+', chunk_text)
        
        # Track position within chunk for precise offset calculation
        sent_pos = 0
        for s in sents:
            # Find where this raw sentence appears in the chunk
            sent_start_in_chunk = chunk_text.find(s, sent_pos)
            if sent_start_in_chunk == -1:
                continue
                
            sent_end_in_chunk = sent_start_in_chunk + len(s)
            sent_pos = sent_end_in_chunk  # Move forward
            
            # Normalize for assertiveness check
            s_normalized = normalize_claim_text(s)
            if not s_normalized:
                continue
            
            if is_assertive(s_normalized):
                claim_texts.append(s_normalized)
                # Store the RAW sentence as quote_text with its exact offsets
                # This ensures text[start:end] == quote_text always holds
                claim_support.append({
                    "quote_text": s,  # Store original, not normalized
                    "chunk_id": c['chunk_id'],
                    "doc_id": doc_id,  # Phase 5: Track document source
                    "start_char": chunk_start + sent_start_in_chunk,
                    "end_char": chunk_start + sent_end_in_chunk
                })
    
    if len(claim_texts) == 0:
        return []
    
    claim_embs = []
    for sup in claim_support:
        idx = int(sup['chunk_id'][1:])
        if idx < len(emb):
            claim_embs.append(emb[idx])
        else:
            claim_embs.append(np.zeros(emb.shape[1], dtype='float32'))
    
    claim_embs_array = np.vstack(claim_embs) if claim_embs else np.zeros((0, emb.shape[1]), dtype='float32')
    
    # Note: Since we're using chunk embeddings (not sentence-level embeddings), deduplication
    # can inadvertently remove contradictory claims from the same chunk (e.g., "A is true" vs "A is false").
    # We use a very high threshold (0.99) to only deduplicate near-identical claims,
    # preserving semantic opposites like contradictions.
    keep = dedupe_claims(list(range(len(claim_texts))), claim_texts, claim_embs_array, thresh=0.99)
    
    for k, i in enumerate(keep):
        support = claim_support[i]
        claims.append({
            "claim_id": f"clm{k}",
            "claim_text": claim_texts[i],
            "doc_id": support["doc_id"],  # Phase 5: Provenance metadata
            "supporting_quotes": [support],
            "ambiguity": {},
        })
    return claims


def extract_claims_with_llm(
    chunk_text: str,
    chunk_id: str,
    start_char: int,
    ollama_client=None,
    model: str = "mistral"
) -> List[Dict]:
    """
    Extract claims using local LLM with mandatory multi-quote grounding.
    Each claim must have 1-3 supporting quotes from the text.
    Falls back to rule-based if LLM unavailable or fails.
    """
    if ollama_client is None:
        return extract_claims_rule_based(chunk_text, chunk_id, start_char)
    
    prompt = f"""Extract EVERY factual claim from this text.

For each claim:
1. State it clearly in one sentence
2. Include 1-3 VERBATIM quotes that support it (as an array)
3. Give exact character offsets (0-indexed) of each quote in the text

Rules:
- Only extract claims explicitly in the text
- Do NOT infer or add information
- Do NOT skip uncertain claims; mark them [uncertain]
- Every quote must be an exact substring from the text
- Do NOT attempt to paraphrase or approximate quotes
- If you cannot find a quote to support a claim, DO NOT include that claim

Text:
{chunk_text}

Respond with ONLY this JSON format, no markdown:
{{"claims": [{{"claim_text": "...", "quotes": [{{"text": "...", "start": int, "end": int}}]}}]}}"""
    
    response_text = ollama_client.generate(model, prompt)
    if not response_text:
        return extract_claims_rule_based(chunk_text, chunk_id, start_char)
    
    try:
        json_match = re.search(r'\{.*"claims".*\}', response_text, re.DOTALL)
        if not json_match:
            return extract_claims_rule_based(chunk_text, chunk_id, start_char)
        
        data = json.loads(json_match.group())
        claims = []
        
        for c in data.get("claims", []):
            claim_text = c.get("claim_text", "").strip()
            quotes_raw = c.get("quotes", [])
            
            if not claim_text or not quotes_raw:
                continue
            
            # Validate and collect quotes
            supporting_quotes = []
            for q in quotes_raw:
                quote_text = q.get("text", "").strip()
                quote_start = q.get("start")
                quote_end = q.get("end")
                
                if not quote_text or quote_start is None or quote_end is None:
                    continue
                
                if quote_start < 0 or quote_end < 0 or quote_start >= len(chunk_text) or quote_end > len(chunk_text):
                    continue
                
                actual_quote = chunk_text[quote_start:quote_end]
                # Strict matching: at least 90% similarity
                if string_similarity(actual_quote, quote_text) < 0.90:
                    continue
                
                supporting_quotes.append({
                    "quote_text": actual_quote,
                    "chunk_id": chunk_id,
                    "start_char": start_char + quote_start,
                    "end_char": start_char + quote_end
                })
            
            # Only add claim if it has at least one valid supporting quote
            if supporting_quotes:
                claims.append({
                    "claim_id": None,
                    "claim_text": claim_text,
                    "supporting_quotes": supporting_quotes,
                    "ambiguity": {}
                })
        
        return claims if claims else extract_claims_rule_based(chunk_text, chunk_id, start_char)
    
    except Exception as e:
        print(f"[LLM extraction JSON parse failed: {e}] Falling back to rule-based.")
        return extract_claims_rule_based(chunk_text, chunk_id, start_char)


def extract_claims_rule_based(
    chunk_text: str,
    chunk_id: str,
    start_char: int
) -> List[Dict]:
    """Rule-based fallback extraction from assertive sentences."""
    sents = re.split(r'(?<=[.!?])\s+', chunk_text)
    claims = []
    offset = 0
    
    for sent in sents:
        sent_normalized = normalize_claim_text(sent)
        if not sent_normalized:
            continue
        
        sent_idx = chunk_text.find(sent, offset)
        if sent_idx == -1:
            continue
        offset = sent_idx + len(sent)
        
        if not is_assertive(sent):
            continue
        
        claims.append({
            "claim_id": None,
            "claim_text": sent_normalized,
            "supporting_quotes": [{
                "quote_text": sent_normalized,
                "chunk_id": chunk_id,
                "start_char": start_char + sent_idx,
                "end_char": start_char + sent_idx + len(sent)
            }],
            "ambiguity": {}
        })
    
    return claims
