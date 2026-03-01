from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class ModelProbeResult:
    model: str
    role: str
    valid_json_rate: float
    avg_latency_ms: float
    attempts: int
    score: float
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "role": self.role,
            "valid_json_rate": round(self.valid_json_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "attempts": self.attempts,
            "score": round(self.score, 4),
            "notes": list(self.notes),
        }


@dataclass
class ModelSelection:
    attacker_model: str
    judge_model: str
    ollama_base_url: str
    probes: List[ModelProbeResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attacker_model": self.attacker_model,
            "judge_model": self.judge_model,
            "ollama_base_url": self.ollama_base_url,
            "probes": [p.to_dict() for p in self.probes],
        }


def _extract_json_obj(text: str) -> Optional[Dict[str, Any]]:
    t = (text or "").strip()
    if not t:
        return None
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    if "```" in t:
        # Try fenced JSON blocks.
        parts = t.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
    return None


def _chat_ollama(
    *,
    ollama_base_url: str,
    model: str,
    system: str,
    user: str,
    timeout_seconds: float,
) -> Tuple[Optional[str], float, Optional[str]]:
    url = f"{ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.2, "num_predict": 180},
    }
    started = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=timeout_seconds)
        latency_ms = (time.perf_counter() - started) * 1000.0
        if not resp.ok:
            return None, latency_ms, f"http_{resp.status_code}"
        body = resp.json()
        message = body.get("message") if isinstance(body, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            return None, latency_ms, "missing_content"
        return content, latency_ms, None
    except Exception as exc:
        return None, (time.perf_counter() - started) * 1000.0, str(exc)


def _list_ollama_models(ollama_base_url: str) -> List[str]:
    url = f"{ollama_base_url.rstrip('/')}/api/tags"
    try:
        resp = requests.get(url, timeout=10.0)
        if not resp.ok:
            return []
        payload = resp.json()
        if not isinstance(payload, dict):
            return []
        models = payload.get("models")
        if not isinstance(models, list):
            return []
        out: List[str] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
        return sorted(set(out))
    except Exception:
        return []


def _is_chat_model(name: str) -> bool:
    n = (name or "").lower()
    disallow = ("embed", "embedding", "bge", "rerank", "nomic-embed", "all-minilm")
    return not any(tok in n for tok in disallow)


def _probe_model_for_role(
    *,
    ollama_base_url: str,
    model: str,
    role: str,
    attempts: int,
    timeout_seconds: float,
) -> ModelProbeResult:
    notes: List[str] = []
    valid = 0
    latencies: List[float] = []

    if role == "attacker":
        required_keys = {"objective_id", "user_message", "hypothesis", "expected_signals"}
        system = (
            "Return strict JSON only. Do not wrap in markdown. "
            "Keys required: objective_id, user_message, hypothesis, expected_signals. "
            "expected_signals must be an array."
        )
        user = (
            "Objective card: capability_target=contradiction handling. "
            "intent_constraints=[avoid static templates]. "
            "Generate one adaptive next user turn."
        )
    else:
        required_keys = {"objective_passed", "summary", "findings"}
        system = (
            "Return strict JSON only. Do not wrap in markdown. "
            "Keys required: objective_passed, summary, findings. "
            "findings must be an array."
        )
        user = (
            "Evaluate one assistant turn where gates_passed=false and unresolved_hard_conflicts=1. "
            "Provide concise findings."
        )

    for _ in range(max(1, attempts)):
        text, latency_ms, err = _chat_ollama(
            ollama_base_url=ollama_base_url,
            model=model,
            system=system,
            user=user,
            timeout_seconds=timeout_seconds,
        )
        latencies.append(latency_ms)
        if err:
            notes.append(err)
            continue
        obj = _extract_json_obj(text or "")
        if obj is None:
            notes.append("invalid_json")
            continue
        if not required_keys.issubset(set(obj.keys())):
            notes.append("missing_required_keys")
            continue
        valid += 1

    valid_rate = float(valid) / float(max(1, attempts))
    avg_latency = sum(latencies) / float(max(1, len(latencies)))
    # Prefer high validity first, then lower latency.
    score = (valid_rate * 100.0) - min(30.0, avg_latency / 150.0)
    return ModelProbeResult(
        model=model,
        role=role,
        valid_json_rate=valid_rate,
        avg_latency_ms=avg_latency,
        attempts=max(1, attempts),
        score=score,
        notes=notes[:8],
    )


def select_models(
    *,
    ollama_base_url: str,
    attacker_model: Optional[str],
    judge_model: Optional[str],
    probe_attempts: int = 2,
    probe_timeout_seconds: float = 45.0,
) -> ModelSelection:
    """Select attacker and judge models, preferring distinct high-fit models."""

    probes: List[ModelProbeResult] = []

    explicit_attacker = (attacker_model or "").strip()
    explicit_judge = (judge_model or "").strip()
    if explicit_attacker and explicit_judge:
        return ModelSelection(
            attacker_model=explicit_attacker,
            judge_model=explicit_judge,
            ollama_base_url=ollama_base_url,
            probes=[],
        )

    available = [m for m in _list_ollama_models(ollama_base_url) if _is_chat_model(m)]
    if not available:
        raise RuntimeError(
            f"No compatible Ollama chat models discovered at {ollama_base_url}. "
            "Start Ollama and install at least one chat model."
        )

    attacker_rank: List[ModelProbeResult] = []
    judge_rank: List[ModelProbeResult] = []
    for model_name in available:
        attacker_probe = _probe_model_for_role(
            ollama_base_url=ollama_base_url,
            model=model_name,
            role="attacker",
            attempts=probe_attempts,
            timeout_seconds=probe_timeout_seconds,
        )
        judge_probe = _probe_model_for_role(
            ollama_base_url=ollama_base_url,
            model=model_name,
            role="judge",
            attempts=probe_attempts,
            timeout_seconds=probe_timeout_seconds,
        )
        probes.extend([attacker_probe, judge_probe])
        attacker_rank.append(attacker_probe)
        judge_rank.append(judge_probe)

    attacker_rank.sort(key=lambda p: p.score, reverse=True)
    judge_rank.sort(key=lambda p: p.score, reverse=True)

    chosen_attacker = explicit_attacker or attacker_rank[0].model

    if explicit_judge:
        chosen_judge = explicit_judge
    else:
        # Prefer a distinct judge model when possible.
        distinct = [p.model for p in judge_rank if p.model != chosen_attacker]
        chosen_judge = distinct[0] if distinct else judge_rank[0].model

    return ModelSelection(
        attacker_model=chosen_attacker,
        judge_model=chosen_judge,
        ollama_base_url=ollama_base_url,
        probes=probes,
    )
