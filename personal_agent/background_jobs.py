from __future__ import annotations

import html
import json
import sqlite3
import time
import urllib.request
from html.parser import HTMLParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.artifact_store import now_iso_utc, sha256_file, write_promotion_proposals
from personal_agent.crt_core import MemorySource
from personal_agent.crt_memory import CRTMemorySystem
from personal_agent.fact_slots import extract_fact_slots


@dataclass(frozen=True)
class ProducedArtifact:
    kind: str
    path: str
    sha256: Optional[str]
    created_at: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        t = (data or "").strip()
        if t:
            self._chunks.append(t)

    def text(self) -> str:
        return " ".join(self._chunks)


def _fetch_url_text(url: str, *, timeout_seconds: float = 10.0, max_bytes: int = 2_000_000) -> Dict[str, Any]:
    url = (url or "").strip()
    if not url:
        raise ValueError("payload.url is required")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CRT/0.1 (+https://local)",
            "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        content_type = str(resp.headers.get("Content-Type") or "").strip()
        raw = resp.read(max_bytes)

    # Best-effort decoding
    try:
        body = raw.decode("utf-8", errors="replace")
    except Exception:
        body = raw.decode(errors="replace")

    extracted = body
    if "html" in content_type.lower() or "<html" in body.lower():
        parser = _HTMLTextExtractor()
        parser.feed(body)
        extracted = parser.text()

    extracted = html.unescape(extracted)
    extracted = " ".join(extracted.split())

    return {
        "url": url,
        "content_type": content_type,
        "bytes": len(raw),
        "text": extracted,
    }


def run_research_fetch(*, payload: Dict[str, Any], artifacts_dir: Path, job_id: str) -> Tuple[Dict[str, Any], List[ProducedArtifact]]:
    url = str((payload or {}).get("url") or "").strip()
    thread_id = str((payload or {}).get("thread_id") or "").strip() or None
    memory_db = str((payload or {}).get("memory_db") or "").strip() or None
    store_external = bool((payload or {}).get("store_as_external_memory", False))

    fetched = _fetch_url_text(url)
    fetched_at = now_iso_utc()

    out_path = artifacts_dir / "research" / f"fetch.{job_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload_out = {
        "metadata": {
            "version": "v1",
            "job_id": job_id,
            "fetched_at": fetched_at,
        },
        "source": {
            "url": fetched.get("url"),
            "content_type": fetched.get("content_type"),
            "bytes": fetched.get("bytes"),
        },
        "text": (fetched.get("text") or "")[:200_000],
    }
    out_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True), encoding="utf-8")

    artifacts = [ProducedArtifact(kind="summary", path=str(out_path), sha256=sha256_file(out_path), created_at=fetched_at)]

    stored_memory_id: Optional[str] = None
    if store_external:
        if not memory_db:
            raise ValueError("payload.memory_db is required when store_as_external_memory=true")

        mem = CRTMemorySystem(db_path=memory_db)
        txt = (f"WEB: {url}\n\n" + (fetched.get("text") or "")[:4000]).strip()
        ctx: Dict[str, Any] = {
            "kind": "web_research_fetch",
            "thread_id": thread_id,
            "provenance": {
                "tool": "urllib.request",
                "retrieved_at": fetched_at,
                "source": url,
                "query": None,
                "params": {"max_bytes": 2000000},
                "excerpt": (fetched.get("text") or "")[:280],
            },
        }
        stored = mem.store_memory(text=txt, confidence=0.6, source=MemorySource.EXTERNAL, context=ctx)
        stored_memory_id = stored.memory_id

    return {
        "url": url,
        "fetched_at": fetched_at,
        "chars": len(fetched.get("text") or ""),
        "stored_memory_id": stored_memory_id,
    }, artifacts


def run_research_summarize(*, payload: Dict[str, Any], artifacts_dir: Path, job_id: str) -> Tuple[Dict[str, Any], List[ProducedArtifact]]:
    # Minimal v1: summarization is deterministic truncation unless an LLM/tool is added.
    txt = str((payload or {}).get("text") or "").strip()
    url = str((payload or {}).get("url") or "").strip() or None
    memory_db = str((payload or {}).get("memory_db") or "").strip() or None
    thread_id = str((payload or {}).get("thread_id") or "").strip() or None
    store_external = bool((payload or {}).get("store_as_external_memory", False))

    summary = "(no text provided)" if not txt else (txt[:1200].strip() + ("…" if len(txt) > 1200 else ""))
    created_at = now_iso_utc()

    out_path = artifacts_dir / "research" / f"summary.{job_id}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary + "\n", encoding="utf-8")
    artifacts = [ProducedArtifact(kind="summary", path=str(out_path), sha256=sha256_file(out_path), created_at=created_at)]

    stored_memory_id: Optional[str] = None
    if store_external:
        if not memory_db:
            raise ValueError("payload.memory_db is required when store_as_external_memory=true")

        mem = CRTMemorySystem(db_path=memory_db)
        src = url or "(unknown)"
        ctx: Dict[str, Any] = {
            "kind": "web_research_summary",
            "thread_id": thread_id,
            "provenance": {
                "tool": "research_summarize",
                "retrieved_at": created_at,
                "source": src,
                "query": None,
                "params": None,
                "excerpt": summary[:280],
            },
        }
        stored = mem.store_memory(text=(f"WEB SUMMARY: {src}\n\n" + summary).strip(), confidence=0.65, source=MemorySource.EXTERNAL, context=ctx)
        stored_memory_id = stored.memory_id

    return {"summary_chars": len(summary), "stored_memory_id": stored_memory_id}, artifacts


