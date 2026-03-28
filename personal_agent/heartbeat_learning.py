"""
Heartbeat learning loop — extract beliefs/facts from conversations into CRT memory.

Runs as step 11 in the heartbeat executor. On each tick:
1. Fetch undigested messages (by watermark)
2. Extract claims via LLM
3. Dedup against existing memories
4. Store novel claims as provisional CRT memories
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────

DEDUP_SIMILARITY_THRESHOLD = 0.82
MAX_MESSAGES_PER_DIGEST = 20
MAX_CLAIMS_PER_DIGEST = 8

# Contradiction detection thresholds
CONTRA_DRIFT_THRESHOLD = 0.28   # Minimum drift_meaning to count as contradiction
CONTRA_TOPIC_SIM_THRESHOLD = 0.4  # Minimum similarity (same topic) to count

EXTRACTION_SYSTEM_PROMPT = """\
You extract factual claims, beliefs, and preferences from conversation messages.
Return a JSON array of objects. Each object has:
- "text": a concise declarative statement of the fact (e.g. "User prefers dark mode")
- "kind": one of "user_fact", "preference", "hypothesis", "observation"
- "confidence": float 0.0-1.0 (how clearly stated vs implied)

Rules:
- Only extract claims ABOUT THE USER or their world, not about the AI.
- Prefer specific facts over vague ones.
- If a message is just a greeting or command with no learnable content, return [].
- Maximum 8 claims per digest.
- Do NOT extract transient requests ("search for X") — only persistent facts/preferences.
- Always respond with ONLY a JSON array, no other text."""

EXTRACTION_USER_TEMPLATE = """\
Extract claims from these user messages:

{messages_block}

