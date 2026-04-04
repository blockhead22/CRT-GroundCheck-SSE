from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from .types import ApiTurnResponse, ProbeSnapshot


class ApiClient:
    """Thin API client for the running CRT service."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        timeout = self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        url = self._url(path)
        try:
            resp = requests.request(method.upper(), url, json=json_payload, timeout=timeout)
            latency_ms = (time.perf_counter() - started) * 1000.0
            raw_text = resp.text or ""
            parsed: Any
            try:
                parsed = resp.json() if raw_text else {}
            except Exception:
                parsed = None
            return {
                "ok": bool(resp.ok),
                "status_code": int(resp.status_code),
                "latency_ms": latency_ms,
                "json": parsed,
                "text": raw_text,
                "error": None,
                "url": url,
            }
        except Exception as exc:
            return {
                "ok": False,
                "status_code": 0,
                "latency_ms": (time.perf_counter() - started) * 1000.0,
                "json": None,
                "text": "",
                "error": str(exc),
                "url": url,
            }

    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health", timeout_seconds=8.0)

    def reset_thread(self, thread_id: str) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/api/thread/reset",
            json_payload={"thread_id": str(thread_id), "target": "all"},
            timeout_seconds=20.0,
        )

    def chat_send(self, *, thread_id: str, message: str) -> ApiTurnResponse:
        call = self._request(
            "POST",
            "/api/chat/send",
            json_payload={"thread_id": str(thread_id), "message": str(message)},
            timeout_seconds=max(self.timeout_seconds, 120.0),
        )
        payload = call.get("json")
        if not isinstance(payload, dict):
            payload = {}
        metadata = payload.get("metadata")
        xray = payload.get("xray")
        return ApiTurnResponse(
            answer=str(payload.get("answer") or ""),
            response_type=str(payload.get("response_type") or "unknown"),
            gates_passed=bool(payload.get("gates_passed")),
            gate_reason=(str(payload.get("gate_reason")) if payload.get("gate_reason") is not None else None),
            session_id=(str(payload.get("session_id")) if payload.get("session_id") is not None else None),
            metadata=metadata if isinstance(metadata, dict) else {},
            xray=xray if isinstance(xray, dict) else None,
            latency_ms=float(call.get("latency_ms") or 0.0),
            status_code=int(call.get("status_code") or 0),
            ok=bool(call.get("ok")),
            error=call.get("error"),
        )

    def get_contradictions(self, *, thread_id: str) -> List[Dict[str, Any]]:
        call = self._request("GET", f"/api/contradictions?thread_id={thread_id}", timeout_seconds=20.0)
        payload = call.get("json")
        if isinstance(payload, dict):
            items = payload.get("contradictions")
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
        return []

    def get_ledger_open(self, *, thread_id: str) -> List[Dict[str, Any]]:
        call = self._request("GET", f"/api/ledger/open?thread_id={thread_id}", timeout_seconds=20.0)
        payload = call.get("json")
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        return []

    def get_profile(self, *, thread_id: str) -> Dict[str, Any]:
        call = self._request("GET", f"/api/profile?thread_id={thread_id}", timeout_seconds=20.0)
        payload = call.get("json")
        return payload if isinstance(payload, dict) else {}

    def get_memory_recent(self, *, thread_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        call = self._request(
            "GET",
            f"/api/memory/recent?thread_id={thread_id}&limit={max(1, int(limit))}",
            timeout_seconds=20.0,
        )
        payload = call.get("json")
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        return []

    def get_introspection(self, *, thread_id: str) -> Dict[str, Any]:
        call = self._request("GET", f"/api/introspection?thread_id={thread_id}", timeout_seconds=20.0)
        payload = call.get("json")
        return payload if isinstance(payload, dict) else {}

    def get_notifications_recent(self, *, thread_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        call = self._request(
            "GET",
            f"/api/notifications?thread_id={thread_id}&limit={max(1, int(limit))}",
            timeout_seconds=20.0,
        )
        payload = call.get("json")
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
        return []

    def get_self_model(self, *, thread_id: str) -> Dict[str, Any]:
        call = self._request("GET", f"/api/self-model/{thread_id}", timeout_seconds=20.0)
        payload = call.get("json")
        return payload if isinstance(payload, dict) else {}

    def get_reflection_journal(self, *, thread_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        call = self._request(
            "GET",
            f"/api/reflection/journal/{thread_id}?limit={max(1, int(limit))}",
            timeout_seconds=20.0,
        )
        payload = call.get("json")
        if isinstance(payload, dict):
            entries = payload.get("entries")
            if isinstance(entries, list):
                return [x for x in entries if isinstance(x, dict)]
        return []

    def get_memory_trust(self, *, memory_id: str, thread_id: str) -> List[Dict[str, Any]]:
        if not str(memory_id or "").strip():
            return []
        call = self._request(
            "GET",
            f"/api/memory/{memory_id}/trust?thread_id={thread_id}",
            timeout_seconds=20.0,
        )
        payload = call.get("json")
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        return []

    def collect_probe_snapshot(self, *, thread_id: str, memory_limit: int = 30) -> ProbeSnapshot:
        recent = self.get_memory_recent(thread_id=thread_id, limit=memory_limit)
        trust_samples: List[Dict[str, Any]] = []
        sampled_ids: List[str] = []
        for item in recent[:5]:
            memory_id = str(item.get("memory_id") or "").strip()
            if not memory_id or memory_id in sampled_ids:
                continue
            sampled_ids.append(memory_id)
            trust_samples.append(
                {
                    "memory_id": memory_id,
                    "history": self.get_memory_trust(memory_id=memory_id, thread_id=thread_id),
                }
            )
        return ProbeSnapshot(
            contradictions=self.get_contradictions(thread_id=thread_id),
            ledger_open=self.get_ledger_open(thread_id=thread_id),
            profile=self.get_profile(thread_id=thread_id),
            memory_recent=recent,
            introspection=self.get_introspection(thread_id=thread_id),
            notifications_recent=self.get_notifications_recent(thread_id=thread_id, limit=20),
            self_model=self.get_self_model(thread_id=thread_id),
            reflection_journal=self.get_reflection_journal(thread_id=thread_id, limit=20),
            memory_trust=trust_samples,
        )
