"""Bootstrap Slot Discovery from GPT Logs

Runs the slot name discovery bootstrapper on Nick's full GPT archive
(25,726 user messages, 1,248 conversations).

No import into CRT memory. Just discover patterns → propose slots → report.
The discovered slots can then be added to the production vocabulary.
"""

import json
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "personal_agent"))

import builtins
_real_open = builtins.open

GPT_DB = r"D:\AI_round2\data\gpt_logs.db"
OUTPUT_FILE = Path(__file__).parent / "results" / "raw" / "gpt_slot_discovery.json"


def p(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def load_user_messages(limit=5000):
    """Load user messages from GPT logs. Most recent first."""
    conn = sqlite3.connect(GPT_DB, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT text FROM messages WHERE role='user' AND text IS NOT NULL "
        "AND LENGTH(text) > 10 AND LENGTH(text) < 500 "
        "ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [row["text"] for row in rows]


def extract_frame_patterns(texts):
    """Extract 'my X is Y' style patterns."""
    PATTERNS = [
        (r"\bmy\s+(\w+(?:\s+\w+)?)\s+(?:is|are)\s+(.+?)(?:\.|,|!|\?|$)", "my_{0}"),
        (r"\bi\s+(?:like|love|prefer|enjoy)\s+(.+?)(?:\.|,|!|\?|$)", "preference"),
        (r"\bi\s+(?:go|went|been)\s+to\s+(.+?)(?:\.|,|!|\?|for|$)", "place_visited"),
        (r"\bi\s+(?:work|worked)\s+(?:at|for)\s+(.+?)(?:\.|,|!|\?|$)", "workplace"),
        (r"\bi\s+live\s+(?:in|at|near)\s+(.+?)(?:\.|,|!|\?|$)", "location"),
        (r"\bi(?:'m| am)\s+a\s+(.+?)(?:\.|,|!|\?|$)", "self_description"),
        (r"(.+?)\s+is\s+my\s+(?:favorite|favourite)\s+(\w+)", "favorite_{1}"),
        (r"\bi\s+use\s+(.+?)(?:\s+for|$|\.|,)", "tool_used"),
        (r"\bi(?:'m| am)\s+(?:learning|studying|taking)\s+(.+?)(?:\.|,|!|\?|$)", "learning"),
        (r"\bi\s+(?:think|believe|feel)\s+(?:that\s+)?(.+?)(?:\.|!|\?|$)", "belief"),
        (r"\bi\s+(?:want|need|wish)\s+(?:to\s+)?(.+?)(?:\.|!|\?|$)", "desire"),
        (r"\bi\s+(?:hate|dislike|can't stand)\s+(.+?)(?:\.|!|\?|$)", "dislike"),
        (r"\bi\s+(?:used to|formerly|previously)\s+(.+?)(?:\.|!|\?|$)", "past_state"),
        (r"\bi\s+(?:just|recently)\s+(.+?)(?:\.|!|\?|$)", "recent_event"),
        (r"\bi\s+(?:always|usually|normally)\s+(.+?)(?:\.|!|\?|$)", "habit"),
        (r"\bmy\s+(?:friend|buddy|colleague)\s+(\w+)", "friend_name"),
        (r"\bi\s+(?:drink|eat|have)\s+(.+?)(?:\s+(?:every|for|in|at)|$|\.|,)", "consumption"),
    ]

    hits = defaultdict(lambda: {"values": set(), "count": 0})

    for text in texts:
        text_lower = text.lower().strip()
        for pattern, name_template in PATTERNS:
            for m in re.finditer(pattern, text_lower):
                groups = m.groups()
                if not groups:
                    continue

                if "{0}" in name_template:
                    slot_name = name_template.format(groups[0].strip().replace(" ", "_")[:20])
                    value = groups[1].strip() if len(groups) > 1 else groups[0].strip()
                elif "{1}" in name_template:
                    slot_name = name_template.format("", groups[1].strip().replace(" ", "_")[:20])
                    value = groups[0].strip()
                else:
                    slot_name = name_template
                    value = groups[-1].strip()

                slot_name = re.sub(r'[^a-z0-9_]', '', slot_name)[:30]
                value = value[:60]

                if slot_name and value and len(value) > 1:
                    hits[slot_name]["values"].add(value)
                    hits[slot_name]["count"] += 1

    return hits


def extract_ngram_patterns(texts, sample_size=2000):
    """Find repeated phrases with variable completions."""
    # Sample to keep runtime reasonable
    sample = texts[:sample_size]

    tokenized = []
    for text in sample:
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        words = clean.split()
        if len(words) >= 4:
            tokenized.append(words)

    ngram_completions = defaultdict(lambda: defaultdict(set))

    for text_idx, words in enumerate(tokenized):
        for n in range(3, 5):
            for i in range(len(words) - n - 1):
                ngram = tuple(words[i:i+n])
                completion = " ".join(words[i+n:i+n+3])
                if completion:
                    ngram_completions[ngram][completion].add(text_idx)

    results = {}
    for ngram, completions in ngram_completions.items():
        all_texts = set()
        for ts in completions.values():
            all_texts |= ts
        if len(completions) >= 3 and len(all_texts) >= 3:
            meaningful = [w for w in ngram if w not in {"the", "a", "an", "is", "are", "was", "i", "my", "to", "at", "in", "for", "it", "that", "this", "of"}]
            if meaningful:
                name = "_".join(meaningful[-2:])[:25]
                name = re.sub(r'[^a-z0-9_]', '', name)
                if name and len(name) > 2:
                    results[f"ngram_{name}"] = {
                        "frame": " ".join(ngram),
                        "values": list(completions.keys())[:10],
                        "text_count": len(all_texts),
                        "completion_count": len(completions),
                    }

    return results


def run():
    p("=" * 60)
    p("GPT LOG SLOT BOOTSTRAPPER")
    p("=" * 60)
    p(f"Source: {GPT_DB}")

    # Load messages
    p("\nLoading user messages...")
    texts = load_user_messages(limit=5000)
    p(f"  Loaded {len(texts)} user messages (most recent)")

    # Known slots to skip
    KNOWN_SLOTS = {
        "name", "location", "employer", "occupation", "age", "birthday",
        "favorite_color", "hobby", "pet", "pet_name", "school", "title",
        "coffee", "book", "spouse", "siblings", "programming_language",
        "assistant_name", "remote_preference", "team_size",
    }

    # Phase 1: Frame patterns
    p("\nPhase 1: Frame pattern extraction...")
    frame_hits = extract_frame_patterns(texts)
    p(f"  {len(frame_hits)} unique patterns found")

    # Filter to multi-value patterns
    multi_value = {k: v for k, v in frame_hits.items()
                   if len(v["values"]) >= 2 and k not in KNOWN_SLOTS}
    p(f"  {len(multi_value)} with 2+ unique values (excluding known slots)")

    # Phase 2: N-gram patterns
    p("\nPhase 2: N-gram variable patterns...")
    ngram_hits = extract_ngram_patterns(texts)
    p(f"  {len(ngram_hits)} n-gram patterns found")

    # Combine and rank
    all_discoveries = []

    for name, data in sorted(multi_value.items(), key=lambda x: x[1]["count"], reverse=True):
        all_discoveries.append({
            "slot_name": name,
            "source": "frame_pattern",
            "values": list(data["values"])[:8],
            "evidence_count": data["count"],
            "unique_values": len(data["values"]),
        })

    for name, data in sorted(ngram_hits.items(), key=lambda x: x[1]["text_count"], reverse=True):
        if name not in {d["slot_name"] for d in all_discoveries}:
            all_discoveries.append({
                "slot_name": name,
                "source": "ngram_pattern",
                "frame": data["frame"],
                "values": data["values"][:8],
                "evidence_count": data["text_count"],
                "unique_values": data["completion_count"],
            })

    # Sort by evidence count
    all_discoveries.sort(key=lambda x: x["evidence_count"], reverse=True)

    # Report
    p(f"\n{'='*60}")
    p(f"DISCOVERED SLOTS ({len(all_discoveries)} total)")
    p(f"{'='*60}")

    frame_discoveries = [d for d in all_discoveries if d["source"] == "frame_pattern"]
    ngram_discoveries = [d for d in all_discoveries if d["source"] == "ngram_pattern"]

    p(f"\n  FRAME PATTERNS ({len(frame_discoveries)}):")
    for i, d in enumerate(frame_discoveries[:25]):
        vals = ", ".join(d["values"][:4])
        p(f"    {i+1}. {d['slot_name']} (count={d['evidence_count']}, unique={d['unique_values']})")
        p(f"       Values: [{vals}]")

    p(f"\n  N-GRAM PATTERNS ({len(ngram_discoveries)}):")
    for i, d in enumerate(ngram_discoveries[:15]):
        vals = ", ".join(d["values"][:4])
        p(f"    {i+1}. {d['slot_name']} (count={d['evidence_count']}, unique={d['unique_values']})")
        p(f"       Frame: \"{d.get('frame', '?')}\"")
        p(f"       Values: [{vals}]")

    # Save
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(OUTPUT_FILE, "w") as f:
        json.dump(all_discoveries, f, indent=2, default=str)

    p(f"\n  Saved {len(all_discoveries)} discoveries to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
