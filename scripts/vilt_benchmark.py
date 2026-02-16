"""
VILT Benchmark — Automated VILT vs SFT Comparison
===================================================

Orchestrates training runs across profiles and models, then produces a
comparison table proving VILT (verification pressure) beats standard SFT.

For each profile × model, it runs:
  1. SFT baseline (--baseline, contradiction_weight=0)
  2. VILT training (full verification pressure)
  3. Evaluates both on the profile's eval queries
  4. Collects metrics and produces a comparison table

Usage:
  python scripts/vilt_benchmark.py                              # default: Qwen2.5-3B, all profiles
  python scripts/vilt_benchmark.py --model Qwen/Qwen2.5-1.5B   # specific model
  python scripts/vilt_benchmark.py --profile alex_denver         # single profile
  python scripts/vilt_benchmark.py --skip-training               # just regenerate tables from existing metrics
  python scripts/vilt_benchmark.py --steps 100                   # custom step count
"""

from __future__ import annotations

import json
import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "benchmark_results"

# Use venv Python if available, else system Python
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"  # Linux/Mac
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

AVAILABLE_MODELS = [
    "Qwen/Qwen2.5-3B",
    "Qwen/Qwen2.5-1.5B",
    "HuggingFaceTB/SmolLM-135M",
]


def discover_profiles() -> list[dict]:
    """Find all generated profiles in data/."""
    profiles = []
    for fp in sorted(DATA_DIR.glob("vilt_facts_*.json")):
        name = fp.stem.replace("vilt_facts_", "")
        training_path = DATA_DIR / f"vilt_training_{name}.json"
        queries_path = DATA_DIR / f"vilt_test_queries_{name}.json"

        if not training_path.exists():
            print(f"  WARNING: {training_path.name} missing, skipping profile '{name}'")
            continue

        profiles.append({
            "name": name,
            "facts": str(fp),
            "training": str(training_path),
            "queries": str(queries_path) if queries_path.exists() else None,
        })

    return profiles


def run_training(
    model: str,
    profile: dict,
    baseline: bool,
    steps: int,
    extra_args: list[str] | None = None,
) -> dict | None:
    """Run a single training job and return metrics."""
    mode = "SFT baseline" if baseline else "VILT"
    profile_name = profile["name"]
    model_short = model.split("/")[-1].lower()
    suffix = "_sft_baseline" if baseline else ""
    # Include profile in output dir
    out_dir = MODELS_DIR / f"vilt_{model_short}_{profile_name}{suffix}"

    print(f"\n{'='*70}")
    print(f"  TRAINING: {mode} | {model} | profile={profile_name}")
    print(f"  Output:   {out_dir.name}")
    print(f"{'='*70}")

    cmd = [
        PYTHON, str(PROJECT_ROOT / "scripts" / "vilt_scaled.py"),
        "--model", model,
        "--steps", str(steps),
        "--facts", profile["facts"],
        "--training", profile["training"],
        "--output-dir", str(out_dir),
    ]
    if profile["queries"]:
        cmd += ["--test-queries", profile["queries"]]
    if baseline:
        cmd.append("--baseline")
    if extra_args:
        cmd.extend(extra_args)

    t0 = time.time()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=False,  # let output stream to console
        env=env,
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"\n  ERROR: Training failed with exit code {result.returncode}")
        return None

    # Read metrics
    metrics_path = out_dir / "vilt_metrics.json"
    if not metrics_path.exists():
        # Try without profile name in dir (fallback)
        alt_dir = MODELS_DIR / f"vilt_{model_short}{suffix}"
        metrics_path = alt_dir / "vilt_metrics.json"

    if not metrics_path.exists():
        print(f"\n  ERROR: Metrics not found at {metrics_path}")
        return None

    with open(metrics_path) as f:
        metrics = json.load(f)

    metrics["profile"] = profile_name
    metrics["elapsed_wall_s"] = elapsed
    return metrics


