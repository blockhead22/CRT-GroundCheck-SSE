"""Compare local-router governance against replay-pack RAG baselines."""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from labs.meaning_compression_lab.local_router_cli import (
    _final_answer_policy_for_task,
    _output_scaffold_for_task,
    build_case,
    build_trace,
    judge_trace,
)
from labs.meaning_compression_lab.local_router_eval import route_for_task, run_route
from labs.meaning_compression_lab.run_lab import OUT_DIR
from labs.meaning_compression_lab.spiral_synthesis_eval import call_ollama, judge_answer, raw_prompt


DEFAULT_PACK = Path("labs/meaning_compression_lab/replay_packs/local_router_replay_curated_v1.json")
DEFAULT_MODES = ("raw", "plain_rag", "scaffolded_rag", "governed")

Runner = Callable[[str, str, int], str]


@dataclass(frozen=True)
class RagChunk:
    case_id: str
    task_type: str
    kind: str
    text: str
    source: dict[str, Any]


def run_rag_suite(
    *,
    pack_path: Path = DEFAULT_PACK,
    timeout: int = 300,
    skip_cases: int = 0,
    max_cases: int | None = None,
    case_ids: tuple[str, ...] = (),
    modes: tuple[str, ...] = DEFAULT_MODES,
    k: int = 5,
    write_results: bool = True,
    runner: Runner | None = None,
) -> dict[str, Any]:
    pack = json.loads(pack_path.read_text(encoding="utf-8-sig"))
    corpus = build_corpus(pack)
    selected = list(pack.get("cases") or [])[skip_cases:]
    if case_ids:
        wanted = set(case_ids)
        selected = [item for item in selected if item.get("id") in wanted]
    cases = selected[:max_cases] if max_cases else selected
    run_model = runner or call_ollama
    rows = [
        _run_case(
            item,
            corpus=corpus,
            timeout=timeout,
            modes=modes,
            k=k,
            runner=run_model,
        )
        for item in cases
    ]
    out = {
        "lab": "local_router_rag_suite",
        "pack": pack.get("pack"),
        "pack_path": str(pack_path),
        "case_count": len(rows),
        "skip_cases": skip_cases,
        "case_ids": list(case_ids),
        "modes": list(modes),
        "retrieval": {
            "corpus_chunk_count": len(corpus),
            "k": k,
            "method": "lexical_overlap_with_task_and_recency_tiebreak",
            "corpus_kinds": dict(sorted(Counter(chunk.kind for chunk in corpus).items())),
        },
        "aggregate": _aggregate(rows, modes),
        "rows": rows,
    }
    if write_results:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"local_router_rag_suite_{int(time.time())}.json"
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["result_path"] = str(path)
    return out


def build_corpus(pack: dict[str, Any]) -> list[RagChunk]:
    chunks: list[RagChunk] = []
    for item in pack.get("cases") or []:
        source = item.get("source") or {}
        case_id = str(item.get("id") or "")
        task_type = str(item.get("task_type") or "unknown")
        prompt = str(item.get("prompt") or "").strip()
        reference = str(item.get("reference_response_excerpt") or "").strip()
        anchors = ", ".join(str(value) for value in item.get("expected_receipts") or [])
        concepts = ", ".join(str(value) for value in item.get("required_concepts") or [])
        if prompt:
            chunks.append(RagChunk(case_id, task_type, "user_prompt", prompt, source))
        if reference:
            chunks.extend(
                RagChunk(case_id, task_type, "reference_response", text, source)
                for text in _split_chunks(reference)
            )
        if anchors or concepts:
            chunks.append(
                RagChunk(
                    case_id=case_id,
                    task_type=task_type,
                    kind="case_requirements",
                    text=f"Expected receipts: {anchors}. Required concepts: {concepts}.",
                    source=source,
                )
            )
    return chunks


def retrieve_chunks(
    *,
    query: str,
    task_type: str,
    corpus: list[RagChunk],
    k: int = 5,
) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    scored = []
    for index, chunk in enumerate(corpus):
        text_tokens = _tokens(chunk.text)
        if not text_tokens:
            continue
        overlap = len(query_tokens & text_tokens)
        union = len(query_tokens | text_tokens)
        lexical = overlap / union if union else 0.0
        phrase_bonus = _phrase_overlap(query, chunk.text)
        task_bonus = 0.06 if chunk.task_type == task_type else 0.0
        kind_bonus = {"reference_response": 0.04, "case_requirements": 0.02, "user_prompt": 0.0}.get(chunk.kind, 0.0)
        score = lexical + phrase_bonus + task_bonus + kind_bonus + (index * 0.000001)
        if score <= 0:
            continue
        scored.append((score, index, chunk, lexical, phrase_bonus, task_bonus, kind_bonus))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [
        {
            "rank": rank,
            "score": round(score, 6),
            "lexical_score": round(lexical, 6),
            "phrase_bonus": round(phrase_bonus, 6),
            "task_bonus": round(task_bonus, 6),
            "kind_bonus": round(kind_bonus, 6),
            "case_id": chunk.case_id,
            "task_type": chunk.task_type,
            "kind": chunk.kind,
            "text": chunk.text,
            "source": chunk.source,
        }
        for rank, (score, _index, chunk, lexical, phrase_bonus, task_bonus, kind_bonus) in enumerate(scored[:k], start=1)
    ]


