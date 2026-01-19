"""Canonical slot view derived from memory + contradiction ledger.

Goal: prevent reintroducing superseded facts by consulting the ledger status.

This module is intentionally deterministic: it reads the ledger DB directly
and uses fact-slot extraction to build a canonical per-slot view.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .fact_slots import extract_fact_slots


@dataclass(frozen=True)
class ContradictionRow:
    ledger_id: str
    timestamp: float
    status: str
    contradiction_type: str
    affects_slots: str
    old_memory_id: str
    new_memory_id: str
    resolution_timestamp: float
    resolution_method: str
    merged_memory_id: str


def _safe_str(v: Any) -> str:
    # Only treat None as empty; preserve False and 0
    if v is None:
        return ""
    return str(v).strip()


def _parse_slots_csv(csv: str) -> List[str]:
    if not csv:
        return []
    parts = [p.strip().lower() for p in csv.split(",")]
    return [p for p in parts if p]


def _fetch_contradictions(db_path: str, limit: int = 2000) -> List[ContradictionRow]:
    if not db_path:
        return []

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ledger_id, timestamp, status, contradiction_type, affects_slots,
                   old_memory_id, new_memory_id, resolution_timestamp, resolution_method, merged_memory_id
            FROM contradictions
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
        conn.close()
    except Exception:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass
        return []

    out: List[ContradictionRow] = []
    for r in rows:
        out.append(
            ContradictionRow(
                ledger_id=_safe_str(r[0]),
                timestamp=float(r[1] or 0.0),
                status=_safe_str(r[2]).lower(),
                contradiction_type=_safe_str(r[3]).lower(),
                affects_slots=_safe_str(r[4]),
                old_memory_id=_safe_str(r[5]),
                new_memory_id=_safe_str(r[6]),
                resolution_timestamp=float(r[7] or 0.0),
                resolution_method=_safe_str(r[8]).lower(),
                merged_memory_id=_safe_str(r[9]),
            )
        )
    return out


def get_contradiction_counts(db_path: str) -> Dict[str, int]:
    """Return ledger counts by status (open/resolved/accepted/etc)."""
    if not db_path:
        return {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT lower(status), COUNT(*) FROM contradictions GROUP BY lower(status)")
        rows = cur.fetchall()
        conn.close()
    except Exception:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass
        return {}

    out: Dict[str, int] = {}
    for st, c in rows:
        s = _safe_str(st).lower()
        if not s:
            continue
        out[s] = int(c or 0)
    return out


def build_canonical_slot_view(
    *,
    user_memories: Iterable[Any],
    memory_get_by_id: Callable[[str], Any],
    ledger_db_path: str,
    scope_slots: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build a canonical per-slot view.

    Output format per slot:
    {
      "status": "open"|"resolved"|"accepted"|"none",
      "value": <str|int|bool|None>,
      "values": [..]  # for open/accepted
      "previous": <optional>  # for resolved
      "ledger_id": <optional>
    }
    """

    scope: Optional[set[str]] = None
    if scope_slots:
        scope = {str(s).strip().lower() for s in scope_slots if str(s).strip()}

    # Latest observed value from user memories.
    latest: Dict[str, Dict[str, Any]] = {}
    for mem in user_memories or []:
        try:
            src = getattr(getattr(mem, "source", None), "value", None) or str(getattr(mem, "source", ""))
            if str(src).lower() != "user":
                continue
            txt = _safe_str(getattr(mem, "text", ""))
            if not txt:
                continue
            ts = float(getattr(mem, "timestamp", 0.0) or 0.0)
            facts = extract_fact_slots(txt) or {}
        except Exception:
            continue

        for slot, f in facts.items():
            s = str(slot).lower().strip()
            if not s:
                continue
            if scope is not None and s not in scope:
                continue
            v = getattr(f, "value", None)
            norm = getattr(f, "normalized", None)
            prev = latest.get(s)
            if prev is None or ts >= float(prev.get("timestamp") or 0.0):
                latest[s] = {"value": v, "normalized": str(norm or ""), "timestamp": ts}

    # Read contradictions.
    contras = _fetch_contradictions(ledger_db_path, limit=2500)

    # Group per slot.
    per_slot: Dict[str, List[Dict[str, Any]]] = {}

    for c in contras:
        slots = _parse_slots_csv(c.affects_slots)

        # If affects_slots wasn't filled, best-effort infer from old/new memory facts.
        if not slots:
            old_mem = memory_get_by_id(c.old_memory_id) if c.old_memory_id else None
            new_mem = memory_get_by_id(c.new_memory_id) if c.new_memory_id else None
            old_f = extract_fact_slots(_safe_str(getattr(old_mem, "text", ""))) if old_mem else {}
            new_f = extract_fact_slots(_safe_str(getattr(new_mem, "text", ""))) if new_mem else {}
            slots = sorted(set(old_f.keys()) & set(new_f.keys()))
            slots = [str(s).lower().strip() for s in slots if str(s).strip()]

        for slot in slots:
            s = str(slot).lower().strip()
            if not s:
                continue
            if scope is not None and s not in scope:
                continue

            per_slot.setdefault(s, []).append(
                {
                    "ledger_id": c.ledger_id,
                    "timestamp": float(c.timestamp or 0.0),
                    "status": c.status,
                    "resolution_timestamp": float(c.resolution_timestamp or 0.0),
                    "resolution_method": c.resolution_method,
                    "old_memory_id": c.old_memory_id,
                    "new_memory_id": c.new_memory_id,
                    "merged_memory_id": c.merged_memory_id,
                }
            )

    view: Dict[str, Dict[str, Any]] = {}

    # Consider every slot we have: from latest memories and from ledger.
    all_slots = set(latest.keys()) | set(per_slot.keys())

    for slot in sorted(all_slots):
        events = per_slot.get(slot, [])

        # OPEN dominates.
        open_events = [e for e in events if (e.get("status") or "").lower() == "open"]
        if open_events:
            # Use most recent open event.
            e = sorted(open_events, key=lambda x: float(x.get("timestamp") or 0.0), reverse=True)[0]
            old_mem = memory_get_by_id(_safe_str(e.get("old_memory_id"))) if e.get("old_memory_id") else None
            new_mem = memory_get_by_id(_safe_str(e.get("new_memory_id"))) if e.get("new_memory_id") else None

            vals: List[str] = []
            for m in (new_mem, old_mem):
                facts = extract_fact_slots(_safe_str(getattr(m, "text", ""))) if m else {}
                f = facts.get(slot)
                if f is None:
                    continue
                v = _safe_str(getattr(f, "value", ""))
                if v and v not in vals:
                    vals.append(v)

            # Fallback: also consider the latest observed value for this slot
            # (helps when one side of the ledger references a memory we can't load).
            try:
                lv = latest.get(slot, {}).get("value") if isinstance(latest, dict) else None
                lv_s = _safe_str(lv)
                if lv_s and lv_s not in vals:
                    vals.insert(0, lv_s)
            except Exception:
                pass

            view[slot] = {
                "status": "open",
                "values": vals,
                "ledger_id": _safe_str(e.get("ledger_id")),
            }
            continue

        # RESOLVED/ACCEPTED.
        resolved_events = [e for e in events if (e.get("status") or "").lower() in {"resolved", "accepted"}]
        if resolved_events:
            e = sorted(
                resolved_events,
                key=lambda x: float(x.get("resolution_timestamp") or 0.0) or float(x.get("timestamp") or 0.0),
                reverse=True,
            )[0]

            old_id = _safe_str(e.get("old_memory_id"))
            new_id = _safe_str(e.get("new_memory_id"))
            merged_id = _safe_str(e.get("merged_memory_id"))
            method = _safe_str(e.get("resolution_method"))
            status = _safe_str(e.get("status")).lower() or "resolved"

            chosen_id = merged_id
            if not chosen_id:
                if "deprecate_new" in method:
                    chosen_id = old_id
                else:
                    chosen_id = new_id

            chosen_mem = memory_get_by_id(chosen_id) if chosen_id else None
            other_mem = None
            if chosen_id and chosen_id == old_id:
                other_mem = memory_get_by_id(new_id) if new_id else None
            elif chosen_id and chosen_id == new_id:
                other_mem = memory_get_by_id(old_id) if old_id else None

            chosen_fact = extract_fact_slots(_safe_str(getattr(chosen_mem, "text", ""))).get(slot) if chosen_mem else None
            other_fact = extract_fact_slots(_safe_str(getattr(other_mem, "text", ""))).get(slot) if other_mem else None

            chosen_val = _safe_str(getattr(chosen_fact, "value", "")) if chosen_fact else ""
            other_val = _safe_str(getattr(other_fact, "value", "")) if other_fact else ""

            payload: Dict[str, Any] = {
                "status": status,
                "value": chosen_val or None,
                "ledger_id": _safe_str(e.get("ledger_id")),
            }

            if status == "accepted":
                vals = []
                if chosen_val:
                    vals.append(chosen_val)
                if other_val and other_val not in vals:
                    vals.append(other_val)
                payload["values"] = vals
            else:
                if other_val and other_val != chosen_val:
                    payload["previous"] = other_val

            view[slot] = payload
            continue

        # No contradiction: use latest.
        if slot in latest:
            v = latest[slot].get("value")
            view[slot] = {"status": "none", "value": v}

    return view


