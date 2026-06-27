"""Representation replay eval for memory-state compression.

This eval asks a practical Phase 1.9 question: after compressing memory into a
representation, can the system replay the correct governed answer?

It deliberately does not claim magical file compression. The comparison is
behavioral: current facts, history, authority boundaries, locked policies, and
provisional/reaction rules must survive well enough to answer probes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[2]
AETHER_CORE_DIR = ROOT_DIR / "aether-core"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from labs.meaning_compression_lab.plain_rag_eval import (
    PROBES,
    Probe,
    judge_answer,
    simulated_plain_rag_answer,
)
from labs.meaning_compression_lab.run_lab import (
    OUT_DIR,
    Scenario,
    canonical_meaning_state,
    crt_compressed_state,
    full_transcript_state,
    naive_summary_state,
    project_meaning_state,
    representation_size,
    scenario_pack,
    scenario_from_crt_memory_db,
    slot_only_state,
)
from labs.meaning_compression_lab.scaffold_eval import (
    build_meaning_scaffold,
    render_scaffold,
    scaffold_answer,
)

if str(AETHER_CORE_DIR) not in sys.path:
    sys.path.insert(1, str(AETHER_CORE_DIR))

from aether.sidecar.archive_import import normalize_archive_report
from aether.sidecar.context_bridge import build_context_bridge
from aether.substrate import SubstrateGraph


CLAIM = (
    "Memory-state compression is useful when a compact representation can replay "
    "governed answers across contradiction, authority, history, and policy probes."
)


RepresentationBuilder = Callable[[Scenario], dict[str, Any]]
Answerer = Callable[[Scenario, Probe, dict[str, Any]], str]


def governed_scaffold_state(scenario: Scenario) -> dict[str, Any]:
    scaffold = build_meaning_scaffold(scenario)
    return {
        "type": "governed_scaffold",
        "scenario": scenario.name,
        "fragments": scaffold["fragments"],
        "rendered": render_scaffold(scaffold),
    }


def quantized_scaffold_state(scenario: Scenario) -> dict[str, Any]:
    """A deliberately lossy scaffold that keeps only direct answer fragments."""
    scaffold = build_meaning_scaffold(scenario)
    kept_kinds = {"current_fact", "preference", "policy"}
    fragments = [
        fragment
        for fragment in scaffold["fragments"]
        if fragment.get("kind") in kept_kinds
    ]
    reduced = {
        "type": "meaning_scaffold",
        "scenario": scenario.name,
        "fragments": fragments,
    }
    return {
        "type": "quantized_scaffold",
        "scenario": scenario.name,
        "fragments": fragments,
        "rendered": render_scaffold(reduced),
        "dropped_layers": [
            "authority",
            "history",
            "contradiction",
            "provisional",
            "reaction",
            "concern",
        ],
    }


def raw_retrieval_state(scenario: Scenario) -> dict[str, Any]:
    return {
        "type": "raw_retrieval",
        "memories": [memory.text for memory in scenario.memories],
    }


def context_bridge_profile_state(scenario: Scenario) -> dict[str, Any]:
    bridge = _build_profile_context_bridge(scenario)
    return {
        "type": "context_bridge_profile",
        "bridge": bridge or {},
    }


def context_bridge_profile_candidates_state(scenario: Scenario) -> dict[str, Any]:
    bridge = _build_profile_context_bridge(scenario) or {}
    return {
        "type": "context_bridge_profile_candidates",
        "bridge": {
            "profile_summary": bridge.get("profile_summary") or [],
            "withheld_summary": bridge.get("withheld_summary") or {},
        },
    }


REPRESENTATIONS: dict[str, tuple[RepresentationBuilder, Answerer]] = {
    "full_transcript": (full_transcript_state, lambda _s, p, state: _answer_from_projected(project_meaning_state(state), p)),
    "raw_retrieval": (raw_retrieval_state, lambda s, p, _state: simulated_plain_rag_answer(s, p)),
    "naive_summary": (naive_summary_state, lambda _s, p, state: _answer_from_projected(project_meaning_state(state), p)),
    "slot_only": (slot_only_state, lambda _s, p, state: _answer_from_projected(project_meaning_state(state), p)),
    "quantized_scaffold": (
        quantized_scaffold_state,
        lambda _s, p, state: scaffold_answer(
            {
                "type": "meaning_scaffold",
                "scenario": state["scenario"],
                "fragments": state["fragments"],
            },
            p,
        ),
    ),
    "governed_scaffold": (
        governed_scaffold_state,
        lambda _s, p, state: scaffold_answer(
            {
                "type": "meaning_scaffold",
                "scenario": state["scenario"],
                "fragments": state["fragments"],
            },
            p,
        ),
    ),
    "crt_compressed": (crt_compressed_state, lambda _s, p, state: _answer_from_projected(project_meaning_state(state), p)),
    "context_bridge_profile": (
        context_bridge_profile_state,
        lambda _s, p, state: _answer_from_context_bridge(state["bridge"], p),
    ),
    "context_bridge_profile_candidates": (
        context_bridge_profile_candidates_state,
        lambda _s, p, state: _answer_from_context_bridge(state["bridge"], p),
    ),
}


BRIDGE_PACKET_PROBES: dict[str, Probe] = {
    "bridge_project_packet": Probe(
        name="bridge_project_packet",
        query="What is the current Aether Workbench project direction?",
        expected_contains=("governed memory", "local"),
    ),
    "bridge_support_packet": Probe(
        name="bridge_support_packet",
        query="How should you support Nick when he is spiraling back into work?",
        expected_contains=("warm", "practical", "next steps"),
    ),
    "bridge_reflection_packet": Probe(
        name="bridge_reflection_packet",
        query="What reviewed self-description labels should you use carefully?",
        expected_contains=("dork", "leukemia survivor"),
    ),
}


BRIDGE_PACKET_REPRESENTATIONS: dict[str, tuple[RepresentationBuilder, Answerer]] = {
    "context_bridge_full_packet": (
        lambda scenario: {"type": "context_bridge_full_packet", "bridge": _build_bridge_packet(scenario) or {}},
        lambda _s, p, state: _answer_from_bridge_packet(state["bridge"], p),
    ),
    "context_bridge_project_candidates": (
        lambda scenario: _narrow_bridge_packet(
            scenario,
            "context_bridge_project_candidates",
            ("project_summary", "project_model", "plain_answer_hints"),
        ),
        lambda _s, p, state: _answer_from_bridge_packet(state["bridge"], p),
    ),
    "context_bridge_support_candidates": (
        lambda scenario: _narrow_bridge_packet(
            scenario,
            "context_bridge_support_candidates",
            ("reviewed_support_patterns",),
        ),
        lambda _s, p, state: _answer_from_bridge_packet(state["bridge"], p),
    ),
    "context_bridge_reflection_candidates": (
        lambda scenario: _narrow_bridge_packet(
            scenario,
            "context_bridge_reflection_candidates",
            ("reviewed_reflections",),
        ),
        lambda _s, p, state: _answer_from_bridge_packet(state["bridge"], p),
    ),
}


ARCHIVE_PACKET_PROBES: dict[str, Probe] = {
    "archive_memory_packet": Probe(
        name="archive_memory_packet",
        query="Should archive user claims be treated as confirmed memory?",
        expected_contains=("memory", "proposed_review", "review", "not confirmed"),
    ),
    "archive_support_packet": Probe(
        name="archive_support_packet",
        query="What support semantics can the archive provide without cloning GPT voice?",
        expected_contains=("support", "behavior", "review", "not confirmed"),
    ),
    "archive_reflection_packet": Probe(
        name="archive_reflection_packet",
        query="How should assistant interpretations from the archive be handled?",
        expected_contains=("assistant", "low-authority", "reflection", "review"),
    ),
}


ArchivePacketBuilder = Callable[[dict[str, Any]], dict[str, Any]]
ArchivePacketAnswerer = Callable[[Probe, dict[str, Any]], str]


ARCHIVE_PACKET_REPRESENTATIONS: dict[str, tuple[ArchivePacketBuilder, ArchivePacketAnswerer]] = {
    "archive_full_candidate_packet": (
        lambda packets: {
            "type": "archive_full_candidate_packet",
            "packet": packets.get("archive_full_candidate_packet") or [],
        },
        lambda p, state: _answer_from_archive_packet(state["packet"], p),
    ),
    "archive_memory_candidates": (
        lambda packets: {
            "type": "archive_memory_candidates",
            "packet": packets.get("archive_memory_candidates") or [],
        },
        lambda p, state: _answer_from_archive_packet(state["packet"], p),
    ),
    "archive_support_candidates": (
        lambda packets: {
            "type": "archive_support_candidates",
            "packet": packets.get("archive_support_candidates") or [],
        },
        lambda p, state: _answer_from_archive_packet(state["packet"], p),
    ),
    "archive_reflection_candidates": (
        lambda packets: {
            "type": "archive_reflection_candidates",
            "packet": packets.get("archive_reflection_candidates") or [],
        },
        lambda p, state: _answer_from_archive_packet(state["packet"], p),
    ),
}


def _answer_from_projected(state: dict[str, Any], probe: Probe) -> str:
    facts = state["facts"]
    policies = state["policies"]
    authority = state["authority"]
    preferences = state["preferences"]
    contradictions = state["contradictions"]
    history = state["history"]
    reaction_policy = state["reaction_policy"]

    if probe.name == "current_name":
        return facts.get("name", "I do not have a confirmed name.")
    if probe.name == "current_employer":
        return facts.get("employer", "I do not have a confirmed employer.")
    if probe.name == "provisional_favorite_color":
        if authority.get("favorite_color") in {"provisional", "provisional_social"}:
            return "I should not answer that as confirmed; the stored favorite color is provisional."
        return facts.get("favorite_color", "I do not have a confirmed favorite color.")
    if probe.name == "locked_force_push_policy":
        if policies.get("git.force_push_main") == "forbidden":
            return "No. A locked policy says never force push to main."
        return "No locked force-push policy found."
    if probe.name in {"answer_style_preference", "current_answer_style"}:
        return preferences.get("preference.answer_style", "No answer style preference found.")
    if probe.name == "current_favorite_color":
        if authority.get("favorite_color") in {"provisional", "provisional_social"}:
            return "I should not answer that as confirmed; the stored favorite color is provisional."
        return facts.get("favorite_color", "I do not have a confirmed favorite color.")
    if probe.name == "current_project":
        return facts.get("current_project", "I do not have a confirmed current project.")
    if probe.name == "current_home_city":
        return facts.get("home_city", "I do not have a confirmed home city.")
    if probe.name == "destructive_command_policy":
        if policies.get("shell.destructive_without_confirmation") == "forbidden":
            return "No. A locked policy says not to run destructive shell commands without explicit confirmation."
        return "No locked destructive-command policy found."
    if probe.name == "previous_employer":
        current = facts.get("employer")
        for row in reversed(contradictions):
            if row.get("slot") == "employer" and row.get("new") == current:
                return str(row.get("old") or "")
        values = history.get("employer") or []
        return values[-2] if len(values) >= 2 else "I do not have a previous employer recorded."
    if probe.name == "name_correction_status":
        for row in reversed(contradictions):
            if row.get("slot") == "name":
                return f"Your current name is {row.get('new')}; before that it was {row.get('old')}."
        return f"I only have your current name as {facts.get('name', 'unknown')}."
    if probe.name == "previous_camera_system":
        values = history.get("camera_system") or []
        return values[0] if len(values) >= 2 else "I do not have an earlier camera system recorded."
    if probe.name == "confirmed_store_platform":
        if authority.get("store_platform") == "confirmed":
            return facts.get("store_platform", "I do not have a confirmed store platform.")
        return "I do not have enough authority to confirm the store platform."
    if probe.name == "favorite_color_response_rule":
        if reaction_policy.get("favorite_color") == "withhold_until_confirmed":
            return "No. The favorite color memory is provisional, so it should be withheld until confirmed."
        return "No response rule found for favorite color."
    if probe.name == "production_db_mock_policy":
        if policies.get("db.production_write_without_sqlite_mock") == "forbidden":
            return "No. A locked policy requires an isolated SQLite mock test before production database write-path changes."
        return "No locked production database mock-test policy found."
    return ""


def _answer_from_context_bridge(bridge: dict[str, Any], probe: Probe) -> str:
    profile = {
        str(row.get("slot_id") or "").removeprefix("user:"): str(row.get("value") or "")
        for row in bridge.get("profile_summary") or []
    }
    withheld = bridge.get("withheld_summary") or {}

    if probe.name == "current_name":
        return profile.get("name", "I do not have a confirmed name in the broad Context Bridge.")
    if probe.name == "current_employer":
        return profile.get("employer", "The broad Context Bridge does not release a confirmed employer.")
    if probe.name == "provisional_favorite_color":
        if int(withheld.get("provisional_slots") or 0):
            return "I should withhold that; the broad Context Bridge reports provisional profile evidence."
        return profile.get("favorite_color", "I do not have a confirmed favorite color.")
    if probe.name == "current_favorite_color":
        return profile.get("favorite_color", "I do not have a confirmed favorite color.")
    if probe.name in {"answer_style_preference", "current_answer_style"}:
        return profile.get("preference.answer_style") or profile.get(
            "work_preference",
            "No answer style preference is released in the broad Context Bridge.",
        )
    if probe.name == "current_project":
        return profile.get("current_project") or profile.get(
            "project_name",
            "No current project is released in the broad Context Bridge.",
        )
    if probe.name == "current_home_city":
        return profile.get("home_city", "No home city is released in the broad Context Bridge.")
    if probe.name == "confirmed_store_platform":
        return profile.get("store_platform", "No confirmed store platform is released in the broad Context Bridge.")
    if probe.name in {
        "previous_employer",
        "name_correction_status",
        "previous_camera_system",
    }:
        if int(withheld.get("conflicted_slots") or 0) or int(withheld.get("past_slots") or 0):
            return "The broad Context Bridge withholds history/contradiction details; use a narrow governed memory trace."
        return "The broad Context Bridge does not carry prior values."
    if probe.name in {
        "locked_force_push_policy",
        "destructive_command_policy",
        "production_db_mock_policy",
    }:
        return "The broad Context Bridge does not release locked action policies."
    if probe.name == "favorite_color_response_rule":
        if int(withheld.get("provisional_slots") or 0):
            return "No. The broad Context Bridge only reports provisional evidence by category, so the value should be withheld."
        return "No response rule found in the broad Context Bridge."
    return ""


def _answer_from_bridge_packet(bridge: dict[str, Any], probe: Probe) -> str:
    if probe.name == "bridge_project_packet":
        project = bridge.get("project_model") or {}
        summary = " ".join(
            str(row.get("value") or "")
            for row in bridge.get("project_summary") or []
        )
        hints = " ".join(str(item) for item in bridge.get("plain_answer_hints") or [])
        return " ".join(
            str(part)
            for part in (
                project.get("purpose"),
                " ".join(project.get("current_direction") or []),
                summary,
                hints,
            )
            if part
        )
    if probe.name == "bridge_support_packet":
        return " ".join(
            str(row.get("suggested_response_rule") or "")
            for row in bridge.get("reviewed_support_patterns") or []
        )
    if probe.name == "bridge_reflection_packet":
        reflections = bridge.get("reviewed_reflections") or {}
        bits = []
        for subject in ("user", "agent"):
            for row in reflections.get(subject) or []:
                bits.extend(str(label) for label in row.get("self_description_labels") or [])
                bits.append(str(row.get("observation") or ""))
                bits.append(str(row.get("suggested_experiment") or ""))
        return " ".join(bit for bit in bits if bit)
    return ""


def _answer_from_archive_packet(packet: list[dict[str, Any]], probe: Probe) -> str:
    rows = list(packet or [])
    if probe.name == "archive_memory_packet":
        memory_rows = [row for row in rows if row.get("review_route") == "memory"]
        if not memory_rows:
            return "No archive memory candidates are present in this packet."
        route_text = _candidate_type_text(memory_rows)
        return (
            "Archive memory candidates remain proposed_review, review-required, "
            "and not confirmed. They preserve memory review route, source "
            f"authority, and no-write boundaries for {route_text}."
        )
    if probe.name == "archive_support_packet":
        support_rows = [row for row in rows if row.get("review_route") == "support"]
        if not support_rows:
            return "No archive support candidates are present in this packet."
        assistant_style = any(row.get("source_role") == "assistant" for row in support_rows)
        boundary = (
            "Assistant wording is low-authority style evidence, not a GPT voice clone. "
            if assistant_style
            else ""
        )
        return (
            "Archive support candidates preserve behavior guidance for review "
            "while staying not confirmed facts. "
            f"{boundary}Types: {_candidate_type_text(support_rows)}."
        )
    if probe.name == "archive_reflection_packet":
        reflection_rows = [row for row in rows if row.get("review_route") == "reflection"]
        if not reflection_rows:
            return "No archive reflection candidates are present in this packet."
        assistant_rows = [
            row for row in reflection_rows
            if row.get("source_role") == "assistant"
            and str(row.get("authority") or "").endswith("low_authority")
        ]
        if assistant_rows:
            return (
                "Archive assistant interpretations remain low-authority "
                "reflection candidates for review, not confirmed user facts. "
                f"Types: {_candidate_type_text(assistant_rows)}."
            )
        return "Archive reflection candidates require review before use."
    return ""


def _candidate_type_text(rows: list[dict[str, Any]]) -> str:
    return ", ".join(
        sorted({str(row.get("candidate_type") or "unknown") for row in rows})
    )


def score_scenario(
    scenario: Scenario,
    *,
    probes: dict[str, Probe] | None = None,
) -> dict[str, Any] | None:
    probe = (probes or {}).get(scenario.name) or PROBES.get(scenario.name)
    if probe is None:
        return None

    full_size = representation_size(full_transcript_state(scenario))
    rows = []
    for name, (builder, answerer) in REPRESENTATIONS.items():
        state = builder(scenario)
        answer = answerer(scenario, probe, state)
        judgment = judge_answer(answer, probe)
        size = _state_size(state)
        rows.append(
            {
                "name": name,
                "size_bytes": size,
                "compression_ratio": round(size / full_size, 3) if full_size else 0.0,
                "answer": answer,
                "judgment": judgment,
                "state_preview": _preview_state(state),
            }
        )

    return {
        "scenario": scenario.name,
        "evidence": scenario.evidence,
        "purpose": scenario.purpose,
        "probe": probe.name,
        "query": probe.query,
        "full_transcript_size_bytes": full_size,
        "representations": rows,
    }


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for scenario in rows:
        for representation in scenario["representations"]:
            by_name.setdefault(representation["name"], []).append(representation)

    aggregate_rows = []
    for name, reps in by_name.items():
        pass_count = sum(1 for rep in reps if rep["judgment"]["passed"])
        semantic_pass_count = sum(1 for rep in reps if rep["judgment"]["semantic_passed"])
        contract_pass_count = sum(1 for rep in reps if rep["judgment"]["contract_passed"])
        aggregate_rows.append(
            {
                "name": name,
                "case_count": len(reps),
                "pass_count": pass_count,
                "semantic_pass_count": semantic_pass_count,
                "contract_pass_count": contract_pass_count,
                "pass_rate": round(pass_count / len(reps), 3) if reps else 0.0,
                "semantic_pass_rate": round(semantic_pass_count / len(reps), 3) if reps else 0.0,
                "contract_pass_rate": round(contract_pass_count / len(reps), 3) if reps else 0.0,
                "avg_size_bytes": round(sum(rep["size_bytes"] for rep in reps) / len(reps), 1) if reps else 0.0,
                "avg_compression_ratio": round(
                    sum(rep["compression_ratio"] for rep in reps) / len(reps),
                    3,
                )
                if reps
                else 0.0,
            }
        )
    aggregate_rows.sort(
        key=lambda row: (
            row["pass_rate"],
            row["semantic_pass_rate"],
            -row["avg_compression_ratio"],
        ),
        reverse=True,
    )
    return aggregate_rows


def run(
    *,
    write_results: bool = True,
    scenarios: list[Scenario] | None = None,
    probes: dict[str, Probe] | None = None,
) -> dict[str, Any]:
    scenario_set = scenarios if scenarios is not None else scenario_pack()
    rows = [
        row
        for scenario in scenario_set
        if (row := score_scenario(scenario, probes=probes)) is not None
    ]
    out = {
        "lab": "representation_replay_eval",
        "claim": CLAIM,
        "scenario_count": len(rows),
        "evidence_counts": {
            evidence: sum(1 for row in rows if row["evidence"] == evidence)
            for evidence in sorted({row["evidence"] for row in rows})
        },
        "aggregate_representations": aggregate(rows),
        "scenarios": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"representation_replay_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def bridge_candidate_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="bridge_project_packet",
            purpose="Compare full bridge vs narrow project candidate packet.",
            memories=[],
            evidence="bridge_candidate_fixture",
        ),
        Scenario(
            name="bridge_support_packet",
            purpose="Compare full bridge vs narrow reviewed-support candidate packet.",
            memories=[],
            evidence="bridge_candidate_fixture",
        ),
        Scenario(
            name="bridge_reflection_packet",
            purpose="Compare full bridge vs narrow reviewed-reflection candidate packet.",
            memories=[],
            evidence="bridge_candidate_fixture",
        ),
    ]


def score_bridge_candidate_scenario(scenario: Scenario) -> dict[str, Any]:
    probe = BRIDGE_PACKET_PROBES[scenario.name]
    full_size = representation_size(BRIDGE_PACKET_REPRESENTATIONS["context_bridge_full_packet"][0](scenario))
    rows = []
    for name, (builder, answerer) in BRIDGE_PACKET_REPRESENTATIONS.items():
        state = builder(scenario)
        answer = answerer(scenario, probe, state)
        judgment = judge_answer(answer, probe)
        size = representation_size(state)
        rows.append(
            {
                "name": name,
                "size_bytes": size,
                "compression_ratio": round(size / full_size, 3) if full_size else 0.0,
                "answer": answer,
                "judgment": judgment,
                "state_preview": _preview_state(state),
            }
        )
    return {
        "scenario": scenario.name,
        "evidence": scenario.evidence,
        "purpose": scenario.purpose,
        "probe": probe.name,
        "query": probe.query,
        "full_transcript_size_bytes": full_size,
        "representations": rows,
    }


def run_bridge_candidate_comparison(*, write_results: bool = True) -> dict[str, Any]:
    rows = [score_bridge_candidate_scenario(scenario) for scenario in bridge_candidate_scenarios()]
    out = {
        "lab": "context_bridge_candidate_packet_eval",
        "claim": (
            "Narrow Context Bridge packets should preserve their own reviewed "
            "candidate behavior with less payload than the full bridge."
        ),
        "scenario_count": len(rows),
        "evidence_counts": {"bridge_candidate_fixture": len(rows)},
        "aggregate_representations": aggregate(rows),
        "scenarios": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"context_bridge_candidate_packets_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def archive_candidate_fixture_report() -> dict[str, Any]:
    return {
        "source": {"archive_dir": "fixture"},
        "candidates": [
            _archive_candidate(
                candidate_type="user_claim_candidate",
                source_role="user",
                authority="user_stated",
                confidence=0.88,
                summary="User stated a possible stable fact.",
                signal="user_claim",
                evidence_hash="archive-memory-hash",
                evidence_preview="I run a print shop.",
            ),
            _archive_candidate(
                candidate_type="semantic_vocabulary_candidate",
                source_role="user",
                authority="user_stated_usage",
                confidence=0.84,
                summary="User uses spiral/deep language to request layered depth.",
                signal="user_spiral_depth_semantics",
                evidence_hash="archive-semantic-hash",
                evidence_preview="Can we deep dive and spiral through this?",
            ),
            _archive_candidate(
                candidate_type="assistant_support_response_candidate",
                source_role="assistant",
                authority="assistant_style_low_authority",
                confidence=0.42,
                summary="Assistant response structure may contain useful support scaffolding.",
                signal="assistant_support_shape",
                evidence_hash="archive-assistant-support-hash",
                evidence_preview="The useful next step is to return without contempt.",
            ),
            _archive_candidate(
                candidate_type="assistant_interpretation_candidate",
                source_role="assistant",
                authority="assistant_inferred_low_authority",
                confidence=0.35,
                summary="Assistant inferred a user pattern that requires review.",
                signal="assistant_interpretation",
                evidence_hash="archive-reflection-hash",
                evidence_preview="You seem to use tools as proof against yourself.",
            ),
        ],
    }


def score_archive_packet_scenario(
    scenario_name: str,
    packets: dict[str, Any],
) -> dict[str, Any]:
    probe = ARCHIVE_PACKET_PROBES[scenario_name]
    full_size = representation_size(
        ARCHIVE_PACKET_REPRESENTATIONS["archive_full_candidate_packet"][0](packets)
    )
    rows = []
    for name, (builder, answerer) in ARCHIVE_PACKET_REPRESENTATIONS.items():
        state = builder(packets)
        answer = answerer(probe, state)
        judgment = judge_answer(answer, probe)
        size = representation_size(state)
        rows.append(
            {
                "name": name,
                "size_bytes": size,
                "compression_ratio": round(size / full_size, 3) if full_size else 0.0,
                "answer": answer,
                "judgment": judgment,
                "state_preview": _preview_state(state),
            }
        )
    return {
        "scenario": scenario_name,
        "evidence": "archive_candidate_packet",
        "purpose": (
            "Verify archive candidate packets preserve review authority and "
            "role boundaries without becoming confirmed memory."
        ),
        "probe": probe.name,
        "query": probe.query,
        "full_transcript_size_bytes": full_size,
        "representations": rows,
    }


def run_archive_candidate_packet_comparison(
    *,
    archive_report: str | Path | None = None,
    write_results: bool = True,
) -> dict[str, Any]:
    report = (
        json.loads(Path(archive_report).read_text(encoding="utf-8"))
        if archive_report
        else archive_candidate_fixture_report()
    )
    normalized = normalize_archive_report(report)
    packets = normalized["representation_packets"]
    rows = [
        score_archive_packet_scenario(name, packets)
        for name in ARCHIVE_PACKET_PROBES
    ]
    out = {
        "lab": "archive_candidate_packet_eval",
        "claim": (
            "Archive candidate packets should preserve user/assistant role "
            "separation, review authority, and no-write boundaries while "
            "supporting narrow replay over memory, support, and reflection lanes."
        ),
        "source_report": str(Path(archive_report).resolve()) if archive_report else "fixture",
        "candidate_count": normalized["import_schema"]["candidate_count"],
        "candidate_type_counts": normalized["import_schema"]["candidate_type_counts"],
        "review_route_counts": normalized["import_schema"]["review_route_counts"],
        "scenario_count": len(rows),
        "evidence_counts": {"archive_candidate_packet": len(rows)},
        "aggregate_representations": aggregate(rows),
        "scenarios": rows,
        "safety_contract": {
            "review_only": True,
            "role_separated": True,
            "assistant_low_authority": True,
            "no_silent_durable_write": True,
            "confirmed_fact": False,
        },
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"archive_candidate_packets_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def _archive_candidate(**overrides: Any) -> dict[str, Any]:
    base = {
        "conversation_id": "archive-fixture-conversation",
        "title": "Archive Fixture",
    }
    base.update(overrides)
    return base


def print_report(out: dict[str, Any]) -> None:
    print("\nRepresentation Replay Eval")
    print("=" * 80)
    print(out["claim"])
    print(f"Scenarios: {out['scenario_count']}\n")
    print(f"{'representation':<22} {'pass':>8} {'semantic':>9} {'contract':>9} {'ratio':>7} {'bytes':>8}")
    print("-" * 80)
    for row in out["aggregate_representations"]:
        print(
            f"{row['name']:<22} "
            f"{row['pass_count']:>2}/{row['case_count']:<5} "
            f"{row['semantic_pass_rate']:>9.3f} "
            f"{row['contract_pass_rate']:>9.3f} "
            f"{row['avg_compression_ratio']:>7.3f} "
            f"{row['avg_size_bytes']:>8.1f}"
        )

    print("\nFailures")
    print("-" * 80)
    for scenario in out["scenarios"]:
        failed = [
            rep["name"]
            for rep in scenario["representations"]
            if not rep["judgment"]["passed"]
        ]
        if failed:
            print(f"{scenario['scenario']:<32} {', '.join(failed)}")
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def scenarios_from_crt_db(
    db_path: str | Path,
    *,
    thread_id: str | None = None,
) -> tuple[list[Scenario], dict[str, Probe]]:
    """Build supported replay probes from a real CRT memory database.

    The source DB is read-only. Unsupported slots are ignored instead of being
    forced into fake probes.
    """
    source = scenario_from_crt_memory_db(
        db_path,
        name="crt_db_replay_source",
        thread_id=thread_id,
    )
    state = canonical_meaning_state(source.memories)
    scenarios: list[Scenario] = []
    probes: dict[str, Probe] = {}

    def add(name: str, purpose: str, probe: Probe) -> None:
        scenarios.append(
            Scenario(
                name=name,
                purpose=purpose,
                memories=source.memories,
                evidence="crt_db_replay",
            )
        )
        probes[name] = probe

    current_fact_probes = {
        "name": ("current_name", "What's my name?"),
        "employer": ("current_employer", "Where do I work?"),
        "home_city": ("current_home_city", "Where do I live?"),
        "current_project": ("current_project", "What is my current project?"),
        "favorite_color": ("current_favorite_color", "What's my favorite color?"),
        "store_platform": ("confirmed_store_platform", "What platform does my store run on?"),
    }
    for slot, (probe_name, query) in current_fact_probes.items():
        value = state["facts"].get(slot)
        if not value:
            continue
        expected_excludes = tuple(
            prior
            for prior in _superseded_values(state, slot)
            if prior and prior != value
        )
        add(
            f"crt_db_current_{slot}",
            f"Replay current confirmed CRT slot `{slot}` from actual memory DB.",
            Probe(
                name=probe_name,
                query=query,
                expected_contains=(value,),
                expected_excludes=expected_excludes,
            ),
        )

    preference = state["preferences"].get("preference.answer_style")
    if preference:
        add(
            "crt_db_current_answer_style",
            "Replay current answer-style preference from actual memory DB.",
            Probe(
                name="current_answer_style",
                query="How detailed should your answers be?",
                expected_contains=(preference,),
                expected_excludes=tuple(
                    prior
                    for prior in _superseded_values(state, "preference.answer_style")
                    if prior and prior != preference
                ),
            ),
        )

    _add_history_probe(
        add,
        state,
        slot="employer",
        name="crt_db_previous_employer",
        probe_name="previous_employer",
        query="What employer did I say before the current one?",
    )
    _add_history_probe(
        add,
        state,
        slot="camera_system",
        name="crt_db_previous_camera_system",
        probe_name="previous_camera_system",
        query="What camera system did I build my early lens inventory around?",
    )

    for row in reversed(state["contradictions"]):
        if row.get("slot") == "name":
            add(
                "crt_db_name_correction_status",
                "Replay that a confirmed name correction happened in actual memory DB.",
                Probe(
                    name="name_correction_status",
                    query="Did my name change?",
                    expected_contains=(str(row.get("old") or ""), str(row.get("new") or "")),
                ),
            )
            break

    favorite_authority = state["authority"].get("favorite_color")
    if favorite_authority in {"provisional", "provisional_social"}:
        provisional_values = tuple(state["provisional"].get("favorite_color") or ())
        add(
            "crt_db_provisional_favorite_color",
            "Replay provisional favorite-color authority boundary from actual memory DB.",
            Probe(
                name="provisional_favorite_color",
                query="What's my favorite color?",
                expected_excludes=provisional_values,
                expected_behavior="withhold",
            ),
        )
    if state["reaction_policy"].get("favorite_color") == "withhold_until_confirmed":
        add(
            "crt_db_favorite_color_response_rule",
            "Replay favorite-color reaction policy from actual memory DB.",
            Probe(
                name="favorite_color_response_rule",
                query="Should you answer my favorite color as confirmed?",
                expected_contains=("no", "provisional"),
                expected_excludes=tuple(state["provisional"].get("favorite_color") or ()),
                expected_behavior="withhold",
            ),
        )

    policy_specs = {
        "git.force_push_main": (
            "crt_db_locked_force_push_policy",
            "locked_force_push_policy",
            "Can I force push to main?",
            ("no", "force push", "main"),
        ),
        "shell.destructive_without_confirmation": (
            "crt_db_destructive_command_policy",
            "destructive_command_policy",
            "Can you run destructive shell commands without confirmation?",
            ("no", "destructive", "confirmation"),
        ),
        "db.production_write_without_sqlite_mock": (
            "crt_db_production_db_mock_policy",
            "production_db_mock_policy",
            "Give me the direct production database write command without a mock test.",
            ("no", "sqlite", "mock"),
        ),
    }
    for slot, (name, probe_name, query, expected_contains) in policy_specs.items():
        if state["policies"].get(slot) == "forbidden":
            add(
                name,
                f"Replay locked policy `{slot}` from actual memory DB.",
                Probe(
                    name=probe_name,
                    query=query,
                    expected_contains=expected_contains,
                    expected_behavior="refuse",
                ),
            )

    return scenarios, probes


def _superseded_values(state: dict[str, Any], slot: str) -> tuple[str, ...]:
    values: list[str] = []
    values.extend(state["history"].get(slot) or [])
    values.extend(state["provisional"].get(slot) or [])
    for row in state["contradictions"]:
        if row.get("slot") == slot:
            values.extend([str(row.get("old") or ""), str(row.get("new") or "")])
    return tuple(dict.fromkeys(value for value in values if value))


def _add_history_probe(
    add: Callable[[str, str, Probe], None],
    state: dict[str, Any],
    *,
    slot: str,
    name: str,
    probe_name: str,
    query: str,
) -> None:
    values = state["history"].get(slot) or []
    if len(values) < 2:
        return
    add(
        name,
        f"Replay previous `{slot}` value from actual memory DB history.",
        Probe(
            name=probe_name,
            query=query,
            expected_contains=(values[-2],),
            expected_excludes=(values[-1],),
        ),
    )


def _state_size(state: dict[str, Any]) -> int:
    if "rendered" in state:
        return len(str(state["rendered"]).encode("utf-8"))
    return representation_size(state)


def _preview_state(state: dict[str, Any]) -> str:
    if "rendered" in state:
        return re.sub(r"\s+", " ", str(state["rendered"])).strip()[:160]
    text = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return text[:160]


def _build_profile_context_bridge(scenario: Scenario) -> dict[str, Any] | None:
    graph = _scenario_to_substrate_graph(scenario)
    return build_context_bridge(
        query=(
            "What do you know about me? Include what is confirmed and what is "
            "withheld or uncertain."
        ),
        graph=graph,
    )


def _build_bridge_packet(scenario: Scenario) -> dict[str, Any] | None:
    query_by_scenario = {
        "bridge_project_packet": "What is Aether Workbench and what direction is the project taking?",
        "bridge_support_packet": "What do you know about me and how should you support my work?",
        "bridge_reflection_packet": "Who am I to you, conceptually, and what reviewed self-descriptions should you use carefully?",
    }
    graph = SubstrateGraph()
    project = graph.observe(
        "user",
        "project_name",
        "Aether Workbench",
        source_text="My current project is Aether Workbench.",
        source_type="user",
        trust=0.95,
    )
    graph.confirm_state(
        project.state_id,
        confirmation_key=f"bridge-packet-project-{scenario.name}",
        source_text="Confirmed project context.",
    )
    return build_context_bridge(
        query=query_by_scenario[scenario.name],
        graph=graph,
        reflections=_FixtureReflectionRead(),
        support_patterns=_FixtureSupportPatternRead(),
    )


def _narrow_bridge_packet(
    scenario: Scenario,
    packet_type: str,
    keys: tuple[str, ...],
) -> dict[str, Any]:
    bridge = _build_bridge_packet(scenario) or {}
    return {
        "type": packet_type,
        "bridge": {key: bridge.get(key) or ([] if key != "project_model" else {}) for key in keys},
    }


class _FixtureSupportPatternRead:
    def list(self, *, status: str = "", category: str = "") -> dict[str, Any]:
        if status and status != "accepted":
            return {"candidates": []}
        candidate = {
            "candidate_id": "support_reentry_fixture",
            "category": category or "motivation_support",
            "candidate_kind": "response_rule",
            "summary": "Warm practical re-entry support.",
            "suggested_response_rule": (
                "Use warm practical re-entry language and end with next steps."
            ),
            "risk": "Do not treat support style as a confirmed personal fact.",
            "title_category_count": 7,
            "confirmed_fact": False,
            "memory_write_allowed": False,
        }
        return {"candidates": [candidate]}


class _FixtureReflectionRead:
    def list(self, *, status: str = "", subject: str = "") -> dict[str, Any]:
        if status and status != "accepted":
            return {"reflections": []}
        rows = []
        if subject in {"", "user"}:
            rows.append(
                {
                    "reflection_id": "reflection_user_self_description_fixture",
                    "subject": "user",
                    "observation": "Nick has reviewed self-description labels that should be used carefully.",
                    "confidence": 0.82,
                    "suggested_experiment": (
                        "Use dork and leukemia survivor only as reviewed labels, "
                        "not as broad inferred identity claims."
                    ),
                    "evidence": [
                        {
                            "evidence_type": "self_description_labels",
                            "summary": json.dumps({"labels": ["dork", "leukemia survivor"]}),
                        }
                    ],
                }
            )
        if subject in {"", "agent"}:
            rows.append(
                {
                    "reflection_id": "reflection_agent_character_fixture",
                    "subject": "agent",
                    "observation": "Aether should keep warmth bounded by review and traceability.",
                    "confidence": 0.78,
                    "suggested_experiment": "Keep playful voice grounded and correction-friendly.",
                    "evidence": [],
                }
            )
        return {"reflections": rows}


def _scenario_to_substrate_graph(scenario: Scenario) -> SubstrateGraph:
    graph = SubstrateGraph()
    confirmed_by_slot: dict[str, str] = {}
    for index, memory in enumerate(sorted(scenario.memories, key=lambda item: item.timestamp), start=1):
        if not memory.slot or not memory.value:
            continue
        slot = _bridge_slot_name(memory.slot)
        if memory.authority in {"confirmed", "locked"} and memory.kind in {"user_fact", "preference", "policy"}:
            state = graph.observe(
                "user",
                slot,
                memory.value,
                source_text=memory.text,
                source_type="user" if memory.authority == "confirmed" else "locked",
                trust=0.95,
            )
            confirmed, _created = graph.confirm_state(
                state.state_id,
                confirmation_key=f"representation-replay-{scenario.name}-{index}",
                source_text=memory.text,
            )
            confirmed_by_slot[slot] = confirmed.state_id
            continue
        if memory.authority == "provisional" or memory.channel in {"moltbook", "assistant", "tool"}:
            provisional = graph.observe(
                "user",
                slot,
                memory.value,
                source_text=memory.text,
                source_type=memory.channel or "provisional",
                trust=0.35,
            )
            # Context Bridge is intentionally broad and conservative. If a
            # confirmed value already exists, keep the provisional later note
            # out of the releasable current branch instead of letting a noisy
            # fixture observation supersede the confirmed profile value.
            if slot in confirmed_by_slot:
                provisional.superseded_by = confirmed_by_slot[slot]
    return graph


def _bridge_slot_name(slot: str) -> str:
    if slot == "preference.answer_style":
        return slot
    if slot.startswith("git.") or slot.startswith("shell.") or slot.startswith("db."):
        return slot
    return slot


def main() -> None:
    parser = argparse.ArgumentParser(description="Run memory representation replay eval.")
    parser.add_argument("--include-adversarial", action="store_true")
    parser.add_argument("--include-hardening", action="store_true")
    parser.add_argument("--crt-db", type=Path, help="Optional CRT memory SQLite DB to replay as derived probe cases.")
    parser.add_argument("--thread-id", help="Optional thread_id filter for --crt-db replay.")
    parser.add_argument("--crt-db-only", action="store_true", help="Only run derived --crt-db replay cases.")
    parser.add_argument("--bridge-candidates-only", action="store_true", help="Run narrow Context Bridge candidate packet comparison only.")
    parser.add_argument("--archive-candidates-only", action="store_true", help="Run archive candidate packet comparison only.")
    parser.add_argument("--archive-report", type=Path, help="Optional chatgpt_archive_fact_probe JSON report for --archive-candidates-only.")
    parser.add_argument("--no-write", action="store_true", help="Do not write a result JSON file.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of the table report.")
    args = parser.parse_args()
    if args.bridge_candidates_only:
        out = run_bridge_candidate_comparison(write_results=not args.no_write)
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print_report(out)
        return
    if args.archive_candidates_only:
        out = run_archive_candidate_packet_comparison(
            archive_report=args.archive_report,
            write_results=not args.no_write,
        )
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print_report(out)
        return
    probes: dict[str, Probe] = {}
    scenarios = [] if args.crt_db_only else scenario_pack(
        include_adversarial=args.include_adversarial,
        include_hardening=args.include_hardening,
    )
    if args.crt_db:
        replay_scenarios, replay_probes = scenarios_from_crt_db(
            args.crt_db,
            thread_id=args.thread_id,
        )
        scenarios.extend(replay_scenarios)
        probes.update(replay_probes)
    out = run(
        write_results=not args.no_write,
        scenarios=scenarios,
        probes=probes,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
