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

ROOT = Path(__file__).parent.parent.parent

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
# Fact vs Belief assertion classifier (regex-based, no ML)
# ---------------------------------------------------------------------------
# Runs after _classify_user_input confirms an assertion.
# Sub-classifies: is this a flat fact ("I live in Denver") or a
# position/stance ("I think open source is the right strategy")?

import re as _re

_STRONG_BELIEF_MARKERS = [
    _re.compile(r"\b(?:i\s+(?:think|believe|feel\s+(?:like|that)|suspect|reckon|bet))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:i'm\s+(?:convinced|skeptical|doubtful|confident|certain|sure|unsure|worried|optimistic|pessimistic))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:i\s+(?:strongly\s+)?(?:disagree|agree|support|oppose|prefer|favor|doubt))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:in\s+my\s+(?:opinion|view|experience|estimation))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:my\s+(?:take|stance|position|view|read)\s+(?:is|on))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:i(?:'m|\s+am)\s+(?:leaning\s+toward|torn\s+(?:between|on)|on\s+the\s+fence))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:it\s+seems?\s+(?:like|to\s+me))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:i\s+(?:don't|do\s+not)\s+(?:think|believe|buy|trust))\b", _re.IGNORECASE),
]

_EVALUATIVE_PATTERNS = [
    _re.compile(r"\b(?:should|ought\s+to|need\s+to)\b.*\b(?:be|do|get|have|make|stop|start)\b", _re.IGNORECASE),
    _re.compile(r"\b(?:is|are|was)\s+(?:better|worse|overrated|underrated|overhyped|important|dangerous|risky|promising|broken|flawed|superior|inferior)\b", _re.IGNORECASE),
    _re.compile(r"\b(?:will\s+(?:never|always|eventually|probably|likely|definitely))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:the\s+(?:best|worst|right|wrong|real|true)\s+(?:way|approach|strategy|move|answer|solution))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:i(?:'d|\s+would)\s+rather)\b", _re.IGNORECASE),
    _re.compile(r"\b(?:the\s+problem\s+(?:is|with))\b", _re.IGNORECASE),
    _re.compile(r"\b(?:what\s+matters\s+(?:is|most))\b", _re.IGNORECASE),
]

# Hard fact slots — if fact_slots extracts one of these, it's a user_fact
_HARD_FACT_SLOTS = {
    "name", "first_name", "last_name", "full_name",
    "age", "birthday", "birth_year",
    "email", "phone",
    "location", "city", "state", "country",
    "employer", "company", "occupation", "job_title",
    "pet", "pet_name",
    "spouse", "partner",
    "programming_language", "framework",
    "education", "degree", "university",
}


def classify_assertion_kind(text: str) -> tuple:
    """Classify an assertion as user_fact or user_belief.

    Args:
        text: User message already classified as an assertion.

    Returns:
        Tuple of (kind, reason):
        - kind: "user_fact" or "user_belief"
        - reason: short explanation for audit trail (or None)
    """
    if not text or not text.strip():
        return "user_fact", None

    lower = text.lower().strip()

    # 1. Strong belief markers → user_belief (high confidence)
    for pattern in _STRONG_BELIEF_MARKERS:
        if pattern.search(lower):
            return "user_belief", f"belief_marker: {pattern.pattern[:40]}"

    # 2. Hard fact slot extraction → user_fact
    try:
        from ..fact_slots import extract_fact_slots
        extracted = extract_fact_slots(text)
        if extracted:
            hard_slots = set(extracted.keys()) & _HARD_FACT_SLOTS
            if hard_slots:
                return "user_fact", f"hard_slot: {','.join(sorted(hard_slots))}"
    except Exception:
        pass

    # 3. Evaluative/stance language without hard slots → user_belief
    for pattern in _EVALUATIVE_PATTERNS:
        if pattern.search(lower):
            return "user_belief", f"evaluative: {pattern.pattern[:40]}"

    # 4. Predictive claims → user_belief
    if _re.search(r"\b(?:will|going\s+to|gonna)\s+(?:replace|kill|change|transform|disrupt|dominate|fail|succeed|win|lose)\b", lower):
        return "user_belief", "predictive_claim"

    # 5. Comparative value judgments → user_belief
    if _re.search(r"\b(?:better|worse|more\s+important|less\s+important)\s+than\b", lower):
        return "user_belief", "comparative_judgment"

    # 6. Default: user_fact (conservative — preserves existing behavior)
    return "user_fact", None


def is_user_belief(text: str) -> bool:
    """Quick check: does this text express a user belief/position?"""
    kind, _ = classify_assertion_kind(text)
    return kind == "user_belief"


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
