#!/usr/bin/env python
"""Train or refresh DNNT tokenizer assets from accumulated corpus data."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List

from .data_extractor import DataExtractor, TrainingExample
from .model import SimpleTokenizer
from .tokenizer_bpe import create_tokenizer


def _load_examples_jsonl(path: Path) -> List[TrainingExample]:
    if not path.exists():
        return []
    out: List[TrainingExample] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                ex = TrainingExample(
                    query=str(data.get("query") or "").strip(),
                    facts=list(data.get("facts") or []),
                    thinking=str(data.get("thinking") or "").strip(),
                    response=str(data.get("response") or "").strip(),
                    confidence=float(data.get("confidence") or 0.7),
                    thread_id=str(data.get("thread_id") or ""),
                )
                if ex.query:
                    out.append(ex)
            except Exception:
                continue
    return out


def _load_collapse_trail_texts(path: Path, limit: int = 20000) -> List[str]:
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT query_text, answer_text, payload_json
            FROM collapse_trails
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()

    texts: List[str] = []
    for row in rows:
        q = str(row["query_text"] or "").strip()
        a = str(row["answer_text"] or "").strip()
        if q:
            texts.append(q)
        if a:
            texts.append(a)
        payload_raw = str(row["payload_json"] or "").strip()
        if payload_raw:
            try:
                payload = json.loads(payload_raw)
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                thinking = str(payload.get("thinking") or payload.get("analysis") or "").strip()
                if thinking:
                    texts.append(thinking)
    return texts


def collect_tokenizer_corpus(
    *,
    include_data_extractor: bool = True,
    include_collected_jsonl: bool = True,
    include_collapse_trails: bool = True,
    collected_jsonl_path: str = "data/dnnt_collected_training_data.jsonl",
    collapse_trails_db_path: str = "personal_agent/crt_collapse_trails.db",
) -> List[str]:
    texts: List[str] = []

    if include_data_extractor:
        extractor = DataExtractor()
        for ex in extractor.extract_all():
            texts.append(ex.to_training_format())

    if include_collected_jsonl:
        for ex in _load_examples_jsonl(Path(collected_jsonl_path)):
            texts.append(ex.to_training_format())

    if include_collapse_trails:
        texts.extend(_load_collapse_trail_texts(Path(collapse_trails_db_path)))

    deduped: List[str] = []
    seen: set[str] = set()
    for text in texts:
        item = str(text or "").strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def train_and_save_tokenizer(
    *,
    output_dir: str,
    backend: str,
    vocab_size: int,
    corpus_texts: Iterable[str],
    allow_fallback: bool = True,
):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = create_tokenizer(
        backend=backend,
        vocab_size=vocab_size,
        texts=list(corpus_texts),
        model_dir=str(out_dir / "tokenizer_assets"),
        allow_fallback=allow_fallback,
    )

    if isinstance(tokenizer, SimpleTokenizer):
        for text in corpus_texts:
            tokenizer.add_tokens_from_text(str(text or ""))

    tokenizer_path = out_dir / "tokenizer.json"
    tokenizer.save(str(tokenizer_path))
    return tokenizer, tokenizer_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train DNNT tokenizer assets")
    parser.add_argument("--output-dir", type=str, default="models/dnnt/model", help="Output tokenizer directory")
    parser.add_argument(
        "--backend",
        type=str,
        default="sentencepiece",
        choices=["simple", "sentencepiece"],
        help="Tokenizer backend",
    )
    parser.add_argument("--vocab-size", type=int, default=8000, help="Target tokenizer vocab size")
    parser.add_argument(
        "--collected-jsonl-path",
        type=str,
        default="data/dnnt_collected_training_data.jsonl",
        help="Path to trust-gated collected LLM outputs",
    )
    parser.add_argument(
        "--collapse-trails-db-path",
        type=str,
        default="personal_agent/crt_collapse_trails.db",
        help="Path to collapse trails DB",
    )
    parser.add_argument("--no-data-extractor", action="store_true", help="Skip DataExtractor databases")
    parser.add_argument("--no-collected-jsonl", action="store_true", help="Skip collected JSONL corpus")
    parser.add_argument("--no-collapse-trails", action="store_true", help="Skip collapse trails corpus")
    parser.add_argument(
        "--strict-backend",
        action="store_true",
        help="Fail if requested backend cannot be initialized instead of falling back",
    )
    args = parser.parse_args()

    corpus = collect_tokenizer_corpus(
        include_data_extractor=not args.no_data_extractor,
        include_collected_jsonl=not args.no_collected_jsonl,
        include_collapse_trails=not args.no_collapse_trails,
        collected_jsonl_path=args.collected_jsonl_path,
        collapse_trails_db_path=args.collapse_trails_db_path,
    )
    print(f"[Tokenizer] Collected {len(corpus)} unique corpus texts")

    tokenizer, path = train_and_save_tokenizer(
        output_dir=args.output_dir,
        backend=args.backend,
        vocab_size=args.vocab_size,
        corpus_texts=corpus,
        allow_fallback=not args.strict_backend,
    )
    print(f"[Tokenizer] Saved tokenizer to: {path}")
    print(f"[Tokenizer] Backend: {type(tokenizer).__name__}")
    print(f"[Tokenizer] Vocab size: {getattr(tokenizer, 'vocab_size', 'unknown')}")


if __name__ == "__main__":
    main()

