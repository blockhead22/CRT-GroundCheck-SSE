"""Read-only live planner/retrieval/compiler smoke against Aether substrate."""

from __future__ import annotations

import argparse
import json

from labs.meaning_compression_lab.aether_live_adapter import ReadOnlyAetherAdapter
from labs.meaning_compression_lab.multi_request_executor import compile_request_packet
from labs.meaning_compression_lab.multi_request_planner import plan_requests


DEFAULT_QUERY = (
    "Where am I currently working, what is my hobby, "
    "and what project framework are we using?"
)


def run_live_smoke(query: str = DEFAULT_QUERY, *, top_k: int = 4) -> dict:
    adapter = ReadOnlyAetherAdapter()
    plan = plan_requests(query, adapter.planner_slots())
    clause_text = {clause.clause_id: clause.text for clause in plan.clauses}
    packets = []
    for request in plan.requests:
        memories = adapter.memories(
            request.slot,
            mode=request.mode,
            k=top_k,
        )
        packet = compile_request_packet(
            clause_id=request.clause_id,
            clause_text=clause_text[request.clause_id],
            slot=adapter.resolve_slot(request.slot),
            mode=request.mode,
            memories=memories,
            dose=3,
        )
        evidence = adapter.retrieve(
            request.slot,
            mode=request.mode,
            k=top_k,
        )
        packet["planner_slot"] = request.slot
        packet["evidence"] = [item.to_dict() for item in evidence]
        packet["release_status"] = (
            "answerable"
            if any(item.releasable for item in evidence)
            else "withhold_unconfirmed"
        )
        packets.append(packet)

    unchanged = adapter.unchanged()
    result = {
        "query": query,
        "adapter_stats": adapter.stats(),
        "plan": plan.to_dict(),
        "packets": packets,
        "substrate_unchanged": unchanged,
    }
    if not unchanged:
        raise RuntimeError("read-only smoke changed the substrate")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--top-k", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run_live_smoke(args.query, top_k=args.top_k), indent=2))


if __name__ == "__main__":
    main()
