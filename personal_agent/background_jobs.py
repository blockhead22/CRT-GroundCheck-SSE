from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.artifact_store import now_iso_utc, sha256_file, write_promotion_proposals
from personal_agent.fact_slots import extract_fact_slots


@dataclass(frozen=True)
class ProducedArtifact:
    kind: str
    path: str
    sha256: Optional[str]
    created_at: str


def _read_user_memories(memory_db: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(memory_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT memory_id, text, timestamp, confidence, trust, source FROM memories ORDER BY timestamp ASC"
    )
    rows = cur.fetchall()
    conn.close()

    out: List[Dict[str, Any]] = []
    for memory_id, text, ts, conf, trust, source in rows:
        out.append(
            {
                "memory_id": str(memory_id),
                "text": str(text or ""),
                "timestamp": float(ts or 0.0),
                "confidence": float(conf or 0.0),
                "trust": float(trust or 0.0),
                "source": str(source or ""),
            }
        )
    return out


def _slot_kind(slot: str) -> str:
    s = (slot or "").strip().lower()
    if s in {"communication_style", "goals"}:
        return "preference"
    return "fact"


def run_propose_promotions(*, payload: Dict[str, Any], artifacts_dir: Path, job_id: str) -> Tuple[Dict[str, Any], List[ProducedArtifact]]:
    memory_db = str((payload or {}).get("memory_db") or "").strip()
    if not memory_db:
        raise ValueError("payload.memory_db is required")

    proposals_path = artifacts_dir / "promotions" / f"proposals.{job_id}.json"
    proposals_path.parent.mkdir(parents=True, exist_ok=True)

    user_memories = [m for m in _read_user_memories(memory_db) if (m.get("source") or "").lower() == "user"]

    # Choose latest per slot.
    best_by_slot: Dict[str, Dict[str, Any]] = {}
    for m in user_memories:
        facts = extract_fact_slots(m.get("text") or "")
        for slot, extracted in (facts or {}).items():
            prev = best_by_slot.get(slot)
            if prev is None or float(m.get("timestamp") or 0.0) >= float(prev.get("timestamp") or 0.0):
                best_by_slot[slot] = {
                    "slot": slot,
                    "value": str(extracted.value),
                    "memory_id": m.get("memory_id"),
                    "trust": m.get("trust"),
                    "confidence": m.get("confidence"),
                    "timestamp": m.get("timestamp"),
                }

    proposals: List[Dict[str, Any]] = []
    for slot, d in sorted(best_by_slot.items(), key=lambda kv: kv[0]):
        proposals.append(
            {
                "id": f"{job_id}:{slot}",
                "status": "proposed",
                "rationale": "Extracted conservatively from user-provided memory text; requires approval.",
                "memory": {
                    "kind": _slot_kind(slot),
                    "lane": "notes",
                    "key": slot,
                    "value_text": str(d.get("value") or "").strip(),
                    "source": "user",
                    "trust": float(d.get("trust")) if d.get("trust") is not None else None,
                    "confidence": float(d.get("confidence")) if d.get("confidence") is not None else None,
                    "supersedes_id": None,
                    "provenance": {"memory_id": d.get("memory_id"), "job_id": job_id},
                    "evidence": [
                        {
                            "source_type": "memory",
                            "memory_id": d.get("memory_id"),
                            "url": None,
                            "quote_text": None,
                            "timestamp": None,
                        }
                    ],
                },
            }
        )

    payload_out: Dict[str, Any] = {
        "metadata": {
            "version": "v1",
            "generated_at": now_iso_utc(),
            "source_job_id": job_id,
            "notes": None,
        },
        "proposals": proposals,
    }

    write_promotion_proposals(proposals_path, payload_out)
    sha = sha256_file(proposals_path)

    artifacts = [
        ProducedArtifact(kind="proposal", path=str(proposals_path), sha256=sha, created_at=now_iso_utc())
    ]

    result = {
        "proposals_written": len(proposals),
        "proposals_path": str(proposals_path),
    }
    return result, artifacts


def run_job(*, job_type: str, payload: Dict[str, Any], artifacts_dir: Path, job_id: str) -> Tuple[Dict[str, Any], List[ProducedArtifact]]:
    if job_type == "propose_promotions":
        return run_propose_promotions(payload=payload, artifacts_dir=artifacts_dir, job_id=job_id)

    if job_type == "summarize_session":
        txt = (payload or {}).get("text") or ""
        txt = (txt or "").strip()
        summary = "(no text provided)" if not txt else (txt[:280].strip() + ("…" if len(txt) > 280 else ""))
        return {"summary": summary, "chars": len(txt)}, []

    raise NotImplementedError(f"Unsupported job type: {job_type}")
