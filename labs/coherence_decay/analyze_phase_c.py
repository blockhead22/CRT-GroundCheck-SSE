"""Phase C analysis — does typed-slot contract close the cross-model gap?

Consumes results/benchmark_debug.csv produced by benchmark_debug.py.
Produces a markdown table + a per-model cross-mode comparison.

Key questions this answers:

1. Is the within-model effect of slot-on vs slot-off uniform across models?
   (If slot-on improves llama3.2 by +3 slot points and phi3 by +3 slot points,
    the scaffold is portable.)

2. Is the cross-model variance smaller with slot-on than with slot-off?
   (This is the direct Phase C co-adaptation test: typed slots should make
    outcomes more model-invariant.)

3. Does the keyword verifier false-positive differently on different models?
   (Measures how bad the keyword grid is as an evaluation instrument.)

Usage:
    python analyze_phase_c.py                                 # default CSV
    python analyze_phase_c.py --csv results/benchmark_debug.csv
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


def load(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("final_kw_score", "final_slot_score", "total_beliefs",
                  "paradigm_shifts", "slot_birthed_total", "gap_count",
                  "hints_used", "elapsed_sec", "trial"):
            if k in r:
                try:
                    r[k] = float(r[k]) if "." in r[k] else int(r[k])
                except (ValueError, TypeError):
                    r[k] = 0
        r["total_tension"] = float(r.get("total_tension", 0) or 0)
        r["solved"] = str(r.get("solved", "")).lower() in ("true", "1", "yes")
        r["epochs_run"] = int(r["epochs_run"]) if r.get("epochs_run") else 0
    return rows


def group(rows, *keys):
    out = defaultdict(list)
    for r in rows:
        out[tuple(r[k] for k in keys)].append(r)
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def stdev(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    return statistics.pstdev(xs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str,
                    default=str(Path(__file__).parent / "results" / "benchmark_debug.csv"))
    args = ap.parse_args()

    rows = load(Path(args.csv))
    if not rows:
        print("empty CSV")
        return

    models = sorted({r["model"] for r in rows})
    modes = sorted({r["mode"] for r in rows})

    print(f"# Phase C Grid Analysis\n")
    print(f"Cells: {len(rows)}  models: {len(models)}  modes: {len(modes)}\n")

    # 1. Per-cell summary
    print("## Per-cell summary\n")
    print("| model | mode | trial | solved | kw | slot | beliefs | "
          "birthed | shifts | epochs | wall(s) |")
    print("|---|---|---:|:-:|:-:|:-:|---:|---:|---:|---:|---:|")
    for r in sorted(rows, key=lambda r: (r["model"], r["mode"], r["trial"])):
        print(f"| {r['model']} | {r['mode']} | {r['trial']} | "
              f"{'Y' if r['solved'] else 'N'} | "
              f"{r['final_kw_score']} | {r['final_slot_score']} | "
              f"{r['total_beliefs']} | {r['slot_birthed_total']} | "
              f"{r['paradigm_shifts']} | {r['epochs_run']} | "
              f"{r['elapsed_sec']} |")

    # 2. Per-model, per-mode aggregates
    print("\n## Per-model aggregates (mean across trials)\n")
    print("| model | mode | solve-rate | mean kw | mean slot | "
          "mean beliefs | mean epochs |")
    print("|---|---|---:|---:|---:|---:|---:|")
    model_mode = group(rows, "model", "mode")
    for (model, mode), rs in sorted(model_mode.items()):
        solve_rate = mean([1 if r["solved"] else 0 for r in rs])
        kw = mean([r["final_kw_score"] for r in rs])
        sl = mean([r["final_slot_score"] for r in rs])
        bel = mean([r["total_beliefs"] for r in rs])
        ep = mean([r["epochs_run"] for r in rs])
        print(f"| {model} | {mode} | {solve_rate*100:.0f}% | "
              f"{kw:.2f} | {sl:.2f} | {bel:.1f} | {ep:.1f} |")

    # 3. Cross-model variance per mode (the Phase C question)
    print("\n## Cross-model variance (the Phase C question)\n")
    print("Higher variance = outcomes depend on executor choice (bad).")
    print("Lower variance = typed-slot contract makes outcomes model-invariant (good).\n")
    print("| mode | mean solve | stdev solve | mean slot | stdev slot | "
          "mean kw | stdev kw |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    by_mode = group(rows, "mode")
    for mode, rs in sorted(by_mode.items()):
        solves = [1 if r["solved"] else 0 for r in rs]
        slots = [r["final_slot_score"] for r in rs]
        kws = [r["final_kw_score"] for r in rs]
        print(f"| {mode} | {mean(solves):.2f} | {stdev(solves):.3f} | "
              f"{mean(slots):.2f} | {stdev(slots):.3f} | "
              f"{mean(kws):.2f} | {stdev(kws):.3f} |")

    # 4. Slot-on vs slot-off within each model
    print("\n## Within-model: slot-on minus slot-off (direct ablation)\n")
    print("| model | delta solve | delta kw | delta slot | delta beliefs |")
    print("|---|---:|---:|---:|---:|")
    for model in models:
        on_rows = [r for r in rows if r["model"] == model and r["mode"] == "belief"]
        off_rows = [r for r in rows if r["model"] == model and r["mode"] == "belief-no-slots"]
        if not on_rows or not off_rows:
            continue
        d_solve = mean([1 if r["solved"] else 0 for r in on_rows]) - \
                  mean([1 if r["solved"] else 0 for r in off_rows])
        d_kw = mean([r["final_kw_score"] for r in on_rows]) - \
               mean([r["final_kw_score"] for r in off_rows])
        d_sl = mean([r["final_slot_score"] for r in on_rows]) - \
               mean([r["final_slot_score"] for r in off_rows])
        d_be = mean([r["total_beliefs"] for r in on_rows]) - \
               mean([r["total_beliefs"] for r in off_rows])
        print(f"| {model} | {d_solve:+.2f} | {d_kw:+.2f} | {d_sl:+.2f} | {d_be:+.1f} |")

    # 5. Keyword-verifier fidelity check: how often does kw disagree with slot?
    print("\n## Keyword-verifier false-positive pressure\n")
    print("Rows where kw >= 4 AND slot < 4: keyword declared solved but slot disagrees.")
    fp = [r for r in rows
          if r["final_kw_score"] >= 4 and r["final_slot_score"] < 4]
    fn = [r for r in rows
          if r["final_kw_score"] < 4 and r["final_slot_score"] >= 4]
    print(f"- kw-solved but slot-unsolved: {len(fp)}/{len(rows)} cells")
    print(f"- slot-solved but kw-unsolved: {len(fn)}/{len(rows)} cells (false-negative check)")
    if fp:
        print("\n  kw false-positive cells:")
        for r in fp:
            print(f"    {r['model']:20s} mode={r['mode']:20s} "
                  f"trial={r['trial']} kw={r['final_kw_score']} "
                  f"slot={r['final_slot_score']}")


if __name__ == "__main__":
    main()