Return ONLY a JSON array, no other text."""


# ── Data ──────────────────────────────────────────────────────────────────

@dataclass
class ExtractedClaim:
    text: str
    kind: str
    confidence: float


# ── Pipeline steps ────────────────────────────────────────────────────────

def fetch_undigested_messages(
    session_db_path: str,
    thread_id: str,
    last_query_id: int,
    limit: int = MAX_MESSAGES_PER_DIGEST,
) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch recent_queries rows newer than the watermark.

    Returns (rows, max_id_seen). Each row has keys:
    id, query_text, response_text, timestamp.
    """
    conn = sqlite3.connect(session_db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT id, query_text, response_text, timestamp
               FROM recent_queries
               WHERE thread_id = ? AND id > ?
               ORDER BY id ASC
               LIMIT ?""",
            (thread_id, last_query_id, limit),
        ).fetchall()
        result = [dict(r) for r in rows]
        max_id = max(r["id"] for r in result) if result else last_query_id
        return result, max_id
    finally:
        conn.close()


def extract_claims_from_messages(
    messages: List[Dict[str, Any]],
    llm_client,
    model: Optional[str] = None,
) -> List[ExtractedClaim]:
    """Use LLM to extract structured claims from user messages."""
    if not messages:
        return []

    # Build message block from user texts only
    lines = []
    for msg in messages:
        text = (msg.get("query_text") or "").strip()
        if text:
            lines.append(f"- {text}")
    if not lines:
        return []

    messages_block = "\n".join(lines[:MAX_MESSAGES_PER_DIGEST])
    prompt = EXTRACTION_USER_TEMPLATE.format(messages_block=messages_block)

    try:
        raw = llm_client.generate(
            prompt=prompt,
            system=EXTRACTION_SYSTEM_PROMPT,
            max_tokens=800,
            temperature=0.3,
            model=model,
        )
    except Exception as e:
        logger.warning("[LEARNING] LLM extraction failed: %s", e)
        return []

    return _parse_claims(raw)


def _parse_claims(raw: str) -> List[ExtractedClaim]:
    """Parse LLM JSON output into ExtractedClaim list. Fail-safe."""
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    # Find the JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        logger.debug("[LEARNING] No JSON array found in LLM response")
        return []

    try:
        arr = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        logger.debug("[LEARNING] JSON parse failed: %s", e)
        return []

    claims = []
    allowed_kinds = {"user_fact", "preference", "hypothesis", "observation"}
    for item in arr[:MAX_CLAIMS_PER_DIGEST]:
        if not isinstance(item, dict):
            continue
        claim_text = str(item.get("text", "")).strip()
        kind = str(item.get("kind", "observation")).strip()
        confidence = float(item.get("confidence", 0.5))
        if not claim_text or len(claim_text) < 5:
            continue
        if kind not in allowed_kinds:
            kind = "observation"
        confidence = max(0.0, min(1.0, confidence))
        claims.append(ExtractedClaim(text=claim_text, kind=kind, confidence=confidence))

    return claims


def dedup_against_memory(
    claims: List[ExtractedClaim],
    memory_system,
    thread_id: str,
    threshold: float = DEDUP_SIMILARITY_THRESHOLD,
) -> List[ExtractedClaim]:
    """Filter out claims that are too similar to existing memories."""
    if not claims:
        return []

    from personal_agent.crt_core import encode_vector, similarity

    novel = []
    for claim in claims:
        try:
            claim_vec = encode_vector(claim.text)
            # Retrieve top-3 similar existing memories
            existing = memory_system.retrieve_memories(claim.text, k=3)
            is_dup = False
            for mem, _score in existing:
                if hasattr(mem, "vector") and mem.vector is not None:
                    sim = similarity(claim_vec, np.array(mem.vector, dtype=np.float32))
                    if sim >= threshold:
                        logger.debug(
                            "[LEARNING] Dedup: '%s' too similar (%.3f) to '%s'",
                            claim.text[:40], sim, mem.text[:40],
                        )
                        is_dup = True
                        break
            if not is_dup:
                novel.append(claim)
        except Exception as e:
            logger.debug("[LEARNING] Dedup check failed for '%s': %s", claim.text[:30], e)
            novel.append(claim)  # On error, keep the claim

    return novel


@dataclass
class DetectedContradiction:
    new_claim: str
    existing_memory_text: str
    existing_memory_id: Optional[str]
    drift_score: float


def detect_contradictions(
    novel_claims: List[ExtractedClaim],
    memory_system,
    thread_id: str,
    drift_threshold: float = CONTRA_DRIFT_THRESHOLD,
    topic_sim_threshold: float = CONTRA_TOPIC_SIM_THRESHOLD,
) -> List[DetectedContradiction]:
    """Check novel claims against existing memories for contradictions.

    A contradiction is detected when a claim is on the same topic
    (similarity >= topic_sim_threshold) but has high meaning drift
    (drift_meaning >= drift_threshold), indicating the user's stance changed.

    Returns a list of DetectedContradiction for each flagged pair.
    """
    if not novel_claims:
        return []

    from personal_agent.crt_core import encode_vector, CRTMath

    crt = CRTMath()
    contradictions: List[DetectedContradiction] = []

    for claim in novel_claims:
        try:
            claim_vec = encode_vector(claim.text)
            existing = memory_system.retrieve_memories(claim.text, k=5)
            for mem, _score in existing:
                if not (hasattr(mem, "vector") and mem.vector is not None):
                    continue
                mem_vec = np.array(mem.vector, dtype=np.float32)
                sim = crt.similarity(claim_vec, mem_vec)
                drift = crt.drift_meaning(claim_vec, mem_vec)

                if drift >= drift_threshold and sim >= topic_sim_threshold:
                    mem_id = getattr(mem, "memory_id", None) or getattr(mem, "id", None)
                    contradictions.append(DetectedContradiction(
                        new_claim=claim.text,
                        existing_memory_text=getattr(mem, "text", str(mem)),
                        existing_memory_id=str(mem_id) if mem_id else None,
                        drift_score=round(drift, 4),
                    ))
                    logger.info(
                        "[LEARNING] Contradiction: '%s' vs '%s' (drift=%.3f, sim=%.3f)",
                        claim.text[:40], getattr(mem, "text", "?")[:40], drift, sim,
                    )
                    break  # One contradiction per claim is enough
        except Exception as e:
            logger.debug("[LEARNING] Contradiction check failed for '%s': %s", claim.text[:30], e)

    return contradictions


def store_claims_as_memories(
    claims: List[ExtractedClaim],
    memory_system,
    thread_id: str,
    contradictions: Optional[List[DetectedContradiction]] = None,
) -> int:
    """Store extracted claims as provisional CRT memories."""
    from personal_agent.crt_memory import MemorySource

    # Build lookup of contradiction drift scores by claim text
    contra_lookup: Dict[str, float] = {}
    if contradictions:
        for c in contradictions:
            contra_lookup[c.new_claim] = c.drift_score

    stored = 0
    for claim in claims:
        try:
            ctx: Dict[str, Any] = {"origin": "heartbeat_learning", "extracted_at": time.time()}
            if claim.text in contra_lookup:
                ctx["contradiction_signal"] = contra_lookup[claim.text]
            memory_system.store_memory(
                text=claim.text,
                confidence=claim.confidence,
                source=MemorySource.REFLECTION,
                context=ctx,
                kind=claim.kind,
                source_kind="model_output",
                authority="provisional",
                thread_id=thread_id,
            )
            stored += 1
            logger.info("[LEARNING] Stored: '%s' (kind=%s, conf=%.2f)", claim.text[:60], claim.kind, claim.confidence)
        except Exception as e:
            logger.warning("[LEARNING] Failed to store claim '%s': %s", claim.text[:40], e)

    return stored


# ── Orchestrator ──────────────────────────────────────────────────────────

def run_learning_digest(
    thread_id: str,
    session_db_path: str,
    memory_system,
    llm_client,
    get_watermark,
    set_watermark,
    model: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Top-level orchestrator called from heartbeat_executor.

    Args:
        thread_id: Thread to digest.
        session_db_path: Path to thread session SQLite DB.
        memory_system: CRTMemorySystem instance.
        llm_client: UnifiedLLMClient instance.
        get_watermark: callable(thread_id) -> int
        set_watermark: callable(thread_id, query_id) -> None
        model: Optional LLM model override.
        dry_run: If True, extract but don't store.

    Returns:
        Summary dict with digested/extracted/novel/stored counts.
    """
    result: Dict[str, Any] = {
        "digested": 0, "extracted": 0, "novel": 0, "stored": 0,
        "max_query_id": 0, "contradictions": [],
    }

    # 1. Read watermark
    last_id = get_watermark(thread_id)

    # 2. Fetch undigested messages
    messages, max_id = fetch_undigested_messages(session_db_path, thread_id, last_id)
    result["digested"] = len(messages)
    result["max_query_id"] = max_id

    if not messages:
        return result

    # 3. Extract claims
    claims = extract_claims_from_messages(messages, llm_client, model=model)
    result["extracted"] = len(claims)

    if not claims:
        # Advance watermark even if nothing extracted
        if not dry_run:
            set_watermark(thread_id, max_id)
        return result

    # 4. Dedup
    novel_claims = dedup_against_memory(claims, memory_system, thread_id)
    result["novel"] = len(novel_claims)

    # 5. Contradiction detection — compare novel claims against existing memories
    contradictions = detect_contradictions(novel_claims, memory_system, thread_id)
    result["contradictions"] = [
        {
            "new_claim": c.new_claim,
            "existing_memory": c.existing_memory_text,
            "existing_memory_id": c.existing_memory_id,
            "drift_score": c.drift_score,
        }
        for c in contradictions
    ]

    # 6. Store (with contradiction signals attached)
    if not dry_run and novel_claims:
        stored = store_claims_as_memories(novel_claims, memory_system, thread_id, contradictions)
        result["stored"] = stored

    # 7. Advance watermark
    if not dry_run:
        set_watermark(thread_id, max_id)

    logger.info(
        "[LEARNING] Digest complete: %d messages -> %d extracted -> %d novel -> %d stored",
        result["digested"], result["extracted"], result["novel"], result["stored"],
    )
    return result