def plain_rag_prompt(query: str, records: list[dict[str, Any]]) -> str:
    return (
        "RAG BASELINE: answer the user using only the retrieved context.\n"
        "Do not use hidden memory, hidden policy, or internal Aether state.\n"
        "If the context is thin, give the best bounded answer from the retrieved text.\n\n"
        f"Retrieved context:\n{_render_records(records)}\n\n"
        f"User question: {query}\n\n"
        "Answer:"
    )


def scaffolded_rag_prompt(case: Any, records: list[dict[str, Any]]) -> str:
    task_type = str(case.spine.get("task_type") or "unknown")
    policy = _final_answer_policy_for_task(task_type)
    policy_text = f"\nFinal-answer policy:\n{json.dumps(policy, indent=2)}\n" if policy else ""
    return (
        "SCAFFOLDED RAG BASELINE: answer from retrieved context, not hidden state.\n"
        "Use the output scaffold and stay bounded. This is retrieval plus formatting, not Mirus belief state.\n\n"
        f"Task type: {task_type}\n"
        f"Output scaffold: {', '.join(_output_scaffold_for_task(task_type))}\n"
        f"Expected evidence anchors: {', '.join(case.expected_receipts)}\n"
        f"Required concepts: {', '.join(case.required_concepts)}\n"
        f"Forbidden unless explicitly negated: {', '.join(case.forbidden_claims)}\n"
        f"{policy_text}\n"
        f"Retrieved context:\n{_render_records(records)}\n\n"
        f"User question: {case.query}\n\n"
        "Answer:"
    )


def _run_case(
    item: dict[str, Any],
    *,
    corpus: list[RagChunk],
    timeout: int,
    modes: tuple[str, ...],
    k: int,
    runner: Runner,
) -> dict[str, Any]:
    case = build_case(
        str(item.get("prompt") or ""),
        task_type=str(item.get("task_type") or ""),
        anchors=tuple(item.get("expected_receipts") or ()),
        concepts=tuple(item.get("required_concepts") or ()),
    )
    route = route_for_task(case.spine["task_type"])
    records = retrieve_chunks(query=case.query, task_type=case.spine["task_type"], corpus=corpus, k=k)
    results: dict[str, Any] = {}
    if "raw" in modes:
        answer = runner(raw_prompt(case), route.model, timeout)
        results["raw"] = _answer_row(answer, case)
    if "plain_rag" in modes:
        answer = runner(plain_rag_prompt(case.query, records), route.model, timeout)
        results["plain_rag"] = _answer_row(answer, case)
    if "scaffolded_rag" in modes:
        answer = runner(scaffolded_rag_prompt(case, records), route.model, timeout)
        results["scaffolded_rag"] = _answer_row(answer, case)
    if "governed" in modes:
        routed = run_route(case, timeout=timeout, runner=runner)
        trace = build_trace(case, routed, source=f"local_router_rag_suite:{item.get('id')}:governed")
        results["governed"] = {
            "answer": routed["answer"],
            "judgment": routed["judgment"],
            "repaired": routed["repaired"],
            "fallback_used": routed["fallback_used"],
            "trace_judgment": judge_trace(trace, routed["judgment"]),
        }
    return {
        "id": item.get("id"),
        "task_type": item.get("task_type"),
        "prompt": item.get("prompt"),
        "route": route.to_dict(),
        "retrieval": {
            "records": records,
            "receipt_coverage": _coverage(records, item.get("expected_receipts") or []),
            "concept_coverage": _coverage(records, item.get("required_concepts") or []),
        },
        "modes": results,
    }


def _answer_row(answer: str, case: Any) -> dict[str, Any]:
    return {
        "answer": answer,
        "judgment": judge_answer(answer, case),
        "repaired": False,
        "fallback_used": False,
        "trace_judgment": None,
    }


