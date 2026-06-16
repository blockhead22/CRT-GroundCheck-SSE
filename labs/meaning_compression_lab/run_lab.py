"""Meaning compression lab.

This lab operationalizes "meaning" as deterministic structure preserved under
compression. It does not try to prove a universal theory of meaning.

The main score compares a projected compressed state against a canonical meaning
state: facts, history, contradictions, authority, policies, volatility, reaction
policy, and bit-level flags. Behavior probes remain as a secondary projection
check, not the core proof.

Run:
    python labs/meaning_compression_lab/run_lab.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


OUT_DIR = Path(__file__).parent / "results"


@dataclass(frozen=True)
class Memory:
    text: str
    kind: str
    authority: str
    channel: str
    timestamp: int
    slot: str | None = None
    value: str | None = None
    prior_value: str | None = None


@dataclass(frozen=True)
class Scenario:
    name: str
    purpose: str
    memories: list[Memory]
    evidence: str = "fixture"


@dataclass(frozen=True)
class Invariant:
    name: str
    dimension: str
    weight: float
    check: Callable[[dict[str, Any]], bool]


SCENARIOS: list[Scenario] = [
    Scenario(
        name="identity_flip",
        purpose="Identity changed; current value, history, contradiction, volatility, and bit flags must survive.",
        memories=[
            Memory("My name is Sarah.", "user_fact", "confirmed", "webchat", 1, "name", "Sarah"),
            Memory("Actually, my name is Emily.", "user_fact", "confirmed", "webchat", 2, "name", "Emily", "Sarah"),
        ],
    ),
    Scenario(
        name="employer_correction",
        purpose="Current employer must supersede prior employer while preserving the contradiction.",
        memories=[
            Memory("I work at Microsoft as a senior developer.", "user_fact", "confirmed", "webchat", 1, "employer", "Microsoft"),
            Memory("Actually, I work at Amazon, not Microsoft.", "user_fact", "confirmed", "webchat", 2, "employer", "Amazon", "Microsoft"),
        ],
    ),
    Scenario(
        name="authority_boundary",
        purpose="A social/provisional claim must remain non-answerable and keep its authority flag.",
        memories=[
            Memory("My favorite color is blue.", "observation", "provisional", "moltbook", 1, "favorite_color", "blue"),
        ],
    ),
    Scenario(
        name="policy_constraint",
        purpose="A locked action policy must survive compression as a refusal policy.",
        memories=[
            Memory("Never force push to main.", "policy", "locked", "webchat", 1, "git.force_push_main", "forbidden"),
        ],
    ),
    Scenario(
        name="concern_preference",
        purpose="A non-contradiction meaning layer must survive: concern plus preference.",
        memories=[
            Memory("I am worried the system forgets contradictions.", "concern", "confirmed", "webchat", 1, "concern.memory", "system forgets contradictions"),
            Memory("Prefer concise technical answers.", "preference", "confirmed", "webchat", 2, "preference.answer_style", "concise technical"),
        ],
    ),
]


ADVERSARIAL_SCENARIOS: list[Scenario] = [
    Scenario(
        name="favorite_color_social_then_confirmed",
        purpose="A provisional social claim must yield to a later confirmed user fact while preserving conflict history.",
        memories=[
            Memory("Moltbook suggests my favorite color is blue.", "observation", "provisional", "moltbook", 1, "favorite_color", "blue"),
            Memory("My favorite color is green, not blue.", "user_fact", "confirmed", "webchat", 2, "favorite_color", "green", "blue"),
        ],
    ),
    Scenario(
        name="answer_style_revision",
        purpose="A changed preference must preserve the old style as history without governing current answers.",
        memories=[
            Memory("Prefer detailed exploratory answers.", "preference", "confirmed", "webchat", 1, "preference.answer_style", "detailed exploratory"),
            Memory("Actually, prefer concise technical answers, not detailed ones.", "preference", "confirmed", "webchat", 2, "preference.answer_style", "concise technical", "detailed exploratory"),
        ],
    ),
    Scenario(
        name="project_revert",
        purpose="A slot can return to a prior value; current value and multiple contradictions must both survive.",
        memories=[
            Memory("My current project is Atlas.", "user_fact", "confirmed", "webchat", 1, "current_project", "Atlas"),
            Memory("My current project is Borealis now.", "user_fact", "confirmed", "webchat", 2, "current_project", "Borealis", "Atlas"),
            Memory("I am back on Project Atlas, not Borealis.", "user_fact", "confirmed", "webchat", 3, "current_project", "Atlas", "Borealis"),
        ],
    ),
    Scenario(
        name="location_correction",
        purpose="A stale location must not remain current just because raw text mentions it.",
        memories=[
            Memory("I live in Denver.", "user_fact", "confirmed", "webchat", 1, "home_city", "Denver"),
            Memory("I moved to Austin, not Denver.", "user_fact", "confirmed", "webchat", 2, "home_city", "Austin", "Denver"),
        ],
    ),
    Scenario(
        name="destructive_command_policy",
        purpose="A second locked action policy must survive as policy, not as ordinary retrieved text.",
        memories=[
            Memory("Never run destructive shell commands without explicit confirmation.", "policy", "locked", "webchat", 1, "shell.destructive_without_confirmation", "forbidden"),
        ],
    ),
    Scenario(
        name="employer_history_question",
        purpose="The system must preserve the superseded value so it can answer history questions, not only current-state questions.",
        memories=[
            Memory("I work at Microsoft.", "user_fact", "confirmed", "webchat", 1, "employer", "Microsoft"),
            Memory("Actually, I work at Amazon, not Microsoft.", "user_fact", "confirmed", "webchat", 2, "employer", "Amazon", "Microsoft"),
        ],
    ),
    Scenario(
        name="name_contradiction_status",
        purpose="The system must represent that a correction happened, not only the latest name value.",
        memories=[
            Memory("My name is Sarah.", "user_fact", "confirmed", "webchat", 1, "name", "Sarah"),
            Memory("Actually, my name is Emily, not Sarah.", "user_fact", "confirmed", "webchat", 2, "name", "Emily", "Sarah"),
        ],
    ),
    Scenario(
        name="multi_fact_update",
        purpose="A single correction can update multiple slots and must preserve each slot's prior value.",
        memories=[
            Memory("My name is Sarah and I work at Microsoft.", "user_fact", "confirmed", "webchat", 1, "name", "Sarah"),
            Memory("My name is Sarah and I work at Microsoft.", "user_fact", "confirmed", "webchat", 1, "employer", "Microsoft"),
            Memory("Actually, my name is Emily and I work at Amazon, not Sarah at Microsoft.", "user_fact", "confirmed", "webchat", 2, "name", "Emily", "Sarah"),
            Memory("Actually, my name is Emily and I work at Amazon, not Sarah at Microsoft.", "user_fact", "confirmed", "webchat", 2, "employer", "Amazon", "Microsoft"),
        ],
    ),
    Scenario(
        name="model_generated_name_contamination",
        purpose="A model/provisional memory about identity must not override a confirmed user identity.",
        memories=[
            Memory("My name is Nick.", "user_fact", "confirmed", "webchat", 1, "name", "Nick"),
            Memory("The assistant guessed the user's name might be Mike.", "observation", "provisional", "assistant", 2, "name", "Mike", "Nick"),
        ],
    ),
    Scenario(
        name="tool_inferred_location_noise",
        purpose="A tool-inferred provisional location must not override a confirmed user location.",
        memories=[
            Memory("I live in Chicago.", "user_fact", "confirmed", "webchat", 1, "home_city", "Chicago"),
            Memory("A browser timezone lookup suggests the user may be in Los Angeles.", "observation", "provisional", "tool", 2, "home_city", "Los Angeles", "Chicago"),
        ],
    ),
]


def scenario_pack(*, include_adversarial: bool = False) -> list[Scenario]:
    scenarios = list(SCENARIOS)
    if include_adversarial:
        scenarios.extend(ADVERSARIAL_SCENARIOS)
    return scenarios


def scenario_from_crt_memory_db(
    db_path: str | Path,
    *,
    name: str = "crt_db_replay",
    purpose: str | None = None,
    thread_id: str | None = None,
) -> Scenario:
    """Build a lab scenario from actual CRT `memories` and `memory_facts` rows."""
    path = Path(db_path)
    where = ["COALESCE(m.deprecated, 0) = 0"]
    params: list[Any] = []
    if thread_id is not None:
        where.append("m.thread_id = ?")
        params.append(thread_id)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT
                m.memory_id,
                m.text,
                m.timestamp,
                m.source,
                COALESCE(m.authority, 'confirmed') AS authority,
                COALESCE(m.channel, 'unknown') AS channel,
                COALESCE(m.kind, 'observation') AS kind,
                mf.slot,
                mf.value,
                mf.normalized
            FROM memories m
            LEFT JOIN memory_facts mf ON mf.memory_id = m.memory_id
            WHERE {" AND ".join(where)}
            ORDER BY m.timestamp ASC, m.memory_id ASC, mf.slot ASC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    memories: list[Memory] = []
    prior_confirmed_values: dict[str, str] = {}
    seen_projected_rows: set[tuple[str, str]] = set()
    for row in rows:
        memory_id = str(row["memory_id"] or "")
        raw_slot = str(row["slot"] or "").strip()
        raw_value = str(row["value"] or "").strip()
        kind = str(row["kind"] or "observation").strip().lower()
        authority = str(row["authority"] or "confirmed").strip().lower()
        channel = str(row["channel"] or "unknown").strip().lower()
        projected_policy = _project_locked_action_policy(
            text=str(row["text"] or ""),
            kind=kind,
            authority=authority,
        )

        if raw_slot and raw_value:
            slot = raw_slot
            value = raw_value
        elif projected_policy is not None:
            slot, value = projected_policy
            kind = "policy"
        else:
            continue

        projection_key = (memory_id, slot)
        if projection_key in seen_projected_rows:
            continue
        seen_projected_rows.add(projection_key)
        prior_value = None

        if kind in {"user_fact", "preference"} and authority in {"confirmed", "locked"}:
            prior = prior_confirmed_values.get(slot)
            if prior is not None and _meaning_value_key(prior) != _meaning_value_key(value):
                prior_value = prior
            prior_confirmed_values[slot] = value

        memories.append(
            Memory(
                text=str(row["text"] or ""),
                kind=kind,
                authority=authority,
                channel=channel,
                timestamp=float(row["timestamp"] or 0.0),
                slot=slot,
                value=value,
                prior_value=prior_value,
            )
        )

    return Scenario(
        name=name,
        purpose=purpose
        or "Replay actual CRT persisted memory facts into the deterministic meaning-compression lab.",
        memories=memories,
        evidence="crt_db_replay",
    )


def _meaning_value_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _authority_rank(value: str | None) -> int:
    return {
        "provisional": 1,
        "provisional_social": 1,
        "confirmed": 2,
        "locked": 3,
    }.get(str(value or ""), 0)


def _set_authority(authority: dict[str, str], slot: str, value: str) -> None:
    if _authority_rank(value) >= _authority_rank(authority.get(slot)):
        authority[slot] = value


def _project_locked_action_policy(
    *,
    text: str,
    kind: str,
    authority: str,
) -> tuple[str, str] | None:
    """Narrow lab projection for the locked action policy already under test."""
    normalized = _meaning_value_key(text)
    if authority != "locked" or kind not in {"ops", "user_fact"}:
        return None
    if "never force push to main" in normalized or "do not force push to main" in normalized:
        return ("git.force_push_main", "forbidden")
    return None


def canonical_meaning_state(memories: list[Memory]) -> dict[str, Any]:
    """Deterministically reduce events into layered meaning state."""
    facts: dict[str, str] = {}
    history: dict[str, list[str]] = {}
    contradictions: list[dict[str, str]] = []
    authority: dict[str, str] = {}
    policies: dict[str, str] = {}
    concerns: list[str] = []
    preferences: dict[str, str] = {}

    for mem in sorted(memories, key=lambda m: m.timestamp):
        if mem.slot is None:
            continue
        if mem.prior_value and mem.value:
            contradictions.append(
                {
                    "slot": mem.slot,
                    "old": mem.prior_value,
                    "new": mem.value,
                    "status": "preserved",
                }
            )
            history.setdefault(mem.slot, [])
            for value in (mem.prior_value, mem.value):
                if value not in history[mem.slot]:
                    history[mem.slot].append(value)
        if mem.kind == "user_fact" and mem.authority in {"confirmed", "locked"} and mem.value:
            facts[mem.slot] = mem.value
            history.setdefault(mem.slot, [])
            if mem.value not in history[mem.slot]:
                history[mem.slot].append(mem.value)
        if mem.kind == "preference" and mem.authority in {"confirmed", "locked"} and mem.value:
            preferences[mem.slot] = mem.value
        if mem.authority == "provisional" or mem.channel == "moltbook":
            _set_authority(
                authority,
                mem.slot,
                "provisional_social" if mem.channel == "moltbook" else "provisional",
            )
        elif mem.authority in {"confirmed", "locked"} and mem.kind in {"user_fact", "preference"}:
            _set_authority(authority, mem.slot, mem.authority)
        if mem.kind == "policy" and mem.authority == "locked" and mem.value:
            policies[mem.slot] = mem.value
        if mem.kind == "concern" and mem.value:
            concerns.append(mem.value)

    volatility = _derive_volatility(history, contradictions, authority)
    reaction_policy = _derive_reaction_policy(volatility, authority, policies)
    bit_flags = _derive_bit_flags(facts, history, contradictions, authority, policies, concerns, preferences)
    return {
        "facts": facts,
        "history": history,
        "contradictions": contradictions,
        "authority": authority,
        "policies": policies,
        "concerns": concerns,
        "preferences": preferences,
        "volatility": volatility,
        "reaction_policy": reaction_policy,
        "bit_flags": bit_flags,
    }


def _derive_volatility(
    history: dict[str, list[str]],
    contradictions: list[dict[str, str]],
    authority: dict[str, str],
) -> dict[str, dict[str, Any]]:
    volatility: dict[str, dict[str, Any]] = {}
    contradiction_slots = {c.get("slot") for c in contradictions}
    for slot, values in history.items():
        flips = max(0, len(values) - 1)
        volatility[slot] = {
            "flips": flips,
            "contradicts_prior": slot in contradiction_slots,
            "level": "volatile" if flips else "stable",
        }
    for slot, value in authority.items():
        if value in {"provisional", "provisional_social"}:
            volatility[slot] = {
                "flips": 0,
                "contradicts_prior": False,
                "level": "provisional",
            }
    return volatility


def _derive_reaction_policy(
    volatility: dict[str, dict[str, Any]],
    authority: dict[str, str],
    policies: dict[str, str],
) -> dict[str, str]:
    reaction: dict[str, str] = {}
    for slot, info in volatility.items():
        if info.get("contradicts_prior"):
            reaction[slot] = "answer_current_with_history"
        elif info.get("level") == "provisional":
            reaction[slot] = "withhold_until_confirmed"
        else:
            reaction[slot] = "answer_direct"
    for slot, value in authority.items():
        if value in {"provisional", "provisional_social"}:
            reaction[slot] = "withhold_until_confirmed"
    for slot, value in policies.items():
        if value == "forbidden":
            reaction[slot] = "refuse_action"
    return reaction


def _derive_bit_flags(
    facts: dict[str, str],
    history: dict[str, list[str]],
    contradictions: list[dict[str, str]],
    authority: dict[str, str],
    policies: dict[str, str],
    concerns: list[str],
    preferences: dict[str, str],
) -> dict[str, bool]:
    contradiction_slots = {c.get("slot") for c in contradictions if c.get("status") == "preserved"}
    flags: dict[str, bool] = {}
    for slot, value in facts.items():
        flags[f"fact:{slot}={value}"] = True
    for slot, values in history.items():
        flags[f"flipped:{slot}"] = len(values) > 1
    for slot in contradiction_slots:
        flags[f"contradiction:{slot}"] = True
    for slot, value in authority.items():
        flags[f"authority:{slot}={value}"] = True
    for slot, value in policies.items():
        flags[f"policy:{slot}={value}"] = True
    for concern in concerns:
        flags[f"concern:{concern}"] = True
    for slot, value in preferences.items():
        flags[f"preference:{slot}={value}"] = True
    return flags


def full_transcript_state(scenario: Scenario) -> dict[str, Any]:
    return {"type": "full_transcript", "memories": [m.__dict__ for m in scenario.memories]}


def naive_summary_state(scenario: Scenario) -> dict[str, Any]:
    latest = canonical_meaning_state(scenario.memories)
    rough_bits = []
    if latest["facts"]:
        rough_bits.append("has some current personal facts")
    if latest["policies"]:
        rough_bits.append("has a work/action preference")
    if latest["concerns"]:
        rough_bits.append("has a memory concern")
    if latest["authority"]:
        rough_bits.append("has an outside/social note")
    return {"type": "naive_summary", "summary": "; ".join(rough_bits) or "short user memory summary"}


def slot_only_state(scenario: Scenario) -> dict[str, Any]:
    canonical = canonical_meaning_state(scenario.memories)
    facts = dict(canonical["facts"])
    for slot, value in canonical["preferences"].items():
        facts[slot] = value
    for slot, value in canonical["policies"].items():
        facts[slot] = value
    for mem in scenario.memories:
        if mem.authority == "provisional" and mem.value:
            facts[mem.slot or "unknown"] = mem.value
    return {"type": "slot_only", "facts": facts}


def crt_compressed_state(scenario: Scenario) -> dict[str, Any]:
    canonical = canonical_meaning_state(scenario.memories)
    return {
        "type": "crt_compressed",
        "facts": canonical["facts"],
        "history": canonical["history"],
        "contradictions": canonical["contradictions"],
        "authority": canonical["authority"],
        "policies": canonical["policies"],
        "concerns": canonical["concerns"],
        "preferences": canonical["preferences"],
    }


def crt_without_contradictions(scenario: Scenario) -> dict[str, Any]:
    state = crt_compressed_state(scenario)
    state = json.loads(json.dumps(state))
    state["type"] = "crt_no_contradictions"
    state["history"] = {}
    state["contradictions"] = []
    return state


def crt_without_authority(scenario: Scenario) -> dict[str, Any]:
    state = crt_compressed_state(scenario)
    state = json.loads(json.dumps(state))
    state["type"] = "crt_no_authority"
    state["authority"] = {}
    for mem in scenario.memories:
        if mem.authority == "provisional" and mem.value:
            state.setdefault("facts", {})[mem.slot or "unknown"] = mem.value
    return state


REPRESENTATIONS: dict[str, Callable[[Scenario], dict[str, Any]]] = {
    "full_transcript": full_transcript_state,
    "naive_summary": naive_summary_state,
    "slot_only": slot_only_state,
    "crt_compressed": crt_compressed_state,
    "crt_no_contradictions": crt_without_contradictions,
    "crt_no_authority": crt_without_authority,
}


def project_meaning_state(state: dict[str, Any]) -> dict[str, Any]:
    """Project any representation into the canonical layer schema."""
    if state["type"] == "full_transcript":
        return canonical_meaning_state([Memory(**m) for m in state["memories"]])
    if state["type"] == "naive_summary":
        facts: dict[str, str] = {}
        history: dict[str, list[str]] = {}
        contradictions: list[dict[str, str]] = []
        authority: dict[str, str] = {}
        policies: dict[str, str] = {}
        concerns: list[str] = []
        preferences: dict[str, str] = {}
    else:
        facts = dict(state.get("facts", {}))
        history = {k: list(v) for k, v in state.get("history", {}).items()}
        contradictions = [dict(c) for c in state.get("contradictions", [])]
        authority = dict(state.get("authority", {}))
        policies = dict(state.get("policies", {}))
        concerns = list(state.get("concerns", []))
        preferences = dict(state.get("preferences", {}))

    volatility = _derive_volatility(history, contradictions, authority)
    reaction_policy = _derive_reaction_policy(volatility, authority, policies)
    bit_flags = _derive_bit_flags(facts, history, contradictions, authority, policies, concerns, preferences)
    return {
        "facts": facts,
        "history": history,
        "contradictions": contradictions,
        "authority": authority,
        "policies": policies,
        "concerns": concerns,
        "preferences": preferences,
        "volatility": volatility,
        "reaction_policy": reaction_policy,
        "bit_flags": bit_flags,
    }


def invariants_for(expected: dict[str, Any]) -> list[Invariant]:
    invariants: list[Invariant] = []

    for slot, value in expected["facts"].items():
        invariants.append(Invariant(f"fact:{slot}", "fact", 1.25, lambda s, slot=slot, value=value: s["facts"].get(slot) == value))
    for slot, values in expected["history"].items():
        if len(values) > 1:
            invariants.append(Invariant(f"history:{slot}", "history", 1.25, lambda s, slot=slot, values=values: s["history"].get(slot) == values))
    for c in expected["contradictions"]:
        slot, old, new = c["slot"], c["old"], c["new"]
        invariants.append(
            Invariant(
                f"contradiction:{slot}",
                "contradiction",
                1.5,
                lambda s, slot=slot, old=old, new=new: any(
                    row.get("slot") == slot and row.get("old") == old and row.get("new") == new
                    for row in s["contradictions"]
                ),
            )
        )
    for slot, value in expected["authority"].items():
        invariants.append(Invariant(f"authority:{slot}", "authority", 1.25, lambda s, slot=slot, value=value: s["authority"].get(slot) == value))
    for slot, value in expected["policies"].items():
        invariants.append(Invariant(f"policy:{slot}", "policy", 1.25, lambda s, slot=slot, value=value: s["policies"].get(slot) == value))
    for i, value in enumerate(expected["concerns"]):
        invariants.append(Invariant(f"concern:{i}", "concern", 1.0, lambda s, value=value: value in s["concerns"]))
    for slot, value in expected["preferences"].items():
        invariants.append(Invariant(f"preference:{slot}", "preference", 1.0, lambda s, slot=slot, value=value: s["preferences"].get(slot) == value))
    for slot, info in expected["volatility"].items():
        if info.get("level") in {"volatile", "provisional"}:
            invariants.append(
                Invariant(
                    f"volatility:{slot}",
                    "volatility",
                    1.25,
                    lambda s, slot=slot, info=info: s["volatility"].get(slot) == info,
                )
            )
    for slot, value in expected["reaction_policy"].items():
        invariants.append(Invariant(f"reaction:{slot}", "reaction_policy", 1.0, lambda s, slot=slot, value=value: s["reaction_policy"].get(slot) == value))
    for bit, value in expected["bit_flags"].items():
        if value is True:
            invariants.append(Invariant(f"bit:{bit}", "bit_flags", 0.75, lambda s, bit=bit: s["bit_flags"].get(bit) is True))

    return invariants


def representation_size(state: dict[str, Any]) -> int:
    return len(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def score_projected(projected: dict[str, Any], invariants: list[Invariant]) -> tuple[float, list[dict[str, Any]]]:
    total = sum(inv.weight for inv in invariants) or 1.0
    passed_weight = 0.0
    rows = []
    for inv in invariants:
        passed = bool(inv.check(projected))
        if passed:
            passed_weight += inv.weight
        rows.append({"invariant": inv.name, "dimension": inv.dimension, "weight": inv.weight, "passed": passed})
    return passed_weight / total, rows


def behavior_projection_score(projected: dict[str, Any], expected: dict[str, Any]) -> float:
    """Secondary sanity score: do the user-facing projections match core layers?"""
    checks = []
    for slot, value in expected["facts"].items():
        checks.append(projected["facts"].get(slot) == value)
    for slot, value in expected["reaction_policy"].items():
        checks.append(projected["reaction_policy"].get(slot) == value)
    for slot, value in expected["policies"].items():
        checks.append(projected["policies"].get(slot) == value)
    if not checks:
        return 1.0
    return sum(1 for ok in checks if ok) / len(checks)


def score_representation(scenario: Scenario, name: str, state: dict[str, Any], full_size: int) -> dict[str, Any]:
    expected = canonical_meaning_state(scenario.memories)
    invariants = invariants_for(expected)
    projected = project_meaning_state(state)
    structural_score, invariant_rows = score_projected(projected, invariants)
    behavior_score = behavior_projection_score(projected, expected)
    size = representation_size(state)
    compression_ratio = size / full_size if full_size else 0.0
    meaning_density = structural_score / compression_ratio if compression_ratio else 0.0
    dimensions: dict[str, list[float]] = {}
    for row in invariant_rows:
        dimensions.setdefault(row["dimension"], []).append(1.0 if row["passed"] else 0.0)

    return {
        "scenario": scenario.name,
        "name": name,
        "size_bytes": size,
        "compression_ratio": round(compression_ratio, 3),
        "structural_score": round(structural_score, 3),
        "behavior_score": round(behavior_score, 3),
        "meaning_density": round(meaning_density, 3),
        "structural_dimension_scores": {
            dim: round(sum(vals) / len(vals), 3) for dim, vals in sorted(dimensions.items())
        },
        "failed_invariants": [r["invariant"] for r in invariant_rows if not r["passed"]],
        "invariants": invariant_rows,
    }


def score_scenario(scenario: Scenario) -> dict[str, Any]:
    full = full_transcript_state(scenario)
    full_size = representation_size(full)
    rows = [
        score_representation(scenario, name, builder(scenario), full_size)
        for name, builder in REPRESENTATIONS.items()
    ]
    rows.sort(key=lambda r: (r["structural_score"], r["meaning_density"]), reverse=True)
    return {
        "name": scenario.name,
        "evidence": scenario.evidence,
        "purpose": scenario.purpose,
        "full_transcript_size_bytes": full_size,
        "canonical_meaning_state": canonical_meaning_state(scenario.memories),
        "representations": rows,
        "semantic_sensitivity": semantic_sensitivity(scenario),
        "bit_sensitivity": bit_sensitivity(scenario),
    }


def aggregate_rows(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for scenario in scenarios:
        for row in scenario["representations"]:
            by_name.setdefault(row["name"], []).append(row)
    aggregate = []
    for name, rows in by_name.items():
        aggregate.append(
            {
                "name": name,
                "avg_size_bytes": round(sum(r["size_bytes"] for r in rows) / len(rows), 1),
                "avg_compression_ratio": round(sum(r["compression_ratio"] for r in rows) / len(rows), 3),
                "avg_structural_score": round(sum(r["structural_score"] for r in rows) / len(rows), 3),
                "avg_behavior_score": round(sum(r["behavior_score"] for r in rows) / len(rows), 3),
                "avg_meaning_density": round(sum(r["meaning_density"] for r in rows) / len(rows), 3),
            }
        )
    aggregate.sort(key=lambda r: (r["avg_structural_score"], r["avg_meaning_density"]), reverse=True)
    return aggregate


def semantic_sensitivity(scenario: Scenario) -> list[dict[str, Any]]:
    base = crt_compressed_state(scenario)
    full_size = representation_size(full_transcript_state(scenario))
    base_score = score_representation(scenario, "crt_compressed", base, full_size)
    fields = ["facts", "history", "contradictions", "authority", "policies", "concerns", "preferences"]
    impacts = []
    for field in fields:
        damaged = json.loads(json.dumps(base))
        damaged[field] = {} if isinstance(damaged.get(field), dict) else []
        result = score_representation(scenario, f"remove_{field}", damaged, full_size)
        impacts.append(
            {
                "perturbation": f"remove_{field}",
                "score_after": result["structural_score"],
                "damage": round(base_score["structural_score"] - result["structural_score"], 3),
                "failed_invariants": result["failed_invariants"],
            }
        )
    impacts.sort(key=lambda x: x["damage"], reverse=True)
    return impacts


def bit_sensitivity(scenario: Scenario) -> list[dict[str, Any]]:
    expected = canonical_meaning_state(scenario.memories)
    invariants = invariants_for(expected)
    base = project_meaning_state(crt_compressed_state(scenario))
    base_score, _ = score_projected(base, invariants)
    impacts = []
    for bit_name, value in sorted(base["bit_flags"].items()):
        damaged = json.loads(json.dumps(base))
        damaged["bit_flags"][bit_name] = not bool(value)
        score_after, rows = score_projected(damaged, invariants)
        impacts.append(
            {
                "bit": bit_name,
                "from": bool(value),
                "to": not bool(value),
                "score_after": round(score_after, 3),
                "damage": round(base_score - score_after, 3),
                "failed_invariants": [r["invariant"] for r in rows if not r["passed"]],
            }
        )
    impacts.sort(key=lambda x: x["damage"], reverse=True)
    return impacts


def run(write_results: bool = True, scenarios: list[Scenario] | None = None) -> dict[str, Any]:
    scenario_set = scenarios if scenarios is not None else SCENARIOS
    scenario_results = [score_scenario(s) for s in scenario_set]
    out = {
        "lab": "meaning_compression_lab",
        "claim": "Meaning can be operationalized as deterministic layered structure preserved per byte under compression.",
        "scenario_count": len(scenario_set),
        "evidence_counts": {
            evidence: sum(1 for s in scenario_set if s.evidence == evidence)
            for evidence in sorted({s.evidence for s in scenario_set})
        },
        "aggregate_representations": aggregate_rows(scenario_results),
        "scenarios": scenario_results,
    }

    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"meaning_compression_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nMeaning Compression Lab")
    print("=" * 80)
    print(out["claim"])
    print(f"Scenarios: {out['scenario_count']}\n")
    if "evidence_counts" in out:
        evidence = ", ".join(f"{k}={v}" for k, v in sorted(out["evidence_counts"].items()))
        print(f"Evidence: {evidence}\n")

    print("Aggregate")
    print("-" * 80)
    print(f"{'representation':<24} {'bytes':>8} {'ratio':>7} {'structure':>9} {'behavior':>9} {'density':>9}")
    for row in out["aggregate_representations"]:
        print(
            f"{row['name']:<24} "
            f"{row['avg_size_bytes']:>8.1f} "
            f"{row['avg_compression_ratio']:>7.3f} "
            f"{row['avg_structural_score']:>9.3f} "
            f"{row['avg_behavior_score']:>9.3f} "
            f"{row['avg_meaning_density']:>9.3f}"
        )

    print("\nPer Scenario")
    print("-" * 80)
    for scenario in out["scenarios"]:
        best = scenario["representations"][0]
        print(
            f"{scenario['name']:<24} [{scenario.get('evidence', 'unknown'):<13}] best={best['name']:<18} "
            f"structure={best['structural_score']:.3f} density={best['meaning_density']:.3f}"
        )
        top_damage = next((x for x in scenario["semantic_sensitivity"] if x["damage"] > 0), None)
        if top_damage:
            print(f"  top structural loss: {top_damage['perturbation']} damage={top_damage['damage']:.3f}")
        top_bit = next((x for x in scenario["bit_sensitivity"] if x["damage"] > 0), None)
        if top_bit:
            print(f"  top bit loss: {top_bit['bit']} damage={top_bit['damage']:.3f}")

    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the meaning compression lab.")
    parser.add_argument("--no-write", action="store_true", help="Do not write a result JSON file.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of the table report.")
    parser.add_argument("--include-adversarial", action="store_true", help="Include the adversarial starter scenario pack.")
    parser.add_argument("--crt-db", type=Path, help="Optional CRT memory SQLite DB to replay as an extra scenario.")
    parser.add_argument("--thread-id", help="Optional thread_id filter for --crt-db replay.")
    args = parser.parse_args()
    scenarios = scenario_pack(include_adversarial=args.include_adversarial)
    if args.crt_db:
        scenarios.append(scenario_from_crt_memory_db(args.crt_db, thread_id=args.thread_id))
    out = run(write_results=not args.no_write, scenarios=scenarios)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
