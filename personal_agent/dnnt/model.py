"""DNNT micro-transformer model and tokenizer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class DNNTConfig:
    """Configuration for the DNNT micro-transformer."""

    vocab_size: int = 8000
    max_seq_length: int = 512
    hidden_dim: int = 256
    num_layers: int = 4
    num_heads: int = 4
    dropout: float = 0.1
    ff_multiplier: int = 4

    # Special tokens
    pad_token_id: int = 0
    bos_token_id: int = 1
    eos_token_id: int = 2
    unk_token_id: int = 3
    special_token_ids: Tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)

    # Triple-loss weights
    semantic_loss_weight: float = 0.5
    syntactic_loss_weight: float = 0.3
    logical_loss_weight: float = 0.2
    label_smoothing: float = 0.03
    red_penalty_init: float = 0.08

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            payload = dict(self.__dict__)
            payload["special_token_ids"] = list(self.special_token_ids)
            json.dump(payload, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "DNNTConfig":
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if "special_token_ids" in payload and isinstance(payload["special_token_ids"], list):
            payload["special_token_ids"] = tuple(int(x) for x in payload["special_token_ids"])
        return cls(**payload)


class RotaryPositionalEncoding(nn.Module):
    def __init__(self, dim: int, max_seq_length: int = 512, base: int = 10000):
        super().__init__()
        self.dim = dim
        self.max_seq_length = max_seq_length
        self.base = base
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq)
        self._build_cache(max_seq_length)

    def _build_cache(self, seq_length: int) -> None:
        t = torch.arange(seq_length, device=self.inv_freq.device)
        freqs = torch.einsum("i,j->ij", t, self.inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)
        self.register_buffer("cos_cached", emb.cos()[None, None, :, :])
        self.register_buffer("sin_cached", emb.sin()[None, None, :, :])

    def forward(self, x: torch.Tensor, seq_len: int) -> Tuple[torch.Tensor, torch.Tensor]:
        if seq_len > self.max_seq_length:
            self._build_cache(seq_len)
        return self.cos_cached[:, :, :seq_len, :], self.sin_cached[:, :, :seq_len, :]


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]
    return torch.cat((-x2, x1), dim=-1)


def apply_rotary_pos_emb(
    q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor
) -> Tuple[torch.Tensor, torch.Tensor]:
    q_embed = (q * cos) + (rotate_half(q) * sin)
    k_embed = (k * cos) + (rotate_half(k) * sin)
    return q_embed, k_embed


class MultiHeadAttention(nn.Module):
    def __init__(self, config: DNNTConfig):
        super().__init__()
        self.num_heads = config.num_heads
        self.head_dim = config.hidden_dim // config.num_heads
        self.scale = self.head_dim ** -0.5
        self.qkv = nn.Linear(config.hidden_dim, 3 * config.hidden_dim, bias=False)
        self.proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.dropout = nn.Dropout(config.dropout)
        self.rope = RotaryPositionalEncoding(self.head_dim, config.max_seq_length)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        bsz, seq_len, channels = x.shape
        qkv = self.qkv(x).reshape(bsz, seq_len, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]

        cos, sin = self.rope(x, seq_len)
        q, k = apply_rotary_pos_emb(q, k, cos, sin)

        attn = (q @ k.transpose(-2, -1)) * self.scale
        if mask is None:
            mask = torch.triu(torch.ones(seq_len, seq_len, device=x.device), diagonal=1).bool()
        attn = attn.masked_fill(mask, float("-inf"))
        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)
        out = (attn @ v).transpose(1, 2).reshape(bsz, seq_len, channels)
        return self.proj(out)


class FeedForward(nn.Module):
    def __init__(self, config: DNNTConfig):
        super().__init__()
        hidden = config.hidden_dim * config.ff_multiplier
        self.w1 = nn.Linear(config.hidden_dim, hidden, bias=False)
        self.w2 = nn.Linear(hidden, config.hidden_dim, bias=False)
        self.w3 = nn.Linear(config.hidden_dim, hidden, bias=False)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.w2(F.silu(self.w1(x)) * self.w3(x)))


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.sqrt(torch.mean(x**2, dim=-1, keepdim=True) + self.eps)
        return x / rms * self.weight


class TransformerBlock(nn.Module):
    def __init__(self, config: DNNTConfig):
        super().__init__()
        self.attn = MultiHeadAttention(config)
        self.ff = FeedForward(config)
        self.ln1 = RMSNorm(config.hidden_dim)
        self.ln2 = RMSNorm(config.hidden_dim)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        x = x + self.attn(self.ln1(x), mask)
        x = x + self.ff(self.ln2(x))
        return x


class DNNTMicroTransformer(nn.Module):
    """Tiny transformer with triple-loss training and dynamic vocab expansion."""

    def __init__(self, config: DNNTConfig):
        super().__init__()
        self.config = config
        self.token_emb = nn.Embedding(config.vocab_size, config.hidden_dim)
        self.blocks = nn.ModuleList([TransformerBlock(config) for _ in range(config.num_layers)])
        self.ln_f = RMSNorm(config.hidden_dim)
        self.lm_head = nn.Linear(config.hidden_dim, config.vocab_size, bias=False)
        self.lm_head.weight = self.token_emb.weight
        self.red_penalty = nn.Parameter(torch.tensor(float(config.red_penalty_init)))
        self._last_loss_breakdown: Dict[str, float] = {}
        self.apply(self._init_weights)
        self.n_params = sum(p.numel() for p in self.parameters())

    def _init_weights(self, module: nn.Module) -> None:
        if isinstance(module, (nn.Linear, nn.Embedding)):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    @staticmethod
    def _masked_ce(
        logits: torch.Tensor,
        labels: torch.Tensor,
        mask: torch.Tensor,
        *,
        label_smoothing: float = 0.0,
        fallback: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if mask.sum().item() == 0:
            if fallback is not None:
                return fallback
            return logits.new_zeros(())
        return F.cross_entropy(
            logits[mask],
            labels[mask],
            label_smoothing=label_smoothing,
        )

    def _span_mask(self, input_ids: torch.Tensor, open_id: int, close_id: int) -> torch.Tensor:
        bsz, seq_len = input_ids.shape
        span = torch.zeros((bsz, seq_len), device=input_ids.device, dtype=torch.bool)
        for b in range(bsz):
            row = input_ids[b]
            open_idx = (row == open_id).nonzero(as_tuple=False).flatten()
            close_idx = (row == close_id).nonzero(as_tuple=False).flatten()
            if open_idx.numel() == 0 or close_idx.numel() == 0:
                continue
            start = int(open_idx[0].item()) + 1
            end = None
            for c in close_idx:
                c_idx = int(c.item())
                if c_idx > start:
                    end = c_idx
                    break
            if end is None or end <= start:
                continue
            span[b, start:end] = True
        return span

    def _triple_loss(
        self,
        *,
        logits: torch.Tensor,
        hidden: torch.Tensor,
        input_ids: torch.Tensor,
        labels: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        pad_id = int(self.config.pad_token_id)
        valid_mask = labels != pad_id

        general_ce = self._masked_ce(
            logits,
            labels,
            valid_mask,
            label_smoothing=float(self.config.label_smoothing),
        )

        special_ids = torch.tensor(
            list(self.config.special_token_ids),
            device=labels.device,
            dtype=labels.dtype,
        )
        is_special = (labels.unsqueeze(-1) == special_ids).any(dim=-1)
        content_mask = valid_mask & (~is_special)
        syntactic_mask = valid_mask & is_special

        semantic_loss = self._masked_ce(
            logits,
            labels,
            content_mask,
            label_smoothing=float(self.config.label_smoothing),
            fallback=general_ce,
        )
        syntactic_loss = self._masked_ce(
            logits,
            labels,
            syntactic_mask,
            label_smoothing=0.0,
            fallback=general_ce,
        )

        facts_mask = self._span_mask(input_ids, 6, 7)
        response_mask = self._span_mask(input_ids, 10, 11)
        logical_terms: List[torch.Tensor] = []
        for b in range(input_ids.shape[0]):
            fm = facts_mask[b]
            rm = response_mask[b]
            if fm.sum().item() == 0 or rm.sum().item() == 0:
                continue
            facts_vec = hidden[b][fm].mean(dim=0, keepdim=True)
            response_vec = hidden[b][rm].mean(dim=0, keepdim=True)
            sim = F.cosine_similarity(facts_vec, response_vec, dim=-1).mean()
            logical_terms.append(1.0 - sim)

        if logical_terms:
            logical_loss = torch.stack(logical_terms).mean()
        else:
            logical_loss = general_ce.detach() * 0.0

        pred = torch.argmax(logits, dim=-1)
        if pred.shape[1] > 1:
            repeated = (pred[:, 1:] == pred[:, :-1]).float().mean()
        else:
            repeated = pred.new_zeros(())
        red_weight = F.softplus(self.red_penalty)
        redundancy_loss = red_weight * repeated

        total = (
            float(self.config.semantic_loss_weight) * semantic_loss
            + float(self.config.syntactic_loss_weight) * syntactic_loss
            + float(self.config.logical_loss_weight) * logical_loss
            + redundancy_loss
        )

        breakdown = {
            "total_loss": float(total.detach().item()),
            "semantic_loss": float(semantic_loss.detach().item()),
            "syntactic_loss": float(syntactic_loss.detach().item()),
            "logical_loss": float(logical_loss.detach().item()),
            "redundancy_loss": float(redundancy_loss.detach().item()),
            "redundancy_weight": float(red_weight.detach().item()),
        }
        return total, breakdown

    def get_last_loss_breakdown(self) -> Dict[str, float]:
        return dict(self._last_loss_breakdown)

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        x = self.token_emb(input_ids)
        for block in self.blocks:
            x = block(x, mask)
        x = self.ln_f(x)
        logits = self.lm_head(x)

        loss = None
        if labels is not None:
            loss, breakdown = self._triple_loss(
                logits=logits,
                hidden=x,
                input_ids=input_ids,
                labels=labels,
            )
            self._last_loss_breakdown = breakdown
        return logits, loss

    def expand_vocab(self, new_vocab_size: int) -> None:
        """Grow embedding + lm head while preserving existing weights."""
        if new_vocab_size <= int(self.config.vocab_size):
            return
        old_vocab = int(self.config.vocab_size)
        hidden_dim = int(self.config.hidden_dim)
        device = self.token_emb.weight.device
        dtype = self.token_emb.weight.dtype

        old_weight = self.token_emb.weight.data
        new_emb = nn.Embedding(new_vocab_size, hidden_dim).to(device=device, dtype=dtype)
        torch.nn.init.normal_(new_emb.weight, mean=0.0, std=0.02)
        with torch.no_grad():
            new_emb.weight[:old_vocab].copy_(old_weight)

        self.token_emb = new_emb
        self.lm_head = nn.Linear(hidden_dim, new_vocab_size, bias=False).to(device=device, dtype=dtype)
        self.lm_head.weight = self.token_emb.weight
        self.config.vocab_size = int(new_vocab_size)
        self.n_params = sum(p.numel() for p in self.parameters())

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_k: int = 50,
        top_p: float = 0.9,
        stop_tokens: Optional[List[int]] = None,
    ) -> torch.Tensor:
        self.eval()
        for _ in range(max_new_tokens):
            idx_cond = (
                input_ids
                if input_ids.size(1) <= self.config.max_seq_length
                else input_ids[:, -self.config.max_seq_length :]
            )
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :] / max(temperature, 1e-6)

            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")

            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                indices_to_remove = sorted_indices_to_remove.scatter(
                    1, sorted_indices, sorted_indices_to_remove
                )
                logits[indices_to_remove] = float("-inf")

            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            input_ids = torch.cat([input_ids, next_token], dim=1)
            if stop_tokens and next_token.item() in stop_tokens:
                break
            if next_token.item() == self.config.eos_token_id:
                break
        return input_ids

    def save(self, path: str) -> None:
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), path_obj / "model.pt")
        self.config.save(str(path_obj / "config.json"))

    @classmethod
    def load(cls, path: str, device: str = "cpu") -> "DNNTMicroTransformer":
        path_obj = Path(path)
        config = DNNTConfig.load(str(path_obj / "config.json"))
        model = cls(config)
        model.load_state_dict(torch.load(path_obj / "model.pt", map_location=device))
        return model.to(device)


class SimpleTokenizer:
    """Character tokenizer with dynamic vocabulary growth."""

    SPECIAL_TOKENS = {
        "<pad>": 0,
        "<bos>": 1,
        "<eos>": 2,
        "<unk>": 3,
        "<query>": 4,
        "</query>": 5,
        "<facts>": 6,
        "</facts>": 7,
        "<think>": 8,
        "</think>": 9,
        "<response>": 10,
        "</response>": 11,
    }

    def __init__(self, vocab_size: int = 8000):
        self.vocab_size = int(vocab_size)
        self.special_tokens = self.SPECIAL_TOKENS.copy()
        self.char_to_id: Dict[str, int] = {}
        self.id_to_char: Dict[int, str] = {}
        idx = len(self.special_tokens)
        for c in range(32, 127):
            char = chr(c)
            self.char_to_id[char] = idx
            self.id_to_char[idx] = char
            idx += 1
        self.unk_id = self.special_tokens["<unk>"]

    def _next_index(self) -> int:
        if not self.char_to_id:
            return len(self.special_tokens)
        return max(self.char_to_id.values()) + 1

    def add_token(self, token: str, allow_expand: bool = True) -> bool:
        if token in self.char_to_id:
            return False
        idx = self._next_index()
        if idx >= self.vocab_size:
            if not allow_expand:
                return False
            self.vocab_size = idx + 256
        self.char_to_id[token] = idx
        self.id_to_char[idx] = token
        return True

    def add_tokens_from_text(self, text: str) -> int:
        added = 0
        for ch in text or "":
            if ch in self.special_tokens:
                continue
            if ch not in self.char_to_id and self.add_token(ch, allow_expand=True):
                added += 1
        return added

    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        tokens: List[int] = []
        if add_special_tokens:
            tokens.append(self.special_tokens["<bos>"])

        i = 0
        while i < len(text):
            matched = False
            for special, token_id in self.special_tokens.items():
                if text[i:].startswith(special):
                    tokens.append(token_id)
                    i += len(special)
                    matched = True
                    break
            if matched:
                continue

            char = text[i]
            if char not in self.char_to_id:
                self.add_token(char, allow_expand=True)
            tokens.append(self.char_to_id.get(char, self.unk_id))
            i += 1

        if add_special_tokens:
            tokens.append(self.special_tokens["<eos>"])
        return tokens

    def decode(self, tokens: List[int]) -> str:
        text: List[str] = []
        id_to_special = {v: k for k, v in self.special_tokens.items()}
        for token_id in tokens:
            if token_id in id_to_special:
                text.append(id_to_special[token_id])
            elif token_id in self.id_to_char:
                text.append(self.id_to_char[token_id])
            else:
                text.append("<unk>")
        return "".join(text)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "tokenizer_type": "simple",
                    "vocab_size": self.vocab_size,
                    "char_to_id": self.char_to_id,
                    "special_tokens": self.special_tokens,
                },
                f,
            )

    @classmethod
    def load(cls, path: str) -> "SimpleTokenizer":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        tokenizer = cls(int(data.get("vocab_size", 8000)))
        tokenizer.char_to_id = {str(k): int(v) for k, v in (data.get("char_to_id") or {}).items()}
        tokenizer.special_tokens = {
            str(k): int(v) for k, v in (data.get("special_tokens") or cls.SPECIAL_TOKENS).items()
        }
        tokenizer.id_to_char = {int(v): str(k) for k, v in tokenizer.char_to_id.items()}
        tokenizer.unk_id = int(tokenizer.special_tokens.get("<unk>", 3))
        return tokenizer


def expand_model_vocab(
    model: DNNTMicroTransformer,
    tokenizer: SimpleTokenizer,
    texts: Iterable[str],
) -> bool:
    """Expand tokenizer + model vocabulary from new user text."""
    grew = False
    for text in texts:
        if tokenizer.add_tokens_from_text(text or "") > 0:
            grew = True
    if tokenizer.vocab_size > model.config.vocab_size:
        model.expand_vocab(tokenizer.vocab_size)
        grew = True
    return grew


# Backward-compatible aliases while migrating callers.
MicroTransformerConfig = DNNTConfig
MicroTransformer = DNNTMicroTransformer
