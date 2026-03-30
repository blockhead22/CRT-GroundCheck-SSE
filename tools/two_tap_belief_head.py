"""
Two-Tap Belief Head
===================
Layer 1 -> domain classification (WHERE in concept space)
Layer 2 -> fragility estimation  (HOW STABLE that position is)

Combined belief state: {domain, fragility} = what the model knows + how sure it is.
This is the architectural version of the belief/speech separation CRT implements at system level.

Findings that motivated this:
  - Layer 1: best geometric separation (cosine sim std=0.1915 vs 0.0578 at L3)
  - Layer 2: best susceptibility differentiation after magnitude correction (std=0.00752)
  - Layer 3: collapses both signals for token generation (speech)

Usage:
  python tools/two_tap_belief_head.py
  python tools/two_tap_belief_head.py --probe "Is it wrong to cheat on a test?"
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


DOMAIN_NAMES = {0: "factual", 1: "moral", 2: "opinion"}

# Measured normalized susceptibility per domain (from probe, layer 2)
# Used as fragility supervision signal
DOMAIN_FRAGILITY = {
    0: 0.177,   # factual  -- higher susceptibility = more fragile
    1: 0.168,   # moral    -- lower
    2: 0.170,   # opinion  -- middle
}

TRAIN_PROMPTS = [
    (0, "What is the capital of France?"),
    (0, "What is the chemical formula for water?"),
    (0, "How many continents are there on Earth?"),
    (0, "What is the healthiest diet for humans?"),
    (0, "What causes depression?"),
    (1, "Should you return a wallet you found on the street?"),
    (1, "Is it wrong to steal food when you are starving?"),
    (1, "Is it okay to lie to protect someones feelings?"),
    (1, "Should you break a promise to prevent harm?"),
    (2, "Is jazz better than classical music?"),
    (2, "Which is the best programming language?"),
    (2, "Is city life better than country life?"),
]


# ---------------------------------------------------------------------------
# Two-tap belief head
# ---------------------------------------------------------------------------

class TwoTapBeliefHead(nn.Module):
    """
    Reads from two transformer layers simultaneously.

    Layer 1 tap (domain head):
        Classifies query into factual / moral / opinion.
        Uses polar direction (unit vector) — magnitude-independent.

    Layer 2 tap (fragility head):
        Estimates how susceptible this query's representation is to perturbation.
        Uses normalized magnitude variance as signal.
        Output: 0.0 = stable (confident) ... 1.0 = fragile (uncertain)

    Combined belief state:
        domain      -> what kind of knowledge is being accessed
        fragility   -> how stable/reliable that knowledge is
        Together:   belief = (domain_type, confidence_proxy)
    """

    def __init__(self, hidden_dim: int, num_domains: int = 3):
        super().__init__()

        # Layer 1 tap: domain classifier on polar direction
        self.domain_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim // 2, num_domains),
        )

        # Layer 2 tap: fragility estimator on normalized hidden state
        self.fragility_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Sigmoid(),   # 0 = stable, 1 = fragile
        )

    def forward(self, layer1_direction: torch.Tensor, layer2_normed: torch.Tensor):
        """
        Args:
            layer1_direction: [batch, hidden] unit vector from layer 1 (polar)
            layer2_normed:    [batch, hidden] magnitude-normalized layer 2 state

        Returns:
            domain_logits: [batch, num_domains]
            fragility:     [batch, 1]
        """
        domain_logits = self.domain_head(layer1_direction)
        fragility = self.fragility_head(layer2_normed)
        return domain_logits, fragility


def belief_state_summary(domain_logits: torch.Tensor, fragility: torch.Tensor) -> str:
    """Human-readable belief state."""
    domain_probs = F.softmax(domain_logits, dim=-1)[0]
    domain_id = domain_probs.argmax().item()
    domain_conf = domain_probs.max().item()
    frag = fragility[0, 0].item()

    confidence = 1.0 - frag
    if confidence > 0.75:
        conf_label = "high confidence"
    elif confidence > 0.55:
        conf_label = "moderate confidence"
    else:
        conf_label = "low confidence"

    return (
        f"domain={DOMAIN_NAMES[domain_id]} ({domain_conf:.0%}) | "
        f"fragility={frag:.3f} | {conf_label}"
    )


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def load_model():
    cfg = DNNTConfig()
    model = DNNTMicroTransformer(cfg)
    ckpt = ROOT / "models" / "dnnt" / "best_model" / "model.pt"
    state = torch.load(str(ckpt), map_location="cpu", weights_only=False)
    model.load_state_dict(state, strict=False)
    model.eval()
    tok = SimpleTokenizer(vocab_size=cfg.vocab_size)
    return model, tok, cfg


def attach_hooks(model):
    captured = {}
    hooks = []
    for i, block in enumerate(model.blocks):
        def hook(m, inp, out, idx=i):
            captured["l%d" % idx] = out.detach().clone()
        hooks.append(block.register_forward_hook(hook))
    return captured, hooks


def get_taps(model, tok, cfg, text, captured):
    ids = tok.encode(text)
    x = torch.tensor([ids[:cfg.max_seq_length]], dtype=torch.long)
    with torch.no_grad():
        model(x)

    # Layer 1: polar direction (unit vector, magnitude-free)
    h1 = captured["l1"][0].mean(dim=0)
    direction = h1 / (h1.norm() + 1e-8)

    # Layer 2: magnitude-normalized hidden state
    h2 = captured["l2"][0].mean(dim=0)
    mag2 = h2.norm()
    normed = h2 / (mag2 + 1e-8)

    return direction, normed


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_belief_head(model, tok, cfg, captured):
    belief_head = TwoTapBeliefHead(hidden_dim=cfg.hidden_dim)
    optimizer = optim.Adam(belief_head.parameters(), lr=1e-3)

    # Build dataset
    directions, normeds, domain_labels, fragility_targets = [], [], [], []
    for domain_id, text in TRAIN_PROMPTS:
        d, n = get_taps(model, tok, cfg, text, captured)
        directions.append(d)
        normeds.append(n)
        domain_labels.append(domain_id)
        fragility_targets.append(DOMAIN_FRAGILITY[domain_id])

    dir_t  = torch.stack(directions)
    norm_t = torch.stack(normeds)
    lbl_t  = torch.tensor(domain_labels, dtype=torch.long)
    frag_t = torch.tensor(fragility_targets, dtype=torch.float32).unsqueeze(1)

    # Normalize fragility targets to [0,1] range
    fmin, fmax = frag_t.min(), frag_t.max()
    frag_t_norm = (frag_t - fmin) / (fmax - fmin + 1e-8)

    print("Training two-tap belief head...")
    belief_head.train()
    for epoch in range(400):
        optimizer.zero_grad()
        domain_logits, fragility = belief_head(dir_t, norm_t)
        domain_loss = F.cross_entropy(domain_logits, lbl_t)
        fragility_loss = F.mse_loss(fragility, frag_t_norm)
        loss = domain_loss + 0.5 * fragility_loss
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 100 == 0:
            preds = domain_logits.argmax(dim=-1)
            acc = (preds == lbl_t).float().mean().item()
            print("  Epoch %3d: loss=%.4f  domain_acc=%.0f%%  frag_loss=%.4f" % (
                epoch+1, loss.item(), acc*100, fragility_loss.item()))

    belief_head.eval()
    return belief_head


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(belief_head, model, tok, cfg, captured):
    held_out = [
        (0, "What is the speed of light in a vacuum?"),
        (0, "How many bones are in the human body?"),
        (0, "What year did World War 2 end?"),
        (1, "Is it ethical to eat meat?"),
        (1, "Should assisted dying be legal?"),
        (2, "Is coffee better than tea?"),
        (2, "Is remote work better than office work?"),
        (2, "Are dogs better pets than cats?"),
    ]

    print("\n=== HELD-OUT EVALUATION ===")
    print("%-8s  %-8s  %s  %s" % ("Truth", "Pred", "Fragility", "Prompt"))
    print("-" * 65)

    correct = 0
    for domain_id, text in held_out:
        d, n = get_taps(model, tok, cfg, text, captured)
        with torch.no_grad():
            domain_logits, fragility = belief_head(d.unsqueeze(0), n.unsqueeze(0))
        pred = domain_logits.argmax(dim=-1).item()
        frag = fragility[0, 0].item()
        ok = "OK" if pred == domain_id else "XX"
        if pred == domain_id:
            correct += 1
        print("%s %-7s  %-7s  frag=%.3f  %s" % (
            ok, DOMAIN_NAMES[domain_id], DOMAIN_NAMES[pred], frag, text[:50]))

    print("\nAccuracy: %d/%d = %.0f%%" % (correct, len(held_out), correct/len(held_out)*100))


def probe_single(belief_head, model, tok, cfg, captured, text):
    print("\n=== BELIEF STATE PROBE ===")
    print("Query: %s" % text)
    d, n = get_taps(model, tok, cfg, text, captured)
    with torch.no_grad():
        domain_logits, fragility = belief_head(d.unsqueeze(0), n.unsqueeze(0))

    probs = F.softmax(domain_logits, dim=-1)[0]
    print("Domain probabilities:")
    for did, name in DOMAIN_NAMES.items():
        bar = "#" * int(probs[did].item() * 40)
        print("  %-8s %.3f  %s" % (name, probs[did].item(), bar))
    print("Fragility: %.3f" % fragility[0,0].item())
    print("Belief:    %s" % belief_state_summary(domain_logits, fragility))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(probe_text=None):
    print("=" * 60)
    print("TWO-TAP BELIEF HEAD")
    print("L1 -> domain  |  L2 -> fragility  |  L3 -> speech")
    print("=" * 60)

    model, tok, cfg = load_model()
    print("\nModel: %s params" % f"{sum(p.numel() for p in model.parameters()):,}")

    captured, hooks = attach_hooks(model)

    belief_head = train_belief_head(model, tok, cfg, captured)

    print("\n=== TRAINING SET BELIEF STATES ===")
    for domain_id, text in TRAIN_PROMPTS:
        d, n = get_taps(model, tok, cfg, text, captured)
        with torch.no_grad():
            domain_logits, fragility = belief_head(d.unsqueeze(0), n.unsqueeze(0))
        summary = belief_state_summary(domain_logits, fragility)
        print("  [%s]  %s" % (summary, text[:55]))

    evaluate(belief_head, model, tok, cfg, captured)

    if probe_text:
        probe_single(belief_head, model, tok, cfg, captured, probe_text)

    # Save
    save_path = ROOT / "models" / "two_tap_belief_head.pt"
    torch.save(belief_head.state_dict(), str(save_path))
    print("\nSaved: %s" % save_path)

    for h in hooks:
        h.remove()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=str, default=None,
                        help="Single query to probe after training")
    args = parser.parse_args()
    run(probe_text=args.probe)
