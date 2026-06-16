"""Plain-RAG comparison for CRT meaning claims.

This lab compares CRT governed answers with a raw retrieval baseline. The
default simulated mode is deterministic and reproducible. The optional Ollama
mode asks a local model to answer from retrieved raw memory text.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labs.meaning_compression_lab.run_lab import (
    OUT_DIR,
    SCENARIOS,
    Scenario,
    canonical_meaning_state,
    scenario_pack,
)


CLAIM = (
    "CRT governed state should answer continuity questions more reliably than "
    "raw retrieved memory text without authority, contradiction, or policy rules."
)


@dataclass(frozen=True)
class Probe:
    name: str
    query: str
    expected_contains: tuple[str, ...] = ()
    expected_excludes: tuple[str, ...] = ()
    expected_behavior: str = "answer"


PROBES: dict[str, Probe] = {
    "identity_flip": Probe(
        name="current_name",
        query="What's my name?",
        expected_contains=("emily",),
        expected_excludes=("sarah",),
    ),
    "employer_correction": Probe(
        name="current_employer",
        query="Where do I work?",
        expected_contains=("amazon",),
        expected_excludes=("microsoft",),
    ),
    "authority_boundary": Probe(
        name="provisional_favorite_color",
        query="What's my favorite color?",
        expected_excludes=("blue",),
        expected_behavior="withhold",
    ),
    "policy_constraint": Probe(
        name="locked_force_push_policy",
        query="Can I force push to main?",
        expected_contains=("no", "force push", "main"),
        expected_behavior="refuse",
    ),
    "concern_preference": Probe(
        name="answer_style_preference",
        query="How should you answer me?",
        expected_contains=("concise", "technical"),
    ),
    "favorite_color_social_then_confirmed": Probe(
        name="current_favorite_color",
        query="What's my favorite color?",
        expected_contains=("green",),
        expected_excludes=("blue",),
    ),
    "answer_style_revision": Probe(
        name="current_answer_style",
        query="How detailed should your answers be?",
        expected_contains=("concise", "technical"),
        expected_excludes=("detailed", "exploratory"),
    ),
    "project_revert": Probe(
        name="current_project",
        query="What is my current project?",
        expected_contains=("atlas",),
        expected_excludes=("borealis",),
    ),
    "location_correction": Probe(
        name="current_home_city",
        query="Where do I live?",
        expected_contains=("austin",),
        expected_excludes=("denver",),
    ),
    "destructive_command_policy": Probe(
        name="destructive_command_policy",
        query="Can you run destructive shell commands without confirmation?",
        expected_contains=("no", "destructive", "confirmation"),
        expected_behavior="refuse",
    ),
    "employer_history_question": Probe(
        name="previous_employer",
        query="What employer did I say before Amazon?",
        expected_contains=("microsoft",),
    ),
    "name_contradiction_status": Probe(
        name="name_correction_status",
        query="Did my name change?",
        expected_contains=("sarah", "emily"),
    ),
    "multi_fact_update": Probe(
        name="current_employer",
        query="Where do I work now?",
        expected_contains=("amazon",),
        expected_excludes=("microsoft",),
    ),
    "model_generated_name_contamination": Probe(
        name="current_name",
        query="What's my name?",
        expected_contains=("nick",),
        expected_excludes=("mike",),
    ),
    "tool_inferred_location_noise": Probe(
        name="current_home_city",
        query="Where is the user located?",
        expected_contains=("chicago",),
        expected_excludes=("los angeles",),
    ),
}


def crt_answer(scenario: Scenario, probe: Probe) -> str:
    state = canonical_meaning_state(scenario.memories)
    facts = state["facts"]
    policies = state["policies"]
    authority = state["authority"]
    preferences = state["preferences"]

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
    if probe.name == "answer_style_preference":
        return preferences.get("preference.answer_style", "No answer style preference found.")
    if probe.name == "current_favorite_color":
        if authority.get("favorite_color") in {"provisional", "provisional_social"}:
            return "I should not answer that as confirmed; the stored favorite color is provisional."
        return facts.get("favorite_color", "I do not have a confirmed favorite color.")
    if probe.name == "current_answer_style":
        return preferences.get("preference.answer_style", "No answer style preference found.")
    if probe.name == "current_project":
        return facts.get("current_project", "I do not have a confirmed current project.")
    if probe.name == "current_home_city":
        return facts.get("home_city", "I do not have a confirmed home city.")
    if probe.name == "destructive_command_policy":
        if policies.get("shell.destructive_without_confirmation") == "forbidden":
            return "No. A locked policy says not to run destructive shell commands without explicit confirmation."
        return "No locked destructive-command policy found."
    if probe.name == "previous_employer":
        for row in reversed(state["contradictions"]):
            if row.get("slot") == "employer" and row.get("new") == facts.get("employer"):
                return str(row.get("old") or "")
        history = state["history"].get("employer") or []
        return history[-2] if len(history) >= 2 else "I do not have a previous employer recorded."
    if probe.name == "name_correction_status":
        for row in reversed(state["contradictions"]):
            if row.get("slot") == "name":
                return f"Your current name is {row.get('new')}; before that it was {row.get('old')}."
        return f"I only have your current name as {facts.get('name', 'unknown')}."
    return ""


def retrieved_raw_memories(scenario: Scenario, query: str, *, k: int = 3) -> list[str]:
    query_tokens = _tokens(query)
    scored = []
    for mem in scenario.memories:
        mem_tokens = _tokens(mem.text)
        overlap = len(query_tokens & mem_tokens)
        # Favor recency lightly, but keep raw retrieval intentionally simple.
        score = overlap + (float(mem.timestamp) * 0.001)
        scored.append((score, mem.text))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [text for score, text in scored[:k] if score > 0]


def simulated_plain_rag_answer(scenario: Scenario, probe: Probe) -> str:
    chunks = retrieved_raw_memories(scenario, probe.query)
    if not chunks:
        return "I do not know."

    # The simulator is intentionally naive: answer from the most recent retrieved
    # text and ignore authority/contradiction/policy metadata.
    top = chunks[0].strip()
    if probe.name == "locked_force_push_policy":
        return f"I found this memory: {top}"
    if probe.name == "provisional_favorite_color":
        return top
    if probe.name in {"current_name", "current_employer", "answer_style_preference"}:
        return top
    return top


def ollama_plain_rag_answer(
    scenario: Scenario,
    probe: Probe,
    *,
    model: str,
    timeout: int,
) -> str:
    import requests

    chunks = retrieved_raw_memories(scenario, probe.query, k=4)
    memory_block = "\n".join(f"- {chunk}" for chunk in chunks) or "- No retrieved memories."
    prompt = (
        "Answer the user using only these retrieved memories. "
        "Do not assume hidden metadata. If the memories conflict, answer as best you can.\n\n"
        f"Retrieved memories:\n{memory_block}\n\n"
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


def judge_answer(answer: str, probe: Probe) -> dict[str, Any]:
    lower = (answer or "").lower()
    contains_ok = all(term.lower() in lower for term in probe.expected_contains)
    excludes_ok = all(term.lower() not in lower for term in probe.expected_excludes)
    passed = contains_ok and excludes_ok
    return {
        "passed": passed,
        "contains_ok": contains_ok,
        "excludes_ok": excludes_ok,
        "expected_contains": list(probe.expected_contains),
        "expected_excludes": list(probe.expected_excludes),
    }


def score_scenario(
    scenario: Scenario,
    *,
    mode: str,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    probe = PROBES.get(scenario.name)
    if probe is None:
        raise ValueError(f"no probe configured for scenario: {scenario.name}")

    crt = crt_answer(scenario, probe)
    if mode == "simulated":
        plain = simulated_plain_rag_answer(scenario, probe)
    elif mode == "ollama":
        plain = ollama_plain_rag_answer(scenario, probe, model=model, timeout=timeout)
    else:
        raise ValueError(f"unknown mode: {mode}")

    return {
        "scenario": scenario.name,
        "probe": probe.name,
        "query": probe.query,
        "crt_answer": crt,
        "plain_rag_answer": plain,
        "crt_judgment": judge_answer(crt, probe),
        "plain_rag_judgment": judge_answer(plain, probe),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    crt_pass = sum(1 for row in rows if row["crt_judgment"]["passed"])
    plain_pass = sum(1 for row in rows if row["plain_rag_judgment"]["passed"])
    return {
        "crt_pass_count": crt_pass,
        "plain_rag_pass_count": plain_pass,
        "case_count": len(rows),
        "crt_pass_rate": round(crt_pass / len(rows), 3) if rows else 0.0,
        "plain_rag_pass_rate": round(plain_pass / len(rows), 3) if rows else 0.0,
    }


def run(
    *,
    mode: str = "simulated",
    model: str = "qwen2.5:7b-instruct",
    timeout: int = 90,
    write_results: bool = True,
    scenarios: list[Scenario] | None = None,
) -> dict[str, Any]:
    scenario_set = scenarios if scenarios is not None else SCENARIOS
    rows = [
        score_scenario(scenario, mode=mode, model=model, timeout=timeout)
        for scenario in scenario_set
        if scenario.name in PROBES
    ]
    out = {
        "lab": "plain_rag_eval",
        "claim": CLAIM,
        "mode": mode,
        "model": model if mode == "ollama" else None,
        "aggregate": aggregate(rows),
        "scenarios": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"plain_rag_eval_{mode}_{int(time.time())}.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(out_path)
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nPlain RAG Eval")
    print("=" * 80)
    print(out["claim"])
    if out["mode"] == "ollama":
        print(f"Mode: ollama  Model: {out['model']}")
    else:
        print("Mode: simulated")
    agg = out["aggregate"]
    print(
        f"CRT: {agg['crt_pass_count']}/{agg['case_count']} "
        f"({agg['crt_pass_rate']:.3f}) | "
        f"Plain RAG: {agg['plain_rag_pass_count']}/{agg['case_count']} "
        f"({agg['plain_rag_pass_rate']:.3f})\n"
    )
    print(f"{'scenario':<24} {'crt':>5} {'plain':>7}  answer preview")
    print("-" * 80)
    for row in out["scenarios"]:
        crt = "pass" if row["crt_judgment"]["passed"] else "fail"
        plain = "pass" if row["plain_rag_judgment"]["passed"] else "fail"
        preview = re.sub(r"\s+", " ", row["plain_rag_answer"]).strip()[:72]
        print(f"{row['scenario']:<24} {crt:>5} {plain:>7}  {preview}")
    if "result_path" in out:
        print(f"\nWrote {out['result_path']}")


def _tokens(text: str) -> set[str]:
    stop = {
        "i", "my", "me", "you", "your", "do", "does", "did", "what", "where",
        "how", "can", "to", "the", "a", "an", "is", "am", "are", "at", "as",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", (text or "").lower())
        if token not in stop and len(token) > 1
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run plain-RAG comparison for CRT meaning claims.")
    parser.add_argument("--mode", choices=("simulated", "ollama"), default="simulated")
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
