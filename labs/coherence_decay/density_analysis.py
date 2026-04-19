"""Belief-density analysis — item #5 of the Aether carry-forward list.

Hypothesis: structural density metrics predict escape better than raw belief
count. Density metrics available from existing logs (no re-run required):

    tension_per_belief   = final_tension / final_beliefs
    gap_per_belief       = final_gap / final_beliefs
    actionable_fraction  = facts / total_beliefs         (from CSV)
    paradigm_churn       = paradigm_shifts / epochs      (from CSV)

For each cell we pull:
  - log path from CSV
  - parse last [BELIEF] beliefs=... tension=... gap=... contradictions=... line
  - combine with CSV fields (escaped, total_beliefs, facts, epochs, shifts)

Then we compute AUC / point-biserial correlation between each metric and the
binary `escaped` outcome. The metric with the strongest separation wins.

Usage:
    python density_analysis.py                 # run analysis, print table
    python density_analysis.py --plot          # also write density chart
    python density_analysis.py --belief-only   # filter to belief-mode cells
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
CSV_PATH = HERE / "results" / "raw" / "benchmark_escape.csv"
CHART_PATH = HERE / "results" / "charts" / "belief_density.png"
REPORT_PATH = HERE / "results" / "belief_density_report.md"

BELIEF_LINE_RE = re.compile(
    r"\[BELIEF\]\s+beliefs=(\d+)\s+tension=([\d.]+)\s+gap=(\d+)\s+contradictions=(\d+)"
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def parse_log_final_state(log_path: Path) -> dict | None:
    """Return {beliefs, tension, gap, contradictions} from the LAST BELIEF line."""
    if not log_path.exists():
        return None
    last = None
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = BELIEF_LINE_RE.search(line)
                if m:
                    last = {
                        "beliefs": int(m.group(1)),
                        "tension": float(m.group(2)),
                        "gap": int(m.group(3)),
                        "contradictions": int(m.group(4)),
                    }
    except Exception:
        return None
    return last


def load_cells(belief_only: bool = False) -> list[dict]:
    """Join CSV rows with parsed log state. Return cells with complete data."""
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    out = []
    for r in rows:
        if belief_only and r.get("mode") != "belief":
            continue
        # coerce
        try:
            total_beliefs = int(r["total_beliefs"]) if r.get("total_beliefs") else None
            epochs = int(r["epochs"]) if r.get("epochs") else None
            shifts = int(r["paradigm_shifts"]) if r.get("paradigm_shifts") else None
            facts = int(r["facts"]) if r.get("facts") else None
            escaped = str(r.get("escaped", "")).lower() == "true"
        except (ValueError, KeyError):
            continue

        log_state = parse_log_final_state(Path(r.get("log_path", "")))
        if not log_state:
            continue

        beliefs = log_state["beliefs"] or total_beliefs or 1
        tension = log_state["tension"]
        gap = log_state["gap"]
        contradictions = log_state["contradictions"]

        # density metrics
        tension_per = tension / beliefs if beliefs else 0.0
        gap_per = gap / beliefs if beliefs else 0.0
        actionable = (facts / beliefs) if (facts is not None and beliefs) else None
        churn = (shifts / epochs) if (shifts is not None and epochs) else None

        out.append({
            "level": r["level"],
            "mode": r["mode"],
            "executor": r.get("executor_model", ""),
            "trial": r.get("trial", ""),
            "escaped": escaped,
            "epochs": epochs,
            "total_beliefs": total_beliefs,
            "facts": facts,
            "paradigm_shifts": shifts,
            "final_beliefs": beliefs,
            "final_tension": tension,
            "final_gap": gap,
            "final_contradictions": contradictions,
            "tension_per_belief": tension_per,
            "gap_per_belief": gap_per,
            "actionable_fraction": actionable,
            "paradigm_churn": churn,
        })
    return out


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def point_biserial(xs: list[float], ys: list[bool]) -> tuple[float, float]:
    """Correlate continuous xs with binary ys.

    Returns (r_pb, mean_gap) where mean_gap = mean[x | escaped] - mean[x | failed].
    """
    if not xs or len(xs) != len(ys):
        return 0.0, 0.0
    xs1 = [x for x, y in zip(xs, ys) if y]
    xs0 = [x for x, y in zip(xs, ys) if not y]
    n1, n0 = len(xs1), len(xs0)
    if n1 == 0 or n0 == 0:
        return 0.0, 0.0
    m1 = sum(xs1) / n1
    m0 = sum(xs0) / n0
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    sd = math.sqrt(var) if var > 0 else 1e-9
    n = len(xs)
    r_pb = ((m1 - m0) / sd) * math.sqrt(n1 * n0 / (n * n))
    return r_pb, m1 - m0


def auc(xs: list[float], ys: list[bool]) -> float:
    """Rank-based AUC. P(x_escaped > x_failed). 0.5 = random, 1.0 = perfect."""
    if not xs:
        return 0.5
    xs1 = [x for x, y in zip(xs, ys) if y]
    xs0 = [x for x, y in zip(xs, ys) if not y]
    if not xs1 or not xs0:
        return 0.5
    wins = ties = 0
    for a in xs1:
        for b in xs0:
            if a > b:
                wins += 1
            elif a == b:
                ties += 1
    return (wins + 0.5 * ties) / (len(xs1) * len(xs0))


def rank_predictors(cells: list[dict]) -> list[tuple[str, float, float, float]]:
    """For each candidate metric, compute (AUC, r_pb, mean_gap).

    Returns sorted by |AUC - 0.5| descending (strongest separator first).
    """
    ys = [c["escaped"] for c in cells]
    metrics = [
        "total_beliefs",
        "final_beliefs",
        "final_tension",
        "final_gap",
        "final_contradictions",
        "tension_per_belief",
        "gap_per_belief",
        "actionable_fraction",
        "paradigm_churn",
        "paradigm_shifts",
        "facts",
    ]
    results = []
    for m in metrics:
        xs = [c[m] for c in cells if c[m] is not None]
        ys_ = [c["escaped"] for c in cells if c[m] is not None]
        if len(xs) < 4:
            continue
        a = auc(xs, ys_)
        r, gap = point_biserial(xs, ys_)
        results.append((m, a, r, gap))
    results.sort(key=lambda t: abs(t[1] - 0.5), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def print_table(cells: list[dict], ranking: list[tuple]) -> None:
    print(f"\nLoaded {len(cells)} cells with log data.")
    esc = sum(1 for c in cells if c["escaped"])
    print(f"Escape base rate: {esc}/{len(cells)} = {esc / len(cells):.1%}")

    by_mode = defaultdict(list)
    for c in cells:
        by_mode[c["mode"]].append(c)
    for mode, cs in sorted(by_mode.items()):
        e = sum(1 for c in cs if c["escaped"])
        print(f"  {mode}: {e}/{len(cs)}")

    print("\nPredictor ranking (|AUC - 0.5| descending):")
    print(f"  {'metric':<24} {'AUC':>6}  {'r_pb':>7}  {'mean_gap':>10}")
    print("  " + "-" * 54)
    for m, a, r, g in ranking:
        arrow = "+" if a > 0.5 else "-" if a < 0.5 else " "
        print(f"  {m:<24} {a:>6.3f}  {r:>+7.3f}  {g:>+10.3f} {arrow}")
    print()


def write_report(cells: list[dict], ranking: list[tuple]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Belief-Density Analysis (Item #5 — Aether Carry-Forward)")
    lines.append("")
    lines.append("**Hypothesis.** Structural density of the belief graph predicts "
                 "escape outcomes better than raw belief count.")
    lines.append("")
    lines.append(f"**Cells analyzed:** {len(cells)} "
                 f"(with complete log + CSV data).")
    esc = sum(1 for c in cells if c["escaped"])
    lines.append(f"**Escape base rate:** {esc}/{len(cells)} = {esc / len(cells):.1%}")
    lines.append("")
    lines.append("## Predictor ranking")
    lines.append("")
    lines.append("AUC = rank-based discrimination "
                 "(0.5 random, 1.0 perfect escape-predictor, "
                 "0.0 perfect failure-predictor). "
                 "`r_pb` = point-biserial correlation. "
                 "`mean_gap` = mean(escaped) − mean(failed).")
    lines.append("")
    lines.append("| metric | AUC | r_pb | mean_gap | direction |")
    lines.append("|---|---:|---:|---:|:--|")
    for m, a, r, g in ranking:
        direction = "higher → escape" if a > 0.55 else \
                    "higher → fail" if a < 0.45 else "weak / noisy"
        lines.append(f"| `{m}` | {a:.3f} | {r:+.3f} | {g:+.3f} | {direction} |")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    top = ranking[0]
    raw_auc = next((r[1] for r in ranking if r[0] == "total_beliefs"), 0.5)
    lines.append(f"- **Best predictor:** `{top[0]}` (AUC={top[1]:.3f}).")
    lines.append(f"- **Raw belief count:** `total_beliefs` AUC={raw_auc:.3f}.")
    delta = abs(top[1] - 0.5) - abs(raw_auc - 0.5)
    lines.append(f"- **Separation improvement over raw count:** {delta:+.3f} "
                 "(positive = density wins).")
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append("- Only structural density metrics available from historical logs. "
                 "True trust-weighted density (originally hypothesised) requires the "
                 "trust_distribution fields which are not yet persisted to CSV "
                 "(stays in tree_summary in memory).")
    lines.append("- Dataset is dominated by L1/L2/L5_misconfigured easy wins and "
                 "L5_hardened deliberate failures, which inflates separation of any "
                 "metric that correlates with level difficulty. The L3/L4 rows are "
                 "the informative cells.")
    lines.append("- Cells where the log is missing the final BELIEF line are dropped.")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[REPORT] wrote {REPORT_PATH}")


def plot_density(cells: list[dict]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[PLOT] matplotlib not available, skipping.")
        return

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    metrics = [
        ("total_beliefs", "Raw belief count"),
        ("tension_per_belief", "Tension per belief (density)"),
        ("gap_per_belief", "Unexploited-fact density"),
        ("actionable_fraction", "Actionable fraction (facts / beliefs)"),
    ]
    for ax, (key, title) in zip(axes.flat, metrics):
        escaped_vals = [c[key] for c in cells if c["escaped"] and c[key] is not None]
        failed_vals = [c[key] for c in cells if not c["escaped"] and c[key] is not None]
        if not escaped_vals or not failed_vals:
            ax.set_title(f"{title}\n(insufficient data)")
            continue
        ax.hist(
            [failed_vals, escaped_vals],
            bins=min(12, max(4, len(cells) // 4)),
            label=["failed", "escaped"],
            color=["#c44", "#4a4"],
            alpha=0.75,
            edgecolor="black",
        )
        ax.set_title(title)
        ax.set_xlabel(key)
        ax.set_ylabel("count")
        ax.legend(fontsize=8)

    fig.suptitle(
        "Belief-density metrics vs escape outcome\n"
        "(item #5: structural density as an Aether health signal)",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=120)
    plt.close(fig)
    print(f"[PLOT] wrote {CHART_PATH}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--belief-only", action="store_true",
                    help="restrict to belief-mode cells (excludes flat/gravity)")
    args = ap.parse_args()

    cells = load_cells(belief_only=args.belief_only)
    if not cells:
        print("No cells loaded. Check CSV_PATH and log_path fields.")
        return
    ranking = rank_predictors(cells)
    print_table(cells, ranking)
    write_report(cells, ranking)
    if args.plot:
        plot_density(cells)


if __name__ == "__main__":
    main()
