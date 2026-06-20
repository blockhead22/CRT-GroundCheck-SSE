"""Strong temporal/metadata-aware RAG baseline.

This arm receives retrieved evidence with source, time, authority, and memory
type metadata. It does not receive CRT's compiled CURRENT/HISTORY/REACTION
state, so the executor must resolve the evidence itself.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from labs.meaning_compression_lab.evaluation_contract import build_decision_trace
from labs.meaning_compression_lab.plain_rag_eval import PROBES, Probe, judge_answer
from labs.meaning_compression_lab.run_lab import OUT_DIR, Scenario, scenario_pack


CLAIM = (
    "A governed CRT scaffold should retain an advantage over a fair RAG baseline "
    "that exposes temporal, source, authority, and provisional metadata."
)

Answerer = Callable[[str, str, int], str]
Embedder = Callable[[list[str]], Sequence[Sequence[float]]]


def retrieve_records(
    scenario: Scenario,
    query: str,
    *,
    k: int = 4,
    retrieval_mode: str = "lexical",
    embedder: Embedder | None = None,
) -> list[dict[str, Any]]:
    if retrieval_mode not in {"lexical", "embedding", "hybrid"}:
        raise ValueError(f"unsupported retrieval mode: {retrieval_mode}")

    query_tokens = _tokens(query)
    semantic_scores = [0.0] * len(scenario.memories)
    if retrieval_mode in {"embedding", "hybrid"}:
        encode = embedder or _default_embedder
        documents = [_retrieval_text(memory) for memory in scenario.memories]
        vectors = list(encode([query, *documents]))
        if len(vectors) != len(documents) + 1:
            raise ValueError("embedder returned an unexpected number of vectors")
        query_vector = vectors[0]
        semantic_scores = [
            _cosine_similarity(query_vector, vector)
            for vector in vectors[1:]
        ]

    max_timestamp = max((memory.timestamp for memory in scenario.memories), default=1)
    scored = []
    for index, memory in enumerate(scenario.memories):
        memory_tokens = _tokens(memory.text)
        overlap = len(query_tokens & memory_tokens)
        union = len(query_tokens | memory_tokens)
        lexical_score = overlap / union if union else 0.0
        slot_bonus = (
            1.0
            if memory.slot and any(token in memory.slot.lower() for token in query_tokens)
            else 0.0
        )
        recency_score = float(memory.timestamp) / max_timestamp
        semantic_score = semantic_scores[index]

        if retrieval_mode == "lexical":
            score = lexical_score + (0.20 * slot_bonus) + (0.01 * recency_score)
        elif retrieval_mode == "embedding":
            score = semantic_score + (0.01 * recency_score)
        else:
            score = (
                (0.65 * semantic_score)
                + (0.25 * lexical_score)
                + (0.08 * slot_bonus)
                + (0.02 * recency_score)
            )
        scored.append(
            (
                score,
                memory.timestamp,
                memory,
                {
                    "score": round(score, 6),
                    "semantic_score": round(semantic_score, 6),
                    "lexical_score": round(lexical_score, 6),
                    "slot_bonus": round(slot_bonus, 6),
                    "recency_score": round(recency_score, 6),
                    "retrieval_mode": retrieval_mode,
                },
            )
        )
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [
        {
            "rank": index,
            **score_detail,
            "text": memory.text,
            "timestamp": memory.timestamp,
            "source": memory.channel,
            "kind": memory.kind,
            "authority": memory.authority,
            "slot": memory.slot,
            "value": memory.value,
            "prior_value": memory.prior_value,
        }
        for index, (score, _timestamp, memory, score_detail) in enumerate(scored[:k], start=1)
        if score > 0
    ]


def render_metadata_context(records: list[dict[str, Any]]) -> str:
    blocks = []
    for row in records:
        blocks.append(
            "\n".join(
                [
                    f"MEMORY {row['rank']}",
                    f"text: {row['text']}",
                    f"retrieval_score: {row.get('score', 'unknown')}",
                    f"time: {row['timestamp']}",
                    f"source: {row['source']}",
                    f"kind: {row['kind']}",
                    f"authority: {row['authority']}",
                    f"slot: {row['slot'] or 'unknown'}",
                    f"value: {row['value'] or 'unknown'}",
                    f"prior_value: {row['prior_value'] or 'none'}",
                ]
            )
        )
    return "\n\n".join(blocks) or "No memories retrieved."


def build_prompt(records: list[dict[str, Any]], probe: Probe) -> str:
    context = render_metadata_context(records)
    return (
        "Answer using only the retrieved memories and their metadata.\n"
        "Resolution rules:\n"
        "- For current-state questions, prefer the latest confirmed or locked user fact.\n"
        "- Provisional, assistant-generated, tool-inferred, and social evidence is not confirmed truth.\n"
        "- For history questions, return the requested earlier value.\n"
        "- For policy questions, refuse actions forbidden by a locked policy.\n"
        "- Do not mention stale or prior values unless the question asks about history or change.\n"
        "- If evidence is insufficient or only provisional, withhold or say it is unconfirmed.\n"
        "- Answer naturally and do not repeat metadata field names.\n\n"
        f"Retrieved memories:\n{context}\n\n"
        f"User question: {probe.query}\n"
        "Answer:"
    )


def ollama_answer(prompt: str, model: str, timeout: int) -> str:
    import requests

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 120},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return str(response.json().get("response") or "").strip()


def score_scenario(
    scenario: Scenario,
    *,
    model: str,
    timeout: int,
    retrieval_mode: str = "hybrid",
    embedder: Embedder | None = None,
    answerer: Answerer = ollama_answer,
) -> dict[str, Any]:
    probe = PROBES[scenario.name]
    records = retrieve_records(
        scenario,
        probe.query,
        retrieval_mode=retrieval_mode,
        embedder=embedder,
    )
    prompt = build_prompt(records, probe)
    answer = answerer(prompt, model, timeout)
    judgment = judge_answer(answer, probe)
    return {
        "scenario": scenario.name,
        "probe": probe.name,
        "query": probe.query,
        "retrieval_mode": retrieval_mode,
        "retrieved_records": records,
        "prompt": prompt,
        "answer": answer,
        "judgment": judgment,
        "decision_trace": build_decision_trace(
            scenario=scenario.name,
            arm="temporal_metadata_rag",
            query=probe.query,
            retrieved_evidence=records,
            state_transformation=None,
            selected_rule="model_resolves_temporal_metadata",
            supplied_context=render_metadata_context(records),
            answer=answer,
            judgment=judgment,
        ),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    semantic = sum(row["judgment"]["semantic_passed"] for row in rows)
    contract = sum(row["judgment"]["contract_passed"] for row in rows)
    severe = sum(row["decision_trace"]["severity"] == "severe_failure" for row in rows)
    return {
        "case_count": count,
        "semantic_pass_count": semantic,
        "contract_pass_count": contract,
        "severe_failure_count": severe,
        "semantic_pass_rate": round(semantic / count, 3) if count else 0.0,
        "contract_pass_rate": round(contract / count, 3) if count else 0.0,
    }


def run(
    *,
    model: str = "qwen2.5:7b-instruct",
    timeout: int = 90,
    include_adversarial: bool = True,
    include_hardening: bool = True,
    write_results: bool = True,
    scenarios: list[Scenario] | None = None,
    retrieval_mode: str = "hybrid",
    embedder: Embedder | None = None,
    answerer: Answerer = ollama_answer,
) -> dict[str, Any]:
    scenario_set = scenarios or scenario_pack(
        include_adversarial=include_adversarial,
        include_hardening=include_hardening,
    )
    rows = [
        score_scenario(
            scenario,
            model=model,
            timeout=timeout,
            retrieval_mode=retrieval_mode,
            embedder=embedder,
            answerer=answerer,
        )
        for scenario in scenario_set
        if scenario.name in PROBES
    ]
    out = {
        "lab": "temporal_metadata_rag_eval",
        "claim": CLAIM,
        "model": model,
        "retrieval_mode": retrieval_mode,
        "include_adversarial": include_adversarial,
        "include_hardening": include_hardening,
        "aggregate": aggregate(rows),
        "scenarios": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"temporal_metadata_rag_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def print_report(out: dict[str, Any]) -> None:
    aggregate_row = out["aggregate"]
    print("\nTemporal Metadata RAG Eval")
    print("=" * 80)
    print(f"Model: {out['model']}")
    print(f"Retrieval: {out.get('retrieval_mode', 'lexical')}")
    print(
        f"Semantic: {aggregate_row['semantic_pass_count']}/{aggregate_row['case_count']} | "
        f"Contract: {aggregate_row['contract_pass_count']}/{aggregate_row['case_count']} | "
        f"Severe failures: {aggregate_row['severe_failure_count']}"
    )
    print(f"\n{'scenario':<34} {'severity':<16} answer")
    print("-" * 96)
    for row in out["scenarios"]:
        answer = re.sub(r"\s+", " ", row["answer"]).strip()
        print(f"{row['scenario']:<34} {row['decision_trace']['severity']:<16} {answer[:44]}")
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


def _retrieval_text(memory: Any) -> str:
    fields = [
        memory.text,
        f"slot {memory.slot}" if memory.slot else "",
        f"value {memory.value}" if memory.value else "",
        f"prior value {memory.prior_value}" if memory.prior_value else "",
    ]
    return " | ".join(field for field in fields if field)


def _default_embedder(texts: list[str]) -> Sequence[Sequence[float]]:
    from personal_agent.embeddings import get_encoder

    return get_encoder().encode_batch(texts)


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding vectors must have matching dimensions")
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    norm_a = math.sqrt(sum(float(x) * float(x) for x in a))
    norm_b = math.sqrt(sum(float(y) * float(y) for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the strong temporal metadata RAG baseline.")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-adversarial", action="store_true")
    parser.add_argument("--no-hardening", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--retrieval-mode",
        choices=("lexical", "embedding", "hybrid"),
        default="hybrid",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run(
        model=args.model,
        timeout=args.timeout,
        include_adversarial=not args.no_adversarial,
        include_hardening=not args.no_hardening,
        write_results=not args.no_write,
        retrieval_mode=args.retrieval_mode,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