def generate_comparison_table(all_metrics: list[dict]) -> str:
    """Generate a markdown comparison table from metrics."""
    lines = []
    lines.append("# VILT Benchmark Results")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Group by (profile, model)
    from collections import defaultdict
    groups = defaultdict(dict)
    for m in all_metrics:
        key = (m.get("profile", "?"), m.get("model", "?"))
        mode = m.get("mode", "vilt")
        groups[key][mode] = m

    # Summary table
    lines.append("## Summary: VILT vs SFT Baseline")
    lines.append("")
    lines.append("| Profile | Model | Mode | Pre-Acc | Post-Acc | Best-Acc | Pre-GC | Post-GC | Hallu | Steps | Time |")
    lines.append("|---------|-------|------|---------|----------|----------|--------|---------|-------|-------|------|")

    for (profile, model), modes in sorted(groups.items()):
        model_short = model.split("/")[-1]
        for mode_name in ["sft_baseline", "vilt"]:
            m = modes.get(mode_name)
            if not m:
                continue
            label = "SFT" if mode_name == "sft_baseline" else "**VILT**"
            pre_acc = f"{m['pre_accuracy']:.0%}"
            post_acc = f"{m['post_accuracy']:.0%}"
            best_acc = f"{m['best_accuracy']:.0%}"
            pre_gc = f"{m['pre_gc_pass']:.0%}"
            post_gc = f"{m['post_gc_pass']:.0%}"
            hallu = m.get("post_hallu", "?")
            steps = m.get("num_steps", "?")
            time_s = m.get("total_time_s", m.get("elapsed_wall_s", 0))
            time_str = f"{time_s/60:.1f}m" if time_s else "?"
            lines.append(
                f"| {profile} | {model_short} | {label} | {pre_acc} | {post_acc} | "
                f"{best_acc} | {pre_gc} | {post_gc} | {hallu} | {steps} | {time_str} |"
            )

    # Delta table
    lines.append("")
    lines.append("## Deltas: VILT Improvement over SFT")
    lines.append("")
    lines.append("| Profile | Model | Acc Delta | GC Delta | Hallu Delta | Verdict |")
    lines.append("|---------|-------|-----------|----------|-------------|---------|")

    for (profile, model), modes in sorted(groups.items()):
        model_short = model.split("/")[-1]
        sft = modes.get("sft_baseline")
        vilt = modes.get("vilt")
        if not sft or not vilt:
            continue

        acc_d = vilt["post_accuracy"] - sft["post_accuracy"]
        gc_d = vilt["post_gc_pass"] - sft["post_gc_pass"]
        hallu_d = vilt.get("post_hallu", 0) - sft.get("post_hallu", 0)

        if acc_d > 0.05 and gc_d > 0.05:
            verdict = "VILT wins"
        elif acc_d > 0 or gc_d > 0:
            verdict = "VILT slight edge"
        elif acc_d == 0 and gc_d == 0:
            verdict = "Tie"
        else:
            verdict = "SFT wins (?)"

        lines.append(
            f"| {profile} | {model_short} | {acc_d:+.0%} | {gc_d:+.0%} | "
            f"{hallu_d:+d} | **{verdict}** |"
        )

    # Detailed per-profile results
    lines.append("")
    lines.append("## Detailed Results")
    lines.append("")
    for m in all_metrics:
        profile = m.get("profile", "?")
        model_short = m.get("model", "?").split("/")[-1]
        mode = m.get("mode", "vilt")
        label = "SFT Baseline" if mode == "sft_baseline" else "VILT"

        lines.append(f"### {profile} / {model_short} / {label}")
        lines.append(f"- Trainable params: {m.get('trainable_params', '?'):,}")
        lines.append(f"- LoRA rank: {m.get('lora_r', '?')}")
        lines.append(f"- Learning rate: {m.get('learning_rate', '?')}")
        lines.append(f"- Accuracy: {m['pre_accuracy']:.0%} -> {m['post_accuracy']:.0%} (best: {m['best_accuracy']:.0%} at step {m.get('best_step', '?')})")
        lines.append(f"- GC Pass: {m['pre_gc_pass']:.0%} -> {m['post_gc_pass']:.0%}")
        lines.append(f"- Grounded: {m.get('pre_grounded', '?')} -> {m.get('post_grounded', '?')}")
        lines.append(f"- Hallucinated: {m.get('pre_hallu', '?')} -> {m.get('post_hallu', '?')}")
        lines.append(f"- N test queries: {m.get('n_test_queries', '?')}")
        lines.append(f"- Training steps: {m.get('num_steps', '?')} (early_stop={m.get('stopped_early', '?')})")
        lines.append(f"- Training time: {m.get('total_time_s', 0)/60:.1f} min")
        cfg = m.get("config", {})
        lines.append(f"- Contradiction weight: {cfg.get('cw', '?')}")
        lines.append("")

    return "\n".join(lines)


