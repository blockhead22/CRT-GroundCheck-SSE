from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from personal_agent.artifact_store import now_iso_utc, validate_payload_against_schema
from personal_agent.crt_core import MemorySource
from personal_agent.crt_memory import CRTMemorySystem
from personal_agent.fact_slots import ExtractedFact, extract_fact_slots


@dataclass(frozen=True)
class ApplyItem:
    proposal_id: str
    decision: str  # approved|rejected|defer
    memory_kind: str
    key: str
    value_text: str
    source: str
    trust: Optional[float]
    confidence: Optional[float]
    provenance: Dict[str, Any]
    evidence: List[Dict[str, Any]]


def load_proposals(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload_against_schema(payload, "crt_promotion_proposals.v1.schema.json")
    return payload


def load_decisions(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload_against_schema(payload, "crt_promotion_decisions.v1.schema.json")
    return payload


def _decision_map(decisions_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for d in (decisions_payload.get("decisions") or []):
        pid = str(d.get("proposal_id") or "").strip()
        if pid:
            out[pid] = dict(d)
    return out


def _structured_text(kind: str, key: str, value_text: str) -> str:
    k = (kind or "").strip().lower()
    prefix = "FACT" if k == "fact" else "PREF" if k == "preference" else "FACT"
    return f"{prefix}: {key} = {value_text}".strip()


def _normalize_slot_value(slot: str, value_text: str) -> str:
    facts = extract_fact_slots(_structured_text("fact", slot, value_text))
    ef = facts.get(slot)
    if ef is None:
        # Fallback normalization.
        return " ".join((value_text or "").strip().lower().split())
    return ef.normalized


def _existing_slot_values(memory: CRTMemorySystem) -> Dict[str, List[ExtractedFact]]:
    """Return extracted slot facts from existing memories (all sources)."""
    # Note: using existing public API would require retrieval; simplest is to scan.
    import sqlite3

    conn = sqlite3.connect(memory.db_path)
    cur = conn.cursor()
    cur.execute("SELECT text FROM memories")
    rows = cur.fetchall()
    conn.close()

    out: Dict[str, List[ExtractedFact]] = {}
    for (text,) in rows:
        facts = extract_fact_slots(str(text or ""))
        for slot, ef in facts.items():
            out.setdefault(slot, []).append(ef)
    return out


def build_apply_items(
    *,
    proposals_payload: Dict[str, Any],
    decisions_payload: Dict[str, Any],
) -> List[ApplyItem]:
    decisions = _decision_map(decisions_payload)
    proposals = proposals_payload.get("proposals") or []

    items: List[ApplyItem] = []
    missing: List[str] = []
    for p in proposals:
        pid = str(p.get("id") or "").strip()
        if not pid:
            continue
        d = decisions.get(pid)
        if d is None:
            missing.append(pid)
            continue

        mem = p.get("memory") or {}
        items.append(
            ApplyItem(
                proposal_id=pid,
                decision=str(d.get("decision") or "defer"),
                memory_kind=str(mem.get("kind") or "fact"),
                key=str(mem.get("key") or "").strip(),
                value_text=str(mem.get("value_text") or "").strip(),
                source=str(mem.get("source") or "system").strip(),
                trust=(float(mem.get("trust")) if mem.get("trust") is not None else None),
                confidence=(float(mem.get("confidence")) if mem.get("confidence") is not None else None),
                provenance=dict(mem.get("provenance") or {}),
                evidence=list(mem.get("evidence") or []),
            )
        )

    if missing:
        # Fail closed: we don’t want partial application with ambiguous decisions.
        raise ValueError(f"Decisions file missing decisions for {len(missing)} proposal(s): {missing[:10]}")

    return items


def apply_promotions(
    *,
    memory_db: str,
    proposals_path: Path,
    decisions_path: Path,
    dry_run: bool,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    proposals_payload = load_proposals(proposals_path)
    decisions_payload = load_decisions(decisions_path)
    items = build_apply_items(proposals_payload=proposals_payload, decisions_payload=decisions_payload)

    mem = CRTMemorySystem(db_path=memory_db)
    existing = _existing_slot_values(mem)

    results: List[Dict[str, Any]] = []
    for it in items:
        if it.decision != "approved":
            results.append(
                {
                    "proposal_id": it.proposal_id,
                    "decision": it.decision,
                    "action": "skipped",
                    "new_memory_id": None,
                    "reason": "not approved",
                }
            )
            continue

        if not it.key or not it.value_text:
            results.append(
                {
                    "proposal_id": it.proposal_id,
                    "decision": it.decision,
                    "action": "error",
                    "new_memory_id": None,
                    "reason": "proposal missing key/value_text",
                }
            )
            continue

        normalized_new = _normalize_slot_value(it.key, it.value_text)
        already = any((ef.normalized == normalized_new) for ef in existing.get(it.key, []))
        if already:
            results.append(
                {
                    "proposal_id": it.proposal_id,
                    "decision": it.decision,
                    "action": "skipped",
                    "new_memory_id": None,
                    "reason": "already present",
                }
            )
            continue

        # Store as a structured memory so downstream slot extraction remains consistent.
        text = _structured_text(it.memory_kind, it.key, it.value_text)

        # Choose source conservatively.
        source = MemorySource.USER if it.source.lower() == "user" else MemorySource.SYSTEM

        context = {
            "promotion": {
                "proposal_id": it.proposal_id,
                "proposals_path": str(proposals_path),
                "decisions_path": str(decisions_path),
                "applied_at": now_iso_utc(),
                "memory": {
                    "kind": it.memory_kind,
                    "key": it.key,
                    "value_text": it.value_text,
                },
                "provenance": it.provenance,
                "evidence": it.evidence,
            }
        }

        if dry_run:
            results.append(
                {
                    "proposal_id": it.proposal_id,
                    "decision": it.decision,
                    "action": "applied",
                    "new_memory_id": "dry_run",
                    "reason": "dry run (no db writes)",
                }
            )
            continue

        confidence = it.confidence if it.confidence is not None else 0.8
        m = mem.store_memory(text=text, confidence=float(confidence), source=source, context=context)

        # Update in-memory cache for dedupe of subsequent items.
        for slot, ef in extract_fact_slots(text).items():
            existing.setdefault(slot, []).append(ef)

        results.append(
            {
                "proposal_id": it.proposal_id,
                "decision": it.decision,
                "action": "applied",
                "new_memory_id": m.memory_id,
                "reason": None,
            }
        )

    apply_payload: Dict[str, Any] = {
        "metadata": {
            "version": "v1",
            "generated_at": now_iso_utc(),
            "memory_db": str(memory_db),
            "proposals_path": str(proposals_path),
            "decisions_path": str(decisions_path),
            "dry_run": bool(dry_run),
            "notes": None,
        },
        "results": results,
    }

    validate_payload_against_schema(apply_payload, "crt_promotion_apply_result.v1.schema.json")
    return apply_payload, results
