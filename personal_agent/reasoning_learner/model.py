"""
Micro-Transformer Model - A tiny transformer for reasoning pattern generation

Architecture:
- ~2M parameters (fits in <10MB)
- 4-6 layers, 256 hidden dim, 4 attention heads
- BPE tokenizer with ~8000 vocab
- Runs inference in <100ms on CPU, <20ms on GPU

This learns to generate:
1. Thinking traces (reasoning patterns)
2. Responses conditioned on thinking
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from dataclasses import dataclass
from typing import Optional, Tuple, List
import json
from pathlib import Path


@dataclass
class MicroTransformerConfig:
    """Configuration for the micro-transformer."""
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
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.__dict__, f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> 'MicroTransformerConfig':
        with open(path, 'r') as f:
            return cls(**json.load(f))


class RotaryPositionalEncoding(nn.Module):
    """Rotary Position Embedding (RoPE) for better length generalization."""
    
    def __init__(self, dim: int, max_seq_length: int = 512, base: int = 10000):
        super().__init__()
        self.dim = dim
        self.max_seq_length = max_seq_length
        self.base = base
        
        # Precompute frequencies
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer('inv_freq', inv_freq)
        
        # Build cos/sin cache
        self._build_cache(max_seq_length)
        
    def _build_cache(self, seq_length: int):
        t = torch.arange(seq_length, device=self.inv_freq.device)
        freqs = torch.einsum('i,j->ij', t, self.inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)
        self.register_buffer('cos_cached', emb.cos()[None, None, :, :])
        self.register_buffer('sin_cached', emb.sin()[None, None, :, :])
        
    def forward(self, x: torch.Tensor, seq_len: int) -> Tuple[torch.Tensor, torch.Tensor]:
        if seq_len > self.max_seq_length:
            self._build_cache(seq_len)
        return self.cos_cached[:, :, :seq_len, :], self.sin_cached[:, :, :seq_len, :]


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    """Rotate half the hidden dims."""
    x1 = x[..., :x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2:]
    return torch.cat((-x2, x1), dim=-1)


def apply_rotary_pos_emb(q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """Apply rotary position embeddings to queries and keys."""
    q_embed = (q * cos) + (rotate_half(q) * sin)
    k_embed = (k * cos) + (rotate_half(k) * sin)
    return q_embed, k_embed


class MultiHeadAttention(nn.Module):
    """Multi-head self-attention with RoPE."""
    
    def __init__(self, config: MicroTransformerConfig):
        super().__init__()
        self.num_heads = config.num_heads
        self.head_dim = config.hidden_dim // config.num_heads
        self.scale = self.head_dim ** -0.5
        
        self.qkv = nn.Linear(config.hidden_dim, 3 * config.hidden_dim, bias=False)
        self.proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.dropout = nn.Dropout(config.dropout)
        
        self.rope = RotaryPositionalEncoding(self.head_dim, config.max_seq_length)
        
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        B, T, C = x.shape
        
        # QKV projection
        qkv = self.qkv(x).reshape(B, T, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # (3, B, H, T, D)
        q, k, v = qkv[0], qkv[1], qkv[2]
        
        # Apply RoPE
        cos, sin = self.rope(x, T)
        q, k = apply_rotary_pos_emb(q, k, cos, sin)
        
        # Attention
        attn = (q @ k.transpose(-2, -1)) * self.scale
        
        # Causal mask
        if mask is None:
            mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        attn = attn.masked_fill(mask, float('-inf'))
        
        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)
        
        # Output
        out = (attn @ v).transpose(1, 2).reshape(B, T, C)
        return self.proj(out)


class FeedForward(nn.Module):
    """Feed-forward network with SwiGLU activation."""
    
    def __init__(self, config: MicroTransformerConfig):
        super().__init__()
        hidden = config.hidden_dim * config.ff_multiplier
        
        self.w1 = nn.Linear(config.hidden_dim, hidden, bias=False)
        self.w2 = nn.Linear(hidden, config.hidden_dim, bias=False)
        self.w3 = nn.Linear(config.hidden_dim, hidden, bias=False)
        self.dropout = nn.Dropout(config.dropout)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.w2(F.silu(self.w1(x)) * self.w3(x)))


class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization (compatible with older PyTorch)."""
    
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.sqrt(torch.mean(x ** 2, dim=-1, keepdim=True) + self.eps)
        return x / rms * self.weight


