"""
Belief Classifier — Two-Tap Belief Head for Live Inference
===========================================================
Runs on every incoming query. Produces a belief state:
  - domain:    factual / moral / opinion
  - fragility: 0.0 (stable) ... 1.0 (fragile)
  - confidence: derived from fragility

Loads once at startup. ~10ms per call on CPU.

Architecture:
  Query -> DNNT (frozen) -> L1 direction (domain) + L2 norm (fragility)
                         -> TwoTapBeliefHead -> belief state

The DNNT is not doing generation. It's being used as a feature extractor.
Its hidden states carry domain signal we measured empirically (88% held-out accuracy).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent

DOMAIN_NAMES = {0: "factual", 1: "moral", 2: "opinion"}


# ---------------------------------------------------------------------------
# Belief state dataclass
# ---------------------------------------------------------------------------

@dataclass
class BeliefState:
    domain: str           # "factual" | "moral" | "opinion"
    domain_confidence: float  # 0-1, how sure we are of domain
    fragility: float      # 0-1, how susceptible this query is
    confidence: float     # 1 - fragility (derived)
    confidence_label: str # "high" | "moderate" | "low"
    latency_ms: float

    def __str__(self):
        return (
            f"domain={self.domain}({self.domain_confidence:.0%}) "
            f"fragility={self.fragility:.3f} "
            f"confidence={self.confidence_label}"
        )

    def to_dict(self):
        return {
            "domain": self.domain,
            "domain_confidence": round(self.domain_confidence, 4),
            "fragility": round(self.fragility, 4),
            "confidence": round(self.confidence, 4),
            "confidence_label": self.confidence_label,
            "latency_ms": round(self.latency_ms, 1),
        }


# ---------------------------------------------------------------------------
# Two-tap head (must match tools/two_tap_belief_head.py)
# ---------------------------------------------------------------------------

class _TwoTapBeliefHead(nn.Module):
    def __init__(self, hidden_dim: int = 256, num_domains: int = 3):
        super().__init__()
        self.domain_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim // 2, num_domains),
        )
        self.fragility_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Sigmoid(),
        )

    def forward(self, layer1_direction, layer2_normed):
        return self.domain_head(layer1_direction), self.fragility_head(layer2_normed)


# ---------------------------------------------------------------------------
# Belief classifier — loads once, runs fast
# ---------------------------------------------------------------------------

class BeliefClassifier:
    """
    Wraps DNNT + TwoTapBeliefHead for live query classification.
    Thread-safe for read-only inference after initialization.
    """

    def __init__(
        self,
        dnnt_ckpt: Optional[str] = None,
        belief_head_ckpt: Optional[str] = None,
        enabled: bool = True,
    ):
        self.enabled = enabled
        self._model = None
        self._tok = None
        self._head = None
        self._captured: dict = {}
        self._hooks = []

        if not enabled:
            logger.info("[BELIEF] Classifier disabled")
            return

        dnnt_path = Path(dnnt_ckpt or ROOT / "models" / "dnnt" / "best_model" / "model.pt")
        head_path = Path(belief_head_ckpt or ROOT / "models" / "two_tap_belief_head.pt")

        if not dnnt_path.exists():
            logger.warning("[BELIEF] DNNT checkpoint not found: %s — disabling", dnnt_path)
            self.enabled = False
            return

        if not head_path.exists():
            logger.warning("[BELIEF] Belief head checkpoint not found: %s — disabling", head_path)
            self.enabled = False
            return

        try:
            self._load(dnnt_path, head_path)
            logger.info("[BELIEF] Classifier ready (DNNT + two-tap head loaded)")
        except Exception as e:
            logger.warning("[BELIEF] Failed to load: %s — disabling", e)
            self.enabled = False

    def _load(self, dnnt_path: Path, head_path: Path):
        from personal_agent.dnnt.model import DNNTMicroTransformer, DNNTConfig, SimpleTokenizer

        cfg = DNNTConfig()
        model = DNNTMicroTransformer(cfg)
        state = torch.load(str(dnnt_path), map_location="cpu", weights_only=False)
        model.load_state_dict(state, strict=False)
        model.eval()

        # Freeze — we're only using it as a feature extractor
        for p in model.parameters():
            p.requires_grad_(False)

        tok = SimpleTokenizer(vocab_size=cfg.vocab_size)

        # Attach hooks to L1 and L2
        captured: dict = {}
        hooks = []
        for i, block in enumerate(model.blocks):
            def hook(m, inp, out, idx=i):
                captured["l%d" % idx] = out.detach()
            hooks.append(block.register_forward_hook(hook))

        head = _TwoTapBeliefHead(hidden_dim=cfg.hidden_dim)
        head_state = torch.load(str(head_path), map_location="cpu", weights_only=False)
        head.load_state_dict(head_state)
        head.eval()
        for p in head.parameters():
            p.requires_grad_(False)

        self._model = model
        self._tok = tok
        self._cfg = cfg
        self._head = head
        self._captured = captured
        self._hooks = hooks

    def classify(self, text: str) -> Optional[BeliefState]:
        """
        Classify a query. Returns None if disabled or on error.
        Non-blocking — catches all exceptions.
        """
        if not self.enabled or self._model is None:
            return None

        t0 = time.perf_counter()
        try:
            ids = self._tok.encode(text)
            x = torch.tensor([ids[:self._cfg.max_seq_length]], dtype=torch.long)

            with torch.no_grad():
                self._model(x)

            # Layer 1: polar direction
            h1 = self._captured["l1"][0].mean(dim=0)
            direction = h1 / (h1.norm() + 1e-8)

            # Layer 2: magnitude-normalized
            h2 = self._captured["l2"][0].mean(dim=0)
            normed = h2 / (h2.norm() + 1e-8)

            domain_logits, fragility = self._head(
                direction.unsqueeze(0), normed.unsqueeze(0)
            )

            probs = F.softmax(domain_logits, dim=-1)[0]
            domain_id = probs.argmax().item()
            domain_conf = probs.max().item()
            frag = fragility[0, 0].item()
            conf = 1.0 - frag

            if conf > 0.75:
                conf_label = "high"
            elif conf > 0.55:
                conf_label = "moderate"
            else:
                conf_label = "low"

            latency = (time.perf_counter() - t0) * 1000

            return BeliefState(
                domain=DOMAIN_NAMES[int(domain_id)],
                domain_confidence=float(domain_conf),
                fragility=float(frag),
                confidence=float(conf),
                confidence_label=conf_label,
                latency_ms=latency,
            )
        except Exception as e:
            logger.debug("[BELIEF] classify error: %s", e)
            return None

    def shutdown(self):
        for h in self._hooks:
            try:
                h.remove()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_classifier: Optional[BeliefClassifier] = None


def init_belief_classifier(**kwargs) -> BeliefClassifier:
    global _classifier
    _classifier = BeliefClassifier(**kwargs)
    return _classifier


def get_belief_classifier() -> Optional[BeliefClassifier]:
    return _classifier


def classify_query(text: str) -> Optional[BeliefState]:
    """Convenience function for use in route handlers."""
    if _classifier is None:
        return None
    return _classifier.classify(text)
