"""Phase D Analyzer — three-claim replay tables from benchmark_phase_d.csv.

Claims:
  Claim 1 — substrate helps            : within each (model,level), compare
                                         belief mode vs flat mode on slot score,
                                         solve rate, and solve-epoch speed.
  Claim 2 — brain-size invariance      : belief-mode slot score across models,
                                         per level. Cross-model variance is the
                                         headline metric.
  Claim 3 — persists across model swaps: binary — does belief mode solve for
                                         every (model,level) cell?

We normalise slot score to a 0-1 fraction (hard_bug has 5 checks, hardest_bug
has 6) so cross-level comparison is meaningful.

Usage:
    python analyze_phase_d.py
    python analyze_phase_d.py --csv results/benchmark_phase_d.csv
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


SLOT_TOTAL = {"hard_bug": 5, "hardest_bug": 6}


def load_rows(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            # cast
            r["trial"] = int(r["trial"]) if r.get("trial") else 0
            r["solved"] = r.get("solved", "").lower() == "true"
            r["use_slots"] = r.get("use_slots", "").lower() == "true"
            try:
                r["final_slot_score"] = int(r.get("final_slot_score") or 0)
            except ValueError:
                r["final_slot_score"] = 0
            try:
                r["final_kw_score"] = int(r.get("final_kw_score") or 0)
            except ValueError:
                r["final_kw_score"] = 0
            try:
                r["epochs_run"] = int(r["epochs_run"]) if r.get("epochs_run") else 0
            except ValueError:
                r["epochs_run"] = 0
            try:
                r["solved_epoch"] = int(r["solved_epoch"]) if r.get("solved_epoch") else None
            except ValueError:
                r["solved_epoch"] = None
            try:
                r["elapsed_sec"] = float(r.get("elapsed_sec") or 0)
            except ValueError:
                r["elapsed_sec"] = 0.0
            try:
                r["total_beliefs"] = int(r.get("total_beliefs") or 0)
            except ValueError:
                r["total_beliefs"] = 0
            try:
                r["slot_birthed_total"] = int(r.get("slot_birthed_total") or 0)
            except ValueError:
                r["slot_birthed_total"] = 0
            r["slot_frac"] = r["final_slot_score"] / SLOT_TOTAL.get(r["level"], 5)
            rows.append(r)
    return rows


def hrule(ch="-", n=82): print(ch * n)


def fmt(x, w=8, prec=3):
    if isinstance(x, float):
        return f"{x:>{w}.{prec}f}"
    return f"{str(x):>{w}}"


def by(rows, *keys):
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in keys)].append(r)
    return g


def claim_1(rows):
    """Substrate-helps: belief vs flat within each (model, level)."""
    print()
    hrule("=")
    print("CLAIM 1 — substrate helps (belief vs flat)")
    hrule("=")
    grp = by(rows, "level", "model", "mode")
    levels = sorted({r["level"] for r in rows})
    models = sorted({r["model"] for r in rows})
    print(f"  {'level':<12} {'model':<28} "
          f"{'mode':<8} {'n':>2} {'solved':>7} {'slot_frac':>10} "
          f"{'epochs':>7} {'wall':>7}")
    for level in levels:
        for model in models:
            for mode in ("flat", "belief"):
                cells = grp.get((level, model, mode), [])
                if not cells:
                    continue
                n = len(cells)
                solve_rate = sum(1 for r in cells if r["solved"]) / n
                mean_slot = statistics.mean(r["slot_frac"] for r in cells)
                mean_ep = statistics.mean(r["epochs_run"] or 0 for r in cells)
                mean_wall = statistics.mean(r["elapsed_sec"] for r in cells)
                print(f"  {level:<12} {model:<28} "
                      f"{mode:<8} {n:>2} "
                      f"{solve_rate:>6.2f}  "
                      f"{mean_slot:>10.3f} "
                      f"{mean_ep:>7.1f} "
                      f"{mean_wall:>7.1f}")
    # Aggregate deltas: belief - flat on slot_frac
    print()
    print("  Aggregate belief-minus-flat delta on slot_frac, per level:")
    for level in levels:
        flat = [r["slot_frac"] for r in rows if r["level"] == level and r["mode"] == "flat"]
        bel = [r["slot_frac"] for r in rows if r["level"] == level and r["mode"] == "belief"]
        if not flat or not bel:
            print(f"    {level:<12} (missing one side)")
            continue
        d = statistics.mean(bel) - statistics.mean(flat)
        fsr = sum(1 for r in rows if r["level"] == level and r["mode"] == "flat" and r["solved"]) / max(1, len(flat))
        bsr = sum(1 for r in rows if r["level"] == level and r["mode"] == "belief" and r["solved"]) / max(1, len(bel))
        print(f"    {level:<12} flat mean={statistics.mean(flat):.3f}  "
              f"belief mean={statistics.mean(bel):.3f}  "
              f"delta=+{d:.3f}   "
              f"solve_rate flat={fsr:.2f} -> belief={bsr:.2f}")


def claim_2(rows):
    """Brain-size invariance: belief-mode slot score across models, per level."""
    print()
    hrule("=")
    print("CLAIM 2 — brain-size invariance (belief-mode cross-model stdev)")
    hrule("=")
    bel = [r for r in rows if r["mode"] == "belief"]
    levels = sorted({r["level"] for r in bel})
    print(f"  {'level':<12} {'n_models':>9} {'mean':>8} {'stdev':>8} "
          f"{'min':>6} {'max':>6}  per-model slot_frac means:")
    for level in levels:
        cells = [r for r in bel if r["level"] == level]
        grp = by(cells, "model")
        per_model = {m[0]: statistics.mean(r["slot_frac"] for r in rs)
                     for m, rs in grp.items()}
        if not per_model:
            continue
        vals = list(per_model.values())
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        hi, lo = max(vals), min(vals)
        per_str = "  ".join(f"{m.split(':')[0]}={v:.2f}" for m, v in sorted(per_model.items()))
        print(f"  {level:<12} {len(vals):>9} {mean:>8.3f} {sd:>8.3f} "
              f"{lo:>6.2f} {hi:>6.2f}  {per_str}")

    # Compare with flat mode as contrast
    print()
    print("  FLAT-mode contrast (same shape):")
    flat = [r for r in rows if r["mode"] == "flat"]
    for level in levels:
        cells = [r for r in flat if r["level"] == level]
        grp = by(cells, "model")
        per_model = {m[0]: statistics.mean(r["slot_frac"] for r in rs)
                     for m, rs in grp.items()}
        if not per_model:
            continue
        vals = list(per_model.values())
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        hi, lo = max(vals), min(vals)
        per_str = "  ".join(f"{m.split(':')[0]}={v:.2f}" for m, v in sorted(per_model.items()))
        print(f"  {level:<12} {len(vals):>9} {mean:>8.3f} {sd:>8.3f} "
              f"{lo:>6.2f} {hi:>6.2f}  {per_str}")


def claim_3(rows):
    """Persists across model swaps: does belief mode solve for every (model,level)?"""
    print()
    hrule("=")
    print("CLAIM 3 — persists across model swaps (belief-mode solve grid)")
    hrule("=")
    bel = [r for r in rows if r["mode"] == "belief"]
    grp = by(bel, "level", "model")
    levels = sorted({r["level"] for r in bel})
    models = sorted({r["model"] for r in bel})
    print(f"  {'model':<28} " + "  ".join(f"{lv:<12}" for lv in levels))
    all_pass = True
    for m in models:
        parts = []
        for lv in levels:
            cells = grp.get((lv, m), [])
            if not cells:
                parts.append("--".center(12))
                continue
            solved_trials = sum(1 for c in cells if c["solved"])
            n = len(cells)
            frac_mean = statistics.mean(c["slot_frac"] for c in cells)
            ok = solved_trials == n
            if not ok:
                all_pass = False
            mark = "PASS" if ok else "FAIL"
            parts.append(f"{mark} {solved_trials}/{n} ({frac_mean:.2f})".center(12))
        print(f"  {m:<28} " + "  ".join(parts))
    print()
    print(f"  Overall: {'ALL MODELS PASS' if all_pass else 'AT LEAST ONE FAIL'}")


def headline(rows):
    print()
    hrule("=")
    print("PHASE D HEADLINE")
    hrule("=")
    print(f"  total cells parsed: {len(rows)}")
    for mode in ("flat", "belief"):
        for level in sorted({r["level"] for r in rows}):
            cells = [r for r in rows if r["mode"] == mode and r["level"] == level]
            if not cells:
                continue
            n = len(cells)
            solved = sum(1 for r in cells if r["solved"])
            mean_slot = statistics.mean(r["slot_frac"] for r in cells)
            print(f"  {mode:<7} {level:<12} solved={solved}/{n}  "
                  f"slot_frac_mean={mean_slot:.3f}")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(Path(__file__).parent / "results" /
                                         "benchmark_phase_d.csv"))
    return ap.parse_args()


def main():
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return
    rows = load_rows(csv_path)
    if not rows:
        print("no rows in CSV")
        return
    headline(rows)
    claim_1(rows)
    claim_2(rows)
    claim_3(rows)


if __name__ == "__main__":
    main()
