"""GroundCheck-to-CRT memory bridge.

Purpose:
- Make Copilot/GroundCheck profile knowledge available to normal CRT retrieval.
- Preserve provenance and trust while avoiding transcript/noise pollution.
- Keep imports conservative (slot-canonical + short high-trust narrative facts).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..crt_core import MemorySource
from ..fact_slots import extract_fact_slots

logger = logging.getLogger(__name__)


_DEFAULT_GROUNDCHECK_PATHS: tuple[str, ...] = (
    "D:/groundcheck/.groundcheck/memory.db",
    "../.groundcheck/memory.db",
    ".groundcheck/memory.db",
)

_MIN_NARRATIVE_CHARS = 10
_MAX_NARRATIVE_CHARS = 420


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = default
    return max(0.0, min(1.0, v))


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _is_good_narrative_fact(text: str) -> bool:
    t = str(text or "").strip()
    if len(t) < _MIN_NARRATIVE_CHARS or len(t) > _MAX_NARRATIVE_CHARS:
        return False
    lower = t.lower()
    # Avoid obvious transcript artifacts and tooling chatter.
    bad_markers = (
        "user:",
        "assistant:",
        "copilot, [",
        "portal>",
        "error:",
        "traceback",
        "to set up:",
    )
    return not any(marker in lower for marker in bad_markers)


def find_groundcheck_db() -> Optional[Path]:
    """Resolve GroundCheck DB path using env override + common defaults."""
    env = str(os.getenv("GROUNDCHECK_DB") or "").strip()
    candidates: List[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.extend(Path(p) for p in _DEFAULT_GROUNDCHECK_PATHS)

    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
        except Exception:
            continue
    return None


def _read_groundcheck_rows(
    *,
    min_trust: float = 0.2,
    limit: int = 400,
    allowed_sources: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    db_path = find_groundcheck_db()
    if not db_path:
        return []

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        table_cols = {str(r[1]).lower() for r in conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "id" not in table_cols or "text" not in table_cols:
            return []

        source_col = "source" if "source" in table_cols else "'unknown' AS source"
        trust_col = "trust" if "trust" in table_cols else "0.0 AS trust"
        ts_col = "timestamp" if "timestamp" in table_cols else "0 AS timestamp"
        thread_col = "thread_id" if "thread_id" in table_cols else "'default' AS thread_id"
        ns_col = "namespace" if "namespace" in table_cols else "'default' AS namespace"
        created_col = "created_at" if "created_at" in table_cols else "NULL AS created_at"

        where_bits = ["text IS NOT NULL", "TRIM(text) <> ''", f"{trust_col} >= ?"]
        params: List[Any] = [_clamp01(min_trust)]
        if allowed_sources:
            normalized = [str(s).strip() for s in allowed_sources if str(s).strip()]
            if normalized:
                placeholders = ",".join("?" for _ in normalized)
                where_bits.append(f"{source_col} IN ({placeholders})")
                params.extend(normalized)

        sql = f"""
            SELECT id, text, {trust_col}, {source_col}, {ts_col}, {thread_col}, {ns_col}, {created_col}
            FROM memories
            WHERE {" AND ".join(where_bits)}
            ORDER BY {ts_col} DESC
            LIMIT ?
        """
        params.append(max(1, int(limit)))
        rows = conn.execute(sql, tuple(params)).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": str(row["id"]),
                    "text": str(row["text"] or "").strip(),
                    "trust": _clamp01(row["trust"]),
                    "source": str(row["source"] or "unknown"),
                    "timestamp": float(row["timestamp"] or 0.0),
                    "thread_id": str(row["thread_id"] or "default"),
                    "namespace": str(row["namespace"] or "default"),
                    "created_at": row["created_at"],
                }
            )
        return out
    finally:
        conn.close()


def _collect_existing_bridge_state(memory_system: Any, thread_id: str) -> tuple[set[str], set[str]]:
    imported_ids: set[str] = set()
    imported_texts: set[str] = set()
    try:
        existing = memory_system._load_memories_filtered(  # noqa: SLF001
            source=MemorySource.EXTERNAL,
            thread_id=thread_id,
            limit=5000,
        )
    except Exception:
        existing = []

    for mem in existing:
        text_norm = _normalize_text(getattr(mem, "text", "") or "")
        if text_norm:
            imported_texts.add(text_norm)

        context = getattr(mem, "context", None)
        if not isinstance(context, dict):
            continue
        gc_meta = context.get("groundcheck")
        if isinstance(gc_meta, dict) and gc_meta.get("id"):
            imported_ids.add(str(gc_meta.get("id")))
            continue
        gc_id = context.get("groundcheck_id")
        if gc_id:
            imported_ids.add(str(gc_id))
    return imported_ids, imported_texts


def _choose_slot_canonical_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Choose best row per extracted slot (highest trust, then newest)."""
    best_by_slot: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        try:
            slots = extract_fact_slots(text) or {}
        except Exception:
            slots = {}
        if not slots:
            continue
        for slot in slots.keys():
            slot_key = str(slot).strip().lower()
            if not slot_key:
                continue
            prev = best_by_slot.get(slot_key)
            if prev is None:
                best_by_slot[slot_key] = row
                continue
            prev_key = (_clamp01(prev.get("trust")), float(prev.get("timestamp") or 0.0))
            next_key = (_clamp01(row.get("trust")), float(row.get("timestamp") or 0.0))
            if next_key > prev_key:
                best_by_slot[slot_key] = row
    return list(best_by_slot.values())


