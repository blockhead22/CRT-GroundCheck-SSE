"""
VILT Test Harness — SFT vs ViLT Comparison
============================================

Runs SFT baseline (contradiction_weight=0) and ViLT (contradiction_weight=0.5)
on each available profile using vilt_scaled.py, then generates a comparison
markdown table with delta columns.

Usage:
  python scripts/vilt_test_harness.py                                    # all profiles, SmolLM-135M, 200 steps
  python scripts/vilt_test_harness.py --model Qwen/Qwen2.5-1.5B         # specific model
  python scripts/vilt_test_harness.py --profile alex_denver              # single profile
  python scripts/vilt_test_harness.py --steps 100                        # custom steps
  python scripts/vilt_test_harness.py --skip-existing                    # skip if metrics already exist
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
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "benchmark_results"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

PYTHON = sys.executable


def discover_profiles(filter_name: str | None = None) -> list[dict]:
    """Find all generated profiles in data/."""
    profiles = []
    for fp in sorted(DATA_DIR.glob("vilt_facts_*.json")):
        name = fp.stem.replace("vilt_facts_", "")
        if filter_name and name != filter_name:
            continue
        training_path = DATA_DIR / f"vilt_training_{name}.json"
        queries_path = DATA_DIR / f"vilt_test_queries_{name}.json"

        if not training_path.exists():
            print(f"  SKIP: {training_path.name} missing for profile '{name}'")
            continue
        if not queries_path.exists():
            print(f"  SKIP: {queries_path.name} missing for profile '{name}'")
            continue

        profiles.append({
            "name": name,
            "facts": str(fp),
            "training": str(training_path),
            "queries": str(queries_path),
        })
    return profiles


def run_single(
    model: str,
    profile: dict,
    baseline: bool,
    steps: int,
    output_dir: Path,
    timeout_s: int = 900,
) -> dict | None:
    """Run vilt_scaled.py as a subprocess. Returns parsed metrics or None on failure."""
    mode_label = "SFT" if baseline else "ViLT"
    print(f"\n  [{mode_label}] {profile['name']} | {model} | {steps} steps")
    print(f"    Output -> {output_dir.name}")

    cmd = [
        PYTHON,
        str(SCRIPTS_DIR / "vilt_scaled.py"),
        "--model", model,
        "--steps", str(steps),
        "--facts", profile["facts"],
        "--training", profile["training"],
        "--test-queries", profile["queries"],
        "--output-dir", str(output_dir),
    ]
    if baseline:
        cmd.append("--baseline")

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT after {timeout_s}s")
        return None

    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"    FAILED (exit code {result.returncode})")
        return None

    metrics_path = output_dir / "vilt_metrics.json"
    if not metrics_path.exists():
        print(f"    ERROR: {metrics_path} not found")
        return None

    with open(metrics_path) as f:
        metrics = json.load(f)

    metrics["profile"] = profile["name"]
    metrics["wall_time_s"] = elapsed
    print(f"    OK: acc={metrics['post_accuracy']:.0%}  gc={metrics['post_gc_pass']:.0%}  "
          f"hallu={metrics.get('post_hallu', '?')}  time={elapsed:.0f}s")
    return metrics


def generate_report(all_metrics: list[dict]) -> str:
    """Generate markdown comparison report with delta columns."""
    lines = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# ViLT Test Harness Results")
    lines.append(f"\nGenerated: {ts}")
    lines.append("")

    # Group by profile
    by_profile: dict[str, dict[str, dict]] = defaultdict(dict)
    for m in all_metrics:
        profile = m.get("profile", "unknown")
        mode = m.get("mode", "vilt")
        by_profile[profile][mode] = m

    # ── Main comparison table ──
    lines.append("## SFT vs ViLT Comparison")
    lines.append("")
    lines.append(
        "| Profile | "
        "SFT Acc | ViLT Acc | Delta Acc | "
        "SFT GC | ViLT GC | Delta GC | "
        "SFT Hallu | ViLT Hallu | Delta Hallu | "
        "Verdict |"
    )
    lines.append(
        "|---------|"
        "---------|----------|-----------|"
        "--------|---------|----------|"
        "-----------|------------|-------------|"
        "---------|"
    )

    for profile in sorted(by_profile.keys()):
        modes = by_profile[profile]
        sft = modes.get("sft_baseline")
        vilt = modes.get("vilt")
        if not sft or not vilt:
            # Only one mode ran
            m = sft or vilt
            label = "SFT only" if sft else "ViLT only"
            lines.append(
                f"| {profile} | "
                f"{m['post_accuracy']:.0%} | - | - | "
                f"{m['post_gc_pass']:.0%} | - | - | "
                f"{m.get('post_hallu', '?')} | - | - | "
                f"{label} |"
            )
            continue

        sft_acc = sft["post_accuracy"]
        vilt_acc = vilt["post_accuracy"]
        d_acc = vilt_acc - sft_acc

        sft_gc = sft["post_gc_pass"]
        vilt_gc = vilt["post_gc_pass"]
        d_gc = vilt_gc - sft_gc

        sft_h = sft.get("post_hallu", 0)
        vilt_h = vilt.get("post_hallu", 0)
        d_h = vilt_h - sft_h  # negative is better

        # Verdict
        if d_acc > 0.05 and d_gc >= 0:
            verdict = "**ViLT wins**"
        elif d_acc > 0 or (d_acc == 0 and d_h < 0):
            verdict = "ViLT edge"
        elif d_acc == 0 and d_gc == 0 and d_h == 0:
            verdict = "Tie"
        elif d_acc < -0.05:
            verdict = "SFT wins"
        else:
            verdict = "Mixed"

        lines.append(
            f"| {profile} | "
            f"{sft_acc:.0%} | {vilt_acc:.0%} | {d_acc:+.1%} | "
            f"{sft_gc:.0%} | {vilt_gc:.0%} | {d_gc:+.1%} | "
            f"{sft_h} | {vilt_h} | {d_h:+d} | "
            f"{verdict} |"
        )

    # ── Detailed per-run table ──
    lines.append("")
    lines.append("## Detailed Per-Run Metrics")
    lines.append("")
    lines.append(
        "| Profile | Mode | Model | Pre-Acc | Post-Acc | Best-Acc | "
        "Pre-GC | Post-GC | Pre-Hallu | Post-Hallu | Steps | Early-Stop | Time |"
    )
    lines.append(
        "|---------|------|-------|---------|----------|----------|"
        "--------|---------|-----------|------------|-------|------------|------|"
    )

    for m in all_metrics:
        profile = m.get("profile", "?")
        mode = "SFT" if m.get("mode") == "sft_baseline" else "ViLT"
        model_short = m.get("model", "?").split("/")[-1]
        pre_acc = f"{m['pre_accuracy']:.0%}"
        post_acc = f"{m['post_accuracy']:.0%}"
        best_acc = f"{m['best_accuracy']:.0%}"
        pre_gc = f"{m['pre_gc_pass']:.0%}"
        post_gc = f"{m['post_gc_pass']:.0%}"
        pre_h = m.get("pre_hallu", "?")
        post_h = m.get("post_hallu", "?")
        steps = m.get("num_steps", "?")
        early = "Yes" if m.get("stopped_early") else "No"
        wall = m.get("wall_time_s", m.get("total_time_s", 0))
        time_str = f"{wall / 60:.1f}m"

        lines.append(
            f"| {profile} | {mode} | {model_short} | {pre_acc} | {post_acc} | {best_acc} | "
            f"{pre_gc} | {post_gc} | {pre_h} | {post_h} | {steps} | {early} | {time_str} |"
        )

    # ── Config summary ──
    lines.append("")
    lines.append("## Configuration")
    if all_metrics:
        m0 = all_metrics[0]
        cfg = m0.get("config", {})
        lines.append(f"- Model: {m0.get('model', '?')}")
        lines.append(f"- Total params: {m0.get('total_params', '?'):,}")
        lines.append(f"- Trainable params: {m0.get('trainable_params', '?'):,}")
        lines.append(f"- LoRA rank: {m0.get('lora_r', '?')}")
        lines.append(f"- Learning rate: {m0.get('learning_rate', '?')}")
        lines.append(f"- SFT contradiction_weight: {0.0}")
        lines.append(f"- ViLT contradiction_weight: {cfg.get('cw', 0.5)}")
        lines.append(f"- Brevity weight: {cfg.get('brevity_weight', '?')}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="ViLT Test Harness")
    parser.add_argument("--model", type=str, default="HuggingFaceTB/SmolLM-135M",
                        help="Model (default: SmolLM-135M)")
    parser.add_argument("--profile", type=str, default=None,
                        help="Single profile (default: all)")
    parser.add_argument("--steps", type=int, default=200,
                        help="Training steps (default: 200)")
    parser.add_argument("--timeout", type=int, default=900,
                        help="Per-run timeout in seconds (default: 900)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip runs whose output dir already has metrics")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    profiles = discover_profiles(args.profile)
    if not profiles:
        print("No profiles found. Exiting.")
        sys.exit(1)

    model_short = args.model.split("/")[-1].lower()

    print("=" * 70)
    print("  ViLT TEST HARNESS")
    print(f"  Model:    {args.model}")
    print(f"  Steps:    {args.steps}")
    print(f"  Profiles: {[p['name'] for p in profiles]}")
    print(f"  Timeout:  {args.timeout}s per run")
    print("=" * 70)

    all_metrics = []
    total_t0 = time.time()

    for profile in profiles:
        print(f"\n{'#' * 60}")
        print(f"  PROFILE: {profile['name']}")
        print(f"{'#' * 60}")

        # SFT baseline
        sft_dir = MODELS_DIR / f"vilt_test_sft_{profile['name']}"
        sft_metrics_path = sft_dir / "vilt_metrics.json"
        if args.skip_existing and sft_metrics_path.exists():
            print(f"\n  [SFT] Skipping (metrics exist at {sft_dir.name})")
            with open(sft_metrics_path) as f:
                m = json.load(f)
            m["profile"] = profile["name"]
            all_metrics.append(m)
        else:
            m = run_single(args.model, profile, baseline=True, steps=args.steps,
                           output_dir=sft_dir, timeout_s=args.timeout)
            if m:
                all_metrics.append(m)
            else:
                print(f"    SFT run failed for {profile['name']}")

        # ViLT
        vilt_dir = MODELS_DIR / f"vilt_test_vilt_{profile['name']}"
        vilt_metrics_path = vilt_dir / "vilt_metrics.json"
        if args.skip_existing and vilt_metrics_path.exists():
            print(f"\n  [ViLT] Skipping (metrics exist at {vilt_dir.name})")
            with open(vilt_metrics_path) as f:
                m = json.load(f)
            m["profile"] = profile["name"]
            all_metrics.append(m)
        else:
            m = run_single(args.model, profile, baseline=False, steps=args.steps,
                           output_dir=vilt_dir, timeout_s=args.timeout)
            if m:
                all_metrics.append(m)
            else:
                print(f"    ViLT run failed for {profile['name']}")

    total_time = time.time() - total_t0

    if not all_metrics:
        print("\nNo metrics collected. All runs failed.")
        sys.exit(1)

    # Generate report
    report = generate_report(all_metrics)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"vilt_test_{timestamp}.md"
    raw_path = RESULTS_DIR / f"vilt_test_{timestamp}_raw.json"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"  HARNESS COMPLETE")
    print(f"  Total time: {total_time / 60:.1f} min")
    print(f"  Report:     {report_path}")
    print(f"  Raw JSON:   {raw_path}")
    print(f"{'=' * 70}")
    print()
    print(report)


if __name__ == "__main__":
    main()
