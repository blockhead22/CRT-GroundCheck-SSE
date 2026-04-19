"""Head-to-head benchmark: scaffold modes vs Docker escape levels.

Grid: levels × modes × trials, one docker_escape.py subprocess per cell.

Modes:
  flat    — base ExplorationTree (no CRT math)
  gravity — GravityExplorationTree (mass/tension/gravity navigation)
  belief  — BeliefExplorationTree (Belnap + trust decay + cascade → actions)

Metrics captured per cell:
  escaped, epochs_to_escape, holden_interventions, total_beliefs,
  paradigm_shifts, facts, first_action_epoch (first non-seed action).

Outputs:
  results/raw/benchmark_escape.csv         — row per cell
  results/raw/benchmark_escape.json        — full per-cell records
  results/charts/benchmark_escape.png      — matplotlib chart
  results/raw/benchmark_logs/<cell>.log    — captured stdout per cell

Usage:
  python benchmark_escape.py --run              # run the grid
  python benchmark_escape.py --plot             # plot from existing CSV
  python benchmark_escape.py --run --plot       # both
  python benchmark_escape.py --levels L5_hardened L5_misconfigured --trials 2
  python benchmark_escape.py --modes belief gravity --trials 3

Defaults to --trials 3 on all 6 levels × 3 modes = 54 runs.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths and config
# ---------------------------------------------------------------------------
LAB_DIR = Path(__file__).parent
RAW_DIR = LAB_DIR / "results" / "raw"
CHART_DIR = LAB_DIR / "results" / "charts"
LOG_DIR = RAW_DIR / "benchmark_logs"

LOCK_FILE = RAW_DIR / "docker_escape.lock"
RESULTS_FILE = RAW_DIR / "docker_escape_results.json"
DISCOVERY_STATE_FILE = RAW_DIR / "discovery_state.json"

CSV_OUT = RAW_DIR / "benchmark_escape.csv"
JSON_OUT = RAW_DIR / "benchmark_escape.json"
CHART_OUT = CHART_DIR / "benchmark_escape.png"

DEFAULT_LEVELS = [
    "L1_volume_mount",
    "L2_docker_socket",
    "L3_privileged",
    "L4_sys_admin",
    "L5_hardened",
    "L5_misconfigured",
]
DEFAULT_MODES = ["flat", "gravity", "belief"]
MODE_FLAGS = {
    "flat": [],
    "gravity": ["--gravity"],
    "belief": ["--belief"],
    "crt": ["--crt"],
    # LLM-extractor modes. These reuse --belief but recruit an LLM to turn
    # (stdout, stderr, rc) into typed beliefs. "hybrid" = regex first, LLM fills
    # gaps. "llm-only" = LLM is the only extractor.
    "belief-llm3b":        ["--belief", "--llm-extractor", "3b",  "--extractor-mode", "hybrid"],
    "belief-llm14b":       ["--belief", "--llm-extractor", "14b", "--extractor-mode", "hybrid"],
    "belief-llm3b-only":   ["--belief", "--llm-extractor", "3b",  "--extractor-mode", "llm-only"],
    "belief-llm14b-only":  ["--belief", "--llm-extractor", "14b", "--extractor-mode", "llm-only"],
}

CELL_TIMEOUT_S = 900  # 15 min / cell

# Benchmark-only overrides passed to each subprocess. Purpose: make failed-escape
# cells terminate quickly (so we can run the grid in reasonable time) and remove
# Holden (LLM coach) so what we measure is the scaffold-only behavior.
BENCH_MAX_EPOCHS = int(os.getenv("BENCHMARK_MAX_EPOCHS", "15"))
BENCH_SKIP_HOLDEN = os.getenv("SKIP_HOLDEN", "1")


# ---------------------------------------------------------------------------
# Cell runner
# ---------------------------------------------------------------------------
def clear_pre_run_state() -> None:
    """Clear lock, prior results, and prior discovery state for a clean cell."""
    for path in (LOCK_FILE, RESULTS_FILE, DISCOVERY_STATE_FILE):
        if path.exists():
            try:
                path.unlink()
            except OSError as e:
                print(f"  [WARN] could not remove {path}: {e}", flush=True)


def _sanitize_model_tag(model: str) -> str:
    """Turn an Ollama model id (e.g. 'qwen3:14b') into a filesystem-safe tag."""
    return model.replace(":", "-").replace("/", "-")


def run_cell(level: str, mode: str, trial: int,
             executor_model: str | None = None) -> dict:
    """Run one docker_escape.py subprocess and parse its result.

    executor_model: optional Ollama model id passed as MIRUS_MODEL env var.
        When set, the cell_id is tagged with the model so multiple executors
        get distinct logs and CSV rows.
    """
    model_tag = _sanitize_model_tag(executor_model) if executor_model else None
    if model_tag:
        cell_id = f"{level}__{mode}__m-{model_tag}__t{trial}"
    else:
        cell_id = f"{level}__{mode}__t{trial}"
    log_path = LOG_DIR / f"{cell_id}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    clear_pre_run_state()

    cmd = [
        sys.executable, "-u",
        str(LAB_DIR / "docker_escape.py"),
        "--levels", level,
        *MODE_FLAGS[mode],
    ]

    start = time.time()
    print(f"\n=== CELL {cell_id} ===", flush=True)
    print(f"  $ {' '.join(cmd)}", flush=True)
    if executor_model:
        print(f"  MIRUS_MODEL={executor_model}", flush=True)

    env = os.environ.copy()
    env["BENCHMARK_MAX_EPOCHS"] = str(BENCH_MAX_EPOCHS)
    env["SKIP_HOLDEN"] = str(BENCH_SKIP_HOLDEN)
    if executor_model:
        env["MIRUS_MODEL"] = executor_model

    try:
        with open(log_path, "w", encoding="utf-8") as log_f:
            proc = subprocess.run(
                cmd,
                cwd=str(LAB_DIR),
                stdout=log_f,
                stderr=subprocess.STDOUT,
                timeout=CELL_TIMEOUT_S,
                text=True,
                env=env,
            )
        wall_s = time.time() - start
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        wall_s = time.time() - start
        rc = -1
        print(f"  [TIMEOUT] cell exceeded {CELL_TIMEOUT_S}s", flush=True)

    # Parse per-run results JSON (written by docker_escape.run())
    record = {
        "level": level,
        "mode": mode,
        "executor_model": executor_model or "llama3.2:latest",
        "trial": trial,
        "wall_s": round(wall_s, 2),
        "returncode": rc,
        "escaped": False,
        "epochs": None,
        "epochs_to_escape": None,
        "first_action_epoch": None,
        "holden_interventions": None,
        "total_beliefs": None,
        "paradigm_shifts": None,
        "facts": None,
        "log_path": str(log_path),
    }

    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  [WARN] parse fail {RESULTS_FILE}: {e}", flush=True)
            data = []

        # Find the entry for this level (should be exactly one)
        for r in data:
            if r.get("level") == level:
                record["escaped"] = bool(r.get("escaped"))
                record["epochs"] = r.get("epochs")
                record["holden_interventions"] = r.get("holden_interventions")
                # First successful-escape epoch within epoch_log
                for ep in r.get("epoch_log", []):
                    if ep.get("escaped"):
                        record["epochs_to_escape"] = ep.get("epoch")
                        break
                # First action where who == 'mirus' (all are mirus today, so = epoch 1)
                for ep in r.get("epoch_log", []):
                    if ep.get("who") == "mirus":
                        record["first_action_epoch"] = ep.get("epoch")
                        break
                tree_sum = r.get("tree_summary", {}) or {}
                record["paradigm_shifts"] = tree_sum.get("paradigm_shifts")
                record["facts"] = tree_sum.get("total_facts")
                belief_state = tree_sum.get("belief_state") or {}
                record["total_beliefs"] = belief_state.get("total_beliefs")
                break

    status = "ESCAPED" if record["escaped"] else "FAILED"
    print(
        f"  -> {status} epochs={record['epochs']} "
        f"ete={record['epochs_to_escape']} beliefs={record['total_beliefs']} "
        f"shifts={record['paradigm_shifts']} rc={rc} wall={wall_s:.1f}s",
        flush=True,
    )
    return record


# ---------------------------------------------------------------------------
# Grid orchestration
# ---------------------------------------------------------------------------
def append_csv_header_if_needed(rows: list[dict]) -> None:
    if not rows:
        return
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    need_header = not CSV_OUT.exists()
    with open(CSV_OUT, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if need_header:
            writer.writeheader()
        writer.writerows(rows)


def _load_existing_cells() -> tuple[list[dict], set[tuple[str, str, int]]]:
    """Load prior CSV rows so we can resume mid-grid without re-running cells.

    Coerces numeric columns and the boolean "escaped" column so the final
    summary loop (which sums epochs_to_escape) doesn't choke on strings
    from DictReader. Leaves unparseable cells as None.
    """
    rows: list[dict] = []
    keys: set[tuple[str, str, int]] = set()
    if not CSV_OUT.exists():
        return rows, keys
    int_cols = (
        "trial", "returncode", "epochs", "epochs_to_escape",
        "first_action_epoch", "holden_interventions",
        "total_beliefs", "paradigm_shifts", "facts",
    )
    float_cols = ("wall_s",)
    with open(CSV_OUT, "r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for k in int_cols:
                v = r.get(k)
                r[k] = int(v) if v not in (None, "", "None") else None
            for k in float_cols:
                v = r.get(k)
                r[k] = float(v) if v not in (None, "", "None") else None
            r["escaped"] = str(r.get("escaped")).lower() == "true"
            # Legacy rows may not have executor_model. Default to the baseline
            # executor so the resume dedup key is stable.
            r.setdefault("executor_model", "llama3.2:latest")
            rows.append(r)
            try:
                keys.add((r["level"], r["mode"], r["executor_model"], int(r["trial"])))
            except (KeyError, ValueError, TypeError):
                pass
    return rows, keys


def run_grid(levels: list[str], modes: list[str], trials: int,
             executor_models: list[str] | None = None,
             resume: bool = False) -> list[dict]:
    """Run full grid, flushing CSV + JSON after each cell.

    executor_models: list of Ollama model ids. Each cell is replicated across
        every model in this list (fourth grid dimension). If None, the grid
        runs with whatever docker_escape.py's default MIRUS_MODEL is.
    resume=True keeps the existing CSV and skips any (level,mode,executor,trial)
    cell already present in it. resume=False starts fresh.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    effective_models = list(executor_models) if executor_models else [None]
    if resume:
        all_records, done = _load_existing_cells()
        print(f"[RESUME] {len(done)} prior cells loaded; skipping those", flush=True)
    else:
        if CSV_OUT.exists():
            CSV_OUT.unlink()
        if JSON_OUT.exists():
            JSON_OUT.unlink()
        all_records = []
        done = set()
    total = len(levels) * len(modes) * len(effective_models) * trials
    i = 0
    t0 = time.time()
    for level in levels:
        for mode in modes:
            for exec_model in effective_models:
                dedup_model = exec_model or "llama3.2:latest"
                for trial in range(trials):
                    i += 1
                    if (level, mode, dedup_model, trial) in done:
                        print(
                            f"\n[GRID {i}/{total}] SKIP (already in CSV): "
                            f"level={level} mode={mode} exec={dedup_model} trial={trial}",
                            flush=True,
                        )
                        continue
                    print(
                        f"\n[GRID {i}/{total}] level={level} mode={mode} "
                        f"exec={dedup_model} trial={trial} "
                        f"elapsed={time.time()-t0:.0f}s",
                        flush=True,
                    )
                    rec = run_cell(level, mode, trial, executor_model=exec_model)
                    all_records.append(rec)
                    append_csv_header_if_needed([rec])
                    with open(JSON_OUT, "w", encoding="utf-8") as f:
                        json.dump(all_records, f, indent=2, default=str)

    # Final summary
    print(f"\n{'='*60}", flush=True)
    print("BENCHMARK SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    for level in levels:
        for mode in modes:
            for exec_model in effective_models:
                dedup_model = exec_model or "llama3.2:latest"
                cells = [r for r in all_records
                         if r["level"] == level and r["mode"] == mode
                         and r.get("executor_model", "llama3.2:latest") == dedup_model]
                if not cells:
                    continue
                n_esc = sum(1 for r in cells if r["escaped"])
                ete = [r["epochs_to_escape"] for r in cells
                       if r["epochs_to_escape"] is not None]
                avg_ete = (sum(ete) / len(ete)) if ete else None
                print(
                    f"  {level:20s} {mode:16s} {dedup_model:24s} "
                    f"escape={n_esc}/{len(cells)}  avg_ete={avg_ete}",
                    flush=True,
                )
    return all_records


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_from_csv(csv_path: Path | None = None, out_path: Path | None = None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import statistics

    src = csv_path or CSV_OUT
    dst = out_path or CHART_OUT
    if not src.exists():
        print(f"  [PLOT] no csv at {src}", flush=True)
        return

    rows: list[dict] = []
    with open(src, "r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            # Type coercion for numerics
            for k in ("epochs", "epochs_to_escape", "holden_interventions",
                      "total_beliefs", "paradigm_shifts", "facts",
                      "first_action_epoch", "trial", "returncode"):
                v = r.get(k)
                r[k] = int(v) if v not in (None, "", "None") else None
            for k in ("wall_s",):
                v = r.get(k)
                r[k] = float(v) if v not in (None, "", "None") else None
            r["escaped"] = str(r.get("escaped")).lower() == "true"
            rows.append(r)

    if not rows:
        print("  [PLOT] empty csv", flush=True)
        return

    # Aggregate
    levels = []
    for r in rows:
        if r["level"] not in levels:
            levels.append(r["level"])
    modes = []
    for r in rows:
        if r["mode"] not in modes:
            modes.append(r["mode"])

    # Make the level order deterministic (follow DEFAULT_LEVELS if possible)
    levels = [L for L in DEFAULT_LEVELS if L in levels] + [
        L for L in levels if L not in DEFAULT_LEVELS
    ]
    modes = [m for m in DEFAULT_MODES if m in modes] + [
        m for m in modes if m not in DEFAULT_MODES
    ]

    fig, (ax_ete, ax_rate, ax_beliefs) = plt.subplots(
        1, 3, figsize=(18, 5.5), sharex=False
    )

    x = list(range(len(levels)))
    colors = {
        "flat": "#888888",
        "gravity": "#1f77b4",
        "belief": "#d62728",
        "crt": "#2ca02c",
        "belief-llm3b": "#ff7f0e",
        "belief-llm14b": "#9467bd",
        "belief-llm3b-only": "#ffbb78",
        "belief-llm14b-only": "#c5b0d5",
    }
    markers = {
        "flat": "o",
        "gravity": "s",
        "belief": "^",
        "crt": "D",
        "belief-llm3b": "P",
        "belief-llm14b": "X",
        "belief-llm3b-only": "p",
        "belief-llm14b-only": "*",
    }
    # Sentinel for failed-to-escape runs: use the actual MAX_EPOCHS observed in
    # the CSV (max of all epochs values) so the "failed = max" interpretation is
    # consistent whether runs used BENCHMARK_MAX_EPOCHS=15 or the default 50.
    _epoch_vals = [r["epochs"] for r in rows if r["epochs"] is not None]
    max_epochs_sentinel = max(_epoch_vals) if _epoch_vals else 50

    # --- Subplot 1: epochs-to-escape (mean ± stdev; failed runs = MAX_EPOCHS) ---
    for mode in modes:
        means, errs = [], []
        for L in levels:
            cells = [r for r in rows if r["mode"] == mode and r["level"] == L]
            vals = []
            for r in cells:
                if r["escaped"] and r["epochs_to_escape"] is not None:
                    vals.append(r["epochs_to_escape"])
                else:
                    vals.append(max_epochs_sentinel)
            if not vals:
                means.append(float("nan")); errs.append(0.0)
            else:
                means.append(sum(vals) / len(vals))
                errs.append(statistics.pstdev(vals) if len(vals) > 1 else 0.0)
        ax_ete.errorbar(
            x, means, yerr=errs, marker=markers.get(mode, "o"),
            color=colors.get(mode, "black"), label=mode,
            capsize=4, linewidth=2, markersize=8,
        )
    ax_ete.set_xticks(x)
    ax_ete.set_xticklabels([L.replace("_", "\n") for L in levels], fontsize=8)
    ax_ete.set_ylabel("epochs to escape (lower = better)")
    ax_ete.set_title(f"Escape speed per mode\n(failed runs = {max_epochs_sentinel} = MAX_EPOCHS)")
    ax_ete.axhline(max_epochs_sentinel, color="gray", linestyle=":", alpha=0.5)
    ax_ete.grid(True, alpha=0.3)
    ax_ete.legend(loc="upper left")

    # --- Subplot 2: escape success rate ---
    width = 0.25
    offsets = {m: (i - (len(modes) - 1) / 2) * width for i, m in enumerate(modes)}
    for mode in modes:
        rates = []
        for L in levels:
            cells = [r for r in rows if r["mode"] == mode and r["level"] == L]
            rates.append(
                (sum(1 for r in cells if r["escaped"]) / len(cells)) if cells else 0.0
            )
        ax_rate.bar(
            [xi + offsets[mode] for xi in x], rates, width=width,
            color=colors.get(mode, "black"), label=mode, edgecolor="black", linewidth=0.5,
        )
    ax_rate.set_xticks(x)
    ax_rate.set_xticklabels([L.replace("_", "\n") for L in levels], fontsize=8)
    ax_rate.set_ylabel("escape success rate")
    ax_rate.set_ylim(0, 1.05)
    ax_rate.set_title("Escape rate per mode")
    ax_rate.grid(True, alpha=0.3, axis="y")
    ax_rate.legend(loc="upper left")

    # --- Subplot 3: total beliefs accumulated ---
    for mode in modes:
        means, errs = [], []
        for L in levels:
            cells = [r for r in rows if r["mode"] == mode and r["level"] == L]
            vals = [r["total_beliefs"] for r in cells if r["total_beliefs"] is not None]
            if not vals:
                means.append(0.0); errs.append(0.0)
            else:
                means.append(sum(vals) / len(vals))
                errs.append(statistics.pstdev(vals) if len(vals) > 1 else 0.0)
        ax_beliefs.errorbar(
            x, means, yerr=errs, marker=markers.get(mode, "o"),
            color=colors.get(mode, "black"), label=mode,
            capsize=4, linewidth=2, markersize=8,
        )
    ax_beliefs.set_xticks(x)
    ax_beliefs.set_xticklabels([L.replace("_", "\n") for L in levels], fontsize=8)
    ax_beliefs.set_ylabel("total beliefs at terminus")
    ax_beliefs.set_title("Epistemic accumulation per mode")
    ax_beliefs.grid(True, alpha=0.3)
    ax_beliefs.legend(loc="upper left")

    fig.suptitle(
        "Scaffold mode comparison: Docker escape benchmark",
        fontsize=14, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    dst.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dst, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] saved {dst}", flush=True)


# ---------------------------------------------------------------------------
# Cross-model plot: claim-3 persistence across executor swaps
# ---------------------------------------------------------------------------
def plot_cross_model_from_csv(
    csv_path: Path | None = None,
    out_path: Path | None = None,
    target_mode: str = "belief",
) -> None:
    """Plot escape metrics for ONE scaffold mode, split by executor_model.

    This is the claim-3 chart: if the substrate persists across model swaps,
    all lines in the left panel cluster tightly; if substrate is model-dependent,
    lines fan out.

    Reads the same CSV as plot_from_csv but filters to rows where mode==target_mode.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import statistics

    src = csv_path or CSV_OUT
    dst_default = CHART_DIR / "benchmark_cross_model.png"
    dst = out_path or dst_default
    if not src.exists():
        print(f"  [CROSS-PLOT] no csv at {src}", flush=True)
        return

    rows: list[dict] = []
    with open(src, "r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("mode") != target_mode:
                continue
            for k in ("epochs", "epochs_to_escape", "holden_interventions",
                      "total_beliefs", "paradigm_shifts", "facts",
                      "first_action_epoch", "trial", "returncode"):
                v = r.get(k)
                r[k] = int(v) if v not in (None, "", "None") else None
            for k in ("wall_s",):
                v = r.get(k)
                r[k] = float(v) if v not in (None, "", "None") else None
            r["escaped"] = str(r.get("escaped")).lower() == "true"
            r.setdefault("executor_model", "llama3.2:latest")
            rows.append(r)

    if not rows:
        print(f"  [CROSS-PLOT] no rows with mode={target_mode}", flush=True)
        return

    levels = [L for L in DEFAULT_LEVELS
              if L in {r["level"] for r in rows}]
    models = []
    for r in rows:
        if r["executor_model"] not in models:
            models.append(r["executor_model"])
    # Deterministic ordering: baseline first
    baseline = "llama3.2:latest"
    if baseline in models:
        models = [baseline] + [m for m in models if m != baseline]

    # Color per model (distinct tableau colors)
    tableau = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]
    model_colors = {m: tableau[i % len(tableau)] for i, m in enumerate(models)}
    model_markers = {m: ("o", "s", "^", "D", "P", "X", "*", "p")[i % 8]
                     for i, m in enumerate(models)}

    _epoch_vals = [r["epochs"] for r in rows if r["epochs"] is not None]
    max_epochs_sentinel = max(_epoch_vals) if _epoch_vals else 50

    fig, (ax_ete, ax_rate, ax_wall) = plt.subplots(
        1, 3, figsize=(18, 5.5), sharex=False
    )
    x = list(range(len(levels)))

    # --- Subplot 1: epochs-to-escape per (level, executor_model) ---
    for m in models:
        means, errs = [], []
        for L in levels:
            cells = [r for r in rows
                     if r["executor_model"] == m and r["level"] == L]
            vals = []
            for r in cells:
                if r["escaped"] and r["epochs_to_escape"] is not None:
                    vals.append(r["epochs_to_escape"])
                else:
                    vals.append(max_epochs_sentinel)
            if not vals:
                means.append(float("nan")); errs.append(0.0)
            else:
                means.append(sum(vals) / len(vals))
                errs.append(statistics.pstdev(vals) if len(vals) > 1 else 0.0)
        ax_ete.errorbar(
            x, means, yerr=errs, marker=model_markers[m],
            color=model_colors[m], label=m,
            capsize=4, linewidth=2, markersize=8,
        )
    ax_ete.set_xticks(x)
    ax_ete.set_xticklabels([L.replace("_", "\n") for L in levels], fontsize=8)
    ax_ete.set_ylabel("epochs to escape (lower = better)")
    ax_ete.set_title(f"Claim 3: persistence across executor models ({target_mode} scaffold)\n"
                     f"(failed = {max_epochs_sentinel} = MAX_EPOCHS; "
                     f"tight clustering = substrate persists)")
    ax_ete.axhline(max_epochs_sentinel, color="gray", linestyle=":", alpha=0.5)
    ax_ete.grid(True, alpha=0.3)
    ax_ete.legend(loc="upper left", fontsize=8)

    # --- Subplot 2: escape success rate per (level, executor_model) ---
    width = 0.8 / max(len(models), 1)
    offsets = {m: (i - (len(models) - 1) / 2) * width
               for i, m in enumerate(models)}
    for m in models:
        rates = []
        for L in levels:
            cells = [r for r in rows
                     if r["executor_model"] == m and r["level"] == L]
            rates.append(
                (sum(1 for r in cells if r["escaped"]) / len(cells)) if cells else 0.0
            )
        ax_rate.bar(
            [xi + offsets[m] for xi in x], rates, width=width,
            color=model_colors[m], label=m,
            edgecolor="black", linewidth=0.5,
        )
    ax_rate.set_xticks(x)
    ax_rate.set_xticklabels([L.replace("_", "\n") for L in levels], fontsize=8)
    ax_rate.set_ylabel("escape success rate")
    ax_rate.set_ylim(0, 1.05)
    ax_rate.set_title("Escape rate per executor model")
    ax_rate.grid(True, alpha=0.3, axis="y")
    ax_rate.legend(loc="upper left", fontsize=8)

    # --- Subplot 3: wall time per cell per (level, executor_model) ---
    for m in models:
        means, errs = [], []
        for L in levels:
            cells = [r for r in rows
                     if r["executor_model"] == m and r["level"] == L]
            vals = [r["wall_s"] for r in cells if r.get("wall_s") is not None]
            if not vals:
                means.append(0.0); errs.append(0.0)
            else:
                means.append(sum(vals) / len(vals))
                errs.append(statistics.pstdev(vals) if len(vals) > 1 else 0.0)
        ax_wall.errorbar(
            x, means, yerr=errs, marker=model_markers[m],
            color=model_colors[m], label=m,
            capsize=4, linewidth=2, markersize=8,
        )
    ax_wall.set_xticks(x)
    ax_wall.set_xticklabels([L.replace("_", "\n") for L in levels], fontsize=8)
    ax_wall.set_ylabel("wall time (s)")
    ax_wall.set_title("Per-cell wall time (executor speed)")
    ax_wall.grid(True, alpha=0.3)
    ax_wall.legend(loc="upper left", fontsize=8)

    fig.suptitle(
        f"Cross-model persistence: Docker escape ({target_mode} scaffold, "
        f"executor swap)",
        fontsize=14, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    dst.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dst, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  [CROSS-PLOT] saved {dst}", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="Run the grid")
    ap.add_argument("--plot", action="store_true", help="Plot from existing CSV")
    ap.add_argument("--plot-cross-model", action="store_true",
                    help="Plot the cross-model persistence chart (claim 3) from CSV")
    ap.add_argument("--target-mode", default="belief",
                    help="Which scaffold mode to slice for the cross-model plot "
                         "(default: belief)")
    ap.add_argument("--resume", action="store_true",
                    help="Keep existing CSV and skip (level,mode,trial) cells already in it")
    ap.add_argument("--levels", nargs="+", default=DEFAULT_LEVELS)
    ap.add_argument("--modes", nargs="+", default=DEFAULT_MODES,
                    choices=list(MODE_FLAGS.keys()))
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--executor-models", nargs="+", default=None,
                    help="Ollama model ids used as Mirus executor (MIRUS_MODEL "
                         "env var). Each model multiplies the grid. Example: "
                         "--executor-models llama3.2:latest phi3:3.8b mistral:latest "
                         "qwen3:14b. If omitted, uses docker_escape.py's default.")
    ap.add_argument("--csv", type=str, default=None,
                    help="Override CSV path for --plot (e.g. a snapshot)")
    ap.add_argument("--out", type=str, default=None,
                    help="Override output PNG path for --plot")
    args = ap.parse_args()

    if not (args.run or args.plot or args.plot_cross_model):
        ap.error("pass --run and/or --plot and/or --plot-cross-model")

    if args.run:
        run_grid(args.levels, args.modes, args.trials,
                 executor_models=args.executor_models,
                 resume=args.resume)
    if args.plot:
        csv_path = Path(args.csv) if args.csv else None
        out_path = Path(args.out) if args.out else None
        plot_from_csv(csv_path=csv_path, out_path=out_path)
    if args.plot_cross_model:
        csv_path = Path(args.csv) if args.csv else None
        out_path = Path(args.out) if args.out else None
        plot_cross_model_from_csv(
            csv_path=csv_path, out_path=out_path,
            target_mode=args.target_mode,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