def _choose_narrative_rows(rows: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    picked: List[Dict[str, Any]] = []
    for row in rows:
        text = str(row.get("text") or "").strip()
        if not _is_good_narrative_fact(text):
            continue
        # Skip rows that already map to structured slots.
        try:
            has_slots = bool(extract_fact_slots(text))
        except Exception:
            has_slots = False
        if has_slots:
            continue
        norm = _normalize_text(text)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def sync_groundcheck_to_memory(
    *,
    memory_system: Any,
    thread_id: str,
    min_trust: float = 0.2,
    raw_limit: int = 400,
    narrative_limit: int = 30,
    allowed_sources: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Import canonical GroundCheck facts into CRT memory for this thread."""
    started = time.time()
    rows = _read_groundcheck_rows(
        min_trust=min_trust,
        limit=raw_limit,
        allowed_sources=allowed_sources,
    )
    if not rows:
        return {
            "ok": True,
            "thread_id": thread_id,
            "db_found": bool(find_groundcheck_db()),
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "source_rows": 0,
            "duration_ms": round((time.time() - started) * 1000, 2),
        }

    imported_ids, imported_texts = _collect_existing_bridge_state(memory_system, thread_id)
    slot_rows = _choose_slot_canonical_rows(rows)
    narrative_rows = _choose_narrative_rows(rows, limit=max(0, int(narrative_limit)))

    # Merge while preserving ranking: slot-canon first, then narrative.
    candidates = slot_rows + narrative_rows

    imported = 0
    skipped = 0
    updated = 0
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for row in candidates:
        gc_id = str(row.get("id") or "").strip()
        text = str(row.get("text") or "").strip()
        if not gc_id or not text:
            skipped += 1
            continue

        norm = _normalize_text(text)
        if gc_id in imported_ids or norm in imported_texts:
            skipped += 1
            continue

        target_trust = _clamp01(row.get("trust"), default=0.7)
        confidence = max(0.55, min(0.99, target_trust))
        context = {
            "type": "groundcheck_bridge",
            "thread_id": thread_id,
            "groundcheck": {
                "id": gc_id,
                "thread_id": row.get("thread_id"),
                "namespace": row.get("namespace"),
                "source": row.get("source"),
                "timestamp": row.get("timestamp"),
                "created_at": row.get("created_at"),
            },
            "provenance": {
                "tool": "groundcheck_mcp",
                "retrieved_at": now_iso,
                "source": f"groundcheck://memories/{gc_id}",
                "query": "bridge_sync_profile",
            },
        }

        try:
            mem = memory_system.store_memory(
                text=text,
                confidence=confidence,
                source=MemorySource.EXTERNAL,
                context=context,
                thread_id=thread_id,
            )
        except Exception as e:
            logger.debug("[MEMORY_BRIDGE] Store failed for %s: %s", gc_id, e)
            skipped += 1
            continue

        try:
            if hasattr(memory_system, "_update_memory_trust"):
                memory_system._update_memory_trust(mem.memory_id, target_trust)  # noqa: SLF001
                updated += 1
        except Exception as e:
            logger.debug("[MEMORY_BRIDGE] Trust update failed for %s: %s", gc_id, e)

        imported_ids.add(gc_id)
        imported_texts.add(norm)
        imported += 1

    return {
        "ok": True,
        "thread_id": thread_id,
        "db_found": True,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "source_rows": len(rows),
        "selected_rows": len(candidates),
        "duration_ms": round((time.time() - started) * 1000, 2),
    }
