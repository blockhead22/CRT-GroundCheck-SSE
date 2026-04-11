"""Slot Bootstrapper: Auto-discover slots from a corpus of evidence.

The case study proved CRT can't analyze domains it doesn't have slots for.
This bootstrapper reads a corpus, finds repeated patterns with variable values,
and proposes new slot names.

Method:
1. Embed all entries, cluster by similarity (>0.7)
2. Within each cluster, extract candidate phrases using NP chunking
3. Find phrases that appear across multiple entries with DIFFERENT completions
4. Those variable completions are slot values. The fixed part is the slot name.
5. Promote candidates that appear 2+ times with different values.

No LLM calls. Pure structural pattern detection.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Set

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "personal_agent"))

import builtins
_real_open = builtins.open

EVIDENCE_FILE = Path(__file__).parent / "evidence_base.json"


def p(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def load_evidence():
    with _real_open(EVIDENCE_FILE) as f:
        return json.loads(f.read())


def extract_variable_patterns(texts: List[str]) -> List[Dict]:
    """Find phrases that appear across texts with variable completions.

    Strategy: Extract 'frame + variable' patterns.
    A frame is a sequence of 3+ words that appears in multiple texts.
    The word(s) following the frame differ = that's a slot.

    Example:
      "the trunk pop happened at Best Buy"
      "the trunk pop happened at his grandmother's house"
      Frame: "trunk pop happened at" -> variable: "Best Buy" / "grandmother's house"
      Slot candidate: "trunk_pop_location"
    """
    # Tokenize all texts into word sequences
    tokenized = []
    for text in texts:
        # Normalize
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        words = clean.split()
        tokenized.append(words)

    # Extract all n-grams (3-6 words) from each text
    ngram_locations = defaultdict(list)  # ngram -> [(text_idx, position)]
    for text_idx, words in enumerate(tokenized):
        for n in range(3, 7):
            for i in range(len(words) - n):
                ngram = tuple(words[i:i+n])
                # What comes after?
                remaining = words[i+n:i+n+5]  # Next 5 words
                if remaining:
                    completion = " ".join(remaining)
                    ngram_locations[ngram].append({
                        "text_idx": text_idx,
                        "position": i,
                        "completion": completion,
                        "full_text": texts[text_idx][:100],
                    })

    # Find ngrams that appear in 2+ DIFFERENT texts with DIFFERENT completions
    candidates = []
    for ngram, occurrences in ngram_locations.items():
        # Must appear in at least 2 different texts
        text_indices = set(o["text_idx"] for o in occurrences)
        if len(text_indices) < 2:
            continue

        # Must have at least 2 different completions
        completions = set(o["completion"] for o in occurrences)
        if len(completions) < 2:
            continue

        # Score by: more texts = better, more unique completions = better
        score = len(text_indices) * len(completions)

        frame = " ".join(ngram)
        candidates.append({
            "frame": frame,
            "completions": list(completions),
            "text_count": len(text_indices),
            "completion_count": len(completions),
            "score": score,
            "examples": [o["full_text"] for o in occurrences[:3]],
        })

    # Deduplicate: if one frame is a substring of another with same completions, keep the longer one
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Remove redundant shorter frames
    filtered = []
    seen_frames = set()
    for c in candidates:
        # Check if this frame is a substring of an already-accepted frame
        is_sub = False
        for seen in seen_frames:
            if c["frame"] in seen or seen in c["frame"]:
                is_sub = True
                break
        if not is_sub:
            filtered.append(c)
            seen_frames.add(c["frame"])

    return filtered[:50]  # Top 50 candidates


def extract_prepositional_patterns(texts: List[str]) -> List[Dict]:
    """Find 'X at/in/near/from Y' patterns where Y varies across texts.

    Many case evidence facts follow the pattern:
    "[action] at [location]" or "[event] in [place]" or "[person] from [origin]"
    """
    prep_patterns = [
        (r'(\w+\s+\w+\s+\w+)\s+(at|in|near|from|outside|to)\s+(.+?)(?:\.|,|;|$)', 'location'),
        (r'(between|from|at|around|approximately)\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)\s+(?:and|to|-)\s+(\d{1,2}:\d{2}\s*(?:am|pm)?)', 'time_range'),
        (r'(at|around|approximately)\s+(\d{1,2}:\d{2}\s*(?:am|pm))', 'time_point'),
        (r'(stated|said|claimed|testified|told)\s+(?:that\s+)?(.+?)(?:\.|,|;|$)', 'witness_claim'),
    ]

    pattern_hits = defaultdict(lambda: defaultdict(list))  # pattern_type -> frame -> [values]

    for text_idx, text in enumerate(texts):
        text_lower = text.lower()
        for regex, ptype in prep_patterns:
            for m in re.finditer(regex, text_lower):
                if ptype == 'location':
                    frame = m.group(1).strip()
                    prep = m.group(2)
                    value = m.group(3).strip()[:50]
                    key = f"{frame} {prep}"
                    pattern_hits[ptype][key].append({
                        "value": value,
                        "text_idx": text_idx,
                        "full_text": text[:100],
                    })
                elif ptype == 'time_point':
                    frame = "time_at"
                    value = m.group(2).strip()
                    pattern_hits[ptype][frame].append({
                        "value": value,
                        "text_idx": text_idx,
                        "full_text": text[:100],
                    })
                elif ptype == 'witness_claim':
                    verb = m.group(1).strip()
                    claim = m.group(2).strip()[:80]
                    pattern_hits[ptype][verb].append({
                        "value": claim,
                        "text_idx": text_idx,
                        "full_text": text[:100],
                    })

    candidates = []
    for ptype, frames in pattern_hits.items():
        for frame, hits in frames.items():
            text_indices = set(h["text_idx"] for h in hits)
            values = set(h["value"] for h in hits)
            if len(text_indices) >= 2 and len(values) >= 2:
                candidates.append({
                    "type": ptype,
                    "frame": frame,
                    "values": list(values)[:5],
                    "text_count": len(text_indices),
                    "value_count": len(values),
                    "score": len(text_indices) * len(values),
                    "examples": [h["full_text"] for h in hits[:3]],
                })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:30]


def propose_slot_names(variable_patterns, prep_patterns) -> List[Dict]:
    """Convert discovered patterns into proposed slot names."""
    proposals = []

    for p in variable_patterns[:15]:
        # Convert frame to slot name
        frame_words = p["frame"].split()
        # Take last 2-4 meaningful words
        meaningful = [w for w in frame_words if w not in {"the", "a", "an", "was", "is", "at", "in", "to", "that", "he", "she", "it"}]
        if meaningful:
            slot_name = "_".join(meaningful[-3:])
            proposals.append({
                "slot_name": slot_name,
                "source": "variable_pattern",
                "frame": p["frame"],
                "example_values": p["completions"][:4],
                "confidence": min(0.9, p["score"] / 20),
                "evidence_count": p["text_count"],
            })

    for p in prep_patterns[:15]:
        frame_words = p["frame"].split()
        meaningful = [w for w in frame_words if w not in {"the", "a", "an", "was", "is"}]
        if meaningful:
            slot_name = f"{p['type']}_{('_'.join(meaningful[-2:]))}"
            proposals.append({
                "slot_name": slot_name,
                "source": "prep_pattern",
                "frame": p["frame"],
                "example_values": p["values"][:4],
                "confidence": min(0.9, p["score"] / 15),
                "evidence_count": p["text_count"],
            })

    # Deduplicate by slot name
    seen = set()
    unique = []
    for prop in proposals:
        if prop["slot_name"] not in seen:
            seen.add(prop["slot_name"])
            unique.append(prop)

    unique.sort(key=lambda x: x["confidence"], reverse=True)
    return unique


def run():
    p("=" * 60)
    p("SLOT BOOTSTRAPPER: Auto-discover slots from evidence")
    p("=" * 60)

    evidence = load_evidence()
    texts = [e["text"] for e in evidence]
    p(f"Loaded {len(texts)} evidence entries")

    # Phase 1: Variable pattern extraction
    p("\nPhase 1: Finding variable patterns...")
    var_patterns = extract_variable_patterns(texts)
    p(f"  Found {len(var_patterns)} candidate patterns")

    p("\n  Top 10 variable patterns:")
    for i, vp in enumerate(var_patterns[:10]):
        p(f"    {i+1}. \"{vp['frame']}\" + [{', '.join(vp['completions'][:3])}...] (score={vp['score']}, texts={vp['text_count']})")

    # Phase 2: Prepositional pattern extraction
    p("\nPhase 2: Finding prepositional patterns...")
    prep_patterns = extract_prepositional_patterns(texts)
    p(f"  Found {len(prep_patterns)} candidate patterns")

    p("\n  Top 10 prepositional patterns:")
    for i, pp in enumerate(prep_patterns[:10]):
        p(f"    {i+1}. [{pp['type']}] \"{pp['frame']}\" -> [{', '.join(pp['values'][:3])}...] (score={pp['score']})")

    # Phase 3: Propose slot names
    p("\nPhase 3: Proposing slot names...")
    proposals = propose_slot_names(var_patterns, prep_patterns)
    p(f"  {len(proposals)} unique slot proposals")

    p(f"\n{'='*60}")
    p("PROPOSED SLOTS")
    p(f"{'='*60}")
    for i, prop in enumerate(proposals):
        p(f"\n  {i+1}. {prop['slot_name']}")
        p(f"     Source: {prop['source']}")
        p(f"     Frame: \"{prop['frame']}\"")
        p(f"     Values: {prop['example_values']}")
        p(f"     Confidence: {prop['confidence']:.2f}")
        p(f"     Evidence: {prop['evidence_count']} texts")

    # Save proposals
    out_path = Path(__file__).parent / "results" / "discovered_slots.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(out_path, "w") as f:
        json.dump(proposals, f, indent=2)
    p(f"\n  Saved to: {out_path}")


if __name__ == "__main__":
    run()
