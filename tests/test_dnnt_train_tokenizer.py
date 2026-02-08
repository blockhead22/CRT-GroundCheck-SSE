from __future__ import annotations

import json
from pathlib import Path

import pytest

from personal_agent.dnnt.model import SimpleTokenizer
from personal_agent.dnnt.tokenizer_bpe import load_tokenizer
from personal_agent.dnnt.train_tokenizer import (
    collect_tokenizer_corpus,
    train_and_save_tokenizer,
)


def test_collect_tokenizer_corpus_from_collected_jsonl_only(tmp_path: Path) -> None:
    collected = tmp_path / "collected.jsonl"
    rows = [
        {
            "query": "What is my name?",
            "facts": ["name=Nick (0.95)"],
            "thinking": "Use trusted slot memory.",
            "response": "Your name is Nick.",
        },
        {
            "query": "What is my name?",
            "facts": ["name=Nick (0.95)"],
            "thinking": "Use trusted slot memory.",
            "response": "Your name is Nick.",
        },
    ]
    with open(collected, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    corpus = collect_tokenizer_corpus(
        include_data_extractor=False,
        include_collected_jsonl=True,
        include_collapse_trails=False,
        collected_jsonl_path=str(collected),
    )
    assert len(corpus) == 1
    assert "<query>What is my name?</query>" in corpus[0]


def test_train_and_save_tokenizer_simple_backend(tmp_path: Path) -> None:
    output_dir = tmp_path / "tok_out"
    corpus = [
        "<query>Hello</query><response>World</response>",
        "<query>What is 2 + 2?</query><response>4</response>",
    ]
    tokenizer, tok_path = train_and_save_tokenizer(
        output_dir=str(output_dir),
        backend="simple",
        vocab_size=512,
        corpus_texts=corpus,
        allow_fallback=True,
    )
    assert isinstance(tokenizer, SimpleTokenizer)
    assert tok_path.exists()

    loaded = load_tokenizer(str(tok_path), allow_fallback=True)
    assert isinstance(loaded, SimpleTokenizer)
    assert loaded.vocab_size >= 512


def test_train_and_save_tokenizer_sentencepiece_strict_raises_without_dependency(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        train_and_save_tokenizer(
            output_dir=str(tmp_path / "tok_out"),
            backend="sentencepiece",
            vocab_size=1024,
            corpus_texts=["hello world"],
            allow_fallback=False,
        )