def run_auto_resolve_contradictions(*, payload: Dict[str, Any], artifacts_dir: Path, job_id: str) -> Tuple[Dict[str, Any], List[ProducedArtifact]]:
    ledger_db = str((payload or {}).get("ledger_db") or "").strip()
    memory_db = str((payload or {}).get("memory_db") or "").strip()
    max_to_resolve = int((payload or {}).get("max_to_resolve") or 10)

    if not ledger_db:
        raise ValueError("payload.ledger_db is required")
    if not memory_db:
        raise ValueError("payload.memory_db is required")

    # Conservative auto-resolution:
    # - only OPEN contradictions
    # - only type == 'revision'
    # - only when new_text has an explicit correction marker
    resolved: List[Dict[str, Any]] = []

    conn = sqlite3.connect(ledger_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT ledger_id, old_memory_id, new_memory_id, contradiction_type, query, summary FROM contradictions "
        "WHERE status = ? ORDER BY timestamp ASC LIMIT ?",
        ("open", max_to_resolve),
    )
    rows = cur.fetchall()

    # Pull memory texts for referenced ids.
    mem_conn = sqlite3.connect(memory_db)
    mem_cur = mem_conn.cursor()

    now_iso = now_iso_utc()
    now_ts = time.time()

    for ledger_id, old_id, new_id, ctype, query, summary in rows:
        ctype_s = str(ctype or "").strip().lower()
        if ctype_s != "revision":
            continue

        mem_cur.execute("SELECT text, source FROM memories WHERE memory_id = ?", (str(new_id),))
        new_row = mem_cur.fetchone()
        mem_cur.execute("SELECT text, source FROM memories WHERE memory_id = ?", (str(old_id),))
        old_row = mem_cur.fetchone()
        if not new_row or not old_row:
            continue

        new_text = str(new_row[0] or "")
        new_src = str(new_row[1] or "")
        old_text = str(old_row[0] or "")
        old_src = str(old_row[1] or "")

        # Only auto-resolve user-to-user revisions.
        if new_src.lower() != "user" or old_src.lower() != "user":
            continue

        nl = new_text.lower()
        if not ("actually" in nl or "correction" in nl or "i meant" in nl or " not " in nl):
            continue

        # Mark resolved with the new memory as the effective winner.
        cur.execute(
            "UPDATE contradictions SET status = ?, resolution_timestamp = ?, resolution_method = ?, merged_memory_id = ? WHERE ledger_id = ?",
            ("resolved", float(now_ts), "auto_revision", str(new_id), str(ledger_id)),
        )
        resolved.append(
            {
                "ledger_id": str(ledger_id),
                "old_memory_id": str(old_id),
                "new_memory_id": str(new_id),
                "method": "auto_revision",
                "query": (str(query) if query is not None else None),
                "summary": (str(summary) if summary is not None else None),
            }
        )

    conn.commit()
    conn.close()
    mem_conn.close()

    out_path = artifacts_dir / "contradictions" / f"auto_resolve.{job_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"resolved": resolved, "ts": now_iso}, indent=2, sort_keys=True), encoding="utf-8")
    artifacts = [ProducedArtifact(kind="contradictions", path=str(out_path), sha256=sha256_file(out_path), created_at=now_iso)]

    return {"resolved_count": len(resolved)}, artifacts


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

    if job_type == "research_fetch":
        return run_research_fetch(payload=payload, artifacts_dir=artifacts_dir, job_id=job_id)

    if job_type == "research_summarize":
        return run_research_summarize(payload=payload, artifacts_dir=artifacts_dir, job_id=job_id)

    if job_type == "auto_resolve_contradictions":
        return run_auto_resolve_contradictions(payload=payload, artifacts_dir=artifacts_dir, job_id=job_id)

    if job_type == "summarize_session":
        txt = (payload or {}).get("text") or ""
        txt = (txt or "").strip()
        summary = "(no text provided)" if not txt else (txt[:280].strip() + ("…" if len(txt) > 280 else ""))
        return {"summary": summary, "chars": len(txt)}, []

    raise NotImplementedError(f"Unsupported job type: {job_type}")