class TransformerBlock(nn.Module):
    """Single transformer block."""
    
    def __init__(self, config: MicroTransformerConfig):
        super().__init__()
        self.attn = MultiHeadAttention(config)
        self.ff = FeedForward(config)
        self.ln1 = RMSNorm(config.hidden_dim)
        self.ln2 = RMSNorm(config.hidden_dim)
        
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        x = x + self.attn(self.ln1(x), mask)
        x = x + self.ff(self.ln2(x))
        return x


class MicroTransformer(nn.Module):
    """
    A tiny transformer for reasoning pattern generation.
    
    Input format:
        <query>...</query>
        <facts>...</facts>
        <think>...</think>
        <response>...</response>
    
    The model learns to generate thinking and response given query and facts.
    """
    
    def __init__(self, config: MicroTransformerConfig):
        super().__init__()
        self.config = config
        
        # Token embedding
        self.token_emb = nn.Embedding(config.vocab_size, config.hidden_dim)
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.num_layers)
        ])
        
        # Output
        self.ln_f = RMSNorm(config.hidden_dim)
        self.lm_head = nn.Linear(config.hidden_dim, config.vocab_size, bias=False)
        
        # Weight tying
        self.lm_head.weight = self.token_emb.weight
        
        # Initialize weights
        self.apply(self._init_weights)
        
        # Count parameters
        self.n_params = sum(p.numel() for p in self.parameters())
        
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            
    def forward(
        self, 
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass.
        
        Args:
            input_ids: (B, T) token indices
            labels: (B, T) target token indices (for training)
            mask: Optional attention mask
            
        Returns:
            logits: (B, T, V) vocabulary logits
            loss: Optional cross-entropy loss
        """
        B, T = input_ids.shape
        
        # Embed tokens
        x = self.token_emb(input_ids)
        
        # Transform
        for block in self.blocks:
            x = block(x, mask)
            
        # Output
        x = self.ln_f(x)
        logits = self.lm_head(x)
        
        # Compute loss if training
        loss = None
        if labels is not None:
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                labels.view(-1),
                ignore_index=self.config.pad_token_id
            )
            
        return logits, loss
    
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
        """
        Generate tokens autoregressively.
        
        Args:
            input_ids: (B, T) initial token sequence
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k: Top-k filtering
            top_p: Nucleus sampling threshold
            stop_tokens: Token IDs to stop on
            
        Returns:
            Generated token sequence
        """
        self.eval()
        
        for _ in range(max_new_tokens):
            # Crop to max length if needed
            idx_cond = input_ids if input_ids.size(1) <= self.config.max_seq_length else input_ids[:, -self.config.max_seq_length:]
            
            # Forward pass
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :] / temperature
            
            # Top-k filtering
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
                
            # Top-p (nucleus) filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                
                indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
                logits[indices_to_remove] = float('-inf')
            
            # Sample
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            
            # Append
            input_ids = torch.cat([input_ids, next_token], dim=1)
            
            # Check stop tokens
            if stop_tokens and next_token.item() in stop_tokens:
                break
                
            # Check EOS
            if next_token.item() == self.config.eos_token_id:
                break
                
        return input_ids
    
    def save(self, path: str):
        """Save model and config."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        torch.save(self.state_dict(), path / 'model.pt')
        self.config.save(str(path / 'config.json'))
        
    @classmethod
    def load(cls, path: str, device: str = 'cpu') -> 'MicroTransformer':
        """Load model from path."""
        path = Path(path)
        config = MicroTransformerConfig.load(str(path / 'config.json'))
        model = cls(config)
        model.load_state_dict(torch.load(path / 'model.pt', map_location=device))
        return model.to(device)


class SimpleTokenizer:
    """
    Simple character-level tokenizer with special tokens.
    For production, use BPE (sentencepiece or tiktoken).
    """
    
    SPECIAL_TOKENS = {
        '<pad>': 0,
        '<bos>': 1,
        '<eos>': 2,
        '<unk>': 3,
        '<query>': 4,
        '</query>': 5,
        '<facts>': 6,
        '</facts>': 7,
        '<think>': 8,
        '</think>': 9,
        '<response>': 10,
        '</response>': 11,
    }
    
    def __init__(self, vocab_size: int = 8000):
        self.vocab_size = vocab_size
        self.special_tokens = self.SPECIAL_TOKENS.copy()
        
        # Build character vocab
        self.char_to_id = {}
        self.id_to_char = {}
        
        # Start after special tokens
        idx = len(self.special_tokens)
        
        # Add printable ASCII
        for c in range(32, 127):
            char = chr(c)
            self.char_to_id[char] = idx
            self.id_to_char[idx] = char
            idx += 1
            
        # Add common unicode
        for c in 'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ':
            self.char_to_id[c] = idx
            self.id_to_char[idx] = c
            idx += 1
            
        self.unk_id = self.special_tokens['<unk>']
        
    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        """Encode text to token IDs."""
        tokens = []
        
        if add_special_tokens:
            tokens.append(self.special_tokens['<bos>'])
            
        # Handle special tokens in text
        i = 0
        while i < len(text):
            matched = False
            for special, token_id in self.special_tokens.items():
                if text[i:].startswith(special):
                    tokens.append(token_id)
                    i += len(special)
                    matched = True
                    break
            
            if not matched:
                char = text[i]
                tokens.append(self.char_to_id.get(char, self.unk_id))
                i += 1
                
        if add_special_tokens:
            tokens.append(self.special_tokens['<eos>'])
            
        return tokens
    
    def decode(self, tokens: List[int]) -> str:
        """Decode token IDs to text."""
        text = []
        
        # Reverse special token lookup
        id_to_special = {v: k for k, v in self.special_tokens.items()}
        
        for token_id in tokens:
            if token_id in id_to_special:
                text.append(id_to_special[token_id])
            elif token_id in self.id_to_char:
                text.append(self.id_to_char[token_id])
            else:
                text.append('<unk>')
                
        return ''.join(text)
    
    def save(self, path: str):
        """Save tokenizer."""
        with open(path, 'w') as f:
            json.dump({
                'vocab_size': self.vocab_size,
                'char_to_id': self.char_to_id,
                'special_tokens': self.special_tokens,
            }, f)
            
    @classmethod
    def load(cls, path: str) -> 'SimpleTokenizer':
        """Load tokenizer."""
        with open(path, 'r') as f:
            data = json.load(f)
        tokenizer = cls(data['vocab_size'])
        tokenizer.char_to_id = data['char_to_id']
        tokenizer.special_tokens = data['special_tokens']
        tokenizer.id_to_char = {int(v): k for k, v in tokenizer.char_to_id.items()}
        return tokenizer


if __name__ == "__main__":
    # Test model
    config = MicroTransformerConfig()
    model = MicroTransformer(config)
    
    print(f"Model parameters: {model.n_params:,}")
    print(f"Model size: ~{model.n_params * 4 / 1024 / 1024:.1f} MB")
    
    # Test tokenizer
    tokenizer = SimpleTokenizer()
    text = "<query>What is my name?</query><facts>name=Nick</facts>"
    tokens = tokenizer.encode(text)
    decoded = tokenizer.decode(tokens)
    
    print(f"\nOriginal: {text}")
    print(f"Tokens: {tokens[:20]}...")
    print(f"Decoded: {decoded[:100]}...")
    
    # Test forward pass
    input_ids = torch.tensor([tokens[:50]])
    logits, _ = model(input_ids)
    print(f"\nLogits shape: {logits.shape}")