def collect_existing_metrics() -> list[dict]:
    """Scan models/ for existing vilt_metrics.json files."""
    metrics = []
    for mp in sorted(MODELS_DIR.glob("vilt_*/vilt_metrics.json")):
        with open(mp) as f:
            m = json.load(f)
        # Infer profile from dir name if not in metrics
        dirname = mp.parent.name
        if "profile" not in m:
            # e.g., vilt_qwen2.5-3b_alex_denver or vilt_qwen2.5-3b_alex_denver_sft_baseline
            parts = dirname.split("_", 1)  # ["vilt", "qwen2.5-3b_alex_denver..."]
            if len(parts) > 1:
                rest = parts[1]
                # Find model name by checking known model shorts
                for model in AVAILABLE_MODELS:
                    ms = model.split("/")[-1].lower()
                    if rest.startswith(ms):
                        profile_part = rest[len(ms):].lstrip("_")
                        profile_part = profile_part.replace("_sft_baseline", "")
                        if profile_part:
                            m["profile"] = profile_part
                        break
        metrics.append(m)
    return metrics


def main():
    parser = argparse.ArgumentParser(description="VILT Benchmark — Automated Comparison")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-3B",
                        help="Model to benchmark (default: Qwen/Qwen2.5-3B)")
    parser.add_argument("--profile", type=str, default=None,
                        help="Single profile name to benchmark (default: all)")
    parser.add_argument("--steps", type=int, default=200,
                        help="Training steps per run (default: 200)")
    parser.add_argument("--skip-training", action="store_true",
                        help="Skip training, just regenerate tables from existing metrics")
    parser.add_argument("--skip-sft", action="store_true",
                        help="Skip SFT baseline runs (only run VILT)")
    parser.add_argument("--skip-vilt", action="store_true",
                        help="Skip VILT runs (only run SFT baseline)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  VILT BENCHMARK — Automated VILT vs SFT Comparison")
    print("=" * 70)

    if args.skip_training:
        print("\n  --skip-training: Collecting existing metrics only...")
        all_metrics = collect_existing_metrics()
        print(f"  Found {len(all_metrics)} existing metric files.")
    else:
        # Discover profiles
        profiles = discover_profiles()
        if not profiles:
            print("\n  No profiles found! Run vilt_generate_profiles.py first.")
            print("    python scripts/vilt_generate_profiles.py")
            sys.exit(1)

        if args.profile:
            profiles = [p for p in profiles if p["name"] == args.profile]
            if not profiles:
                print(f"\n  Profile '{args.profile}' not found.")
                sys.exit(1)

        print(f"\n  Profiles: {[p['name'] for p in profiles]}")
        print(f"  Model:    {args.model}")
        print(f"  Steps:    {args.steps}")
        print(f"  Modes:    {'SFT + VILT' if not args.skip_sft and not args.skip_vilt else 'SFT' if args.skip_vilt else 'VILT'}")

        all_metrics = []
        total_t0 = time.time()

        for profile in profiles:
            print(f"\n\n{'#'*70}")
            print(f"  PROFILE: {profile['name']}")
            print(f"    Facts:    {profile['facts']}")
            print(f"    Training: {profile['training']}")
            print(f"    Queries:  {profile['queries'] or '(default)'}")
            print(f"{'#'*70}")

            # Check if eval queries exist, generate if not
            if not profile["queries"]:
                print(f"\n  Generating eval queries for {profile['name']}...")
                queries_out = str(DATA_DIR / f"vilt_test_queries_{profile['name']}.json")
                gen_cmd = [
                    PYTHON, str(PROJECT_ROOT / "scripts" / "vilt_generate_eval.py"),
                    "--facts", profile["facts"],
                    "--output", queries_out,
                    "--offline",
                ]
                subprocess.run(gen_cmd, cwd=str(PROJECT_ROOT))
                if Path(queries_out).exists():
                    profile["queries"] = queries_out
                else:
                    print(f"  WARNING: Failed to generate queries, using defaults")

            # Run SFT baseline
            if not args.skip_sft:
                m = run_training(args.model, profile, baseline=True, steps=args.steps)
                if m:
                    all_metrics.append(m)

            # Run VILT
            if not args.skip_vilt:
                m = run_training(args.model, profile, baseline=False, steps=args.steps)
                if m:
                    all_metrics.append(m)

        total_time = time.time() - total_t0
        print(f"\n\n  Total benchmark time: {total_time/60:.1f} min")

    if not all_metrics:
        print("\n  No metrics collected. Nothing to report.")
        sys.exit(1)

    # Generate comparison table
    table = generate_comparison_table(all_metrics)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"benchmark_{timestamp}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(table)
    print(f"\n  Report saved: {report_path}")

    # Also save raw metrics
    raw_path = RESULTS_DIR / f"benchmark_{timestamp}_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"  Raw data:  {raw_path}")

    # Print table to console
    print(f"\n{'='*70}")
    print(table)
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
