"""Slot Name Discovery: Auto-discover new slot names from memory text.

Existing slot_discovery.py learns slot TYPES (exclusive, additive, temporal).
This module discovers slot NAMES — patterns in memory text that repeat
with different values, suggesting a trackable fact category.

Example:
  Memory: "I go to Steaming Cup for coffee"
  Memory: "I tried Blue Owl for coffee today"
  Discovery: "coffee_shop" slot with values ["steaming cup", "blue owl"]

Runs as a batch job in the heartbeat, not on every write.
Reads recent memories, compares against existing corpus, proposes new slots.

Design Law 3: "Structure should emerge, not be hardcoded."
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SlotCandidate:
    """A proposed slot name discovered from text patterns."""
    slot_name: str
    frame: str              # The fixed part of the pattern
    values: List[str]       # Different completions seen
    evidence_count: int     # How many memories contain this pattern
    first_seen: float       # Timestamp of first detection
    promoted: bool = False  # Whether this has been promoted to fact_slots


# ============================================================================
# Candidate table management
# ============================================================================

def _ensure_candidate_table(db_path: str):
    """Create the slot_candidates table if it doesn't exist."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS slot_candidates (
            slot_name TEXT PRIMARY KEY,
            frame TEXT NOT NULL,
            values_json TEXT NOT NULL DEFAULT '[]',
            evidence_count INTEGER NOT NULL DEFAULT 1,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL,
            promoted INTEGER NOT NULL DEFAULT 0,
            source TEXT DEFAULT 'auto_discovery'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_slot_cand_promoted ON slot_candidates(promoted)")
    conn.commit()
    conn.close()


def load_candidates(db_path: str) -> List[SlotCandidate]:
    """Load all unpromoted slot candidates."""
    _ensure_candidate_table(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT slot_name, frame, values_json, evidence_count, first_seen, promoted "
        "FROM slot_candidates WHERE promoted = 0"
    ).fetchall()
    conn.close()

    return [
        SlotCandidate(
            slot_name=row["slot_name"],
            frame=row["frame"],
            values=json.loads(row["values_json"]),
            evidence_count=row["evidence_count"],
            first_seen=row["first_seen"],
            promoted=bool(row["promoted"]),
        )
        for row in rows
    ]


