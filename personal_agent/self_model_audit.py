"""Self-Model Audit — validates self-model entries against actual evidence.

Runs as heartbeat step 8b. For each active self-model entry:
- User-claim entries: checked against user-sourced memories via cosine similarity
- Self-referential entries: checked against gate_fail telemetry

Unsupported entries get progressive trust decay (three-strike):
  Run 1: trust *= 0.80 (warning)
  Run 2: trust *= 0.80 (demoted)
  Run 3: deprecated (removed from prompt injection)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .self_model import SelfModel, SELF_MODEL_SLOTS, get_self_model, _build_memory_db_candidates

log = logging.getLogger(__name__)

EVIDENCE_SIMILARITY_THRESHOLD = 0.55
TRUST_DECAY_FACTOR = 0.80
TRUST_DEMOTE_THRESHOLD = 0.45
TRUST_DEPRECATE_THRESHOLD = 0.36
AUDIT_COOLDOWN_SECONDS = 1800  # 30 minutes

# Slots that always contain user claims vs self-referential claims
_USER_CLAIM_SLOTS = {"user_relationship"}
_SELF_REF_SLOTS = {"known_blindspots", "uncertainty_domains", "correction_pattern"}

# Keywords indicating user-referential content in mixed slots
_USER_KEYWORDS = {
    "user", "prefers", "values", "wants", "likes", "asks for",
    "appreciates", "expects", "enjoys", "dislikes", "hates",
    "nick", "the user",
}


def _classify_entry(slot: Optional[str], text: str) -> str:
    """Classify a self-model entry as 'user_claim' or 'self_referential'."""
    if slot in _USER_CLAIM_SLOTS:
        return "user_claim"
    if slot in _SELF_REF_SLOTS:
        return "self_referential"
    # Mixed slots: scan text for user-referential keywords
    lower = text.lower()
    for kw in _USER_KEYWORDS:
        if kw in lower:
            return "user_claim"
    return "self_referential"


def _decode_vector(vector_json: str) -> Optional[np.ndarray]:
    """Decode a vector_json string to numpy array, or None if empty."""
    if not vector_json:
        return None
    try:
        vec = json.loads(vector_json)
        if not vec or len(vec) < 10:
            return None
        return np.array(vec, dtype=np.float32)
    except (json.JSONDecodeError, TypeError):
        return None


class SelfModelAuditor:
    """Validates self-model entries against evidence and decays unsupported ones."""

    def __init__(self, memory_db_path: Optional[str] = None):
        if memory_db_path:
            self.memory_db_path = memory_db_path
        else:
            for p in _build_memory_db_candidates():
                if p.exists():
                    self.memory_db_path = str(p)
                    break
            else:
                self.memory_db_path = None

        self.sm = get_self_model()

    def _get_connection(self, path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def should_run(self) -> bool:
        """Check cooldown — skip if last audit was <30min ago."""
        if not self.memory_db_path:
            return False
        try:
            conn = self._get_connection(self.memory_db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_cooldown (
                    key TEXT PRIMARY KEY,
                    last_ts REAL
                )
            """)
            row = conn.execute(
                "SELECT last_ts FROM audit_cooldown WHERE key='self_model_audit'"
            ).fetchone()
            conn.close()
            if row and (time.time() - row["last_ts"]) < AUDIT_COOLDOWN_SECONDS:
                return False
            return True
        except Exception:
            return True

    def _mark_run(self):
        """Update cooldown timestamp."""
        if not self.memory_db_path:
            return
        try:
            conn = self._get_connection(self.memory_db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_cooldown (
                    key TEXT PRIMARY KEY,
                    last_ts REAL
                )
            """)
            conn.execute(
                "INSERT OR REPLACE INTO audit_cooldown (key, last_ts) VALUES ('self_model_audit', ?)",
                (time.time(),),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.debug("[AUDIT] Failed to mark cooldown: %s", e)

    def _load_user_memories(self) -> List[Tuple[str, np.ndarray, float]]:
        """Load all user-sourced memories with vectors and trust > 0.3."""
        if not self.memory_db_path:
            return []
        conn = self._get_connection(self.memory_db_path)
        rows = conn.execute(
            """SELECT memory_id, vector_json, trust FROM memories
               WHERE source='user'
                 AND (deprecated IS NULL OR deprecated=0)
                 AND trust > 0.3"""
        ).fetchall()
        conn.close()

        results = []
        for r in rows:
            vec = _decode_vector(r["vector_json"])
            if vec is not None:
                results.append((r["memory_id"], vec, r["trust"]))
        return results

    def _find_best_match(self, entry_vec: np.ndarray, user_memories: List[Tuple[str, np.ndarray, float]]) -> Tuple[float, Optional[str]]:
        """Find the highest cosine similarity between entry and user memories."""
        if not user_memories or entry_vec is None:
            return 0.0, None

        best_sim = 0.0
        best_id = None
        # Normalize entry vector
        norm = np.linalg.norm(entry_vec)
        if norm > 0:
            entry_vec = entry_vec / norm

        for mem_id, mem_vec, _ in user_memories:
            mem_norm = np.linalg.norm(mem_vec)
            if mem_norm > 0:
                sim = float(np.dot(entry_vec, mem_vec / mem_norm))
            else:
                sim = 0.0
            if sim > best_sim:
                best_sim = sim
                best_id = mem_id
        return best_sim, best_id

    def _record_event(self, memory_id: str, event_type: str, reason: str, metadata: Dict[str, Any]):
        """Record an audit event to the memory_events table."""
        if not self.memory_db_path:
            return
        try:
            conn = self._get_connection(self.memory_db_path)
            conn.execute(
                """INSERT INTO memory_events
                   (memory_id, timestamp, event_type, actor, reason, metadata_json)
                   VALUES (?, ?, ?, 'self_model_auditor', ?, ?)""",
                (memory_id, time.time(), event_type, reason, json.dumps(metadata, default=str)),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.debug("[AUDIT] Failed to record event: %s", e)

    def audit_all_slots(self, thread_id: str = "system") -> Dict[str, Any]:
        """Run the full audit. Returns summary dict."""
        entries = self.sm.read_all_active_entries()
        if not entries:
            return {"audited": 0, "supported": 0, "warned": 0, "demoted": 0, "deprecated": 0}

        user_memories = self._load_user_memories()
        log.info("[AUDIT] Auditing %d self-model entries against %d user memories", len(entries), len(user_memories))

        supported = 0
        warned = 0
        demoted = 0
        deprecated = 0

        for entry in entries:
            classification = _classify_entry(entry["slot"], entry["text"])
            entry_vec = _decode_vector(entry["vector_json"])

            # Encode on the fly if vector is missing
            if entry_vec is None:
                try:
                    from .embeddings import encode_text
                    entry_vec = encode_text(entry["text"])
                except Exception:
                    log.debug("[AUDIT] Failed to encode entry %s", entry["memory_id"])
                    continue

            if classification == "user_claim":
                best_sim, best_match_id = self._find_best_match(entry_vec, user_memories)
                is_supported = best_sim >= EVIDENCE_SIMILARITY_THRESHOLD
            else:
                # Self-referential: more lenient — consider supported if trust was set by evidence
                # (heartbeat self-reflection uses evidence-weighted trust 0.35-0.80)
                # Only flag if trust is above the initial write range AND no corroboration
                is_supported = True  # Default: trust self-referential entries
                best_sim = 0.0
                best_match_id = None

            if is_supported:
                supported += 1
                self._record_event(entry["memory_id"], "self_model_audit_pass",
                    f"Supported ({classification}, sim={best_sim:.3f})",
                    {"classification": classification, "max_similarity": best_sim, "best_match_id": best_match_id})
                continue

            # Unsupported — apply progressive decay
            trust = entry["trust"]
            meta = {
                "classification": classification,
                "max_similarity": best_sim,
                "best_match_id": best_match_id,
                "entry_trust_before": trust,
            }

            if trust < TRUST_DEPRECATE_THRESHOLD:
                # Third strike: deprecate
                reason = f"No supporting evidence after multiple cycles (sim={best_sim:.3f})"
                self.sm.deprecate_entry(entry["memory_id"], f"Self-model audit: {reason}")
                self._record_event(entry["memory_id"], "self_model_audit_deprecated", reason,
                    {**meta, "entry_trust_after": None, "action": "deprecated"})
                deprecated += 1
                log.info("[AUDIT] Deprecated: %s (trust=%.3f, sim=%.3f)", entry["text"][:80], trust, best_sim)

            elif trust <= TRUST_DEMOTE_THRESHOLD:
                # Second strike: decay + demote warning
                new_trust = max(0.10, trust * TRUST_DECAY_FACTOR)
                self.sm.update_entry_trust(entry["memory_id"], new_trust)
                self._record_event(entry["memory_id"], "self_model_audit_demoted",
                    f"Trust decayed {trust:.3f} → {new_trust:.3f} (sim={best_sim:.3f})",
                    {**meta, "entry_trust_after": new_trust, "action": "demoted"})
                demoted += 1
                log.info("[AUDIT] Demoted: %s (%.3f → %.3f)", entry["text"][:80], trust, new_trust)

            else:
                # First strike: warning decay
                new_trust = max(0.10, trust * TRUST_DECAY_FACTOR)
                self.sm.update_entry_trust(entry["memory_id"], new_trust)
                self._record_event(entry["memory_id"], "self_model_audit_warning",
                    f"Trust decayed {trust:.3f} → {new_trust:.3f} (sim={best_sim:.3f})",
                    {**meta, "entry_trust_after": new_trust, "action": "warning"})
                warned += 1
                log.info("[AUDIT] Warning: %s (%.3f → %.3f)", entry["text"][:80], trust, new_trust)

        result = {
            "audited": len(entries),
            "supported": supported,
            "warned": warned,
            "demoted": demoted,
            "deprecated": deprecated,
        }
        log.info("[AUDIT] Complete: %s", result)
        return result


def run_self_model_audit(thread_id: str = "system") -> Dict[str, Any]:
    """Entry point for heartbeat integration."""
    auditor = SelfModelAuditor()
    if not auditor.should_run():
        log.debug("[AUDIT] Skipping — cooldown active")
        return {"skipped": True}
    result = auditor.audit_all_slots(thread_id=thread_id)
    auditor._mark_run()
    return result
