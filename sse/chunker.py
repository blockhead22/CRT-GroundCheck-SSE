import re
from typing import List, Dict, Tuple


_ABBREVIATIONS = set([
    "mr", "mrs", "dr", "ms", "jr", "sr", "prof", "inc", "e.g", "i.e", "etc", "vs", "st", "rd",
])


def _split_sentences_with_offsets(text: str) -> List[Tuple[str, int, int]]:
    sentences = []
    if not text:
        return sentences
    length = len(text)
    start = 0
    # find sentence-ending punctuation
    for m in re.finditer(r'[.!?]+', text):
        end_p = m.end()
        # token immediately before punctuation
        pre = text[:m.start()].rstrip()
        token = ''
        if pre:
            token = re.split(r'\s+', pre)[-1].strip().rstrip('.')
        # check common abbreviations
        if token and token.lower() in _ABBREVIATIONS:
            continue
        # if punctuation is part of ellipsis, continue until the last
        # ensure sentence boundary is followed by whitespace or end
        if end_p < length and not text[end_p].isspace():
            continue
        sent = text[start:end_p].strip()
        if sent:
            s_start = text.find(sent, start)
            s_end = s_start + len(sent)
            sentences.append((sent, s_start, s_end))
            start = s_end
    # trailing
    tail = text[start:].strip()
    if tail:
        s_start = text.find(tail, start)
        s_end = s_start + len(tail)
        sentences.append((tail, s_start, s_end))
    return sentences


def chunk_text(text: str, max_chars: int = 800, overlap: int = 200) -> List[Dict]:
    sent_offsets = _split_sentences_with_offsets(text)
    chunks = []
    i = 0
    chunk_id = 0
    n = len(sent_offsets)
    while i < n:
        cur_text, start_char, end_char = sent_offsets[i]
        j = i + 1
        while j < n and (end_char - start_char) + 1 + len(sent_offsets[j][0]) <= max_chars:
            # append next sentence
            cur_text = cur_text + " " + sent_offsets[j][0]
            end_char = sent_offsets[j][2]
            j += 1
        chunks.append({
            "chunk_id": f"c{chunk_id}",
            "text": cur_text,
            "start_char": start_char,
            "end_char": end_char,
            "embedding_id": f"e{chunk_id}",
        })
        chunk_id += 1
        # compute next start index by overlap
        if j >= n:
            break
        target = end_char - overlap
        # find earliest sentence whose start >= target, but > i
        k = j
        while k > i and sent_offsets[k-1][1] > target:
            k -= 1
        if k <= i:
            k = j
        i = k
    return chunks


def split_sentences(text: str) -> List[str]:
    return [s for s, _, _ in _split_sentences_with_offsets(text)]
