"""Report generation for the CRT eval harness.

Produces:
  README_eval.md       — paper-style Markdown with tables and interpretation
  results.csv          — flat CSV for downstream analysis
  figures/             — matplotlib line graphs (optional, requires matplotlib)
"""

from __future__ import annotations

import csv
import io
import logging
import math
from pathlib import Path
from typing import List, Optional

from eval.runner import EvalMatrix
from eval.metrics import MetricsBundle

logger = logging.getLogger(__name__)

_METRIC_LABELS = {
    "contradiction_recurrence_rate": ("CRR", "↓ lower"),
    "correction_recovery_rate":      ("CRec", "↑ higher"),
    "trust_calibration_error":       ("TCE", "↓ lower"),
    "hallucination_leakage_rate":    ("HLR", "↓ lower"),
    "gate_precision":                ("GP", "↑ higher"),
    "epistemic_improvement_score":   ("EIS", "↑ higher"),
    "open_contradiction_age":        ("OCA turns", "↓ lower"),
    "fact_fidelity_over_time":       ("FFoT", "↑ higher"),
}


def _fmt(v: float, decimals: int = 3) -> str:
    if math.isnan(v):
        return "—"
    return f"{v:.{decimals}f}"


def _markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    col_widths = [
        max(len(h), max((len(r[i]) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    def _row(cells: List[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, col_widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in col_widths) + " |"
    lines = [_row(headers), sep] + [_row(r) for r in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Primary: README_eval.md
# ---------------------------------------------------------------------------

def generate_report(
    matrix: EvalMatrix,
    output_dir: Path,
    title: str = "CRT Long-Horizon Eval Report",
) -> Path:
    """Write README_eval.md (and optional figures) to output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    md = _build_markdown(matrix, title)
    report_path = output_dir / "README_eval.md"
    report_path.write_text(md, encoding="utf-8")
    logger.info("[report] wrote %s", report_path)

    _write_csv(matrix, output_dir / "results.csv")

    try:
        _write_figures(matrix, output_dir / "figures")
    except ImportError:
        logger.debug("[report] matplotlib not available, skipping figures")
    except Exception as exc:
        logger.warning("[report] figure generation failed: %s", exc)

    return report_path


def _build_markdown(matrix: EvalMatrix, title: str) -> str:
    cfg = matrix.config
    scenarios = sorted({k[0] for k in matrix.metrics})
    systems = sorted({k[1] for k in matrix.metrics})
    seeds = sorted({k[2] for k in matrix.metrics})

    buf = io.StringIO()
    w = buf.write

    w(f"# {title}\n\n")
    w(f"**Turns per run:** {cfg.n_turns}  ")
    w(f"**Seeds:** {seeds}  ")
    w(f"**Scenarios:** {len(scenarios)}  ")
    w(f"**Systems:** {len(systems)}\n\n")
    w("---\n\n")

    # --- Overview ---
    w("## Overview\n\n")
    w("This report compares CRT against ablation baselines on four long-horizon ")
    w("scenarios.  Metrics are averaged across seeds.  ")
    w("EIS (Epistemic Improvement Score) is the primary composite.\n\n")
    w("**Metric glossary:**\n")
    w("| Abbrev | Full name | Direction |\n|---|---|---|\n")
    for attr, (abbrev, direction) in _METRIC_LABELS.items():
        w(f"| {abbrev} | {attr.replace('_', ' ').title()} | {direction} |\n")
    w("\n")

    # --- Per-scenario tables ---
    for scenario in scenarios:
        w(f"---\n\n## Scenario: {scenario}\n\n")

        headers = ["System", "CRR↓", "CRec↑", "TCE↓", "HLR↓", "GP↑", "EIS↑", "OCA↓", "FFoT↑"]
        rows = []
        for system in systems:
            b = matrix.mean_bundle(scenario, system)
            if b is None:
                rows.append([system] + ["—"] * 8)
                continue
            rows.append([
                system,
                _fmt(b.contradiction_recurrence_rate),
                _fmt(b.correction_recovery_rate),
                _fmt(b.trust_calibration_error),
                _fmt(b.hallucination_leakage_rate),
                _fmt(b.gate_precision),
                _fmt(b.epistemic_improvement_score),
                _fmt(b.open_contradiction_age, 1),
                _fmt(b.fact_fidelity_over_time),
            ])
        w(_markdown_table(headers, rows))
        w("\n\n")

        # Count summary
        w("**Turn counts (mean across seeds):**\n")
        count_headers = ["System", "Gate pass", "Gate fail", "Beliefs", "Contradictions", "Thumbs↑", "Thumbs↓"]
        count_rows = []
        for system in systems:
            b = matrix.mean_bundle(scenario, system)
            if b is None:
                count_rows.append([system] + ["—"] * 6)
                continue
            n = max(len(seeds), 1)
            count_rows.append([
                system,
                str(b.n_gate_pass // n),
                str(b.n_gate_fail // n),
                str(b.n_beliefs // n),
                str(b.n_contradictions // n),
                str(b.n_thumbs_up // n),
                str(b.n_thumbs_down // n),
            ])
        w(_markdown_table(count_headers, count_rows))
        w("\n\n")

    # --- Cross-scenario EIS summary ---
    w("---\n\n## EIS Summary (all scenarios × systems)\n\n")
    eis_headers = ["System"] + scenarios
    eis_rows = []
    for system in systems:
        row = [system]
        for scenario in scenarios:
            b = matrix.mean_bundle(scenario, system)
            row.append(_fmt(b.epistemic_improvement_score) if b else "—")
        eis_rows.append(row)
    w(_markdown_table(eis_headers, eis_rows))
    w("\n\n")

    # --- Errors ---
    if matrix.errors:
        w("---\n\n## Errors\n\n")
        for e in matrix.errors:
            w(f"- **{e['scenario']} × {e['system']} × seed={e['seed']}**: `{e['error']}`\n")
        w("\n")

    # --- Methodology ---
    w("---\n\n## Methodology\n\n")
    w("### Metrics\n\n")
    w("| Metric | Formula |\n|---|---|\n")
    w("| CRR | P(same slot contradicted again within 50 turns) |\n")
    w("| CRec | P(no thumbs-down relapse within 20 turns after correction) |\n")
    w("| TCE | 1 − |mean_conf(gate-pass) − mean_conf(thumbs-down)| |\n")
    w("| HLR | thumbs-down / gate-pass belief turns |\n")
    w("| GP | thumbs-up / rated gate-pass turns |\n")
    w("| EIS | 0.4·CRec + 0.3·(1-CRR) + 0.2·(1-TCE) + 0.1·GP |\n")
    w("| OCA | mean turns between contradiction flag and resolution |\n")
    w("| FFoT | fraction of ground-truth turns answered correctly |\n")
    w("\n")
    w("### Systems under test\n\n")
    for system in systems:
        w(f"- **{system}**\n")
    w("\n### Figures\n\nSee `figures/` for per-scenario turn-over-turn plots ")
    w("(generated if matplotlib is installed).\n")

    return buf.getvalue()


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def _write_csv(matrix: EvalMatrix, path: Path) -> None:
    metric_attrs = list(_METRIC_LABELS.keys())
    count_attrs = [
        "n_turns", "n_gate_pass", "n_gate_fail", "n_contradictions",
        "n_thumbs_up", "n_thumbs_down", "n_beliefs", "n_speech",
    ]
    fieldnames = ["scenario", "system", "seed"] + metric_attrs + count_attrs

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for (scenario, system, seed), b in sorted(matrix.metrics.items()):
            row: dict = {"scenario": scenario, "system": system, "seed": seed}
            for attr in metric_attrs:
                v = getattr(b, attr, float("nan"))
                row[attr] = "" if math.isnan(v) else v
            for attr in count_attrs:
                row[attr] = getattr(b, attr, 0)
            writer.writerow(row)
    logger.info("[report] wrote %s", path)


# ---------------------------------------------------------------------------
# Figures (optional matplotlib)
# ---------------------------------------------------------------------------

def _write_figures(matrix: EvalMatrix, figures_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    scenarios = sorted({k[0] for k in matrix.records})
    systems = sorted({k[1] for k in matrix.records})

    for scenario in scenarios:
        # EIS over turn number for each system (rolling window = 50)
        fig, ax = plt.subplots(figsize=(10, 5))
        for system in systems:
            # Collect records across seeds, average by turn_idx
            all_records_by_turn: dict = {}
            for (sc, sy, sd), recs in matrix.records.items():
                if sc != scenario or sy != system:
                    continue
                for r in recs:
                    all_records_by_turn.setdefault(r.turn_idx, []).append(r)

            if not all_records_by_turn:
                continue

            turns = sorted(all_records_by_turn)
            # Rolling gate_precision as proxy for EIS over time
            window_size = 50
            rolling: List[float] = []
            for i, t in enumerate(turns):
                start = max(0, i - window_size)
                window_recs = []
                for t2 in turns[start:i + 1]:
                    window_recs.extend(all_records_by_turn[t2])
                rated = [r for r in window_recs if r.thumbs_up is not None and r.gates_passed]
                if rated:
                    rolling.append(sum(1 for r in rated if r.thumbs_up) / len(rated))
                else:
                    rolling.append(float("nan"))

            valid = [(t, v) for t, v in zip(turns, rolling) if not math.isnan(v)]
            if valid:
                xs, ys = zip(*valid)
                ax.plot(xs, ys, label=system)

        ax.set_xlabel("Turn")
        ax.set_ylabel("Rolling gate precision (window=50)")
        ax.set_title(f"{scenario} — Gate Precision Over Time")
        ax.legend()
        ax.set_ylim(0, 1)
        fig_path = figures_dir / f"{scenario}_gate_precision.png"
        fig.savefig(fig_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        logger.info("[report] figure: %s", fig_path)

        # Contradiction count over time
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        for system in systems:
            all_records_by_turn = {}
            for (sc, sy, sd), recs in matrix.records.items():
                if sc != scenario or sy != system:
                    continue
                for r in recs:
                    all_records_by_turn.setdefault(r.turn_idx, []).append(r)
            if not all_records_by_turn:
                continue
            turns = sorted(all_records_by_turn)
            cumulative = 0
            xs, ys = [], []
            for t in turns:
                cumulative += sum(1 for r in all_records_by_turn[t] if r.contradiction_detected)
                xs.append(t)
                ys.append(cumulative)
            if xs:
                ax2.plot(xs, [y / max(len(matrix.config.seeds), 1) for y in ys], label=system)

        ax2.set_xlabel("Turn")
        ax2.set_ylabel("Cumulative contradictions detected (mean/seed)")
        ax2.set_title(f"{scenario} — Contradiction Accumulation")
        ax2.legend()
        fig2_path = figures_dir / f"{scenario}_contradictions.png"
        fig2.savefig(fig2_path, dpi=120, bbox_inches="tight")
        plt.close(fig2)
        logger.info("[report] figure: %s", fig2_path)