def save_candidate(candidate: SlotCandidate, db_path: str):
    """Upsert a slot candidate."""
    _ensure_candidate_table(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("""
        INSERT INTO slot_candidates (slot_name, frame, values_json, evidence_count, first_seen, last_seen, promoted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slot_name) DO UPDATE SET
            values_json = excluded.values_json,
            evidence_count = excluded.evidence_count,
            last_seen = excluded.last_seen
    """, (
        candidate.slot_name,
        candidate.frame,
        json.dumps(candidate.values),
        candidate.evidence_count,
        candidate.first_seen,
        time.time(),
        1 if candidate.promoted else 0,
    ))
    conn.commit()
    conn.close()


def promote_candidate(slot_name: str, db_path: str):
    """Mark a candidate as promoted."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute(
        "UPDATE slot_candidates SET promoted = 1 WHERE slot_name = ?",
        (slot_name,)
    )
    conn.commit()
    conn.close()


# ============================================================================
# Pattern extraction from memory text
# ============================================================================

# Common frame patterns that indicate a fact with a variable value
FRAME_PATTERNS = [
    # "my X is Y" / "my X are Y"
    (r"\bmy\s+(\w+(?:\s+\w+)?)\s+(?:is|are)\s+(.+?)(?:\.|,|!|\?|$)", "my_{0}"),
    # "I like/love/prefer X"
    (r"\bi\s+(?:like|love|prefer|enjoy)\s+(.+?)(?:\.|,|!|\?|$)", "preference"),
    # "I go to X" / "I went to X"
    (r"\bi\s+(?:go|went|been)\s+to\s+(.+?)(?:\.|,|!|\?|for|$)", "place_visited"),
    # "I work at/for X"
    (r"\bi\s+(?:work|worked)\s+(?:at|for)\s+(.+?)(?:\.|,|!|\?|$)", "workplace"),
    # "I live in/at X"
    (r"\bi\s+live\s+(?:in|at|near)\s+(.+?)(?:\.|,|!|\?|$)", "location"),
    # "I'm a X" / "I am a X"
    (r"\bi(?:'m| am)\s+a\s+(.+?)(?:\.|,|!|\?|$)", "self_description"),
    # "X is my favorite Y"
    (r"(.+?)\s+is\s+my\s+(?:favorite|favourite)\s+(\w+)", "favorite_{1}"),
    # "I use X for Y" / "I use X"
    (r"\bi\s+use\s+(.+?)(?:\s+for|$|\.|,)", "tool_used"),
    # "I'm learning X" / "I started X"
    (r"\bi(?:'m| am)\s+(?:learning|studying|taking)\s+(.+?)(?:\.|,|!|\?|$)", "learning"),
    # "X is called Y" / "my X name is Y"
    (r"(?:called|named)\s+(.+?)(?:\.|,|!|\?|$)", "named_entity"),
]


def extract_candidates_from_texts(texts: List[str]) -> Dict[str, SlotCandidate]:
    """Extract slot candidates from a list of memory texts.

    Returns dict of slot_name -> SlotCandidate.
    """
    # Track: frame_key -> {values: set, count: int, frame: str}
    frame_hits: Dict[str, Dict] = defaultdict(lambda: {"values": set(), "count": 0, "frame": ""})

    for text in texts:
        text_lower = text.lower().strip()

        for pattern, name_template in FRAME_PATTERNS:
            for m in re.finditer(pattern, text_lower):
                groups = m.groups()
                if not groups:
                    continue

                # Build slot name from template
                if "{0}" in name_template:
                    slot_name = name_template.format(groups[0].strip().replace(" ", "_")[:20])
                    value = groups[1].strip() if len(groups) > 1 else groups[0].strip()
                elif "{1}" in name_template:
                    slot_name = name_template.format("", groups[1].strip().replace(" ", "_")[:20])
                    value = groups[0].strip()
                else:
                    slot_name = name_template
                    value = groups[-1].strip()

                # Normalize
                slot_name = re.sub(r'[^a-z0-9_]', '', slot_name)[:30]
                value = value[:50]

                if slot_name and value and len(value) > 1:
                    frame_hits[slot_name]["values"].add(value)
                    frame_hits[slot_name]["count"] += 1
                    frame_hits[slot_name]["frame"] = name_template

    # Convert to candidates (only those with 2+ different values)
    candidates = {}
    now = time.time()
    for slot_name, data in frame_hits.items():
        if len(data["values"]) >= 2:
            candidates[slot_name] = SlotCandidate(
                slot_name=slot_name,
                frame=data["frame"],
                values=list(data["values"])[:10],
                evidence_count=data["count"],
                first_seen=now,
            )

    return candidates


# ============================================================================
# Also use n-gram variable pattern detection (from bootstrapper)
# ============================================================================

def extract_ngram_candidates(texts: List[str]) -> Dict[str, SlotCandidate]:
    """Find n-grams that appear in 2+ texts with different completions.

    Adapted from case study bootstrapper for production use.
    """
    tokenized = []
    for text in texts:
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        words = clean.split()
        tokenized.append(words)

    ngram_completions: Dict[tuple, Dict[str, Set[int]]] = defaultdict(lambda: defaultdict(set))

    for text_idx, words in enumerate(tokenized):
        for n in range(3, 5):  # 3-4 word frames (shorter than case study to fit conversational text)
            for i in range(len(words) - n - 1):
                ngram = tuple(words[i:i+n])
                completion = " ".join(words[i+n:i+n+3])  # Next 3 words
                if completion:
                    ngram_completions[ngram][completion].add(text_idx)

    candidates = {}
    now = time.time()
    for ngram, completions in ngram_completions.items():
        # Must have 2+ different completions from different texts
        all_texts = set()
        for texts_set in completions.values():
            all_texts |= texts_set
        if len(completions) >= 2 and len(all_texts) >= 2:
            # Build slot name from meaningful words
            meaningful = [w for w in ngram if w not in {"the", "a", "an", "is", "are", "was", "i", "my", "to", "at", "in", "for"}]
            if meaningful:
                slot_name = "_".join(meaningful[-2:])[:25]
                slot_name = re.sub(r'[^a-z0-9_]', '', slot_name)
                if slot_name and len(slot_name) > 2:
                    candidates[slot_name] = SlotCandidate(
                        slot_name=f"ngram_{slot_name}",
                        frame=" ".join(ngram),
                        values=list(completions.keys())[:8],
                        evidence_count=len(all_texts),
                        first_seen=now,
                    )

    return candidates


# ============================================================================
# Main discovery pass — called from heartbeat
# ============================================================================

PROMOTION_THRESHOLD = 3  # Need 3+ evidence hits to promote
MIN_UNIQUE_VALUES = 2     # Need 2+ different values


def run_name_discovery_pass(
    memory_db_path: str,
    discovery_db_path: Optional[str] = None,
    lookback_hours: float = 24.0,
) -> Dict:
    """Run slot name discovery on recent memories.

    Called from the heartbeat. Scans recent memories, finds new patterns,
    updates candidate table, promotes mature candidates.

    Args:
        memory_db_path: Path to the CRT memory database
        discovery_db_path: Path to slot discovery DB (defaults to same dir)
        lookback_hours: How far back to scan for new patterns

    Returns:
        Dict with discovery stats and any newly promoted slots.
    """
    if not discovery_db_path:
        discovery_db_path = str(Path(memory_db_path).parent / "slot_discovery.db")

    _ensure_candidate_table(discovery_db_path)

    # Load recent memories
    cutoff = time.time() - (lookback_hours * 3600)
    conn = sqlite3.connect(memory_db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT text FROM memories WHERE deprecated = 0 AND timestamp > ? ORDER BY timestamp DESC LIMIT 200",
        (cutoff,)
    ).fetchall()
    conn.close()

    recent_texts = [row["text"] for row in rows if row["text"]]

    if not recent_texts:
        return {"scanned": 0, "candidates_found": 0, "promoted": []}

    # Also load ALL texts for n-gram analysis (need full corpus for pattern detection)
    conn = sqlite3.connect(memory_db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    all_rows = conn.execute(
        "SELECT text FROM memories WHERE deprecated = 0 ORDER BY timestamp DESC LIMIT 500"
    ).fetchall()
    conn.close()
    all_texts = [row["text"] for row in all_rows if row["text"]]

    # Extract candidates using both methods
    frame_candidates = extract_candidates_from_texts(all_texts)
    ngram_candidates = extract_ngram_candidates(all_texts)

    # Merge (frame patterns take priority)
    all_candidates = {**ngram_candidates, **frame_candidates}

    # Load existing candidates to update counts
    existing = {c.slot_name: c for c in load_candidates(discovery_db_path)}

    # Check which existing hardcoded slots we already have
    known_slots: Set[str] = set()
    try:
        from .fact_slots import extract_fact_slots
        # Get the list of known slot names from a test extraction
        test_result = extract_fact_slots("My name is Test and I live in Testville and my favorite color is blue")
        known_slots = set(test_result.keys()) if test_result else set()
    except Exception:
        pass

    # Add seed slots
    known_slots.update({
        "name", "location", "employer", "occupation", "age", "birthday",
        "favorite_color", "hobby", "pet", "pet_name", "school", "title",
        "coffee", "book", "spouse", "siblings", "programming_language",
    })

    # Update candidates
    new_candidates = 0
    updated_candidates = 0
    for name, candidate in all_candidates.items():
        # Skip if already a known hardcoded slot
        if name in known_slots:
            continue

        if name in existing:
            # Merge values
            old = existing[name]
            merged_values = list(set(old.values + candidate.values))[:15]
            old.values = merged_values
            old.evidence_count = max(old.evidence_count, candidate.evidence_count)
            save_candidate(old, discovery_db_path)
            updated_candidates += 1
        else:
            save_candidate(candidate, discovery_db_path)
            new_candidates += 1

    # Check for promotions
    promoted = []
    all_current = load_candidates(discovery_db_path)
    for candidate in all_current:
        if (candidate.evidence_count >= PROMOTION_THRESHOLD
                and len(candidate.values) >= MIN_UNIQUE_VALUES
                and not candidate.promoted):
            # Promote: register with slot_discovery as UNKNOWN type
            try:
                from .slot_discovery import SlotProfile, SlotType, save_slot_profile
                profile = SlotProfile(
                    slot_name=candidate.slot_name,
                    discovered_type=SlotType.UNKNOWN,
                    confidence=0.3,
                    evidence_count=candidate.evidence_count,
                    unique_values_seen=len(candidate.values),
                    last_updated=time.time(),
                    metadata={
                        "values_seen": candidate.values,
                        "frame": candidate.frame,
                        "source": "auto_name_discovery",
                    },
                )
                save_slot_profile(profile)
                promote_candidate(candidate.slot_name, discovery_db_path)
                promoted.append(candidate.slot_name)
                logger.info(
                    "[SLOT_NAME_DISCOVERY] Promoted '%s' (evidence=%d, values=%d): %s",
                    candidate.slot_name, candidate.evidence_count,
                    len(candidate.values), candidate.values[:3],
                )
            except Exception as e:
                logger.debug("[SLOT_NAME_DISCOVERY] Promotion failed for '%s': %s", candidate.slot_name, e)

    result = {
        "scanned": len(recent_texts),
        "corpus_size": len(all_texts),
        "candidates_found": new_candidates,
        "candidates_updated": updated_candidates,
        "promoted": promoted,
        "total_candidates": len(all_current) + new_candidates,
    }

    logger.info(
        "[SLOT_NAME_DISCOVERY] Scanned %d memories, %d new candidates, %d promoted",
        len(recent_texts), new_candidates, len(promoted),
    )

    return result