def _aggregate(rows: list[dict[str, Any]], modes: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "retrieval": {
            "avg_receipt_coverage": _avg(row["retrieval"]["receipt_coverage"]["coverage"] for row in rows),
            "avg_concept_coverage": _avg(row["retrieval"]["concept_coverage"]["coverage"] for row in rows),
        }
    }
    for mode in modes:
        judgments = [row["modes"][mode]["judgment"] for row in rows if mode in row["modes"]]
        traces = [row["modes"][mode].get("trace_judgment") for row in rows if mode in row["modes"]]
        trace_rows = [trace for trace in traces if trace is not None]
        failed_rows = [
            row for row in rows
            if mode in row["modes"]
            and (
                not row["modes"][mode]["judgment"].get("passed")
                or (
                    row["modes"][mode].get("trace_judgment")
                    and not row["modes"][mode]["trace_judgment"].get("passed")
                )
            )
        ]
        by_task_type = Counter(str(row.get("task_type") or "unknown") for row in failed_rows)
        out[mode] = {
            "answer_pass_count": sum(1 for judgment in judgments if judgment.get("passed")),
            "answer_avg_score": _avg(float(judgment.get("score") or 0) for judgment in judgments),
            "trace_pass_count": sum(1 for trace in trace_rows if trace.get("passed")),
            "trace_avg_score": _avg(float(trace.get("score") or 0) for trace in trace_rows) if trace_rows else None,
            "repair_count": sum(1 for row in rows if mode in row["modes"] and row["modes"][mode].get("repaired")),
            "fallback_count": sum(1 for row in rows if mode in row["modes"] and row["modes"][mode].get("fallback_used")),
            "failure_count": len(failed_rows),
            "failures_by_task_type": dict(sorted(by_task_type.items())),
        }
    return out


def print_report(out: dict[str, Any]) -> None:
    print("\nLocal Router RAG Suite")
    print("=" * 80)
    print(f"Pack: {out['pack']} | Cases: {out['case_count']} | k={out['retrieval']['k']}")
    retrieval = out["aggregate"]["retrieval"]
    print(
        f"Retrieval coverage: receipts {retrieval['avg_receipt_coverage']:.3f} | "
        f"concepts {retrieval['avg_concept_coverage']:.3f}"
    )
    for mode in out["modes"]:
        aggregate = out["aggregate"][mode]
        print(
            f"{mode}: answer {aggregate['answer_pass_count']}/{out['case_count']} "
            f"avg {aggregate['answer_avg_score']:.3f} "
            f"trace {aggregate['trace_pass_count']}/{out['case_count']} "
            f"repairs {aggregate['repair_count']} fallbacks {aggregate['fallback_count']} "
            f"failures {aggregate['failure_count']}"
        )
    if "result_path" in out:
        print(f"Wrote {out['result_path']}")


def _render_records(records: list[dict[str, Any]]) -> str:
    if not records:
        return "No retrieved context."
    rendered = []
    for row in records:
        rendered.append(
            "\n".join(
                [
                    f"CONTEXT {row['rank']}",
                    f"case_id: {row['case_id']}",
                    f"task_type: {row['task_type']}",
                    f"kind: {row['kind']}",
                    f"score: {row['score']}",
                    f"text: {row['text']}",
                ]
            )
        )
    return "\n\n".join(rendered)


def _split_chunks(text: str, *, max_words: int = 120) -> list[str]:
    words = re.findall(r"\S+", text)
    chunks = []
    for start in range(0, len(words), max_words):
        chunk = " ".join(words[start : start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "that", "this", "with", "from", "into", "would", "could",
        "should", "about", "have", "what", "when", "where", "your", "you", "for",
        "are", "but", "not", "all", "how", "why", "can", "maybe", "just",
    }
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9_.-]+", str(text).lower())
        if token not in stop and len(token) > 2
    }


def _phrase_overlap(query: str, text: str) -> float:
    query_terms = [term for term in re.findall(r"[a-z0-9][a-z0-9_.-]+", query.lower()) if len(term) > 3]
    text_lower = text.lower()
    hits = sum(1 for term in query_terms if term in text_lower)
    return min(0.12, hits * 0.015)


def _coverage(records: list[dict[str, Any]], expected: list[str]) -> dict[str, Any]:
    context = " ".join(str(row.get("text") or "") for row in records).lower()
    hits = [item for item in expected if str(item).lower() in context]
    return {
        "hits": hits,
        "missing": [item for item in expected if item not in hits],
        "coverage": round(len(hits) / max(1, len(expected)), 3),
    }


def _avg(values: Any) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(math.fsum(float(item) for item in items) / len(items), 3)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run replay-pack RAG baselines against governed local routing.")
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--skip-cases", type=int, default=0)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--mode", action="append", choices=DEFAULT_MODES)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = run_rag_suite(
        pack_path=args.pack,
        timeout=args.timeout,
        skip_cases=args.skip_cases,
        max_cases=args.max_cases,
        case_ids=tuple(args.case_id or ()),
        modes=tuple(args.mode or DEFAULT_MODES),
        k=args.k,
        write_results=not args.no_write,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_report(out)


if __name__ == "__main__":
    main()
