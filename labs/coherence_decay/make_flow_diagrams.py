"""Render three flow diagrams for the belief-scaffold escape benchmark:

  1. scaffold_pipeline.png   — per-epoch belief loop (how the system works)
  2. scaffold_vs_crt.png     — mapping each scaffold primitive to Aether/CRT
  3. scaffold_vs_rag.png     — belief scaffold vs advanced RAG

All three land in results/charts/.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

CHART_DIR = Path(__file__).parent / "results" / "charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)


def _box(ax, x, y, w, h, text, color="#eef3fb", edge="#2c3e50",
         fontsize=10, bold=False, text_color="#111"):
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.2, edgecolor=edge, facecolor=color,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, weight=weight, color=text_color, wrap=True)


def _arrow(ax, x1, y1, x2, y2, color="#2c3e50", style="->",
           lw=1.4, label=None, label_offset=(0.0, 0.0), ls="-"):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, color=color,
        mutation_scale=15, linewidth=lw, linestyle=ls,
    )
    ax.add_patch(arr)
    if label:
        mx, my = (x1 + x2) / 2 + label_offset[0], (y1 + y2) / 2 + label_offset[1]
        ax.text(mx, my, label, fontsize=8, color=color, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor="none", alpha=0.85))


# ---------------------------------------------------------------------------
# 1. Scaffold pipeline — one epoch of the belief loop
# ---------------------------------------------------------------------------
def draw_pipeline():
    fig, ax = plt.subplots(figsize=(14, 8.5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Belief Scaffold — One Epoch of the Escape Loop",
                 fontsize=14, weight="bold", pad=12)

    # Top row — physical world
    _box(ax, 0.3, 8.3, 3.2, 1.1,
         "Container\n(docker exec cmd)", color="#fde9d9", edge="#b8651a", bold=True)
    _box(ax, 4.0, 8.3, 3.2, 1.1,
         "Captured output\nstdout / stderr / rc", color="#fff6df", edge="#b8651a")
    _box(ax, 10.3, 8.3, 3.4, 1.1,
         "Ground truth probe\n(flag file on host Desktop?)",
         color="#e8f5e9", edge="#2e7d32", bold=True)

    # Extractor layer
    _box(ax, 4.0, 6.5, 3.2, 1.1,
         "Belief extractor\nregex → typed belief keys", color="#eef3fb", edge="#2c3e50")
    _box(ax, 0.3, 6.5, 3.2, 1.1,
         "Extracted beliefs\n(this epoch)\ne.g. host_bind_mount:/host_data",
         color="#eef3fb", edge="#2c3e50", fontsize=9)

    # Belief graph (center)
    _box(ax, 4.5, 3.8, 5.0, 1.8,
         "BELIEF GRAPH\n"
         "Belnap {T, F, Both, Neither}  ×  trust[0..1]  ×  domain\n"
         "edges: supports · contradicts · cascades_from",
         color="#fae3f5", edge="#8e1b6b", bold=True, fontsize=10.5)

    # Math modules
    _box(ax, 0.3, 3.8, 3.5, 1.1,
         "Trust decay  (λ=10 epochs)\nt ← t · exp(-Δepoch/λ)",
         color="#dbefff", edge="#1b4f72", fontsize=9.5)
    _box(ax, 10.2, 3.8, 3.5, 1.1,
         "Contradiction cascade\ndamping: contradicts 0.60 · supports 0.30",
         color="#dbefff", edge="#1b4f72", fontsize=9.5)

    # Action layer
    _box(ax, 4.5, 1.6, 5.0, 1.1,
         "Urgency-sorted action selector\nargmax( priority(belief) · trust · unacted )",
         color="#f4f3ec", edge="#6b5400", fontsize=10)
    _box(ax, 0.3, 1.6, 3.5, 1.1,
         "Belief → action template\nhost_bind_mount:/X → ls /X && echo HELLO > /X/flag",
         color="#f4f3ec", edge="#6b5400", fontsize=9)
    _box(ax, 10.2, 1.6, 3.5, 1.1,
         "Chosen command\nemitted to Docker exec",
         color="#f4f3ec", edge="#6b5400", fontsize=10, bold=True)

    # Loop back (bottom)
    _box(ax, 4.5, 0.1, 5.0, 0.85,
         "Epoch counter += 1   →   loop",
         color="#ececec", edge="#444", fontsize=9)

    # Arrows
    # top row
    _arrow(ax, 3.5, 8.85, 4.0, 8.85)
    _arrow(ax, 7.2, 8.85, 10.3, 8.85, label="side-effect check")
    # output -> extractor
    _arrow(ax, 5.6, 8.3, 5.6, 7.6, label="parse")
    # extractor -> beliefs
    _arrow(ax, 4.0, 7.05, 3.5, 7.05)
    # beliefs -> graph
    _arrow(ax, 1.9, 6.5, 5.0, 5.6, label="merge / update")
    # decay -> graph
    _arrow(ax, 3.8, 4.35, 4.5, 4.35, label="decay")
    # graph -> cascade
    _arrow(ax, 9.5, 4.35, 10.2, 4.35, label="propagate")
    _arrow(ax, 10.2, 4.1, 9.5, 4.1, color="#8e1b6b", label="damped trust")
    # graph -> action selector
    _arrow(ax, 7.0, 3.8, 7.0, 2.7, label="urgency")
    # selector -> template
    _arrow(ax, 4.5, 2.15, 3.8, 2.15)
    # selector -> command
    _arrow(ax, 9.5, 2.15, 10.2, 2.15)
    # command -> container (loop up)
    _arrow(ax, 11.95, 2.7, 11.95, 8.3, color="#b8651a", lw=1.6, ls="--",
           label="next epoch\ncmd")
    # ground truth gates terminate
    _arrow(ax, 12.0, 8.3, 12.0, 0.5, color="#2e7d32", lw=1.6, ls=":",
           label="ESCAPED → stop")

    # Footer legend
    ax.text(7, 0.1 + 0.42, "Epoch counter += 1   →   loop",
            ha="center", va="center", fontsize=9, color="#444")
    _arrow(ax, 7.0, 1.6, 7.0, 1.0, color="#444", lw=1.0)

    fig.tight_layout()
    out = CHART_DIR / "scaffold_pipeline.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


# ---------------------------------------------------------------------------
# 2. Mapping — scaffold primitive ↔ Aether/CRT primitive
# ---------------------------------------------------------------------------
def draw_mapping():
    rows = [
        ("command stdout / stderr",        "user utterance / memory item"),
        ("typed belief key\n(host_bind_mount:/X)", "user_belief / episodic memory"),
        ("Belnap T / F / Both / Neither",  "belief state (aether_remember)"),
        ("trust ∈ [0,1] on each belief",   "trust score on memory"),
        ("trust decay  λ=10 epochs",       "temporal decay  (crt_run_trust_decay)"),
        ("contradiction cascade damping",  "BDG cascade (backprop_engine)"),
        ("belief → urgency → action",      "aether_ask / aether_dispatch"),
        ("flag file on host (ground truth)","aether_done_check / aether_fidelity"),
        ("paradigm tag\n(fs/net/proc/social)","domain tag / namespace"),
        ("scaffold = governor\nmodel = executor", "Aether = governor\nClaude Code = executor"),
    ]

    fig, ax = plt.subplots(figsize=(13, 0.62 * len(rows) + 1.4))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, len(rows) + 1.2)
    ax.axis("off")
    ax.set_title("Mapping — Docker-Escape Scaffold  ↔  Aether / CRT",
                 fontsize=14, weight="bold", pad=12)

    # Column headers
    _box(ax, 0.2, len(rows) + 0.3, 6.0, 0.75,
         "Docker-escape belief scaffold (today's experiment)",
         color="#fde9d9", edge="#b8651a", bold=True)
    _box(ax, 7.8, len(rows) + 0.3, 6.0, 0.75,
         "Aether / CRT substrate (production)",
         color="#fae3f5", edge="#8e1b6b", bold=True)

    for i, (left, right) in enumerate(rows):
        y = len(rows) - 1 - i + 0.25
        _box(ax, 0.2, y, 6.0, 0.55, left, color="#fff6df",
             edge="#b8651a", fontsize=9.5)
        _box(ax, 7.8, y, 6.0, 0.55, right, color="#f6e7f1",
             edge="#8e1b6b", fontsize=9.5)
        # equivalence arrow
        _arrow(ax, 6.3, y + 0.28, 7.7, y + 0.28, style="<->", color="#555", lw=1.1)

    fig.tight_layout()
    out = CHART_DIR / "scaffold_vs_crt.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


# ---------------------------------------------------------------------------
# 3. Belief scaffold vs advanced RAG
# ---------------------------------------------------------------------------
def draw_vs_rag():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("Advanced RAG  vs  Belief Scaffold",
                 fontsize=14, weight="bold", pad=12)

    # LEFT COLUMN — Advanced RAG
    rag_x = 0.4
    rag_w = 5.8
    ax.text(rag_x + rag_w / 2, 10.5,
            "Advanced RAG  (state-of-art retrieval pipeline)",
            ha="center", fontsize=12, weight="bold", color="#1b4f72")

    rag_steps = [
        ("Query",                       "#dbefff"),
        ("Embed  (dense / sparse / hybrid)", "#dbefff"),
        ("Vector-DB retrieval (top-k)", "#dbefff"),
        ("Cross-encoder rerank",        "#dbefff"),
        ("Context window assembly",     "#dbefff"),
        ("Generator LLM",               "#cfe4f3"),
        ("Answer  (confidence = retrieval score)", "#cfe4f3"),
    ]
    y = 9.3
    for i, (label, col) in enumerate(rag_steps):
        _box(ax, rag_x, y, rag_w, 0.75, label, color=col, edge="#1b4f72",
             fontsize=10)
        if i < len(rag_steps) - 1:
            _arrow(ax, rag_x + rag_w / 2, y, rag_x + rag_w / 2, y - 0.45)
        y -= 1.2

    # Stateless note
    _box(ax, rag_x, 0.3, rag_w, 0.8,
         "State lives in the INDEX.  Each query is stateless.\n"
         "Truth ≈ nearest-neighbor in embedding space.",
         color="#fdecea", edge="#922b21", fontsize=9.5)

    # RIGHT COLUMN — Belief scaffold
    bel_x = 7.7
    bel_w = 5.9
    ax.text(bel_x + bel_w / 2, 10.5,
            "Belief Scaffold  (today's experiment)",
            ha="center", fontsize=12, weight="bold", color="#8e1b6b")

    bel_steps = [
        ("Environment probe  (command)",         "#f6e7f1"),
        ("Typed belief extraction  (regex → key)","#f6e7f1"),
        ("Belnap truth assignment  {T,F,B,N}",   "#f6e7f1"),
        ("Trust decay  ·  Cascade damping",      "#f6e7f1"),
        ("Urgency ranking  (priority · trust)",  "#f6e7f1"),
        ("Action chosen FROM belief  (not LLM)", "#eed0e7"),
        ("Execute  →  ground-truth check",       "#eed0e7"),
    ]
    y = 9.3
    for i, (label, col) in enumerate(bel_steps):
        _box(ax, bel_x, y, bel_w, 0.75, label, color=col, edge="#8e1b6b",
             fontsize=10)
        if i < len(bel_steps) - 1:
            _arrow(ax, bel_x + bel_w / 2, y, bel_x + bel_w / 2, y - 0.45)
        y -= 1.2
    # Feedback loop
    _arrow(ax, bel_x + bel_w + 0.15, 0.85,
           bel_x + bel_w + 0.15, 9.3 + 0.38,
           style="->", color="#8e1b6b", lw=1.6, ls="--",
           label="loop")
    _arrow(ax, bel_x + bel_w, 0.85, bel_x + bel_w + 0.15, 0.85,
           color="#8e1b6b", lw=1.6, ls="--")
    _arrow(ax, bel_x + bel_w + 0.15, 9.3 + 0.38, bel_x + bel_w, 9.3 + 0.38,
           color="#8e1b6b", lw=1.6, ls="--")

    _box(ax, bel_x, 0.3, bel_w, 0.8,
         "State lives in the BELIEF GRAPH.  Stateful across epochs.\n"
         "Truth = survived contradiction cascade + decay.",
         color="#e8f5e9", edge="#2e7d32", fontsize=9.5)

    # Divider + differences ribbon across bottom
    ax.axvline(6.95, ymin=0.08, ymax=0.95, color="#999", ls=":", lw=1)

    fig.tight_layout()
    out = CHART_DIR / "scaffold_vs_rag.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    draw_pipeline()
    draw_mapping()
    draw_vs_rag()
