"""CRT Self-Model — persistent self-awareness for Aether.

The self-model gives the system a continuously evolving picture of its own
epistemic state. It is stored as ordinary CRT memories (kind='self_model')
so it inherits trust decay, contradiction detection, and append-only audit —
the same guarantees as every other claim the system holds.

Slots (one CRT memory per slot, trust reflects confidence in the assessment):

  uncertainty_domains   — topics where the system knows it often gets things wrong
  correction_pattern    — pattern observed in user corrections (e.g. "tends to over-state recency")
  trust_trajectory      — broad narrative of how trust has moved recently
  known_blindspots      — structural weaknesses (e.g. "poor temporal reasoning")
  growing_confidence    — areas where the system has been consistently reinforced
  user_relationship     — character of the interaction style with the primary user
  response_style        — current response style calibration notes

personality_checkpoints captures full periodic snapshots with diffs so the
timeline endpoint can show how the self-model has changed over time.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SELF_MODEL_SLOTS = [
    "uncertainty_domains",
    "correction_pattern",
    "trust_trajectory",
    "known_blindspots",
    "growing_confidence",
    "user_relationship",
    "response_style",
]

# Canonical DB path — same file as active_learning so it lives in one place
_DEFAULT_DB = Path("personal_agent/active_learning.db")

# Memory DB candidates (for storing self_model CRT memories).
# When CRT_SHARED_MEMORY is set the engine uses crt_memory_shared.db, so
# we must check that first so read_slot/update_slot target the same DB.
def _build_memory_db_candidates() -> list:
    import os as _os
    _shared = _os.environ.get("CRT_SHARED_MEMORY", "false").lower() == "true"
    _env_db = _os.environ.get("CRT_MEMORY_DB", "").strip()
    cands = []
    if _env_db:
        cands.append(Path(_env_db))
    if _shared:
        cands.append(Path("personal_agent/crt_memory_shared.db"))
    cands += [
        Path("personal_agent/crt_memory_shared.db"),
        Path("personal_agent/crt_memory.db"),
        Path("data/crt_memory.db"),
    ]
    return cands

_MEMORY_DB_CANDIDATES = _build_memory_db_candidates()


def _get_db_connection(path: str):
    """Open a WAL-mode SQLite connection."""
    import sqlite3
    conn = sqlite3.connect(path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.row_factory = sqlite3.Row
    return conn


class SelfModel:
    """Manages the system's persistent self-knowledge.

    Writes go through two paths:
    - personality_checkpoints table in active_learning.db (full periodic snapshots)
    - CRT memory store (kind='self_model') so each slot evolves with trust

    Reads for prompt injection use the trust-ordered slot values from
    the CRT memory store.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._init_checkpoints_table()

    # ------------------------------------------------------------------
    # Checkpoint table (full snapshots with diffs)
    # ------------------------------------------------------------------

    def _init_checkpoints_table(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = _get_db_connection(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personality_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    period_days REAL DEFAULT 1.0,
                    snapshot_json TEXT NOT NULL,
                    delta_json TEXT,
                    notable_events_json TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_personality_ts "
                "ON personality_checkpoints(ts)"
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("[SELF_MODEL] checkpoint table init failed: %s", exc)

    def checkpoint(
        self,
        snapshot: Dict[str, Any],
        delta: Optional[Dict[str, Any]] = None,
        notable_events: Optional[List[str]] = None,
        period_days: float = 1.0,
    ) -> None:
        """Write a full periodic snapshot with diff to personality_checkpoints."""
        try:
            conn = _get_db_connection(str(self.db_path))
            conn.execute(
                """
                INSERT INTO personality_checkpoints
                    (ts, period_days, snapshot_json, delta_json, notable_events_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    period_days,
                    json.dumps(snapshot, ensure_ascii=False),
                    json.dumps(delta, ensure_ascii=False) if delta else None,
                    json.dumps(notable_events, ensure_ascii=False) if notable_events else None,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("[SELF_MODEL] checkpoint write failed: %s", exc)

    def get_timeline(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return ordered personality checkpoints for the timeline endpoint."""
        try:
            conn = _get_db_connection(str(self.db_path))
            rows = conn.execute(
                """
                SELECT id, ts, period_days, snapshot_json, delta_json, notable_events_json
                FROM personality_checkpoints
                ORDER BY ts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            conn.close()
            result = []
            for r in rows:
                try:
                    result.append({
                        "id": r["id"],
                        "ts": r["ts"],
                        "period_days": r["period_days"],
                        "snapshot": json.loads(r["snapshot_json"] or "{}"),
                        "delta": json.loads(r["delta_json"] or "{}") if r["delta_json"] else None,
                        "notable_events": json.loads(r["notable_events_json"] or "[]") if r["notable_events_json"] else [],
                    })
                except Exception:
                    pass
            return result
        except Exception as exc:
            logger.warning("[SELF_MODEL] timeline read failed: %s", exc)
            return []

    def get_last_snapshot(self) -> Dict[str, Any]:
        """Return the most recent checkpoint snapshot, or empty dict."""
        timeline = self.get_timeline(limit=1)
        return timeline[0]["snapshot"] if timeline else {}

    # ------------------------------------------------------------------
    # CRT memory store — slot storage and retrieval
    # ------------------------------------------------------------------

    def _find_memory_db(self) -> Optional[Path]:
        for p in _MEMORY_DB_CANDIDATES:
            if p.exists():
                return p
        return None

    def update_slot(
        self,
        slot: str,
        value: str,
        trust: float = 0.5,
        thread_id: str = "system",
    ) -> Optional[str]:
        """Store or update a self-model slot in CRT memory.

        Uses direct SQL rather than going through the full CRTMemorySystem to
        avoid circular imports and keep the write lightweight.  The memory is
        stored with kind='self_model' and source='self_reflection'.
        """
        if slot not in SELF_MODEL_SLOTS:
            logger.warning("[SELF_MODEL] unknown slot '%s', skipping", slot)
            return None

        mem_db = self._find_memory_db()
        if mem_db is None:
            logger.debug("[SELF_MODEL] no memory DB found, skipping slot write")
            return None

        text = f"[self_model:{slot}] {value.strip()}"
        try:
            import uuid
            conn = _get_db_connection(str(mem_db))

            # Soft-deprecate any existing slot memories
            conn.execute(
                """
                UPDATE memories
                SET deprecated = 1
                WHERE kind = 'self_model'
                  AND text LIKE ?
                  AND (deprecated IS NULL OR deprecated = 0)
                """,
                (f"[self_model:{slot}]%",),
            )

            memory_id = str(uuid.uuid4())
            # vector_json and sse_mode are NOT NULL — provide defaults
            import json as _json
            empty_vec = _json.dumps([])
            conn.execute(
                """
                INSERT INTO memories
                    (memory_id, text, timestamp, confidence, trust, source,
                     kind, thread_id, deprecated, vector_json, sse_mode)
                VALUES (?, ?, ?, ?, ?, 'self_reflection', 'self_model', ?, 0, ?, 'L')
                """,
                (memory_id, text, time.time(), trust, trust, thread_id, empty_vec),
            )
            conn.commit()
            conn.close()
            logger.debug("[SELF_MODEL] wrote slot=%s trust=%.2f", slot, trust)
            return memory_id
        except Exception as exc:
            logger.warning("[SELF_MODEL] slot write failed slot=%s: %s", slot, exc)
            return None

    def read_slot(self, slot: str) -> Optional[str]:
        """Return current value of a single slot (strips the prefix tag)."""
        mem_db = self._find_memory_db()
        if mem_db is None:
            return None
        try:
            conn = _get_db_connection(str(mem_db))
            row = conn.execute(
                """
                SELECT text FROM memories
                WHERE kind = 'self_model'
                  AND text LIKE ?
                  AND (deprecated IS NULL OR deprecated = 0)
                ORDER BY trust DESC, timestamp DESC
                LIMIT 1
                """,
                (f"[self_model:{slot}]%",),
            ).fetchone()
            conn.close()
            if row:
                raw = row["text"]
                prefix = f"[self_model:{slot}] "
                return raw[len(prefix):] if raw.startswith(prefix) else raw
            return None
        except Exception as exc:
            logger.debug("[SELF_MODEL] read_slot failed slot=%s: %s", slot, exc)
            return None

    def read_model(self) -> Dict[str, Optional[str]]:
        """Return all slots as a dict {slot: value}."""
        return {slot: self.read_slot(slot) for slot in SELF_MODEL_SLOTS}

    def get_top_facts(self, n: int = 3) -> List[str]:
        """Return top-n trust-weighted self-model fact strings for prompt injection.

        Filters to only non-empty slots so the prompt block is always meaningful.
        """
        mem_db = self._find_memory_db()
        if mem_db is None:
            return []
        try:
            conn = _get_db_connection(str(mem_db))
            rows = conn.execute(
                """
                SELECT text, trust FROM memories
                WHERE kind = 'self_model'
                  AND (deprecated IS NULL OR deprecated = 0)
                ORDER BY trust DESC, timestamp DESC
                LIMIT ?
                """,
                (n,),
            ).fetchall()
            conn.close()
            facts = []
            for r in rows:
                raw = r["text"] or ""
                # Strip the [self_model:slot] prefix for readability
                if "] " in raw:
                    raw = raw.split("] ", 1)[1]
                if raw.strip():
                    facts.append(raw.strip())
            return facts
        except Exception as exc:
            logger.debug("[SELF_MODEL] get_top_facts failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: Optional[SelfModel] = None


def get_self_model(db_path: Optional[str] = None) -> SelfModel:
    global _instance
    if _instance is None:
        _instance = SelfModel(db_path=db_path)
    return _instance
