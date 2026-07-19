"""Provider-transport adaptation for the sealed causal receipt experiment.

The original Grok CLI run failed twice with ``max turns reached`` while the
renderer was configured for one internal turn.  This adapter changes only the
CLI transport allowance from one turn to two.  It imports the already-sealed
manifest, prompts, decision engine, and scorer unchanged.  Tools, retrieval,
memory, subagents, web access, repair calls, and authority upgrades remain
disabled by ``GrokBuildShadowRenderer``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from labs.causal_evidence_receipt_lab.causal_evidence_receipt_lab import (
    CASE_PATH,
    GrokCliGovernedRenderer,
    load_manifest,
    run,
)
from aether.sidecar.frontier_shadow import GrokBuildShadowRenderer


class GrokTwoTurnTransport(GrokBuildShadowRenderer):
    """Allow one provider-internal retry without granting any new authority."""

    def command(self, *, prompt: str, system_prompt: str, cwd: Path) -> list[str]:
        command = super().command(
            prompt=prompt,
            system_prompt=system_prompt,
            cwd=cwd,
        )
        marker = command.index("--max-turns")
        if command[marker + 1] != "1":
            raise RuntimeError("sealed base transport no longer uses one turn")
        command[marker + 1] = "2"
        return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite sealed artifact: {args.output}")

    manifest = load_manifest()
    renderer = GrokCliGovernedRenderer(renderer=GrokTwoTurnTransport())
    payload = run([renderer], manifest)
    payload["provider_transport_adaptation"] = {
        "reason": "Two exact one-turn CLI attempts failed with max turns reached.",
        "base_attempts": 2,
        "base_attempt_result": "blocked_no_artifact",
        "changed_parameter": "grok_cli --max-turns 1 -> 2",
        "evidence_packet_changed": False,
        "prompts_changed": False,
        "scorer_changed": False,
        "tools_allowed": False,
        "retrieval_allowed": False,
        "memory_allowed": False,
        "repair_calls_allowed": False,
        "adaptation_executable_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "case_file_sha256": hashlib.sha256(CASE_PATH.read_bytes()).hexdigest(),
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
