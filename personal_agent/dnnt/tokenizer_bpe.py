"""Optional SentencePiece BPE tokenizer with dynamic fallback overlays."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .model import SimpleTokenizer

try:
    import sentencepiece as spm  # type: ignore[import-not-found]
except Exception:
    spm = None


_DEFAULT_SPECIAL_TOKENS = SimpleTokenizer.SPECIAL_TOKENS.copy()


class SentencePieceTokenizer:
    """SentencePiece-backed tokenizer with dynamic OOV overlays."""

    def __init__(self, model_file: str, vocab_size: int = 8000):
        if spm is None:
            raise RuntimeError(
                "sentencepiece is not installed. Install with `pip install sentencepiece` "
                "or use the simple tokenizer backend."
            )

        self.model_file = str(model_file)
        self.sp = spm.SentencePieceProcessor(model_file=self.model_file)
        self.base_vocab_size = int(self.sp.get_piece_size())
        self.special_tokens: Dict[str, int] = {}
        self.extra_tokens: Dict[str, int] = {}
        self.extra_id_to_token: Dict[int, str] = {}
        self.char_to_id: Dict[str, int] = {}
        self.id_to_char: Dict[int, str] = {}
        self.next_id = int(self.base_vocab_size)
        self.vocab_size = max(int(vocab_size), self.base_vocab_size)

        for token in _DEFAULT_SPECIAL_TOKENS:
            piece_id = int(self.sp.piece_to_id(token))
            if piece_id >= 0:
                self.special_tokens[token] = piece_id
            else:
                self.special_tokens[token] = self._allocate_id()
                self.extra_id_to_token[self.special_tokens[token]] = token

        self.id_to_special = {int(v): str(k) for k, v in self.special_tokens.items()}
        self.unk_id = int(self.special_tokens.get("<unk>", 3))
        self.vocab_size = max(int(vocab_size), self.next_id)

    def _allocate_id(self) -> int:
        token_id = int(self.next_id)
        self.next_id += 1
        self.vocab_size = max(self.vocab_size, self.next_id)
        return token_id

    def _get_or_add_extra_token(self, token: str) -> int:
        if token in self.extra_tokens:
            return int(self.extra_tokens[token])
        token_id = self._allocate_id()
        self.extra_tokens[token] = token_id
        self.extra_id_to_token[token_id] = token
        return token_id

    def _get_or_add_char_token(self, char: str) -> int:
        if char in self.char_to_id:
            return int(self.char_to_id[char])
        token_id = self._allocate_id()
        self.char_to_id[char] = token_id
        self.id_to_char[token_id] = char
        return token_id

    def _encode_chunk(self, text: str) -> List[int]:
        ids: List[int] = []
        for segment in re.findall(r"\s+|[^\s]+", text or ""):
            if not segment:
                continue
            if segment in self.extra_tokens:
                ids.append(int(self.extra_tokens[segment]))
                continue

            sp_ids = list(self.sp.encode(segment, out_type=int))
            if not sp_ids:
                continue

            if len(sp_ids) == 1 and int(sp_ids[0]) == self.unk_id and segment.strip():
                ids.append(self._get_or_add_extra_token(segment))
                continue

            if self.unk_id in {int(x) for x in sp_ids}:
                ids.extend(self._get_or_add_char_token(ch) for ch in segment)
                continue

            ids.extend(int(x) for x in sp_ids)
        return ids

    def add_tokens_from_text(self, text: str) -> int:
        added = 0
        for token in re.findall(r"[^\s]+", text or ""):
            if token in self.special_tokens or token in self.extra_tokens:
                continue
            ids = list(self.sp.encode(token, out_type=int))
            if len(ids) == 1 and int(ids[0]) == self.unk_id:
                self._get_or_add_extra_token(token)
                added += 1
        return added

    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        tokens: List[int] = []
        if add_special_tokens:
            tokens.append(int(self.special_tokens["<bos>"]))

        i = 0
        special_items = sorted(
            self.special_tokens.items(),
            key=lambda kv: len(kv[0]),
            reverse=True,
        )
        while i < len(text):
            matched = False
            for special, token_id in special_items:
                if special in {"<pad>", "<bos>", "<eos>", "<unk>"}:
                    continue
                if text[i:].startswith(special):
                    tokens.append(int(token_id))
                    i += len(special)
                    matched = True
                    break
            if matched:
                continue

            next_pos = len(text)
            for special in self.special_tokens:
                if special in {"<pad>", "<bos>", "<eos>", "<unk>"}:
                    continue
                pos = text.find(special, i)
                if pos != -1:
                    next_pos = min(next_pos, pos)

            chunk = text[i:next_pos]
            tokens.extend(self._encode_chunk(chunk))
            i = next_pos

        if add_special_tokens:
            tokens.append(int(self.special_tokens["<eos>"]))
        return tokens

    def decode(self, tokens: List[int]) -> str:
        out: List[str] = []
        sp_buffer: List[int] = []

        def flush() -> None:
            nonlocal sp_buffer
            if sp_buffer:
                out.append(self.sp.decode(sp_buffer))
                sp_buffer = []

        for token_id in tokens:
            tid = int(token_id)
            if tid in self.id_to_special:
                flush()
                out.append(self.id_to_special[tid])
            elif tid in self.extra_id_to_token:
                flush()
                out.append(self.extra_id_to_token[tid])
            elif tid in self.id_to_char:
                flush()
                out.append(self.id_to_char[tid])
            elif 0 <= tid < self.base_vocab_size:
                sp_buffer.append(tid)
            else:
                flush()
                out.append("<unk>")

        flush()
        return "".join(out)

    def save(self, path: str) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        model_target = out_path.parent / "tokenizer_sentencepiece.model"
        model_source = Path(self.model_file)
        if model_source.exists() and model_source.resolve() != model_target.resolve():
            shutil.copyfile(str(model_source), str(model_target))
        elif not model_target.exists() and model_source.exists():
            shutil.copyfile(str(model_source), str(model_target))

        payload = {
            "tokenizer_type": "sentencepiece",
            "vocab_size": int(self.vocab_size),
            "model_file": model_target.name,
            "special_tokens": self.special_tokens,
            "extra_tokens": self.extra_tokens,
            "char_to_id": self.char_to_id,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "SentencePieceTokenizer":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        model_file = str(data.get("model_file") or "tokenizer_sentencepiece.model")
        model_path = Path(path).parent / model_file
        tokenizer = cls(str(model_path), vocab_size=int(data.get("vocab_size", 8000)))

        tokenizer.special_tokens = {
            str(k): int(v) for k, v in (data.get("special_tokens") or tokenizer.special_tokens).items()
        }
        tokenizer.id_to_special = {int(v): str(k) for k, v in tokenizer.special_tokens.items()}
        tokenizer.unk_id = int(tokenizer.special_tokens.get("<unk>", 3))

        tokenizer.extra_tokens = {
            str(k): int(v) for k, v in (data.get("extra_tokens") or {}).items()
        }
        tokenizer.extra_id_to_token = {int(v): str(k) for k, v in tokenizer.extra_tokens.items()}

        tokenizer.char_to_id = {
            str(k): int(v) for k, v in (data.get("char_to_id") or {}).items()
        }
        tokenizer.id_to_char = {int(v): str(k) for k, v in tokenizer.char_to_id.items()}

        all_ids = [tokenizer.base_vocab_size]
        all_ids.extend(tokenizer.special_tokens.values())
        all_ids.extend(tokenizer.extra_tokens.values())
        all_ids.extend(tokenizer.char_to_id.values())
        tokenizer.next_id = max(int(x) for x in all_ids) + 1
        tokenizer.vocab_size = max(int(data.get("vocab_size", tokenizer.next_id)), tokenizer.next_id)
        return tokenizer

    @classmethod
    def train_from_texts(
        cls,
        texts: Iterable[str],
        model_dir: str,
        vocab_size: int = 8000,
    ) -> "SentencePieceTokenizer":
        if spm is None:
            raise RuntimeError(
                "sentencepiece is not installed. Install with `pip install sentencepiece`."
            )

        out_dir = Path(model_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        corpus_path = out_dir / "tokenizer_corpus.txt"
        with open(corpus_path, "w", encoding="utf-8") as f:
            written = 0
            for text in texts:
                line = str(text or "").strip()
                if not line:
                    continue
                f.write(line + "\n")
                written += 1
            if written == 0:
                f.write("placeholder\n")

        model_prefix = out_dir / "tokenizer_sentencepiece"
        user_symbols = [
            "<query>",
            "</query>",
            "<facts>",
            "</facts>",
            "<think>",
            "</think>",
            "<response>",
            "</response>",
        ]
        spm.SentencePieceTrainer.Train(
            input=str(corpus_path),
            model_prefix=str(model_prefix),
            vocab_size=max(int(vocab_size), 256),
            model_type="bpe",
            character_coverage=1.0,
            hard_vocab_limit=False,
            pad_id=0,
            bos_id=1,
            eos_id=2,
            unk_id=3,
            user_defined_symbols=user_symbols,
        )

        model_file = str(model_prefix) + ".model"
        tokenizer = cls(model_file=model_file, vocab_size=vocab_size)
        tokenizer.vocab_size = max(tokenizer.vocab_size, int(vocab_size))
        return tokenizer


def load_tokenizer(path: str, allow_fallback: bool = True):
    """Load tokenizer from disk, supporting simple and sentencepiece payloads."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    tokenizer_type = str(payload.get("tokenizer_type") or "simple").strip().lower()
    if tokenizer_type == "sentencepiece":
        if spm is None and allow_fallback:
            return SimpleTokenizer()
        try:
            return SentencePieceTokenizer.load(path)
        except Exception:
            if allow_fallback:
                return SimpleTokenizer()
            raise
    return SimpleTokenizer.load(path)


