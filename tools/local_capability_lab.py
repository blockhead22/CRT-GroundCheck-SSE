from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests import exceptions as requests_exceptions


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


@dataclass
class ScenarioResult:
    name: str
    prompt: str
    thread_id: str
    response_text: str
    tool_names: List[str]
    tool_events: List[Dict[str, Any]]
    event_types: List[str]
    done_metadata: Dict[str, Any]
    passed: bool = True
    failures: List[str] = None


def _request_json(method: str, url: str, *, json_body: Optional[dict] = None) -> Any:
    resp = requests.request(method, url, json=json_body, timeout=30)
    resp.raise_for_status()
    if not resp.text:
        return {}
    return resp.json()


def ensure_backend_ready(base_url: str, *, timeout_seconds: float = 3.0) -> None:
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        resp = requests.get(health_url, timeout=timeout_seconds)
        resp.raise_for_status()
    except requests_exceptions.RequestException as exc:
        raise SystemExit(
            "Local Capability Lab could not reach the CRT API.\n"
            f"Tried: {health_url}\n"
            "Start the backend first, or pass --base-url if it is running elsewhere.\n"
            f"Underlying error: {exc}"
        ) from exc


def _parse_sse(raw_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in raw_text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[len("data: ") :].strip()
        if not payload:
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


def configure_local_only(base_url: str) -> Dict[str, Any]:
    body = {
        "generation_mode": "local",
        "routing_mode": "local_only",
        "enable_tooling": "true",
        "tooling_fallback_policy": "local_only",
        "tooling_tool_enabled_memory_recall": "true",
    }
    return _request_json("PATCH", f"{base_url}/api/auth/settings", json_body=body)


def seed_memory(base_url: str, thread_id: str, text: str, *, kind: str = "observation") -> Dict[str, Any]:
    body = {
        "thread_id": thread_id,
        "text": text,
        "confidence": 0.95,
        "source": "user",
        "kind": kind,
        "context": {"thread_id": thread_id, "lab_seed": True},
    }
    return _request_json("POST", f"{base_url}/api/memory/store", json_body=body)


def run_stream_prompt(base_url: str, thread_id: str, prompt: str) -> ScenarioResult:
    body = {
        "thread_id": thread_id,
        "message": prompt,
        "generation_mode": "local",
    }
    resp = requests.post(f"{base_url}/api/chat/stream", json=body, timeout=180)
    resp.raise_for_status()
    events = _parse_sse(resp.text)
    response_chunks: List[str] = []
    tool_events: List[Dict[str, Any]] = []
    tool_names: List[str] = []
    done_metadata: Dict[str, Any] = {}

    for event in events:
        etype = str(event.get("type") or "")
        if etype == "token":
            response_chunks.append(str(event.get("content") or ""))
        elif etype in {"tool_start", "tool_result"}:
            tool_events.append(event)
            tool_name = str((event.get("metadata") or {}).get("tool_name") or "")
            if tool_name and tool_name not in tool_names:
                tool_names.append(tool_name)
        elif etype == "done":
            done_metadata = dict(event.get("metadata") or {})
            if not response_chunks and event.get("content"):
                response_chunks.append(str(event.get("content") or ""))

    return ScenarioResult(
        name="",
        prompt=prompt,
        thread_id=thread_id,
        response_text="".join(response_chunks).strip(),
        tool_names=tool_names,
        tool_events=tool_events,
        event_types=[str(event.get("type") or "") for event in events],
        done_metadata=done_metadata,
        failures=[],
    )


def _contains_visible_think(text: str) -> bool:
    lowered = str(text or "").lower()
    return "<think>" in lowered or "</think>" in lowered


def evaluate_result(result: ScenarioResult) -> ScenarioResult:
    failures: List[str] = []
    response = result.response_text or str(result.done_metadata.get("answer") or "")
    tools = set(result.tool_names)

    if _contains_visible_think(response):
        failures.append("visible <think> leakage")

    if result.name in {"memory_grounding", "explicit_memory_tool"}:
        if "memory_recall" not in tools:
            failures.append("memory prompt did not call memory_recall")
        if "web_search" in tools:
            failures.append("memory prompt drifted to web_search")

    if result.name == "memory_grounding":
        if "yosemite" not in response.lower():
            failures.append("memory grounding answer did not recover seeded Yosemite fact")

    if result.name == "explicit_memory_tool":
        if "model as the mouth" not in response.lower():
            failures.append("explicit memory answer missed the seeded phrase")

    if result.name == "local_file_tool":
        if "file_read" not in tools:
            failures.append("file prompt did not call file_read")
        if "web_search" in tools:
            failures.append("file prompt drifted to web_search")
        roadmap_markers = ("v3.7.x", "cookie orchestrator stabilization", "external integrations")
        if not any(marker in response.lower() for marker in roadmap_markers):
            failures.append("file answer did not reflect current ROADMAP.md content")

    if result.name == "continuity_followup":
        if "web_search" in tools:
            failures.append("continuity follow-up drifted to web_search")
        if "local" not in response.lower() and "system" not in response.lower():
            failures.append("continuity follow-up did not stay grounded in prior roadmap context")

    result.failures = failures
    result.passed = not failures
    return result


def build_default_scenarios(thread_id: str) -> Iterable[tuple[str, str]]:
    return [
        (
            "memory_grounding",
            "What national park did I say I wanted to visit, and answer only from what you actually know from memory?",
        ),
        (
            "explicit_memory_tool",
            "Use memory recall to answer: what phrase did I say about using the model as the mouth?",
        ),
        (
            "local_file_tool",
            "Read ROADMAP.md and tell me what roadmap phase is currently in progress.",
        ),
        (
            "continuity_followup",
            "What does that suggest about the system design direction?",
        ),
    ]


def run_smoke(base_url: str) -> List[ScenarioResult]:
    thread_id = f"lab_{uuid.uuid4().hex[:10]}"
    configure_local_only(base_url)

    seed_memory(base_url, thread_id, "I want to visit Yosemite someday.", kind="preference")
    seed_memory(base_url, thread_id, "Let the model be the mouth while the system carries memory and structure.", kind="belief")

    results: List[ScenarioResult] = []
    for name, prompt in build_default_scenarios(thread_id):
        result = run_stream_prompt(base_url, thread_id, prompt)
        result.name = name
        results.append(evaluate_result(result))
        time.sleep(0.5)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small local capability lab against Aether.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for the running CRT API.")
    parser.add_argument("--scenario", default="smoke", choices=["smoke"], help="Scenario set to run.")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON instead of a readable summary.")
    args = parser.parse_args()

    if args.scenario != "smoke":
        raise SystemExit(f"Unsupported scenario: {args.scenario}")

    ensure_backend_ready(args.base_url)
    results = run_smoke(args.base_url)

    if args.json:
        print(json.dumps([asdict(item) for item in results], indent=2))
        raise SystemExit(1 if any(not item.passed for item in results) else 0)

    print("Local Capability Lab")
    print("====================")
    for item in results:
        print(f"\nScenario: {item.name}")
        print(f"Status: {'PASS' if item.passed else 'FAIL'}")
        print(f"Prompt: {item.prompt}")
        print(f"Thread: {item.thread_id}")
        print(f"Tools: {', '.join(item.tool_names) if item.tool_names else '(none)'}")
        print(f"Event types: {', '.join(item.event_types)}")
        print(f"Done metadata: {json.dumps(item.done_metadata, ensure_ascii=True)}")
        print("Response:")
        print(item.response_text or "(empty)")
        if item.failures:
            print("Failures:")
            for failure in item.failures:
                print(f"- {failure}")

    raise SystemExit(1 if any(not item.passed for item in results) else 0)


if __name__ == "__main__":
    main()
