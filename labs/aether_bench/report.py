"""Aggregate aether_bench trials + judgments into a markdown report + chart.

Reads trials.sqlite (trials + judgments), groups by (brain, arm), computes
tokens / correctness / wall / tool-call medians and means, runs a paired
t-test on tokens and a sign test on correctness per brain, writes:
  - results.md    (human-readable report)
  - results.png   (Cold vs Warm bars by brain; tokens + correctness)

Usage:
    python -m labs.aether_bench.report
"""
from __future__ import annotations

import sqlite3
import statistics as stats
from math import sqrt
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
DB_PATH = LAB_DIR / "trials.sqlite"
MD_PATH = LAB_DIR / "results.md"
PNG_PATH = LAB_DIR / "results.png"


def rows() -> list[sqlite3.Row]:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return list(c.execute("""
        SELECT t.brain, t.arm, t.task_id, t.tokens_in, t.tokens_out,
               t.tool_calls, t.substrate_tool_calls, t.wall_ms, t.error,
               j.score
        FROM trials t
        LEFT JOIN judgments j ON j.trial_id = t.trial_id
    """))


def paired_t(cold: list[float], warm: list[float]) -> tuple[float, int]:
    """Paired t-stat on matched lists. Returns (t, n). p-value left to reader
    (scipy not guaranteed available). Just reporting t and n."""
    n = min(len(cold), len(warm))
    if n < 2:
        return 0.0, n
    diffs = [cold[i] - warm[i] for i in range(n)]
    m = stats.mean(diffs)
    sd = stats.stdev(diffs) if n > 1 else 0.0
    if sd == 0:
        return 0.0, n
    return m / (sd / sqrt(n)), n


def sign_test(cold: list[int], warm: list[int]) -> tuple[int, int, int]:
    """Returns (warm_better, cold_better, ties)."""
    wb = cb = tie = 0
    for c, w in zip(cold, warm):
        if w > c: wb += 1
        elif c > w: cb += 1
        else: tie += 1
    return wb, cb, tie


def aggregate() -> dict:
    data = rows()
    by_brain: dict[str, dict[str, list[dict]]] = {}
    for r in data:
        by_brain.setdefault(r["brain"], {"cold": [], "warm": []})
        by_brain[r["brain"]][r["arm"]].append(dict(r))
    summary = {}
    for brain, arms in by_brain.items():
        s = {}
        for arm in ("cold", "warm"):
            xs = arms[arm]
            if not xs:
                s[arm] = None
                continue
            toks = [(x["tokens_in"] or 0) + (x["tokens_out"] or 0) for x in xs]
            scores = [x["score"] for x in xs if x["score"] is not None]
            tools = [x["tool_calls"] or 0 for x in xs]
            sub = [x["substrate_tool_calls"] or 0 for x in xs]
            wall = [x["wall_ms"] or 0 for x in xs]
            s[arm] = {
                "n": len(xs),
                "tokens_mean": stats.mean(toks) if toks else 0,
                "tokens_median": stats.median(toks) if toks else 0,
                "correct_mean": stats.mean(scores) / 2.0 if scores else None,
                "tool_calls_mean": stats.mean(tools) if tools else 0,
                "substrate_calls_mean": stats.mean(sub) if sub else 0,
                "wall_ms_median": stats.median(wall) if wall else 0,
                "errors": sum(1 for x in xs if x["error"]),
            }
        # paired tests, matched by task_id
        if arms["cold"] and arms["warm"]:
            by_task_cold = {x["task_id"]: x for x in arms["cold"]}
            by_task_warm = {x["task_id"]: x for x in arms["warm"]}
            shared = sorted(set(by_task_cold) & set(by_task_warm))
            ct = [(by_task_cold[t]["tokens_in"] or 0) + (by_task_cold[t]["tokens_out"] or 0) for t in shared]
            wt = [(by_task_warm[t]["tokens_in"] or 0) + (by_task_warm[t]["tokens_out"] or 0) for t in shared]
            cs = [by_task_cold[t]["score"] or 0 for t in shared]
            ws = [by_task_warm[t]["score"] or 0 for t in shared]
            t, n = paired_t(ct, wt)
            wb, cb, tie = sign_test(cs, ws)
            s["paired"] = {"n": n, "t_tokens_cold_minus_warm": round(t, 3),
                           "sign_warm_better": wb, "sign_cold_better": cb, "ties": tie}
        summary[brain] = s
    return summary


def render_md(summary: dict) -> str:
    lines = ["# Aether Bench Results", ""]
    if not summary:
        lines.append("_no trials yet_")
        return "\n".join(lines)
    for brain, s in summary.items():
        lines.append(f"## Brain: `{brain}`")
        lines.append("")
        lines.append("| arm | n | tokens (mean) | tokens (median) | correct | tools | substrate tools | wall ms (median) | errors |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for arm in ("cold", "warm"):
            a = s.get(arm)
            if not a:
                lines.append(f"| {arm} | 0 | - | - | - | - | - | - | - |")
                continue
            c = f"{a['correct_mean']:.2f}" if a["correct_mean"] is not None else "-"
            lines.append(
                f"| {arm} | {a['n']} | {a['tokens_mean']:.0f} | {a['tokens_median']:.0f} | "
                f"{c} | {a['tool_calls_mean']:.1f} | {a['substrate_calls_mean']:.1f} | "
                f"{a['wall_ms_median']:.0f} | {a['errors']} |"
            )
        p = s.get("paired")
        if p:
            lines.append("")
            lines.append(f"**Paired (n={p['n']})** — t on tokens (cold−warm): {p['t_tokens_cold_minus_warm']} "
                         f"· sign test correctness: warm-better={p['sign_warm_better']}, "
                         f"cold-better={p['sign_cold_better']}, ties={p['ties']}")
        lines.append("")
    return "\n".join(lines)


def render_png(summary: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping PNG")
        return
    brains = list(summary.keys())
    if not brains:
        return
    cold_tok = [summary[b]["cold"]["tokens_mean"] if summary[b].get("cold") else 0 for b in brains]
    warm_tok = [summary[b]["warm"]["tokens_mean"] if summary[b].get("warm") else 0 for b in brains]
    cold_cor = [(summary[b]["cold"]["correct_mean"] or 0) if summary[b].get("cold") else 0 for b in brains]
    warm_cor = [(summary[b]["warm"]["correct_mean"] or 0) if summary[b].get("warm") else 0 for b in brains]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    x = range(len(brains))
    w = 0.38
    ax1.bar([i - w/2 for i in x], cold_tok, w, label="cold", color="#888")
    ax1.bar([i + w/2 for i in x], warm_tok, w, label="warm", color="#3a7")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(brains)
    ax1.set_ylabel("tokens (mean)")
    ax1.set_title("Token cost: Cold vs Warm")
    ax1.legend()

    ax2.bar([i - w/2 for i in x], cold_cor, w, label="cold", color="#888")
    ax2.bar([i + w/2 for i in x], warm_cor, w, label="warm", color="#3a7")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(brains)
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("correctness (0-1)")
    ax2.set_title("Correctness: Cold vs Warm")
    ax2.legend()

    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=120)
    plt.close(fig)
    print(f"wrote {PNG_PATH}")


def main() -> None:
    s = aggregate()
    md = render_md(s)
    MD_PATH.write_text(md, encoding="utf-8")
    print(f"wrote {MD_PATH}")
    render_png(s)


if __name__ == "__main__":
    main()