def create_tokenizer(
    *,
    backend: str = "simple",
    vocab_size: int = 8000,
    texts: Optional[Iterable[str]] = None,
    model_dir: Optional[str] = None,
    allow_fallback: bool = True,
):
    """Create tokenizer backend for DNNT training."""
    normalized = str(backend or "simple").strip().lower()
    if normalized in {"simple", "char", "character"}:
        return SimpleTokenizer(vocab_size=vocab_size)

    if normalized in {"sentencepiece", "bpe"}:
        if spm is None:
            if allow_fallback:
                return SimpleTokenizer(vocab_size=vocab_size)
            raise RuntimeError("sentencepiece backend requested but dependency is not installed")

        if model_dir and texts is not None:
            return SentencePieceTokenizer.train_from_texts(
                texts=texts,
                model_dir=model_dir,
                vocab_size=vocab_size,
            )

        if model_dir:
            model_path = Path(model_dir) / "tokenizer_sentencepiece.model"
            if model_path.exists():
                return SentencePieceTokenizer(str(model_path), vocab_size=vocab_size)

        if allow_fallback:
            return SimpleTokenizer(vocab_size=vocab_size)
        raise RuntimeError("unable to initialize sentencepiece tokenizer")

    raise ValueError(f"Unsupported tokenizer backend: {backend}")
