"""
Polar Belief Head Experiment
============================
Tests whether applying a polar coordinate transform to DNNT layer 1 hidden states
produces better domain separation than raw Cartesian layer 3 outputs.

Hypothesis (from TurboQuant + hidden state analysis):
  - Domain information (factual/moral/opinion) lives in early layers
  - Residual stream collapses it by depth (measured: sim 0.34 → 0.80 across layers)
  - Polar transform separates magnitude (confidence) from direction (domain type)
  - Belief head reading polar layer 1 should cluster domains better than speech head at layer 3

Architecture:
  Input → [Layer 0] → [Layer 1*] → [Layer 2] → [Layer 3] → lm_head (speech)
                           ↓
                     polar_transform
                     magnitude + direction
                           ↓
                     belief_head → domain logits / confidence
                     (* hooked, not modified)

Usage:
  python tools/polar_belief_head.py
  python tools/polar_belief_head.py --train     # also train belief head
  python tools/polar_belief_head.py --layer 2   # tap a different layer
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from personal_agent.dnnt.model import DNNTMicroTransformer, DNNTConfig, SimpleTokenizer


# ---------------------------------------------------------------------------
# Probe prompts — same 5 domains as the variance experiment
# ---------------------------------------------------------------------------

PROMPTS = [
    # (domain_label, domain_id, text)
    ("factual_settled",   0, "What is the capital of France?"),
    ("factual_settled",   0, "What is the chemical formula for water?"),
    ("factual_settled",   0, "How many continents are there on Earth?"),
    ("factual_contested", 0, "What is the healthiest diet for humans?"),
    ("factual_contested", 0, "What causes depression?"),
    ("moral_clear",       1, "Should you return a wallet you found on the street?"),
    ("moral_clear",       1, "Is it wrong to steal food when you are starving?"),
    ("moral_ambiguous",   1, "Is it okay to lie to protect someone's feelings?"),
    ("moral_ambiguous",   1, "Should you break a promise to prevent harm?"),
    ("opinion",           2, "Is jazz better than classical music?"),
    ("opinion",           2, "Which is the best programming language?"),
    ("opinion",           2, "Is city life better than country life?"),
]

DOMAIN_NAMES = {0: "factual", 1: "moral", 2: "opinion"}


# ---------------------------------------------------------------------------
# Polar transform
# ---------------------------------------------------------------------------

def to_polar(x: torch.Tensor):
    """
    Convert hidden state tensor to polar components.

    Args:
        x: [batch, seq, hidden]

    Returns:
        magnitude: [batch, seq, 1]  — how strongly activated (confidence proxy)
        direction: [batch, seq, hidden]  — unit vector (domain/content type)
    """
    magnitude = torch.norm(x, dim=-1, keepdim=True)          # L2 norm per position
    direction = x / (magnitude + 1e-8)                        # unit vector
    return magnitude, direction


def polar_pool(x: torch.Tensor):
    """
    Mean-pool hidden states then convert to polar.
    Returns (magnitude scalar, direction vector) for a sequence.
    """
    pooled = x.mean(dim=1)          # [batch, hidden]
    mag = torch.norm(pooled, dim=-1, keepdim=True)
    direction = pooled / (mag + 1e-8)
    return mag, direction


# ---------------------------------------------------------------------------
# Belief head — small MLP on top of polar direction
# ---------------------------------------------------------------------------

class BeliefHead(nn.Module):
    """
    Reads the direction vector from a polar-projected intermediate layer.
    Predicts: domain class (factual / moral / opinion) and confidence score.
    """
    def __init__(self, hidden_dim: int, num_classes: int = 3):
        super().__init__()
        self.domain_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, num_classes),
        )
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Sigmoid(),
        )

    def forward(self, direction: torch.Tensor):
        """
        Args:
            direction: [batch, hidden] — unit vector from polar transform

        Returns:
            domain_logits: [batch, num_classes]
            confidence:    [batch, 1]
        """
        domain_logits = self.domain_head(direction)
        confidence = self.confidence_head(direction)
        return domain_logits, confidence


# ---------------------------------------------------------------------------
# Geometry analysis — no training needed
# ---------------------------------------------------------------------------

def measure_separation(vecs: dict[str, torch.Tensor], label: str) -> dict:
    """
    Measure intra-cluster vs inter-cluster cosine similarity.
    Returns separation score: higher = better separated.
    """
    domains = {0: [], 1: [], 2: []}
    for (_, domain_id, _), vec in vecs.items():
        domains[domain_id].append(vec)

    # Average within-cluster similarity
    intra_sims = []
    for did, dvecs in domains.items():
        if len(dvecs) < 2:
            continue
        for i in range(len(dvecs)):
            for j in range(i + 1, len(dvecs)):
                sim = F.cosine_similarity(dvecs[i].unsqueeze(0), dvecs[j].unsqueeze(0)).item()
                intra_sims.append(sim)

    # Average between-cluster similarity
    inter_sims = []
    domain_ids = list(domains.keys())
    for i in range(len(domain_ids)):
        for j in range(i + 1, len(domain_ids)):
            for vi in domains[domain_ids[i]]:
                for vj in domains[domain_ids[j]]:
                    sim = F.cosine_similarity(vi.unsqueeze(0), vj.unsqueeze(0)).item()
                    inter_sims.append(sim)

    intra = sum(intra_sims) / len(intra_sims) if intra_sims else 0.0
    inter = sum(inter_sims) / len(inter_sims) if inter_sims else 0.0
    separation = intra - inter  # Higher = clusters are tighter internally, farther apart

    print(f"\n  [{label}]")
    print(f"    Intra-cluster similarity : {intra:.4f}  (same domain, should be HIGH)")
    print(f"    Inter-cluster similarity : {inter:.4f}  (diff domain, should be LOW)")
    print(f"    Separation score         : {separation:.4f}  (higher = better domain clustering)")

    return {"intra": intra, "inter": inter, "separation": separation}


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run(layer_idx: int = 1, train: bool = False):
    print("=" * 60)
    print("POLAR BELIEF HEAD EXPERIMENT")
    print(f"Tapping layer {layer_idx} for belief head")
    print("=" * 60)

    # Load model
    cfg = DNNTConfig()
    model = DNNTMicroTransformer(cfg)
    ckpt_path = ROOT / "models" / "dnnt" / "best_model" / "model.pt"
    state = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    model.load_state_dict(state, strict=False)
    model.eval()
    tok = SimpleTokenizer(vocab_size=cfg.vocab_size)

    print(f"\nLoaded DNNT: {sum(p.numel() for p in model.parameters()):,} params")

    # Hook to capture intermediate layer
    captured = {}
    def make_hook(name):
        def hook(module, inp, out):
            captured[name] = out.detach().clone()
        return hook

    hooks = []
    for i, block in enumerate(model.blocks):
        hooks.append(block.register_forward_hook(make_hook(f"layer_{i}")))

    # Collect hidden states for all prompts
    cartesian_layer1 = {}   # raw layer-N hidden state (pooled)
    cartesian_layer3 = {}   # raw final layer hidden state (pooled)
    polar_direction  = {}   # polar direction from layer N
    polar_magnitude  = {}   # polar magnitude from layer N

    print(f"\nForward pass for {len(PROMPTS)} prompts...")
    for prompt_tuple in PROMPTS:
        domain_label, domain_id, text = prompt_tuple
        ids = tok.encode(text)
        x = torch.tensor([ids[:cfg.max_seq_length]], dtype=torch.long)

        with torch.no_grad():
            model(x)

        # Layer N (belief source)
        h_n = captured[f"layer_{layer_idx}"]   # [1, seq, hidden]
        pooled_n = h_n[0].mean(dim=0)           # [hidden]
        mag, direction = polar_pool(h_n)
        direction_vec = direction[0]             # [hidden]

        # Final layer (speech source)
        h_3 = captured["layer_3"]
        pooled_3 = h_3[0].mean(dim=0)

        cartesian_layer1[prompt_tuple] = pooled_n
        cartesian_layer3[prompt_tuple] = pooled_3
        polar_direction[prompt_tuple]  = direction_vec
        polar_magnitude[prompt_tuple]  = mag[0, 0].item()

    for h in hooks:
        h.remove()

    # Print magnitude by domain
    print("\n  Polar magnitudes by domain (proxy for activation strength):")
    by_domain: dict[int, list] = {0: [], 1: [], 2: []}
    for prompt_tuple, mag in polar_magnitude.items():
        by_domain[prompt_tuple[1]].append(mag)
    for did, mags in by_domain.items():
        avg = sum(mags) / len(mags)
        print(f"    {DOMAIN_NAMES[did]:10s}: avg magnitude = {avg:.4f}")

    # Geometry analysis
    print("\n--- DOMAIN SEPARATION ANALYSIS ---")
    results_cart1 = measure_separation(cartesian_layer1, f"Cartesian layer {layer_idx} (raw)")
    results_cart3 = measure_separation(cartesian_layer3,  "Cartesian layer 3 (speech/current)")
    results_polar = measure_separation(polar_direction,   f"Polar direction layer {layer_idx} (belief head)")

    print("\n--- SUMMARY ---")
    print(f"  Cartesian layer {layer_idx} separation : {results_cart1['separation']:.4f}")
    print(f"  Cartesian layer 3 separation  : {results_cart3['separation']:.4f}")
    print(f"  Polar direction separation    : {results_polar['separation']:.4f}  <- hypothesis")

    winner = max(
        [("cartesian_layer1", results_cart1["separation"]),
         ("cartesian_layer3", results_cart3["separation"]),
         ("polar_direction",  results_polar["separation"])],
        key=lambda x: x[1]
    )
    print(f"\n  Best separation: {winner[0]} ({winner[1]:.4f})")
    if winner[0] == "polar_direction":
        print("  [PASS] Hypothesis supported -- polar transform improves domain clustering")
    elif winner[0] == "cartesian_layer1":
        print("  [~] Cartesian layer 1 already best -- polar transform not needed")
    else:
        print("  [FAIL] Hypothesis not supported -- final layer dominates")

    # Optional: train belief head
    if train:
        _train_belief_head(cfg, polar_direction, layer_idx, model, tok)


def _train_belief_head(cfg, polar_direction, layer_idx, model, tok):
    print("\n\n--- TRAINING BELIEF HEAD ---")
    print("(supervising on domain labels from polar direction vectors)")

    belief_head = BeliefHead(hidden_dim=cfg.hidden_dim, num_classes=3)
    optimizer = optim.Adam(belief_head.parameters(), lr=1e-3)
    ce_loss = nn.CrossEntropyLoss()

    # Build dataset from collected vectors
    directions = []
    labels = []
    for prompt_tuple, direction_vec in polar_direction.items():
        directions.append(direction_vec)
        labels.append(prompt_tuple[1])  # domain_id

    dir_tensor = torch.stack(directions)        # [N, hidden]
    lbl_tensor = torch.tensor(labels, dtype=torch.long)

    # Simple training loop
    belief_head.train()
    for epoch in range(200):
        optimizer.zero_grad()
        domain_logits, confidence = belief_head(dir_tensor)
        loss = ce_loss(domain_logits, lbl_tensor)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 50 == 0:
            preds = domain_logits.argmax(dim=-1)
            acc = (preds == lbl_tensor).float().mean().item()
            print(f"  Epoch {epoch+1:3d}: loss={loss.item():.4f}  domain_acc={acc:.2%}")

    # Final eval
    belief_head.eval()
    with torch.no_grad():
        domain_logits, confidence = belief_head(dir_tensor)
        preds = domain_logits.argmax(dim=-1)

    print("\n  Predictions vs truth:")
    for i, prompt_tuple in enumerate(polar_direction.keys()):
        domain_label, domain_id, text = prompt_tuple
        pred = preds[i].item()
        conf = confidence[i].item()
        correct = "OK" if pred == domain_id else "XX"
        print(f"  {correct} [{DOMAIN_NAMES[domain_id]:8s}->{DOMAIN_NAMES[pred]:8s}] conf={conf:.2f}  {text[:45]}")

    # Compare: what does the same head get on Cartesian layer 3?
    print("\n  Belief head geometry in polar vs Cartesian space:")
    print("  (Does polar direction carry more separable domain signal?)")

    # Re-measure with trained head activations as features
    with torch.no_grad():
        polar_features = belief_head.domain_head[0](dir_tensor)  # post first linear
    print(f"  Polar post-linear mean pairwise dist: {_mean_pairwise_dist(polar_features):.4f}")

    print("\nBelief head trained. Save with: torch.save(belief_head.state_dict(), 'models/belief_head.pt')")


def _mean_pairwise_dist(vecs: torch.Tensor) -> float:
    n = vecs.shape[0]
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            d = (vecs[i] - vecs[j]).norm().item()
            total += d
            count += 1
    return total / count if count else 0.0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polar Belief Head Experiment")
    parser.add_argument("--layer", type=int, default=1, help="Which layer to tap for belief head (0-3)")
    parser.add_argument("--train", action="store_true", help="Also train the belief head on domain labels")
    args = parser.parse_args()

    run(layer_idx=args.layer, train=args.train)
