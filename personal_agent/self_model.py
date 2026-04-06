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

    # ------------------------------------------------------------------
    # Behavioral directives — reflection → action
    # ------------------------------------------------------------------

    # Domain keywords that map blindspot/uncertainty text to query domains
    _DOMAIN_KEYWORDS: Dict[str, List[str]] = {
        "temporal": ["time", "when", "date", "ago", "recently", "last", "year", "month",
                     "week", "day", "timeline", "history", "before", "after", "since"],
        "names": ["name", "who", "person", "people", "called", "named", "confusing",
                  "similar-sounding"],
        "numerical": ["number", "count", "how many", "how much", "percentage", "ratio",
                      "score", "total", "amount", "statistic"],
        "preference": ["favorite", "favourite", "prefer", "like", "dislike", "love",
                       "hate", "best", "worst", "opinion"],
        "recency": ["latest", "newest", "most recent", "current", "now", "today",
                    "updated", "changed"],
        "recall": ["memory", "recall", "remember", "forgot", "forget", "degradation",
                   "cognitive load"],
        "accuracy": ["accuracy", "factual", "confident", "over-stat", "complex topics",
                     "contradiction"],
    }

    # Hedging instructions per domain
    _DOMAIN_HEDGES: Dict[str, str] = {
        "temporal": "Cite explicit dates/timeframes. Say 'around' or 'approximately' for uncertain timestamps.",
        "names": "Double-check name references against stored memories before stating them.",
        "numerical": "Hedge numerical claims with 'approximately' unless you have exact data.",
        "preference": "Confirm preference values against stored memories; preferences may have changed.",
        "recency": "Flag whether your information may be outdated. Qualify with 'as of [date]' when possible.",
        "recall": "Verify claims against stored memories before stating them. If unsure, say so.",
        "accuracy": "Hedge confident-sounding claims. Use 'I believe' or 'based on what I have' instead of absolutes.",
    }

    def get_behavioral_directives(self, query: str = "") -> Dict[str, Any]:
        """Parse actionable slots into behavioral flags for the generation pipeline.

        Returns:
            {
                "caution_domains": ["temporal", "names", ...],
                "hedge_instructions": ["Cite explicit dates...", ...],
                "gate_boost": float,  # additive threshold raise (0.0-0.15)
                "correction_note": str | None,
            }
        """
        directives: Dict[str, Any] = {
            "caution_domains": [],
            "hedge_instructions": [],
            "gate_boost": 0.0,
            "correction_note": None,
        }

        # Read the 3 actionable slots
        blindspots = (self.read_slot("known_blindspots") or "").lower()
        uncertainty = (self.read_slot("uncertainty_domains") or "").lower()
        correction = (self.read_slot("correction_pattern") or "").strip()

        if correction:
            directives["correction_note"] = correction

        # Combine blindspot + uncertainty text for domain matching
        awareness_text = f"{blindspots} {uncertainty}"
        if not awareness_text.strip():
            return directives

        # Detect which domains the system knows it's weak in
        weak_domains: List[str] = []
        for domain, keywords in self._DOMAIN_KEYWORDS.items():
            if any(kw in awareness_text for kw in keywords):
                weak_domains.append(domain)

        if not weak_domains:
            return directives

        # If a query is provided, check if it touches a weak domain
        query_lower = query.lower()
        active_domains: List[str] = []
        for domain in weak_domains:
            domain_kws = self._DOMAIN_KEYWORDS[domain]
            if not query_lower or any(kw in query_lower for kw in domain_kws):
                active_domains.append(domain)

        if active_domains:
            directives["caution_domains"] = active_domains
            directives["hedge_instructions"] = [
                self._DOMAIN_HEDGES[d] for d in active_domains
                if d in self._DOMAIN_HEDGES
            ]
            # Gate boost: 0.05 per active weak domain, capped at 0.15
            directives["gate_boost"] = min(len(active_domains) * 0.05, 0.15)

        return directives

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

    def read_all_active_entries(self) -> List[Dict[str, Any]]:
        """Return all active self-model entries with full metadata for auditing."""
        mem_db = self._find_memory_db()
        if mem_db is None:
            return []
        try:
            conn = _get_db_connection(str(mem_db))
            rows = conn.execute(
                """SELECT memory_id, text, trust, vector_json, timestamp
                   FROM memories
                   WHERE kind = 'self_model'
                     AND (deprecated IS NULL OR deprecated = 0)
                   ORDER BY trust DESC""",
            ).fetchall()
            conn.close()
            results = []
            for r in rows:
                text = r["text"]
                slot = None
                for s in SELF_MODEL_SLOTS:
                    if text.startswith(f"[self_model:{s}]"):
                        slot = s
                        break
                results.append({
                    "memory_id": r["memory_id"],
                    "text": text,
                    "trust": r["trust"],
                    "vector_json": r["vector_json"],
                    "timestamp": r["timestamp"],
                    "slot": slot,
                })
            return results
        except Exception as exc:
            logger.debug("[SELF_MODEL] read_all_active_entries failed: %s", exc)
            return []

    def deprecate_entry(self, memory_id: str, reason: str) -> bool:
        """Deprecate a specific self-model entry by memory_id."""
        mem_db = self._find_memory_db()
        if mem_db is None:
            return False
        try:
            conn = _get_db_connection(str(mem_db))
            conn.execute(
                "UPDATE memories SET deprecated=1, deprecation_reason=? WHERE memory_id=?",
                (reason, memory_id),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as exc:
            logger.warning("[SELF_MODEL] deprecate_entry failed: %s", exc)
            return False

    def update_entry_trust(self, memory_id: str, new_trust: float) -> bool:
        """Update trust for a specific self-model entry."""
        mem_db = self._find_memory_db()
        if mem_db is None:
            return False
        try:
            conn = _get_db_connection(str(mem_db))
            conn.execute(
                "UPDATE memories SET trust=? WHERE memory_id=?",
                (new_trust, memory_id),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as exc:
            logger.warning("[SELF_MODEL] update_entry_trust failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Execution state verification — runs on startup to keep self-model current
# ---------------------------------------------------------------------------

def verify_execution_state() -> Dict[str, str]:
    """Check current system state and return facts about what's running.

    Call this on startup to ensure the self-model has accurate information
    about enabled/disabled features, active models, and system scale.
    Prevents stale beliefs like "agent loop is disabled" when it's actually live.
    """
    state: Dict[str, str] = {}
    import os

    # Agent loop / orchestrator status
    try:
        from routes.chat import _AGENT_LOOP_ENABLED
        state["agent_loop"] = "enabled" if _AGENT_LOOP_ENABLED else "disabled"
    except Exception:
        # Check by inspecting the code directly
        try:
            import inspect
            from routes import chat as _chat_mod
            src = inspect.getsource(_chat_mod)
            if "and False" in src and "_layer4_orchestrator" in src:
                state["agent_loop"] = "disabled (and False gate found)"
            else:
                state["agent_loop"] = "enabled (no gate found)"
        except Exception:
            state["agent_loop"] = "unknown"

    # Active models
    state["generation_model"] = os.getenv("CRT_OLLAMA_MODEL", "unknown")
    state["intent_model"] = os.getenv("CRT_INTENT_MODEL", "unknown")

    # Memory scale
    try:
        import sqlite3
        mem_db = os.getenv("CRT_SHARED_MEMORY", "personal_agent/crt_memory_shared.db")
        if os.path.exists(mem_db):
            conn = sqlite3.connect(mem_db)
            cnt = conn.execute("SELECT COUNT(*) FROM memories WHERE deprecated=0").fetchone()[0]
            conn.close()
            state["active_memories"] = str(cnt)
    except Exception:
        pass

    # Claude CLI availability
    try:
        from personal_agent.cookie_orchestrator import ClaudeCliBrain
        brain = ClaudeCliBrain()
        state["claude_cli"] = f"available ({brain._bin})"
    except Exception:
        state["claude_cli"] = "unavailable"

    logger.info("[SELF_MODEL] Execution state: %s", state)
    return state


def write_execution_state_to_memory(state: Optional[Dict[str, str]] = None) -> None:
    """Write verified execution state to CRT memory store.

    Creates/updates a special memory with kind='ops' that contains the current
    system state. This memory has a 7-day review_after so it auto-stales if
    not refreshed.
    """
    if state is None:
        state = verify_execution_state()

    summary_parts = []
    for k, v in state.items():
        summary_parts.append(f"{k}: {v}")
    text = "System execution state (auto-verified on startup): " + "; ".join(summary_parts)

    sm = get_self_model()
    mem_db = sm._find_memory_db()
    if mem_db is None:
        return

    try:
        import uuid, json as _json
        conn = _get_db_connection(str(mem_db))

        # Deprecate previous execution state memories
        conn.execute(
            """UPDATE memories SET deprecated = 1
               WHERE kind = 'ops'
               AND text LIKE 'System execution state%'
               AND (deprecated IS NULL OR deprecated = 0)"""
        )

        memory_id = str(uuid.uuid4())
        now = time.time()
        review_after = now + 7 * 86400  # 7-day review
        conn.execute(
            """INSERT INTO memories
                (memory_id, text, timestamp, confidence, trust, source,
                 kind, thread_id, deprecated, vector_json, sse_mode,
                 source_kind, review_after)
            VALUES (?, ?, ?, 0.90, 0.90, 'system', 'ops', 'system', 0, ?, 'L',
                    'system', ?)""",
            (memory_id, text, now, _json.dumps([]), review_after),
        )
        conn.commit()
        conn.close()
        logger.info("[SELF_MODEL] Wrote execution state memory: %s", memory_id)
    except Exception as exc:
        logger.warning("[SELF_MODEL] Execution state write failed: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: Optional[SelfModel] = None


def get_self_model(db_path: Optional[str] = None) -> SelfModel:
    global _instance
    if _instance is None:
        _instance = SelfModel(db_path=db_path)
    return _instance
