"""Generate an adversarial pack without importing the circuit-breaker implementation.

The expectations are planted analytically by scenario construction.  This file
must remain outside the target implementation and must never call its exact or
greedy quarantine routines.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import random
import time
from typing import Any


SCHEMA = "aether.epistemic_circuit_breaker_blind_manifest.v0"
SEED = 2026071803
CASES_PER_CATEGORY = 8
CATEGORIES = (
    "benign_margin",
    "benign_near_limit",
    "unstable_competing_cuts",
    "broad_fanout",
    "protected_utility_conflict",
    "independent_corroboration",
    "duplicate_laundering",
    "stale_witness",
    "low_authority_independent",
    "malformed_provenance",
    "held_contradiction",
    "parallel_sign_cancellation",
)


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    label: str
    gain: float
    authority: int
    protected: bool = False
    held: bool = False


@dataclass(frozen=True)
class EdgeSpec:
    edge_id: str
    source: str
    target: str
    weight: float
    sign: int = 1
    removal_cost: float = 1.0
    protected: bool = False
    proposed: bool = False


@dataclass(frozen=True)
class EventSpec:
    event_id: str
    session: int
    operation: str
    parent_event_id: str | None
    provenance_root: str
    authority: int


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _nodes(prefix: str, names: tuple[str, ...], *, gain: float = 1.0) -> list[NodeSpec]:
    return [NodeSpec(f"{prefix}-{name}", name, gain, 2) for name in names]


def _edge(
    prefix: str,
    name: str,
    source: str,
    target: str,
    weight: float,
    *,
    sign: int = 1,
    cost: float = 1.0,
    protected: bool = False,
    proposed: bool = False,
) -> EdgeSpec:
    return EdgeSpec(
        f"{prefix}-{name}",
        f"{prefix}-{source}",
        f"{prefix}-{target}",
        round(weight, 5),
        sign,
        round(cost, 5),
        protected,
        proposed,
    )


def _chain_events(
    prefix: str,
    *,
    copies: int,
    authority: int,
    session: int,
    provenance_root: str | None = None,
) -> list[EventSpec]:
    root_id = f"{prefix}-origin"
    root = root_id if provenance_root is None else provenance_root
    events = [EventSpec(root_id, session, "origin", None, root, authority)]
    parent = root_id
    operations = ("copy", "summary", "tool_echo", "syndication")
    for index in range(1, copies):
        event_id = f"{prefix}-derived-{index:02d}"
        events.append(EventSpec(
            event_id,
            session + index,
            operations[(index - 1) % len(operations)],
            parent,
            root,
            authority,
        ))
        parent = event_id
    return events


def _two_origins(prefix: str, *, authority: int, session: int) -> list[EventSpec]:
    return [
        EventSpec(
            f"{prefix}-origin-a",
            session,
            "origin",
            None,
            f"{prefix}-root-a",
            authority,
        ),
        EventSpec(
            f"{prefix}-origin-b",
            session + 1,
            "origin",
            None,
            f"{prefix}-root-b",
            authority,
        ),
    ]


def _safe_graph(prefix: str, rng: random.Random) -> tuple[list[NodeSpec], list[EdgeSpec]]:
    nodes = _nodes(prefix, ("proposal", "anchor", "decision"))
    edges = [
        _edge(
            prefix,
            "proposal-anchor",
            "proposal",
            "anchor",
            rng.uniform(0.24, 0.34),
            cost=rng.uniform(0.7, 1.0),
            proposed=True,
        ),
        _edge(
            prefix,
            "anchor-decision",
            "anchor",
            "decision",
            rng.uniform(0.22, 0.32),
            cost=rng.uniform(0.9, 1.2),
        ),
    ]
    return nodes, edges


def _case(category: str, index: int, rng: random.Random) -> dict[str, Any]:
    prefix = f"blind-{category[:5]}-{index:02d}"
    commit_session = 300 + index * 5
    witness_valid_until = commit_session + 12
    required_sources = 1
    required_authority = 2
    held_conflict = False
    protected_paths: list[list[str]] = []
    origin_authority = 2
    events = _chain_events(
        prefix, copies=1, authority=origin_authority, session=commit_session - 8
    )
    expected_action = "accept"
    expected_reason = "safe_authorized_commit"
    analytic_note = "Low-gain acyclic graph is safely below both bounds."
    nodes, edges = _safe_graph(prefix, rng)

    if category == "benign_near_limit":
        nodes = _nodes(prefix, ("proposal", "anchor"))
        nodes.extend(
            NodeSpec(f"{prefix}-leaf-{leaf}", f"leaf-{leaf}", 1.0, 1)
            for leaf in range(5)
        )
        edges = [
            _edge(
                prefix,
                "proposal-anchor",
                "proposal",
                "anchor",
                rng.uniform(0.87, 0.91),
                cost=0.75,
                proposed=True,
            )
        ]
        edges.extend(
            EdgeSpec(
                f"{prefix}-anchor-leaf-{leaf}",
                f"{prefix}-anchor",
                f"{prefix}-leaf-{leaf}",
                round(rng.uniform(0.77, 0.81), 5),
                removal_cost=1.4,
            )
            for leaf in range(5)
        )
        analytic_note = (
            "Acyclic nominal impact is below 6, but a uniform positive weight "
            "perturbation can cross the impact boundary."
        )
    elif category == "unstable_competing_cuts":
        nodes = _nodes(prefix, ("proposal", "anchor", "bridge"), gain=1.1)
        nodes.append(NodeSpec(f"{prefix}-decision", "decision", 1.0, 2, True))
        edges = [
            _edge(prefix, "proposal-anchor", "proposal", "anchor", 0.95, cost=0.92, proposed=True),
            _edge(prefix, "anchor-bridge", "anchor", "bridge", 0.94, cost=0.68),
            _edge(prefix, "bridge-proposal", "bridge", "proposal", 0.93, cost=1.18, proposed=True),
            _edge(prefix, "anchor-decision", "anchor", "decision", 0.28, cost=3.0, protected=True),
        ]
        protected_paths = [[f"{prefix}-anchor", f"{prefix}-decision"]]
        expected_action = "quarantine"
        expected_reason = "feedback_instability"
        analytic_note = "Three-edge amplified cycle has multiple permissible cuts."
    elif category == "broad_fanout":
        nodes = _nodes(prefix, ("proposal", "anchor"))
        nodes.extend(
            NodeSpec(f"{prefix}-leaf-{leaf}", f"leaf-{leaf}", 1.0, 1)
            for leaf in range(8)
        )
        edges = [
            _edge(prefix, "proposal-anchor", "proposal", "anchor", 0.91, cost=0.72, proposed=True)
        ]
        edges.extend(
            EdgeSpec(
                f"{prefix}-anchor-leaf-{leaf}",
                f"{prefix}-anchor",
                f"{prefix}-leaf-{leaf}",
                round(rng.uniform(0.78, 0.84), 5),
                removal_cost=1.3,
            )
            for leaf in range(8)
        )
        expected_action = "quarantine"
        expected_reason = "broad_aggregate_impact"
        analytic_note = "DAG has rho zero but planted total impulse above 6."
    elif category == "protected_utility_conflict":
        nodes = _nodes(prefix, ("proposal", "anchor", "bridge"), gain=1.1)
        nodes.append(NodeSpec(f"{prefix}-decision", "decision", 1.0, 2, True))
        edges = [
            _edge(prefix, "proposal-anchor", "proposal", "anchor", 0.96, protected=True, proposed=True),
            _edge(prefix, "anchor-bridge", "anchor", "bridge", 0.95, protected=True),
            _edge(prefix, "bridge-proposal", "bridge", "proposal", 0.94, protected=True, proposed=True),
            _edge(prefix, "bridge-decision", "bridge", "decision", 0.30, protected=True),
        ]
        protected_paths = [[f"{prefix}-proposal", f"{prefix}-decision"]]
        expected_action = "reject"
        expected_reason = "no_safe_quarantine"
        analytic_note = "Unstable cycle is entirely protected, leaving no admissible cut."
    elif category == "independent_corroboration":
        required_sources = 2
        events = _two_origins(prefix, authority=2, session=commit_session - 8)
        analytic_note = "Two independent fresh authority-two origins support a safe write."
    elif category == "duplicate_laundering":
        required_sources = 2
        events = _chain_events(
            prefix,
            copies=rng.randint(9, 15),
            authority=2,
            session=commit_session - 30,
        )
        expected_action = "reject"
        expected_reason = "insufficient_independent_sources"
        analytic_note = "Many derived documents share one causal origin."
    elif category == "stale_witness":
        witness_valid_until = commit_session - rng.randint(1, 9)
        expected_action = "reject"
        expected_reason = "stale_authority_witness"
        analytic_note = "The evidence witness expired before commit."
    elif category == "low_authority_independent":
        required_sources = 2
        required_authority = 2
        events = _two_origins(prefix, authority=1, session=commit_session - 8)
        expected_action = "reject"
        expected_reason = "insufficient_authority"
        analytic_note = "Independent corroboration cannot raise origin authority above one."
    elif category == "malformed_provenance":
        events = _chain_events(
            prefix,
            copies=1,
            authority=2,
            session=commit_session - 8,
            provenance_root="",
        )
        expected_action = "reject"
        expected_reason = "invalid_provenance"
        analytic_note = "A blank provenance root cannot authorize persistence."
    elif category == "held_contradiction":
        held_conflict = True
        nodes.append(NodeSpec(f"{prefix}-counterclaim", "counterclaim", 1.0, 2, held=True))
        edges.append(
            _edge(
                prefix,
                "counterclaim",
                "proposal",
                "counterclaim",
                0.35,
                sign=-1,
                protected=True,
                proposed=True,
            )
        )
        expected_action = "hold"
        expected_reason = "unresolved_equal_authority_contradiction"
        analytic_note = "Equal-authority conflict must remain held."
    elif category == "parallel_sign_cancellation":
        nodes = _nodes(prefix, ("proposal", "anchor"), gain=1.1)
        edges = [
            _edge(prefix, "support", "proposal", "anchor", 0.90, sign=1, cost=0.72, proposed=True),
            _edge(prefix, "oppose", "proposal", "anchor", 0.90, sign=-1, cost=0.82, proposed=True),
            _edge(prefix, "feedback", "anchor", "proposal", 0.70, sign=1, cost=1.15, proposed=True),
        ]
        expected_action = "quarantine"
        expected_reason = "feedback_instability"
        analytic_note = (
            "Parallel positive and negative influences must not cancel before "
            "the conservative magnitude-stability calculation."
        )

    latest_event = max(events, key=lambda event: event.session)
    by_id = {event.event_id: event for event in events}
    origin = latest_event
    while origin.parent_event_id:
        origin = by_id[origin.parent_event_id]

    proposal = {
        "source_node_id": f"{prefix}-proposal",
        "assertive": True,
        "route_write_allowed": True,
        "route_authority_cap": 2,
        "required_authority": required_authority,
        "required_independent_sources": required_sources,
        "commit_session": commit_session,
        "witness_valid_until": witness_valid_until,
        "held_conflict": held_conflict,
    }
    return {
        "case_id": f"blind-{category}-{index:02d}",
        "category": category,
        "graph": {
            "nodes": [asdict(node) for node in nodes],
            "edges": [asdict(edge) for edge in edges],
            "protected_paths": protected_paths,
        },
        "events": [asdict(event) for event in events],
        "proposal": proposal,
        "blind_expectation": {
            "action": expected_action,
            "reason_class": expected_reason,
            "origin_event_id": origin.event_id,
            "independent_roots": len({event.provenance_root for event in events if event.provenance_root}),
            "benign": expected_action == "accept",
            "analytic_note": analytic_note,
        },
    }


def generate_pack() -> dict[str, Any]:
    rng = random.Random(SEED)
    cases = [
        _case(category, index, rng)
        for category in CATEGORIES
        for index in range(CASES_PER_CATEGORY)
    ]
    return {
        "schema": SCHEMA,
        "seed": SEED,
        "generated_without_target_import": True,
        "expectations_derived_from_target_oracle": False,
        "cases_per_category": CASES_PER_CATEGORY,
        "categories": list(CATEGORIES),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    args = parser.parse_args()
    if args.freeze.exists():
        raise FileExistsError(f"refusing to overwrite blind seal: {args.freeze}")
    pack = generate_pack()
    payload = {
        "sealed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pack_sha256": sha256(pack),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "evaluator_sha256": hashlib.sha256(args.evaluator.read_bytes()).hexdigest(),
        "target_sha256": hashlib.sha256(args.target.read_bytes()).hexdigest(),
        "pack": pack,
    }
    args.freeze.parent.mkdir(parents=True, exist_ok=True)
    args.freeze.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "path": str(args.freeze),
        "cases": len(pack["cases"]),
        "pack_sha256": payload["pack_sha256"],
        "target_sha256": payload["target_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

