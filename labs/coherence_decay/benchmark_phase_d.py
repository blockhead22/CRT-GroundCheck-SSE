"""Phase D Benchmark Grid — three-claim replay on the debugging benchmark.

Phase D builds on Phase C's finding (slot-on achieves zero cross-model variance
on hard_bug). Slot-on is the default substrate. We now re-test the original
three claims from the Aether-benchmark plan against the debugging task:

  Claim 1 — substrate helps            : belief (slot-on) > flat  within each cell
  Claim 2 — brain-size invariance      : belief-mode score stable across model sizes
  Claim 3 — persists across model swaps: belief-mode passes for every tested model

Grid shape:
    levels = hard_bug, hardest_bug                 (2)
    modes  = flat, belief                          (2, slot-on is the belief default)
    models = 5 (3B -> 14B brain-size spread)
    trials = 2
    total  = 2 * 2 * 5 * 2 = 40 cells

Output:
    results/benchmark_phase_d.csv  (one row per cell)

Usage:
    python benchmark_phase_d.py                              # full grid
    python benchmark_phase_d.py --models llama3.2:latest     # subset
    python benchmark_phase_d.py --trials 1 --max-epochs 10   # quick check
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

LAB_ROOT = Path(__file__).parent
RESULT_DIR = LAB_ROOT / "results" / "debug_benchmark"
CSV_OUT = LAB_ROOT / "results" / "benchmark_phase_d.csv"

DEFAULT_MODELS = [
    "llama3.2:latest",       # ~3B
    "phi3:3.8b",             # ~3.8B
    "mistral:latest",        # ~7B
    "qwen2.5-coder:7b",      # ~7B (different family / coding-tuned)
    "qwen3:14b",             # ~14B
]
DEFAULT_MODES = ["flat", "belief"]
DEFAULT_LEVELS = ["hard_bug", "hardest_bug"]
DEFAULT_TRIALS = 2
DEFAULT_MAX_EPOCHS = 12


def run_cell(level: str, mode: str, model: str, trial: int,
             max_epochs: int, stop_on: str, nudge: bool,
             verbose: bool = True) -> dict:
    cmd = [
        sys.executable,
        str(LAB_ROOT / "debug_scaffold.py"),
        "--mode", mode,
        "--level", level,
        "--model", model,
        "--max-epochs", str(max_epochs),
        "--stop-on", stop_on,
    ]
    if nudge:
        cmd.append("--nudge")
    if verbose:
        print(f"  + {' '.join(cmd)}", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    wall = time.time() - t0

    # debug_scaffold writes to results/debug_benchmark/{level}_{mode}.json
    result_file = RESULT_DIR / f"{level}_{mode}.json"
    if proc.returncode != 0:
        print(f"  ! subprocess rc={proc.returncode}")
        if proc.stderr:
            print(f"  ! stderr: {proc.stderr[-400:]}")
    try:
        with open(result_file, "r", encoding="utf-8") as f:
            result = json.load(f)
    except Exception as e:
        print(f"  ! failed to read {result_file}: {e}")
        result = {
            "level": level, "mode": mode, "model": model,
            "solved": False, "solved_epoch": None,
            "epochs_run": max_epochs, "final_score": 0,
            "final_slot_score": 0,
            "paradigm_shifts": 0, "slot_birthed_total": 0,
            "elapsed_sec": round(wall, 2),
            "belief_summary": {},
            "use_slots": (mode == "belief"),
        }
    result["trial"] = trial
    result["wall_sec"] = round(wall, 2)
    return result


def result_to_csv_row(r: dict) -> dict:
    bs = r.get("belief_summary") or {}
    return {
        "level": r.get("level", ""),
        "mode": r.get("mode", ""),
        "model": r.get("model", ""),
        "trial": r.get("trial", 0),
        "use_slots": r.get("use_slots", False),
        "solved": bool(r.get("solved")),
        "solved_epoch": r.get("solved_epoch") or "",
        "epochs_run": r.get("epochs_run") or r.get("max_epochs", ""),
        "final_kw_score": r.get("final_score", 0),
        "final_slot_score": r.get("final_slot_score", 0),
        "total_beliefs": bs.get("total_beliefs", 0),
        "paradigm_shifts": r.get("paradigm_shifts", 0),
        "slot_birthed_total": r.get("slot_birthed_total", 0),
        "gap_count": bs.get("gap_count", 0),
        "total_tension": bs.get("total_tension", 0),
        "hints_used": r.get("hints_used", 0),
        "elapsed_sec": r.get("elapsed_sec", 0),
    }


def parse_args():
    ap = argparse.ArgumentParser(description="Phase D three-claim grid")
    ap.add_argument("--models", type=str, default=",".join(DEFAULT_MODELS))
    ap.add_argument("--modes", type=str, default=",".join(DEFAULT_MODES))
    ap.add_argument("--levels", type=str, default=",".join(DEFAULT_LEVELS))
    ap.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    ap.add_argument("--max-epochs", type=int, default=DEFAULT_MAX_EPOCHS)
    ap.add_argument("--stop-on", choices=["kw", "slot"], default="slot",
                    help="Pass/fail verifier per cell (default: slot).")
    ap.add_argument("--nudge", action="store_true",
                    help="Enable Holden nudges (off by default).")
    ap.add_argument("--out", type=str, default=str(CSV_OUT))
    return ap.parse_args()


def main():
    args = parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    levels = [l.strip() for l in args.levels.split(",") if l.strip()]
    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    cells = [(lv, mo, model, tr)
             for lv in levels
             for mo in modes
             for model in models
             for tr in range(1, args.trials + 1)]

    print(f"Phase D grid: {len(cells)} cells "
          f"= {len(levels)} levels x {len(modes)} modes "
          f"x {len(models)} models x {args.trials} trials")
    print(f"  stop_on={args.stop_on}  max_epochs={args.max_epochs}  nudge={args.nudge}")
    print(f"  CSV -> {out_csv}")
    print("-" * 72)

    fieldnames = [
        "level", "mode", "model", "trial", "use_slots",
        "solved", "solved_epoch", "epochs_run",
        "final_kw_score", "final_slot_score",
        "total_beliefs", "paradigm_shifts", "slot_birthed_total",
        "gap_count", "total_tension", "hints_used", "elapsed_sec",
    ]
    writer_file = open(out_csv, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(writer_file, fieldnames=fieldnames)
    writer.writeheader()
    writer_file.flush()

    start = time.time()
    for i, (level, mode, model, trial) in enumerate(cells, 1):
        print(f"\n[{i}/{len(cells)}] level={level}  mode={mode}  "
              f"model={model}  trial={trial}")
        r = run_cell(level, mode, model, trial,
                     args.max_epochs, args.stop_on, args.nudge,
                     verbose=True)
        row = result_to_csv_row(r)
        writer.writerow(row)
        writer_file.flush()
        total_slot = row["final_slot_score"]
        total_denom = 6 if level == "hardest_bug" else 5
        print(f"  -> solved={row['solved']}  "
              f"kw={row['final_kw_score']}  slot={total_slot}/{total_denom}  "
              f"epochs={row['epochs_run']}  beliefs={row['total_beliefs']}  "
              f"wall={row['elapsed_sec']}s")
    writer_file.close()
    elapsed = time.time() - start
    print("-" * 72)
    print(f"grid complete: {len(cells)} cells in {elapsed/60:.1f} min  ->  {out_csv}")


if __name__ == "__main__":
    main()
