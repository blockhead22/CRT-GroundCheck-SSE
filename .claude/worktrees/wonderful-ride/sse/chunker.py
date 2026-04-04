import re
from typing import List, Dict, Tuple


_ABBREVIATIONS = set([
    "mr", "mrs", "dr", "ms", "jr", "sr", "prof", "inc", "e.g", "i.e", "etc", "vs", "st", "rd",
])


def _find_sentence_boundaries(text: str) -> List[Tuple[int, int]]:
    """
    Find sentence boundaries as (start, end) spans in original text.
    
    Phase 5 Fix: Returns spans, NOT extracted strings.
    This preserves exact whitespace/newlines for lossless reconstruction.
    """
    spans = []
    if not text:
        return spans
    
    length = len(text)
    sent_start = 0
    
    # Find sentence-ending punctuation
    for m in re.finditer(r'[.!?]+', text):
        end_p = m.end()
        
        # Check for abbreviations before punctuation
        pre = text[:m.start()].rstrip()
        token = ''
        if pre:
            token = re.split(r'\s+', pre)[-1].strip().rstrip('.')
        if token and token.lower() in _ABBREVIATIONS:
            continue
        
        # Ensure sentence boundary is followed by whitespace or end
        if end_p < length and not text[end_p].isspace():
            continue
        
        # Record span (sent_start to end_p)
        # Don't strip - preserve exact boundaries
        if end_p > sent_start:
            spans.append((sent_start, end_p))
            sent_start = end_p
    
    # Trailing text after last punctuation
    if sent_start < length:
        spans.append((sent_start, length))
    
    return spans


def chunk_text(text: str, max_chars: int = 800, overlap: int = 200, doc_id: str = "doc0") -> List[Dict]:
    """
    Chunk text using lossless span-based approach.
    
    Phase 5 Fix: GUARANTEES text[chunk['start_char']:chunk['end_char']] == chunk['text']
    
    Args:
        text: Original document text (never modified)
        max_chars: Maximum chunk size
        overlap: Overlap between chunks
        doc_id: Document identifier for provenance
        
    Returns:
        List of chunks with exact offsets into original text
    """
    spans = _find_sentence_boundaries(text)
    chunks = []
    
    if not spans:
        return chunks
    
    i = 0
    chunk_id = 0
    n = len(spans)
    
    while i < n:
        # Start with first sentence span
        chunk_start = spans[i][0]
        chunk_end = spans[i][1]
        j = i + 1
        
        # Add sentences while within max_chars
        while j < n:
            potential_end = spans[j][1]
            if (potential_end - chunk_start) <= max_chars:
                chunk_end = potential_end
                j += 1
            else:
                break
        
        # Extract chunk text by slicing original (LOSSLESS)
        chunk_text = text[chunk_start:chunk_end]
        
        chunks.append({
            "chunk_id": f"c{chunk_id}",
            "doc_id": doc_id,
            "text": chunk_text,
            "start_char": chunk_start,
            "end_char": chunk_end,
            "embedding_id": f"e{chunk_id}",
        })
        chunk_id += 1
        
        # Compute next start with overlap
        if j >= n:
            break
        
        # Find sentence whose start is >= (chunk_end - overlap)
        target = chunk_end - overlap
        k = j
        while k > i and spans[k-1][0] >= target:
            k -= 1
        
        # Ensure we move forward
        if k <= i:
            k = j
        i = k
    
    # PHASE 5 INVARIANT: Assert lossless reconstruction
    for chunk in chunks:
        reconstructed = text[chunk["start_char"]:chunk["end_char"]]
        assert reconstructed == chunk["text"], (
            f"LOSSLESS INVARIANT VIOLATED: chunk {chunk['chunk_id']} "
            f"reconstruction mismatch at [{chunk['start_char']}:{chunk['end_char']}]"
        )
    
    return chunks


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences (legacy function for compatibility).
    
    Phase 5: Now uses span-based approach, slices original text.
    """
    spans = _find_sentence_boundaries(text)
    return [text[start:end] for start, end in spans]
