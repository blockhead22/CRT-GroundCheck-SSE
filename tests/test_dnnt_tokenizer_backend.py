from __future__ import annotations

from pathlib import Path
import json

from personal_agent.dnnt.model import SimpleTokenizer
from personal_agent.dnnt.tokenizer_bpe import create_tokenizer, load_tokenizer


def test_create_tokenizer_simple_backend() -> None:
    tokenizer = create_tokenizer(backend="simple", vocab_size=1024)
    assert isinstance(tokenizer, SimpleTokenizer)
    assert tokenizer.vocab_size >= 1024


def test_create_tokenizer_sentencepiece_fallback_without_assets(tmp_path: Path) -> None:
    tokenizer = create_tokenizer(
        backend="sentencepiece",
        vocab_size=1024,
        texts=None,
        model_dir=str(tmp_path / "missing_assets"),
        allow_fallback=True,
    )
    assert isinstance(tokenizer, SimpleTokenizer)


def test_load_tokenizer_simple_payload_roundtrip(tmp_path: Path) -> None:
    tok_path = tmp_path / "tokenizer.json"
    original = SimpleTokenizer(vocab_size=512)
    original.save(str(tok_path))

    loaded = load_tokenizer(str(tok_path), allow_fallback=True)
    assert isinstance(loaded, SimpleTokenizer)
    sample = "<query>Hello</query><response>World</response>"
    assert loaded.decode(loaded.encode(sample)) == original.decode(original.encode(sample))


def test_load_tokenizer_sentencepiece_payload_falls_back_if_missing_assets(tmp_path: Path) -> None:
    tok_path = tmp_path / "tokenizer.json"
    tok_path.write_text(
        json.dumps(
            {
                "tokenizer_type": "sentencepiece",
                "model_file": "missing.model",
                "special_tokens": SimpleTokenizer.SPECIAL_TOKENS,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    loaded = load_tokenizer(str(tok_path), allow_fallback=True)
    assert isinstance(loaded, SimpleTokenizer)
