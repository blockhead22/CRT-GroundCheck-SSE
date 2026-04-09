"""Dynamic Slot Discovery for CRT/Aether.

Sprint 6: Replace hardcoded EXCLUSIVE_SLOTS with a learned model that discovers
slot behavior from contradiction patterns and memory data.

Design Law 3: "Structure should emerge, not be hardcoded."
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Slot types
# ---------------------------------------------------------------------------

class SlotType(Enum):
    EXCLUSIVE = "exclusive"        # Only one value true at a time (favorite_color, name, age)
    ADDITIVE = "additive"          # Multiple values coexist (hobby, skill, project)
    TEMPORAL = "temporal"          # Value changes over time, history matters (location, job)
    HIERARCHICAL = "hierarchical"  # Values have parent/child structure (role: developer > frontend)
    UNKNOWN = "unknown"            # Not enough data to classify yet


# ---------------------------------------------------------------------------
# Slot profile dataclass
# ---------------------------------------------------------------------------

@dataclass
class SlotProfile:
    slot_name: str
    discovered_type: SlotType
    confidence: float = 0.0
    evidence_count: int = 0
    resolution_pattern: str = ""        # "always_latest", "user_resolves", "coexist", "temporal_chain"
    unique_values_seen: int = 0
    contradiction_count: int = 0
    avg_resolution_time: Optional[float] = None
    last_updated: float = 0.0
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Seed lists — bootstrap before enough contradiction data exists
# ---------------------------------------------------------------------------

_SEED_EXCLUSIVE = {
    # Hard identity facts — only one value true at a time
    "name", "first_name", "last_name", "birthday",
    "birth_date", "legal_name", "age", "email", "phone",
    "relationship_status", "zodiac_sign", "mbti", "nickname",
}

_SEED_TEMPORAL = {
    # Preferences and life facts — value changes over time, history matters.
    # Previously these were EXCLUSIVE which caused false contradiction
    # detection when preferences naturally evolved (Bug #4).
    "favorite_color", "favorite_drink", "favorite_food", "favorite_book",
    "favorite_movie", "favorite_music", "favorite_artist", "favorite_game",
    "favorite_sport", "favorite_team", "favorite_animal",
    "primary_city", "city", "employer", "job_title",
}

_SEED_ADDITIVE = {
    "hobby", "skill", "interest", "project", "friend",
    "language", "pet", "pet_name", "tool", "framework",
}


# ---------------------------------------------------------------------------
# Storage — SQLite
# ---------------------------------------------------------------------------

def _get_db_path(memory_db_path: Optional[str] = None) -> str:
    """Derive slot discovery DB path from memory DB path.

    Uses the same directory as the memory DB so slot profiles are co-located
    with the data they describe.
    """
    if memory_db_path:
        p = Path(memory_db_path)
        return str(p.parent / "slot_discovery.db")
    return str(Path(__file__).resolve().parent / "slot_discovery.db")


def _get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _ensure_tables(db_path: str) -> None:
    conn = _get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS slot_profiles (
            slot_name TEXT PRIMARY KEY,
            discovered_type TEXT NOT NULL DEFAULT 'unknown',
            confidence REAL NOT NULL DEFAULT 0.0,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            resolution_pattern TEXT,
            unique_values_seen INTEGER DEFAULT 0,
            contradiction_count INTEGER DEFAULT 0,
            avg_resolution_time REAL,
            last_updated REAL NOT NULL,
            metadata TEXT DEFAULT '{}'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS slot_discovery_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_name TEXT NOT NULL,
            old_type TEXT,
            new_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            trigger TEXT NOT NULL,
            evidence_summary TEXT,
            timestamp REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_slot_profile(profile: SlotProfile, db_path: Optional[str] = None) -> None:
    db = db_path or _get_db_path()
    _ensure_tables(db)
    conn = _get_connection(db)
    conn.execute("""
        INSERT OR REPLACE INTO slot_profiles
            (slot_name, discovered_type, confidence, evidence_count,
             resolution_pattern, unique_values_seen, contradiction_count,
             avg_resolution_time, last_updated, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        profile.slot_name,
        profile.discovered_type.value,
        profile.confidence,
        profile.evidence_count,
        profile.resolution_pattern,
        profile.unique_values_seen,
        profile.contradiction_count,
        profile.avg_resolution_time,
        profile.last_updated,
        json.dumps(profile.metadata),
    ))
    conn.commit()
    conn.close()


