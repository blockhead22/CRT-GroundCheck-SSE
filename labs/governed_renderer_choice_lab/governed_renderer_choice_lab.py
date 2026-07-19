"""Compare interchangeable renderers beneath one frozen Aether packet contract.

This is deliberately a lab boundary, not Workbench provider wiring.  Aether
selects the evidence and ownership contract before either renderer runs.  The
renderer receives no retrieval, tool, memory-write, or authority capability,
and its candidate is accepted only after the same deterministic verifier runs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Protocol
from urllib import request


ROOT = Path(__file__).resolve().parents[2]
AETHER_CORE = ROOT / "aether-core"
if str(AETHER_CORE) not in sys.path:
    sys.path.insert(0, str(AETHER_CORE))

from aether.sidecar.frontier_shadow import (  # noqa: E402
    GrokBuildShadowRenderer,
)
from scripts.frontier_boundary_eval import SYSTEM_PROMPT  # noqa: E402
from scripts.model_boundary_eval import (  # noqa: E402
    _cases,
    _failures,
    _repair_prompt,
)


SCHEMA = "aether.governed_renderer_choice_lab.v0"
DEFAULT_LOCAL_MODEL = "qwen2.5:7b-instruct"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


@dataclass(frozen=True)
class RenderReceipt:
    answer: str
    provider: str
    model: str
    latency_s: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None


class GovernedRenderer(Protocol):
    provider: str
    model: str

    def preflight(self) -> dict[str, Any]: ...

    def render(self, *, prompt: str, system_prompt: str) -> RenderReceipt: ...


class OllamaGovernedRenderer:
    provider = "ollama"

    def __init__(
        self,
        *,
        model: str = DEFAULT_LOCAL_MODEL,
        url: str = DEFAULT_OLLAMA_URL,
        seed: int = 20260717,
        timeout_s: float = 180.0,
    ) -> None:
        self.model = model
        self.url = url
        self.seed = int(seed)
        self.timeout_s = float(timeout_s)

    def preflight(self) -> dict[str, Any]:
        tags_url = self.url.rsplit("/api/", 1)[0] + "/api/tags"
        with request.urlopen(tags_url, timeout=5.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        available = {
            str(row.get("name") or row.get("model") or "")
            for row in payload.get("models") or []
        }
        if self.model not in available:
            raise RuntimeError(f"local model is not installed: {self.model}")
        return {
            "provider": self.provider,
            "model": self.model,
            "endpoint": self.url,
            "tools_allowed": False,
            "retrieval_allowed": False,
            "durable_memory_allowed": False,
            "writes_allowed": False,
        }

    def render(self, *, prompt: str, system_prompt: str) -> RenderReceipt:
        rendered_prompt = (
            f"{system_prompt}\n\n"
            "The following is the complete governed packet. Use only this packet.\n\n"
            f"{prompt}"
        )
        body = json.dumps({
            "model": self.model,
            "prompt": rendered_prompt,
            "stream": False,
            "options": {"temperature": 0, "seed": self.seed},
        }).encode("utf-8")
        req = request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        with request.urlopen(req, timeout=self.timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
        answer = str(payload.get("response") or "").strip()
        if not answer:
            raise RuntimeError("Ollama returned an empty answer")
        return RenderReceipt(
            answer=answer,
            provider=self.provider,
            model=self.model,
            latency_s=round(time.perf_counter() - started, 3),
            input_tokens=_optional_int(payload.get("prompt_eval_count")),
            output_tokens=_optional_int(payload.get("eval_count")),
        )


class GrokCliGovernedRenderer:
    provider = "grok_cli"

    def __init__(self, renderer: GrokBuildShadowRenderer | None = None) -> None:
        self.renderer = renderer or GrokBuildShadowRenderer()
        self.model = self.renderer.config.model

    def preflight(self) -> dict[str, Any]:
        result = self.renderer.preflight()
        return {
            "provider": self.provider,
            "model": self.model,
            **result,
            "tools_allowed": False,
            "retrieval_allowed": False,
            "durable_memory_allowed": False,
            "writes_allowed": False,
        }

    def render(self, *, prompt: str, system_prompt: str) -> RenderReceipt:
        result = self.renderer.render(prompt=prompt, system_prompt=system_prompt)
        return RenderReceipt(
            answer=result.answer,
            provider=self.provider,
            model=result.model,
            latency_s=result.latency_s,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=result.request_id,
        )


def frozen_packet(case: dict[str, Any]) -> dict[str, Any]:
    """Return the provider-independent packet and its stable content seal."""

    contract = {
        "required": list(case.get("required") or ()),
        "forbidden": list(case.get("forbidden") or ()),
        "expected_builder": case.get("expected_builder"),
        "expected_name": case.get("expected_name"),
        "expected_color": case.get("expected_color"),
    }
    content = {
        "case_id": str(case["id"]),
        "prompt": str(case["prompt"]),
        "verification_contract": contract,
        "authority": {
            "evidence_selection": "aether",
            "renderer_role": "wording_only",
            "retrieval_allowed": False,
            "durable_memory_allowed": False,
            "writes_allowed": False,
            "authority_upgrades_allowed": False,
        },
    }
    raw = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**content, "sha256": hashlib.sha256(raw).hexdigest()}


def packet_set_sha256(packets: list[dict[str, Any]]) -> str:
    raw = json.dumps(packets, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def evaluate_renderer(
    renderer: GovernedRenderer,
    *,
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    preflight = renderer.preflight()
    rows: list[dict[str, Any]] = []
    for case in cases:
        packet = frozen_packet(case)
        first = renderer.render(prompt=case["prompt"], system_prompt=SYSTEM_PROMPT)
        first_failures = _failures(first.answer, case)
        final = first
        final_failures = list(first_failures)
        repaired = False
        rejected_draft_sha256 = None
        if first_failures:
            repaired = True
            rejected_draft_sha256 = hashlib.sha256(
                first.answer.encode("utf-8")
            ).hexdigest()
            final = renderer.render(
                prompt=_repair_prompt(case, first.answer, first_failures),
                system_prompt=SYSTEM_PROMPT,
            )
            final_failures = _failures(final.answer, case)
        passed = not final_failures
        rows.append({
            "case_id": case["id"],
            "governed_packet_sha256": packet["sha256"],
            "first_pass": not first_failures,
            "repaired": repaired,
            "final_pass": passed,
            "first_failures": first_failures,
            "final_failures": final_failures,
            "rejected_draft_sha256": rejected_draft_sha256,
            "accepted_answer": final.answer if passed else None,
            "latency_s": round(
                first.latency_s + (final.latency_s if repaired else 0.0), 3
            ),
            "input_tokens": (first.input_tokens or 0)
            + ((final.input_tokens or 0) if repaired else 0),
            "output_tokens": (first.output_tokens or 0)
            + ((final.output_tokens or 0) if repaired else 0),
            "request_ids": [
                value for value in (
                    first.request_id,
                    final.request_id if repaired else None,
                ) if value
            ],
            "authority": packet["authority"],
        })
    return {
        "provider": renderer.provider,
        "model": renderer.model,
        "preflight": preflight,
        "summary": {
            "cases": len(rows),
            "first_pass": sum(bool(row["first_pass"]) for row in rows),
            "final_pass": sum(bool(row["final_pass"]) for row in rows),
            "repair_calls": sum(bool(row["repaired"]) for row in rows),
            "total_latency_s": round(sum(row["latency_s"] for row in rows), 3),
            "input_tokens": sum(row["input_tokens"] for row in rows),
            "output_tokens": sum(row["output_tokens"] for row in rows),
        },
        "results": rows,
    }


def run(
    renderers: list[GovernedRenderer],
    *,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    cases = _cases(synthetic=True)
    if case_ids:
        cases = [case for case in cases if case["id"] in case_ids]
        found = {str(case["id"]) for case in cases}
        missing = sorted(case_ids - found)
        if missing:
            raise ValueError(f"unknown case ids: {missing}")
    packets = [frozen_packet(case) for case in cases]
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    results = [evaluate_renderer(renderer, cases=cases) for renderer in renderers]
    return {
        "schema": SCHEMA,
        "started_at": started_at,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "profile": "synthetic_only",
        "packet_count": len(packets),
        "packet_set_sha256": packet_set_sha256(packets),
        "packet_hashes": {
            packet["case_id"]: packet["sha256"] for packet in packets
        },
        "same_packets_all_providers": True,
        "same_verifier_all_providers": True,
        "rejected_draft_text_persisted": False,
        "results": results,
    }


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        action="append",
        choices=("ollama", "grok_cli"),
        dest="providers",
    )
    parser.add_argument("--local-model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    names = args.providers or ["ollama", "grok_cli"]
    renderers: list[GovernedRenderer] = []
    for name in names:
        if name == "ollama":
            renderers.append(OllamaGovernedRenderer(
                model=args.local_model,
                url=args.ollama_url,
                seed=args.seed,
            ))
        else:
            renderers.append(GrokCliGovernedRenderer())
    report = run(renderers, case_ids=set(args.case_ids or ()))
    rendered = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

