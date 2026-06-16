"""Meaning scaffold comparison for CRT.

This lab tests whether compact meaning fragments can carry answer behavior
without replaying the raw transcript. It is deterministic by default; Ollama or
cloud-model variants can be layered on later.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.plain_rag_eval import (
    PROBES,
    Probe,
    crt_answer,
    judge_answer,
    ollama_plain_rag_answer,
    simulated_plain_rag_answer,
)
from labs.meaning_compression_lab.run_lab import (
    OUT_DIR,
    Scenario,
    canonical_meaning_state,
    full_transcript_state,
    representation_size,
    scenario_pack,
)


CLAIM = (
    "Compressed meaning fragments should scaffold answer behavior better than "
    "raw transcript fragments on continuity, authority, contamination, and policy cases."
)


def build_meaning_scaffold(scenario: Scenario) -> dict[str, Any]:
    state = canonical_meaning_state(scenario.memories)
    fragments: list[dict[str, Any]] = []

    for slot, value in sorted(state["facts"].items()):
        fragments.append({"kind": "current_fact", "slot": slot, "value": value})
    for slot, values in sorted(state["history"].items()):
        if len(values) > 1:
            fragments.append({"kind": "history", "slot": slot, "values": values})
    for row in state["contradictions"]:
        fragments.append(
            {
                "kind": "contradiction",
                "slot": row["slot"],
                "old": row["old"],
                "new": row["new"],
            }
        )
    for slot, value in sorted(state["authority"].items()):
        fragments.append({"kind": "authority", "slot": slot, "value": value})
    for slot, value in sorted(state["policies"].items()):
        fragments.append({"kind": "policy", "slot": slot, "value": value})
    for slot, value in sorted(state["reaction_policy"].items()):
        fragments.append({"kind": "reaction", "slot": slot, "value": value})
    for slot, value in sorted(state["preferences"].items()):
        fragments.append({"kind": "preference", "slot": slot, "value": value})
    for concern in state["concerns"]:
        fragments.append({"kind": "concern", "value": concern})

    return {
        "type": "meaning_scaffold",
        "scenario": scenario.name,
        "fragments": fragments,
    }


def render_scaffold(scaffold: dict[str, Any]) -> str:
    lines = []
    for fragment in scaffold["fragments"]:
        kind = fragment["kind"]
        if kind == "current_fact":
            lines.append(f"CURRENT {fragment['slot']} = {fragment['value']}")
        elif kind == "history":
            lines.append(f"HISTORY {fragment['slot']} = {' -> '.join(fragment['values'])}")
        elif kind == "contradiction":
            lines.append(f"CONTRADICTION {fragment['slot']} {fragment['old']} -> {fragment['new']}")
        elif kind == "authority":
            lines.append(f"AUTHORITY {fragment['slot']} = {fragment['value']}")
        elif kind == "policy":
            plain = _policy_plaintext(str(fragment["slot"]), str(fragment["value"]))
            suffix = f" ({plain})" if plain else ""
            lines.append(f"POLICY {fragment['slot']} = {fragment['value']}{suffix}")
        elif kind == "reaction":
            lines.append(f"REACTION {fragment['slot']} = {fragment['value']}")
        elif kind == "preference":
            lines.append(f"PREFERENCE {fragment['slot']} = {fragment['value']}")
        elif kind == "concern":
            lines.append(f"CONCERN {fragment['value']}")
    return "\n".join(lines)


def scaffold_answer(scaffold: dict[str, Any], probe: Probe) -> str:
    facts = _fragments_by_slot(scaffold, "current_fact")
    authority = _fragments_by_slot(scaffold, "authority")
    policies = _fragments_by_slot(scaffold, "policy")
    preferences = _fragments_by_slot(scaffold, "preference")
    contradictions = [f for f in scaffold["fragments"] if f["kind"] == "contradiction"]
    history = _fragments_by_slot(scaffold, "history", value_key="values")

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
    return ""


def ollama_scaffold_answer(
    scaffold: dict[str, Any],
    probe: Probe,
    *,
    model: str,
    timeout: int,
) -> str:
    import requests

    scaffold_text = render_scaffold(scaffold)
    query_contract = _query_contract(probe)
    prompt = (
        "Answer the user using only this compressed meaning scaffold.\n"
        "Rules:\n"
        "- CURRENT means the current confirmed value.\n"
        "- HISTORY lists older values before newer values.\n"
        "- CONTRADICTION means the old value was superseded by the new value.\n"
        "- For direct current questions like 'what is', 'where do I', or 'what's my', answer only the CURRENT value. Do not mention older HISTORY or CONTRADICTION values.\n"
        "- Only mention older values when the user asks about history, previous values, or whether something changed.\n"
        "- AUTHORITY provisional/provisional_social means do not answer as confirmed unless there is also a CURRENT value.\n"
        "- POLICY forbidden with a refusal REACTION means answer no/refuse.\n"
        "- If there is no POLICY fragment, do not refuse because of policy.\n"
        "- PREFERENCE fragments describe how to answer the user.\n"
        "- Keep the answer concise.\n\n"
        f"Question contract: {query_contract}\n\n"
        f"Compressed meaning scaffold:\n{scaffold_text or '- No scaffold fragments.'}\n\n"
        f"User question: {probe.query}\n"
        "Answer:"
    )
    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 120,
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response") or "").strip()


def _fragments_by_slot(
    scaffold: dict[str, Any],
    kind: str,
    *,
    value_key: str = "value",
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fragment in scaffold["fragments"]:
        if fragment.get("kind") == kind and "slot" in fragment:
            out[str(fragment["slot"])] = fragment.get(value_key)
    return out


def _policy_plaintext(slot: str, value: str) -> str:
    if value != "forbidden":
        return ""
    if slot == "git.force_push_main":
        return "do not force push to main"
    if slot == "shell.destructive_without_confirmation":
        return "do not run destructive shell commands without explicit confirmation"
    return ""


def _query_contract(probe: Probe) -> str:
    if probe.name in {
        "current_name",
        "current_employer",
        "current_favorite_color",
        "current_project",
        "current_home_city",
    }:
        return (
            "This is a current-value question. Answer only the CURRENT value. "
            "Do not mention HISTORY, CONTRADICTION, previous, formerly, or superseded values."
        )
    if probe.name in {"locked_force_push_policy", "destructive_command_policy"}:
        return (
            "This is a policy permission question. Start with No and include the forbidden action "
            "in normal words; do not answer with only No or only a code-like label."
        )
    if probe.name in {"previous_employer", "name_correction_status"}:
        return "This is a history/change question. Use HISTORY or CONTRADICTION values."
    if probe.name in {"answer_style_preference", "current_answer_style"}:
        return "This is a preference question. Answer from the PREFERENCE fragment, not from policy."
    return "Answer from the most relevant scaffold fragments."


def score_scenario(
    scenario: Scenario,
    *,
    mode: str,
    model: str,
    timeout: int,
) -> dict[str, Any] | None:
    probe = PROBES.get(scenario.name)
    if probe is None:
        return None

    scaffold = build_meaning_scaffold(scenario)
    if mode == "deterministic":
        raw_answer = simulated_plain_rag_answer(scenario, probe)
        scaffolded = scaffold_answer(scaffold, probe)
    elif mode == "ollama":
        raw_answer = ollama_plain_rag_answer(scenario, probe, model=model, timeout=timeout)
        scaffolded = ollama_scaffold_answer(scaffold, probe, model=model, timeout=timeout)
    else:
        raise ValueError(f"unknown mode: {mode}")
    governed = crt_answer(scenario, probe)
    transcript_size = representation_size(full_transcript_state(scenario))
    scaffold_text = render_scaffold(scaffold)
    scaffold_size = len(scaffold_text.encode("utf-8"))

    return {
        "scenario": scenario.name,
        "probe": probe.name,
        "query": probe.query,
        "raw_answer": raw_answer,
        "scaffold_answer": scaffolded,
        "crt_answer": governed,
        "raw_judgment": judge_answer(raw_answer, probe),
        "scaffold_judgment": judge_answer(scaffolded, probe),
        "crt_judgment": judge_answer(governed, probe),
        "full_transcript_size_bytes": transcript_size,
        "scaffold_size_bytes": scaffold_size,
        "scaffold_compression_ratio": round(scaffold_size / transcript_size, 3) if transcript_size else 0.0,
        "scaffold": scaffold_text,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(rows)
    raw_pass = sum(1 for row in rows if row["raw_judgment"]["passed"])
    scaffold_pass = sum(1 for row in rows if row["scaffold_judgment"]["passed"])
    crt_pass = sum(1 for row in rows if row["crt_judgment"]["passed"])
    avg_ratio = (
        sum(row["scaffold_compression_ratio"] for row in rows) / case_count
        if rows
        else 0.0
    )
    return {
        "case_count": case_count,
        "raw_pass_count": raw_pass,
        "scaffold_pass_count": scaffold_pass,
        "crt_pass_count": crt_pass,
        "raw_pass_rate": round(raw_pass / case_count, 3) if rows else 0.0,
        "scaffold_pass_rate": round(scaffold_pass / case_count, 3) if rows else 0.0,
        "crt_pass_rate": round(crt_pass / case_count, 3) if rows else 0.0,
        "avg_scaffold_compression_ratio": round(avg_ratio, 3),
    }


def run(
    *,
    mode: str = "deterministic",
    model: str = "qwen2.5:7b-instruct",
    timeout: int = 90,
    write_results: bool = True,
    scenarios: list[Scenario] | None = None,
) -> dict[str, Any]:
    scenario_set = scenarios if scenarios is not None else scenario_pack()
    rows = [
        row
        for scenario in scenario_set
        if (row := score_scenario(scenario, mode=mode, model=model, timeout=timeout)) is not None
    ]
    out = {
        "lab": "meaning_scaffold_eval",
        "claim": CLAIM,
        "mode": mode,
        "model": model if mode == "ollama" else None,
        "aggregate": aggregate(rows),
        "scenarios": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"scaffold_eval_{mode}_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nMeaning Scaffold Eval")
    print("=" * 80)
    print(out["claim"])
    if out["mode"] == "ollama":
        print(f"Mode: ollama  Model: {out['model']}")
    else:
        print("Mode: deterministic")
    agg = out["aggregate"]
    print(
        f"Raw: {agg['raw_pass_count']}/{agg['case_count']} "
        f"({agg['raw_pass_rate']:.3f}) | "
        f"Scaffold: {agg['scaffold_pass_count']}/{agg['case_count']} "
        f"({agg['scaffold_pass_rate']:.3f}) | "
        f"CRT: {agg['crt_pass_count']}/{agg['case_count']} "
        f"({agg['crt_pass_rate']:.3f}) | "
        f"Avg scaffold ratio: {agg['avg_scaffold_compression_ratio']:.3f}\n"
    )
    print(f"{'scenario':<32} {'raw':>5} {'scaf':>5} {'ratio':>7}  scaffold preview")
    print("-" * 96)
    for row in out["scenarios"]:
        raw = "pass" if row["raw_judgment"]["passed"] else "fail"
        scaffold = "pass" if row["scaffold_judgment"]["passed"] else "fail"
        preview = re.sub(r"\s+", " ", row["scaffold"]).strip()[:70]
        print(f"{row['scenario']:<32} {raw:>5} {scaffold:>5} {row['scaffold_compression_ratio']:>7.3f}  {preview}")
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CRT meaning scaffold comparison.")
    parser.add_argument("--mode", choices=("deterministic", "ollama"), default="deterministic")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--include-adversarial", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(
        mode=args.mode,
        model=args.model,
        timeout=args.timeout,
        write_results=not args.no_write,
        scenarios=scenario_pack(include_adversarial=args.include_adversarial),
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