def load_slot_profile(slot_name: str, db_path: Optional[str] = None) -> Optional[SlotProfile]:
    db = db_path or _get_db_path()
    _ensure_tables(db)
    conn = _get_connection(db)
    cur = conn.execute(
        "SELECT * FROM slot_profiles WHERE slot_name = ?", (slot_name,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_profile(row)


def load_all_profiles(db_path: Optional[str] = None) -> List[SlotProfile]:
    db = db_path or _get_db_path()
    _ensure_tables(db)
    conn = _get_connection(db)
    rows = conn.execute("SELECT * FROM slot_profiles ORDER BY slot_name").fetchall()
    conn.close()
    return [_row_to_profile(r) for r in rows]


def delete_slot_profile(slot_name: str, db_path: Optional[str] = None) -> None:
    db = db_path or _get_db_path()
    _ensure_tables(db)
    conn = _get_connection(db)
    conn.execute("DELETE FROM slot_profiles WHERE slot_name = ?", (slot_name,))
    conn.commit()
    conn.close()


def _row_to_profile(row: tuple) -> SlotProfile:
    return SlotProfile(
        slot_name=row[0],
        discovered_type=SlotType(row[1]) if row[1] else SlotType.UNKNOWN,
        confidence=float(row[2] or 0),
        evidence_count=int(row[3] or 0),
        resolution_pattern=row[4] or "",
        unique_values_seen=int(row[5] or 0),
        contradiction_count=int(row[6] or 0),
        avg_resolution_time=float(row[7]) if row[7] is not None else None,
        last_updated=float(row[8] or 0),
        metadata=json.loads(row[9]) if row[9] else {},
    )


# ---------------------------------------------------------------------------
# Lineage logging
# ---------------------------------------------------------------------------

def _log_reclassification(
    slot_name: str,
    old_type: Optional[SlotType],
    new_type: SlotType,
    confidence: float,
    trigger: str,
    evidence_summary: Optional[dict] = None,
    db_path: Optional[str] = None,
) -> None:
    db = db_path or _get_db_path()
    _ensure_tables(db)
    conn = _get_connection(db)
    conn.execute("""
        INSERT INTO slot_discovery_log
            (slot_name, old_type, new_type, confidence, trigger, evidence_summary, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        slot_name,
        old_type.value if old_type else None,
        new_type.value,
        confidence,
        trigger,
        json.dumps(evidence_summary) if evidence_summary else None,
        time.time(),
    ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Classification logic (rule-based, no ML)
# ---------------------------------------------------------------------------

def classify_slot(
    slot_name: str,
    facts: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
) -> SlotType:
    """Classify a slot's behavior from its facts and contradictions.

    Args:
        slot_name: Normalized slot name.
        facts: List of dicts with keys: value, trust, timestamp, memory_id.
        contradictions: List of dicts with keys: resolution, old_value, new_value,
            timestamp, suggested_policy.

    Returns:
        SlotType classification.
    """
    n_facts = len(facts)
    n_contras = len(contradictions)

    if n_facts < 2 and n_contras == 0:
        return SlotType.UNKNOWN

    # Count distinct values
    distinct_values = set()
    for f in facts:
        v = str(f.get("value", "")).strip().lower()
        if v:
            distinct_values.add(v)

    # Analyze resolution patterns
    override_count = 0
    preserve_count = 0
    ask_count = 0
    for c in contradictions:
        res = str(c.get("resolution", c.get("suggested_policy", ""))).strip().lower()
        if res in ("override", "accept_new", "always_latest"):
            override_count += 1
        elif res in ("preserve", "keep_both", "coexist"):
            preserve_count += 1
        elif res in ("ask_user", "ask"):
            ask_count += 1

    # Count high-trust coexisting values
    high_trust_values = set()
    for f in facts:
        trust = float(f.get("trust", 0))
        v = str(f.get("value", "")).strip().lower()
        if trust >= 0.7 and v:
            high_trust_values.add(v)

    # --- HIERARCHICAL check: substring/containment relationships ---
    if len(distinct_values) >= 2:
        vals = sorted(distinct_values, key=len)
        containment_pairs = 0
        for i, shorter in enumerate(vals):
            for longer in vals[i + 1:]:
                if shorter in longer or longer.startswith(shorter):
                    containment_pairs += 1
        if containment_pairs >= 1 and containment_pairs >= len(distinct_values) // 2:
            return SlotType.HIERARCHICAL

    # --- ADDITIVE check: multiple high-trust values coexist, few contradictions ---
    if len(high_trust_values) >= 2 and n_contras <= 1:
        return SlotType.ADDITIVE
    if preserve_count > 0 and preserve_count >= override_count:
        return SlotType.ADDITIVE

    # --- TEMPORAL check: many distinct values changing over time, high volume ---
    # Checked before EXCLUSIVE because temporal slots also resolve by override but
    # have a distinctive pattern of 4+ sequential values.
    if len(distinct_values) >= 4 and override_count >= 3:
        timestamps = sorted([float(f.get("timestamp", 0)) for f in facts if f.get("timestamp")])
        if len(timestamps) >= 4:
            return SlotType.TEMPORAL

    # --- EXCLUSIVE check: contradictions resolved by override, single high-trust value ---
    if n_contras >= 1 and override_count > preserve_count:
        return SlotType.EXCLUSIVE
    if len(high_trust_values) <= 1 and len(distinct_values) >= 2 and n_contras >= 1:
        return SlotType.EXCLUSIVE

    # Default for ambiguous cases
    if n_contras == 0 and len(distinct_values) >= 2 and len(high_trust_values) >= 2:
        return SlotType.ADDITIVE

    return SlotType.UNKNOWN


def compute_slot_confidence(slot_name: str, evidence: Dict[str, Any]) -> float:
    """Compute confidence in a slot classification based on evidence volume and consistency.

    Args:
        slot_name: Normalized slot name.
        evidence: Dict with keys: contradiction_count, override_count, preserve_count,
            ask_count, distinct_values, high_trust_coexisting.

    Returns:
        Float 0.0-1.0 confidence score.
    """
    n_contras = evidence.get("contradiction_count", 0)
    override_count = evidence.get("override_count", 0)
    preserve_count = evidence.get("preserve_count", 0)
    ask_count = evidence.get("ask_count", 0)
    total_resolved = override_count + preserve_count + ask_count

    if n_contras == 0 and evidence.get("distinct_values", 0) < 2:
        return 0.0

    # Base confidence from evidence volume
    if n_contras >= 10:
        base = 0.95
    elif n_contras >= 4:
        base = 0.85
    elif n_contras >= 2:
        base = 0.60
    elif n_contras == 1:
        base = 0.30
    else:
        # No contradictions but has multiple facts (additive signal)
        base = 0.50

    # Consistency penalty: mixed resolution signals lower confidence
    if total_resolved >= 2:
        dominant = max(override_count, preserve_count, ask_count)
        consistency = dominant / total_resolved
        base *= (0.5 + 0.5 * consistency)  # Range: 50%-100% of base

    return round(min(base, 0.99), 3)


def _determine_resolution_pattern(contradictions: List[Dict[str, Any]]) -> str:
    """Determine the observed resolution pattern from contradiction history."""
    if not contradictions:
        return "coexist"

    override_count = 0
    preserve_count = 0
    ask_count = 0
    for c in contradictions:
        res = str(c.get("resolution", c.get("suggested_policy", ""))).strip().lower()
        if res in ("override", "accept_new", "always_latest"):
            override_count += 1
        elif res in ("preserve", "keep_both", "coexist"):
            preserve_count += 1
        elif res in ("ask_user", "ask"):
            ask_count += 1

    if override_count > preserve_count and override_count > ask_count:
        return "always_latest"
    if preserve_count > override_count:
        return "coexist"
    if ask_count > override_count:
        return "user_resolves"
    return "always_latest"


# ---------------------------------------------------------------------------
# Primary lookup
# ---------------------------------------------------------------------------

def get_slot_type(slot_name: str, db_path: Optional[str] = None) -> SlotType:
    """Look up slot type with fallback chain: learned → seed → unknown.

    Args:
        slot_name: Slot name (will be normalized to lowercase).
        db_path: Optional path to slot discovery DB.

    Returns:
        SlotType for the slot.
    """
    norm = slot_name.strip().lower().replace(" ", "_")

    # 1. Check learned profiles (highest priority — but only if they've
    #    actually learned something, not just defaulted to UNKNOWN)
    try:
        profile = load_slot_profile(norm, db_path=db_path)
        if profile and profile.confidence >= 0.5 and profile.discovered_type != SlotType.UNKNOWN:
            return profile.discovered_type
    except Exception:
        pass

    # 2. Fall back to seed lists
    if norm in _SEED_EXCLUSIVE:
        return SlotType.EXCLUSIVE
    if norm in _SEED_TEMPORAL:
        return SlotType.TEMPORAL
    if norm in _SEED_ADDITIVE:
        return SlotType.ADDITIVE

    # 3. Unknown
    return SlotType.UNKNOWN


def suggest_resolution_policy(
    slot_name: str,
    new_value: str,
    existing_value: str,
    db_path: Optional[str] = None,
) -> str:
    """Suggest a resolution policy based on learned slot type.

    Returns one of: "override", "preserve", "archive", "merge", "ask_user".
    """
    slot_type = get_slot_type(slot_name, db_path=db_path)

    if slot_type == SlotType.EXCLUSIVE:
        return "override"
    elif slot_type == SlotType.ADDITIVE:
        return "preserve"
    elif slot_type == SlotType.TEMPORAL:
        return "archive"
    elif slot_type == SlotType.HIERARCHICAL:
        # Check if values have containment relationship
        nv = new_value.strip().lower()
        ev = existing_value.strip().lower()
        if nv in ev or ev in nv:
            return "merge"
        return "override"
    else:  # UNKNOWN
        return "ask_user"


# ---------------------------------------------------------------------------
# Event hooks — called when contradictions or facts are recorded
# ---------------------------------------------------------------------------

def on_contradiction_recorded(
    slot_name: str,
    old_value: str,
    new_value: str,
    resolution: str,
    db_path: Optional[str] = None,
) -> None:
    """Hook called after a contradiction is recorded.

    Updates the slot profile with new evidence and reclassifies if needed.
    """
    norm = slot_name.strip().lower().replace(" ", "_")
    if not norm:
        return

    db = db_path or _get_db_path()
    _ensure_tables(db)

    profile = load_slot_profile(norm, db_path=db) or SlotProfile(
        slot_name=norm,
        discovered_type=SlotType.UNKNOWN,
        last_updated=time.time(),
    )

    old_type = profile.discovered_type
    profile.contradiction_count += 1
    profile.evidence_count += 1
    profile.last_updated = time.time()

    # Track distinct values
    vals = profile.metadata.get("values_seen", [])
    for v in [old_value.strip().lower(), new_value.strip().lower()]:
        if v and v not in vals:
            vals.append(v)
    profile.metadata["values_seen"] = vals
    profile.unique_values_seen = len(vals)

    # Track resolution history
    res_history = profile.metadata.get("resolution_history", [])
    res_history.append(resolution.strip().lower())
    # Keep last 20
    profile.metadata["resolution_history"] = res_history[-20:]

    # Build synthetic evidence for reclassification
    facts = [{"value": v, "trust": 0.8, "timestamp": time.time()} for v in vals]
    contras = [{"resolution": r} for r in profile.metadata["resolution_history"]]

    new_type = classify_slot(norm, facts, contras)
    conf = compute_slot_confidence(norm, {
        "contradiction_count": profile.contradiction_count,
        "override_count": sum(1 for r in profile.metadata["resolution_history"] if r in ("override", "accept_new", "always_latest")),
        "preserve_count": sum(1 for r in profile.metadata["resolution_history"] if r in ("preserve", "keep_both", "coexist")),
        "ask_count": sum(1 for r in profile.metadata["resolution_history"] if r in ("ask_user", "ask")),
        "distinct_values": profile.unique_values_seen,
    })

    profile.discovered_type = new_type
    profile.confidence = conf
    profile.resolution_pattern = _determine_resolution_pattern(contras)

    save_slot_profile(profile, db_path=db)

    if new_type != old_type:
        _log_reclassification(
            norm, old_type, new_type, conf,
            trigger="contradiction",
            evidence_summary={"old_value": old_value, "new_value": new_value, "resolution": resolution},
            db_path=db,
        )
        logger.info(
            "[SLOT_DISCOVERY] Slot '%s' reclassified as %s (confidence: %.2f) after contradiction #%d",
            norm, new_type.value, conf, profile.contradiction_count,
        )
    else:
        logger.debug(
            "[SLOT_DISCOVERY] Slot '%s' remains %s (confidence: %.2f) after contradiction #%d",
            norm, new_type.value, conf, profile.contradiction_count,
        )


def on_fact_stored(
    slot_name: str,
    value: str,
    trust_score: float,
    db_path: Optional[str] = None,
) -> None:
    """Hook called after a fact is stored.

    Updates unique_values_seen and checks for additive signals.
    """
    norm = slot_name.strip().lower().replace(" ", "_")
    if not norm:
        return

    db = db_path or _get_db_path()
    _ensure_tables(db)

    profile = load_slot_profile(norm, db_path=db) or SlotProfile(
        slot_name=norm,
        discovered_type=SlotType.UNKNOWN,
        last_updated=time.time(),
    )

    old_type = profile.discovered_type
    profile.evidence_count += 1
    profile.last_updated = time.time()

    # Track distinct values
    vals = profile.metadata.get("values_seen", [])
    v_norm = value.strip().lower()
    if v_norm and v_norm not in vals:
        vals.append(v_norm)
    profile.metadata["values_seen"] = vals
    profile.unique_values_seen = len(vals)

    # Track high-trust values
    if trust_score >= 0.7:
        ht = profile.metadata.get("high_trust_values", [])
        if v_norm and v_norm not in ht:
            ht.append(v_norm)
        profile.metadata["high_trust_values"] = ht

    # Only reclassify if we have enough evidence (at least 2 values)
    if profile.unique_values_seen >= 2:
        facts = [
            {"value": v, "trust": 0.8 if v in profile.metadata.get("high_trust_values", []) else 0.4, "timestamp": time.time()}
            for v in vals
        ]
        contras = [{"resolution": r} for r in profile.metadata.get("resolution_history", [])]

        new_type = classify_slot(norm, facts, contras)
        conf = compute_slot_confidence(norm, {
            "contradiction_count": profile.contradiction_count,
            "override_count": sum(1 for r in profile.metadata.get("resolution_history", []) if r in ("override", "accept_new", "always_latest")),
            "preserve_count": sum(1 for r in profile.metadata.get("resolution_history", []) if r in ("preserve", "keep_both", "coexist")),
            "ask_count": sum(1 for r in profile.metadata.get("resolution_history", []) if r in ("ask_user", "ask")),
            "distinct_values": profile.unique_values_seen,
            "high_trust_coexisting": len(profile.metadata.get("high_trust_values", [])),
        })

        profile.discovered_type = new_type
        profile.confidence = conf

        if new_type != old_type:
            _log_reclassification(
                norm, old_type, new_type, conf,
                trigger="fact_stored",
                evidence_summary={"value": value, "trust": trust_score},
                db_path=db,
            )
            logger.info(
                "[SLOT_DISCOVERY] Slot '%s' reclassified as %s (confidence: %.2f) after fact stored",
                norm, new_type.value, conf,
            )

    save_slot_profile(profile, db_path=db)


def on_contradiction_resolved(
    slot_name: str,
    resolution: str,
    was_suggested: str,
    db_path: Optional[str] = None,
) -> None:
    """Hook called when user resolves a contradiction differently than suggested.

    This is counter-evidence: e.g., user picks "keep both" on a slot the system
    thought was exclusive.
    """
    norm = slot_name.strip().lower().replace(" ", "_")
    if not norm:
        return

    db = db_path or _get_db_path()
    _ensure_tables(db)

    profile = load_slot_profile(norm, db_path=db)
    if not profile:
        return

    # Record the counter-evidence
    res_history = profile.metadata.get("resolution_history", [])
    res_history.append(resolution.strip().lower())
    profile.metadata["resolution_history"] = res_history[-20:]
    profile.evidence_count += 1
    profile.last_updated = time.time()

    # Reclassify
    old_type = profile.discovered_type
    facts = [{"value": v, "trust": 0.8, "timestamp": time.time()} for v in profile.metadata.get("values_seen", [])]
    contras = [{"resolution": r} for r in res_history]
    new_type = classify_slot(norm, facts, contras)
    conf = compute_slot_confidence(norm, {
        "contradiction_count": profile.contradiction_count,
        "override_count": sum(1 for r in res_history if r in ("override", "accept_new", "always_latest")),
        "preserve_count": sum(1 for r in res_history if r in ("preserve", "keep_both", "coexist")),
        "ask_count": sum(1 for r in res_history if r in ("ask_user", "ask")),
        "distinct_values": profile.unique_values_seen,
    })

    profile.discovered_type = new_type
    profile.confidence = conf
    profile.resolution_pattern = _determine_resolution_pattern(contras)
    save_slot_profile(profile, db_path=db)

    if new_type != old_type:
        _log_reclassification(
            norm, old_type, new_type, conf,
            trigger="user_override",
            evidence_summary={"resolution": resolution, "was_suggested": was_suggested},
            db_path=db,
        )
        logger.info(
            "[SLOT_DISCOVERY] Slot '%s' reclassified as %s (confidence: %.2f) after user chose '%s' over suggested '%s'",
            norm, new_type.value, conf, resolution, was_suggested,
        )


# ---------------------------------------------------------------------------
# Full discovery pass — for heartbeat / manual trigger
# ---------------------------------------------------------------------------

def analyze_slot_patterns(
    memory_db_path: Optional[str] = None,
    ledger_db_path: Optional[str] = None,
    discovery_db_path: Optional[str] = None,
) -> Dict[str, SlotProfile]:
    """Analyze all slots from memory facts and contradiction ledger.

    Queries memory_facts for all facts grouped by slot, and the contradictions
    table for all contradictions with affects_slots data.

    Returns dict of slot_name -> SlotProfile for every slot with enough data.
    """
    profiles: Dict[str, SlotProfile] = {}

    # --- Gather facts from memory DB ---
    slot_facts: Dict[str, List[Dict[str, Any]]] = {}
    if memory_db_path and Path(memory_db_path).exists():
        try:
            conn = sqlite3.connect(memory_db_path, timeout=30.0)
            conn.execute("PRAGMA busy_timeout=10000")
            rows = conn.execute("""
                SELECT mf.slot, mf.value, mf.normalized, m.trust, m.timestamp, mf.memory_id
                FROM memory_facts mf
                JOIN memories m ON mf.memory_id = m.memory_id
                WHERE m.deprecated = 0
                ORDER BY m.timestamp DESC
            """).fetchall()
            conn.close()
            for slot, value, normalized, trust, ts, mem_id in rows:
                slot_norm = slot.strip().lower()
                slot_facts.setdefault(slot_norm, []).append({
                    "value": normalized or value,
                    "trust": float(trust or 0),
                    "timestamp": float(ts or 0),
                    "memory_id": mem_id,
                })
        except Exception as e:
            logger.debug(f"[SLOT_DISCOVERY] Failed to read memory facts: {e}")

    # --- Gather contradictions from ledger DB ---
    slot_contras: Dict[str, List[Dict[str, Any]]] = {}
    if ledger_db_path and Path(ledger_db_path).exists():
        try:
            conn = sqlite3.connect(ledger_db_path, timeout=30.0)
            conn.execute("PRAGMA busy_timeout=10000")
            rows = conn.execute("""
                SELECT ledger_id, affects_slots, status, metadata, timestamp,
                       old_memory_id, new_memory_id, summary
                FROM contradictions
                ORDER BY timestamp DESC
            """).fetchall()
            conn.close()
            for ledger_id, affects, status, meta_json, ts, old_id, new_id, summary in rows:
                if not affects:
                    continue
                meta = {}
                try:
                    meta = json.loads(meta_json) if meta_json else {}
                except Exception:
                    pass
                suggested_policy = meta.get("suggested_policy", "")
                resolution = status if status == "resolved" else suggested_policy
                for slot in affects.split(","):
                    slot_norm = slot.strip().lower()
                    if not slot_norm:
                        continue
                    slot_contras.setdefault(slot_norm, []).append({
                        "resolution": resolution or suggested_policy,
                        "suggested_policy": suggested_policy,
                        "old_value": "",
                        "new_value": "",
                        "timestamp": float(ts or 0),
                        "summary": summary or "",
                    })
        except Exception as e:
            logger.debug(f"[SLOT_DISCOVERY] Failed to read contradictions: {e}")

    # --- Classify each slot ---
    all_slots = set(slot_facts.keys()) | set(slot_contras.keys())
    for slot in all_slots:
        facts = slot_facts.get(slot, [])
        contras = slot_contras.get(slot, [])

        if len(facts) < 2 and len(contras) == 0:
            continue

        slot_type = classify_slot(slot, facts, contras)

        # Count resolution types
        override_count = sum(1 for c in contras if str(c.get("resolution", "")).lower() in ("override", "accept_new", "always_latest", "resolved"))
        preserve_count = sum(1 for c in contras if str(c.get("resolution", "")).lower() in ("preserve", "keep_both", "coexist"))
        ask_count = sum(1 for c in contras if str(c.get("resolution", "")).lower() in ("ask_user", "ask"))

        distinct_values = set()
        for f in facts:
            v = str(f.get("value", "")).strip().lower()
            if v:
                distinct_values.add(v)

        conf = compute_slot_confidence(slot, {
            "contradiction_count": len(contras),
            "override_count": override_count,
            "preserve_count": preserve_count,
            "ask_count": ask_count,
            "distinct_values": len(distinct_values),
        })

        profiles[slot] = SlotProfile(
            slot_name=slot,
            discovered_type=slot_type,
            confidence=conf,
            evidence_count=len(facts) + len(contras),
            resolution_pattern=_determine_resolution_pattern(contras),
            unique_values_seen=len(distinct_values),
            contradiction_count=len(contras),
            avg_resolution_time=None,
            last_updated=time.time(),
            metadata={
                "values_seen": list(distinct_values),
            },
        )

    return profiles


def run_discovery_pass(
    memory_db_path: Optional[str] = None,
    ledger_db_path: Optional[str] = None,
    discovery_db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a full discovery pass — suitable for heartbeat or manual trigger.

    Analyzes all slots, compares with existing profiles, saves updates,
    and returns a summary.
    """
    db = discovery_db_path or _get_db_path(memory_db_path)
    _ensure_tables(db)

    new_profiles = analyze_slot_patterns(
        memory_db_path=memory_db_path,
        ledger_db_path=ledger_db_path,
        discovery_db_path=db,
    )

    existing = {p.slot_name: p for p in load_all_profiles(db_path=db)}
    new_classifications: List[Tuple[str, str]] = []
    unchanged = 0

    for slot_name, new_profile in new_profiles.items():
        old_profile = existing.get(slot_name)
        if old_profile and old_profile.discovered_type == new_profile.discovered_type:
            # Update evidence counts even if type unchanged
            if new_profile.evidence_count > old_profile.evidence_count:
                save_slot_profile(new_profile, db_path=db)
            unchanged += 1
        else:
            save_slot_profile(new_profile, db_path=db)
            new_classifications.append((slot_name, new_profile.discovered_type.value))
            old_type = old_profile.discovered_type if old_profile else None
            _log_reclassification(
                slot_name, old_type, new_profile.discovered_type,
                new_profile.confidence,
                trigger="heartbeat_pass",
                evidence_summary={
                    "evidence_count": new_profile.evidence_count,
                    "contradiction_count": new_profile.contradiction_count,
                    "unique_values": new_profile.unique_values_seen,
                },
                db_path=db,
            )

    return {
        "new_classifications": new_classifications,
        "unchanged": unchanged,
        "total_slots": len(new_profiles),
    }


# ---------------------------------------------------------------------------
# Stats helper
# ---------------------------------------------------------------------------

def get_slot_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return summary stats for the slot discovery system."""
    profiles = load_all_profiles(db_path=db_path)
    type_counts: Dict[str, int] = {}
    confidence_buckets = {"high": 0, "medium": 0, "low": 0, "none": 0}

    for p in profiles:
        t = p.discovered_type.value
        type_counts[t] = type_counts.get(t, 0) + 1
        if p.confidence >= 0.8:
            confidence_buckets["high"] += 1
        elif p.confidence >= 0.5:
            confidence_buckets["medium"] += 1
        elif p.confidence > 0:
            confidence_buckets["low"] += 1
        else:
            confidence_buckets["none"] += 1

    typed = sum(v for k, v in type_counts.items() if k != "unknown")
    untyped = type_counts.get("unknown", 0)

    return {
        "total_slots": len(profiles),
        "typed": typed,
        "untyped": untyped,
        "type_breakdown": type_counts,
        "confidence_distribution": confidence_buckets,
        "seed_exclusive_count": len(_SEED_EXCLUSIVE),
        "seed_additive_count": len(_SEED_ADDITIVE),
    }
