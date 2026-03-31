"""
CRT Session State — Running Belief State per Conversation

Tracks turn-by-turn epistemic changes during a conversation: trust shifts,
contradictions detected/resolved, slot classifications, memory citations.
No LLM calls — pure aggregation from existing pipeline signals.

Inspired by Claude Code's .session.md (11 structured sections, updated
after each turn) but transformed through CRT: this isn't a content summary,
it's a belief state that evolves.

Unlocks:
1. Compaction source — hot memory IDs prioritized for verbatim
2. Away/resume belief diff — what changed since user was last here
3. Density-weighted extraction trigger — replaces 30-min timer
4. Consolidation prioritization — session-flagged contradictions first
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_TURNS_KEPT = 50
SESSION_GAP_SECONDS = 1800        # 30 min idle → new session segment
SESSION_EVICT_SECONDS = 7200      # 2 hours idle → evict from memory
FLUSH_EVERY_N_TURNS = 5

# Density extraction thresholds
DEFAULT_TOKEN_THRESHOLD = 5000
DEFAULT_DENSITY_THRESHOLD = 0.02
DEFAULT_TIME_FALLBACK = 1800      # 30 min safety net


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TurnSnapshot:
    """Per-turn epistemic snapshot."""
    turn_number: int
    timestamp: float
    memories_created_ids: List[str] = field(default_factory=list)
    trust_shifts: List[Dict[str, Any]] = field(default_factory=list)
    contradictions_detected: List[str] = field(default_factory=list)
    contradictions_resolved: List[str] = field(default_factory=list)
    slots_classified: Dict[str, Any] = field(default_factory=dict)
    memories_cited_ids: List[str] = field(default_factory=list)
    tokens_estimated: int = 0
    density_score: float = 0.0


@dataclass
class SessionState:
    """Per-session running belief state."""
    thread_id: str
    session_start: float
    last_active: float
    turns: List[TurnSnapshot] = field(default_factory=list)

    # Rolling aggregates
    total_trust_delta: float = 0.0
    open_contradiction_count: int = 0
    memories_confirmed: int = 0       # trust went up
    memories_expired: int = 0         # trust hit floor or deprecated
    cumulative_tokens: int = 0
    cumulative_numerator: int = 0     # slots + contradictions + trust_shifts
    turns_since_last_extraction: int = 0
    last_extraction_ts: float = 0.0

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def cumulative_density(self) -> float:
        if self.cumulative_tokens < 1:
            return 0.0
        return self.cumulative_numerator / self.cumulative_tokens

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "session_start": self.session_start,
            "last_active": self.last_active,
            "turn_count": self.turn_count,
            "total_trust_delta": round(self.total_trust_delta, 4),
            "open_contradiction_count": self.open_contradiction_count,
            "memories_confirmed": self.memories_confirmed,
            "memories_expired": self.memories_expired,
            "cumulative_tokens": self.cumulative_tokens,
            "cumulative_numerator": self.cumulative_numerator,
            "cumulative_density": round(self.cumulative_density, 4),
            "turns_since_last_extraction": self.turns_since_last_extraction,
            "last_extraction_ts": self.last_extraction_ts,
            "turns": [asdict(t) for t in self.turns[-10:]],  # last 10 for serialization
        }


# ---------------------------------------------------------------------------
# In-memory session store (thread-safe)
# ---------------------------------------------------------------------------

_sessions: Dict[str, SessionState] = {}
_lock = threading.Lock()


def get_or_create_session(thread_id: str) -> SessionState:
    """Get existing session or create fresh one.

    Creates a new session if:
    - No session exists for this thread
    - Gap since last_active > SESSION_GAP_SECONDS
    """
    now = time.time()

    with _lock:
        session = _sessions.get(thread_id)

        if session is not None:
            gap = now - session.last_active
            if gap > SESSION_GAP_SECONDS:
                # Session expired — start fresh but preserve the old one's data
                # for the away/resume diff
                logger.info(
                    f"[SESSION_STATE] Session gap {gap:.0f}s for {thread_id[:12]}, "
                    f"starting new segment (old: {session.turn_count} turns)"
                )
                old_session = session
                session = SessionState(
                    thread_id=thread_id,
                    session_start=now,
                    last_active=now,
                )
                # Stash the old session for away/resume diff
                session._previous = old_session  # type: ignore
                _sessions[thread_id] = session
            elif gap > SESSION_EVICT_SECONDS:
                # Very stale — evict entirely
                session = SessionState(
                    thread_id=thread_id,
                    session_start=now,
                    last_active=now,
                )
                _sessions[thread_id] = session
        else:
            # Try loading from DB
            session = _try_load_from_db(thread_id)
            if session is None:
                session = SessionState(
                    thread_id=thread_id,
                    session_start=now,
                    last_active=now,
                )
            _sessions[thread_id] = session

        return session


def _try_load_from_db(thread_id: str) -> Optional[SessionState]:
    """Try to load persisted session state from DB."""
    try:
        from personal_agent.db_utils import get_db_connection
        db_path = _resolve_session_db()
        if not db_path or not Path(db_path).exists():
            return None

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT state_json, updated_at FROM session_snapshots WHERE thread_id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            state_dict = json.loads(row[0])
            session = SessionState(
                thread_id=state_dict.get("thread_id", thread_id),
                session_start=state_dict.get("session_start", 0),
                last_active=state_dict.get("last_active", 0),
                total_trust_delta=state_dict.get("total_trust_delta", 0),
                open_contradiction_count=state_dict.get("open_contradiction_count", 0),
                memories_confirmed=state_dict.get("memories_confirmed", 0),
                memories_expired=state_dict.get("memories_expired", 0),
                cumulative_tokens=state_dict.get("cumulative_tokens", 0),
                cumulative_numerator=state_dict.get("cumulative_numerator", 0),
                turns_since_last_extraction=state_dict.get("turns_since_last_extraction", 0),
                last_extraction_ts=state_dict.get("last_extraction_ts", 0),
            )
            return session
    except Exception as e:
        logger.debug(f"[SESSION_STATE] DB load failed for {thread_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# Per-turn recording
# ---------------------------------------------------------------------------

def record_turn(
    session: SessionState,
    *,
    result: Dict[str, Any],
    prompt_mems: List[Dict[str, Any]],
    message: str,
    engine_memory: Any,
    turn_start_ts: Optional[float] = None,
) -> TurnSnapshot:
    """Record a single turn's epistemic signals into the session state.

    Aggregates from existing pipeline signals — no LLM calls.
    Target: <50ms (3 indexed SQLite reads + in-memory math).
    """
    now = time.time()
    ts = turn_start_ts or (now - 5.0)  # approximate if not provided

    turn_number = session.turn_count + 1

    # --- Slots classified ---
    slots = result.get("slots_extracted") or result.get("facts") or {}
    if not isinstance(slots, dict):
        slots = {}

    # --- Memories cited ---
    cited_ids = []
    for m in (prompt_mems or []):
        if isinstance(m, dict):
            mid = m.get("memory_id")
            if mid:
                cited_ids.append(mid)

    # --- Trust shifts this turn ---
    trust_shifts = []
    try:
        db_path = getattr(engine_memory, "db_path", None)
        if db_path and Path(db_path).exists():
            import sqlite3
            conn = sqlite3.connect(db_path, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_id, old_trust, new_trust, reason FROM trust_log "
                "WHERE timestamp > ? ORDER BY timestamp",
                (ts,)
            )
            for row in cursor.fetchall():
                trust_shifts.append({
                    "memory_id": row[0],
                    "old_trust": row[1],
                    "new_trust": row[2],
                    "reason": row[3],
                })
            conn.close()
    except Exception as e:
        logger.debug(f"[SESSION_STATE] trust_log query failed: {e}")

    # --- Contradictions detected this turn ---
    contradictions_detected = []
    contradictions_resolved = []
    try:
        led_path = getattr(engine_memory, "db_path", "").replace("crt_memory", "crt_ledger")
        if led_path and Path(led_path).exists():
            import sqlite3
            conn = sqlite3.connect(led_path, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ledger_id, status FROM contradictions WHERE timestamp > ?",
                (ts,)
            )
            for row in cursor.fetchall():
                if row[1] in ("open", "reflecting"):
                    contradictions_detected.append(row[0])
                else:
                    contradictions_resolved.append(row[0])
            conn.close()
    except Exception as e:
        logger.debug(f"[SESSION_STATE] contradictions query failed: {e}")

    # --- Token estimate ---
    tokens = max(1, len(message) // 4)

    # --- Density score ---
    numerator = len(slots) + len(contradictions_detected) + len(trust_shifts)
    density = numerator / max(1, tokens)

    # --- Build snapshot ---
    snapshot = TurnSnapshot(
        turn_number=turn_number,
        timestamp=now,
        memories_created_ids=[],  # populated by store_memory hooks if wired
        trust_shifts=trust_shifts,
        contradictions_detected=contradictions_detected,
        contradictions_resolved=contradictions_resolved,
        slots_classified=slots,
        memories_cited_ids=cited_ids,
        tokens_estimated=tokens,
        density_score=density,
    )

    # --- Update rolling aggregates ---
    session.last_active = now
    session.cumulative_tokens += tokens
    session.cumulative_numerator += numerator
    session.turns_since_last_extraction += 1

    # Trust delta
    for ts_entry in trust_shifts:
        old_t = ts_entry.get("old_trust", 0)
        new_t = ts_entry.get("new_trust", 0)
        delta = new_t - old_t
        session.total_trust_delta += delta
        if delta > 0:
            session.memories_confirmed += 1
        elif delta < -0.1:  # significant drop
            session.memories_expired += 1

    session.open_contradiction_count += len(contradictions_detected)
    session.open_contradiction_count -= len(contradictions_resolved)
    session.open_contradiction_count = max(0, session.open_contradiction_count)

    # Append and cap
    session.turns.append(snapshot)
    if len(session.turns) > MAX_TURNS_KEPT:
        session.turns = session.turns[-MAX_TURNS_KEPT:]

    # Periodic flush
    if turn_number % FLUSH_EVERY_N_TURNS == 0:
        try:
            flush_to_db(session)
        except Exception:
            pass

    logger.info(
        f"[SESSION_STATE] turn={turn_number} thread={session.thread_id[:12]} "
        f"slots={len(slots)} cited={len(cited_ids)} trust_shifts={len(trust_shifts)} "
        f"contras={len(contradictions_detected)} density={density:.4f} "
        f"cumulative_density={session.cumulative_density:.4f}"
    )

    return snapshot


# ---------------------------------------------------------------------------
# Density-weighted extraction trigger
# ---------------------------------------------------------------------------

def should_extract(
    session: SessionState,
    token_threshold: int = DEFAULT_TOKEN_THRESHOLD,
    density_threshold: float = DEFAULT_DENSITY_THRESHOLD,
    time_fallback: float = DEFAULT_TIME_FALLBACK,
) -> bool:
    """Should we trigger memory extraction for this session?

    Dual trigger: tokens OR density, with time-based safety net.
    """
    now = time.time()

    # Token threshold — enough content to extract from
    if session.cumulative_tokens >= token_threshold:
        logger.debug(f"[SESSION_STATE] Extract trigger: token threshold ({session.cumulative_tokens} >= {token_threshold})")
        return True

    # Density threshold — information-rich but shorter conversation
    if (session.cumulative_density >= density_threshold
            and session.cumulative_tokens >= 500):
        logger.debug(f"[SESSION_STATE] Extract trigger: density ({session.cumulative_density:.4f} >= {density_threshold})")
        return True

    # Time fallback — safety net
    if session.last_extraction_ts > 0:
        elapsed = now - session.last_extraction_ts
    else:
        elapsed = now - session.session_start

    if elapsed >= time_fallback and session.cumulative_tokens > 100:
        logger.debug(f"[SESSION_STATE] Extract trigger: time fallback ({elapsed:.0f}s >= {time_fallback})")
        return True

    return False


# ---------------------------------------------------------------------------
# Away/resume belief state diff
# ---------------------------------------------------------------------------

def render_away_resume_diff(session: SessionState) -> str:
    """Render what changed since the user was last here.

    Called when gap > 30 min detected. Returns formatted string
    for system prompt injection.
    """
    # Check for previous session data
    prev = getattr(session, "_previous", None)
    if prev is None:
        return ""

    lines = ["## Since you were last here:"]

    # Trust changes
    if prev.total_trust_delta != 0:
        direction = "+" if prev.total_trust_delta > 0 else ""
        lines.append(
            f"- Trust changes: {prev.memories_confirmed} confirmed, "
            f"{prev.memories_expired} expired "
            f"(net delta: {direction}{prev.total_trust_delta:.2f})"
        )

    # Contradictions
    if prev.open_contradiction_count > 0:
        lines.append(f"- Open contradictions: {prev.open_contradiction_count}")

    # Density
    if prev.cumulative_density > 0:
        label = "high-density" if prev.cumulative_density > 0.03 else "normal"
        lines.append(
            f"- Session was {label} ({prev.turn_count} turns, "
            f"density={prev.cumulative_density:.3f})"
        )

    # Last turn details
    if prev.turns:
        last = prev.turns[-1]
        if last.slots_classified:
            slot_names = list(last.slots_classified.keys())[:3]
            lines.append(f"- Last detected slots: {', '.join(slot_names)}")
        if last.contradictions_detected:
            lines.append(f"- Last turn had {len(last.contradictions_detected)} new contradiction(s)")

    if len(lines) == 1:
        return ""  # nothing meaningful to report

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hot memory IDs (for compaction prioritization)
# ---------------------------------------------------------------------------

def get_hot_memory_ids(session: SessionState) -> Set[str]:
    """Get memory IDs that were active this session.

    Union of: cited, trust-shifted, and contradiction-involved memories.
    These get priority boost in compaction.
    """
    hot: Set[str] = set()

    for turn in session.turns:
        hot.update(turn.memories_cited_ids)
        hot.update(turn.memories_created_ids)
        for ts in turn.trust_shifts:
            mid = ts.get("memory_id")
            if mid:
                hot.add(mid)

    return hot


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

def _resolve_session_db() -> Optional[str]:
    """Find the thread sessions DB path."""
    candidates = [
        Path("personal_agent/crt_thread_sessions.db"),
        Path("data/crt_thread_sessions.db"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Default — will be created
    return str(candidates[0])


def _ensure_table(db_path: str) -> None:
    """Create session_snapshots table if needed."""
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_snapshots (
            thread_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def flush_to_db(session: SessionState, db_path: Optional[str] = None) -> None:
    """Persist session state to SQLite."""
    import sqlite3

    db_path = db_path or _resolve_session_db()
    if not db_path:
        return

    _ensure_table(db_path)

    state_json = json.dumps(session.to_dict())
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        INSERT OR REPLACE INTO session_snapshots (thread_id, state_json, updated_at)
        VALUES (?, ?, ?)
    """, (session.thread_id, state_json, time.time()))
    conn.commit()
    conn.close()

    logger.debug(f"[SESSION_STATE] Flushed {session.thread_id[:12]} ({session.turn_count} turns)")