def format_slot_view(
    view: Dict[str, Dict[str, Any]],
    *,
    ordered_slots: Sequence[str],
) -> List[str]:
    lines: List[str] = []
    for s in ordered_slots:
        slot = str(s).strip().lower()
        if not slot or slot not in view:
            continue
        info = view.get(slot) or {}
        st = _safe_str(info.get("status")).lower()

        label = slot.replace("_", " ")
        if st == "open":
            vals = [v for v in (info.get("values") or []) if _safe_str(v)]
            if len(vals) >= 2:
                lines.append(f"- {label}: {vals[0]} vs {vals[1]} (unresolved)")
            elif len(vals) == 1:
                lines.append(f"- {label}: {vals[0]} (unresolved)")
            else:
                lines.append(f"- {label}: (unresolved)")
            continue

        if st == "accepted":
            vals = [v for v in (info.get("values") or []) if _safe_str(v)]
            if vals:
                lines.append(f"- {label}: " + " / ".join(vals) + " (both accepted)")
            continue

        val = info.get("value")
        if val is None or _safe_str(val) == "":
            continue

        prev = info.get("previous")
        if prev is not None and _safe_str(prev) and _safe_str(prev) != _safe_str(val):
            lines.append(f"- {label}: {val} (previously claimed: {prev})")
        else:
            lines.append(f"- {label}: {val}")

    return lines
