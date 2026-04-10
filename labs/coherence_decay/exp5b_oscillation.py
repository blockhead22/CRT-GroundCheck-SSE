"""Experiment #5b: Trust Oscillation as Correction Predictor

Exp5 showed embedding tension doesn't predict corrections.
Aether's diagnosis: the signal isn't in geometry, it's in trust history.

Question: Do memories with oscillating trust get corrected more often?

Trust oscillation = trust went up then down (or down then up) multiple times.
A memory that oscillates is genuinely contested — the system keeps changing
its mind. That should predict future corrections.

Method:
1. For each memory, extract its trust history from trust_log
2. Count "direction changes" (up→down or down→up)
3. Classify: 0 changes = stable, 1 = single shift, 2+ = oscillating
4. Correlate oscillation count with subsequent corrections
"""

import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import builtins
_real_open = builtins.open

MEMORY_DB = r"D:\AI_round2\personal_agent\crt_memory_shared.db"
LOG_FILE = Path(__file__).parent / "results" / "raw" / "exp5b_oscillation.jsonl"

REAL_CORRECTION_PREFIXES = (
    "slot_demotion",
    "cascade",
    "governance_bridge",
    "contested_cap",
    "tension_conflict",
    "tension_refinement",
    "breathing_loop",
)


def p(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def log(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _real_open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def load_trust_histories():
    """Build per-memory trust change histories from trust_log."""
    conn = sqlite3.connect(MEMORY_DB, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT memory_id, timestamp, old_trust, new_trust, reason
        FROM trust_log
        ORDER BY timestamp ASC
    """).fetchall()
    conn.close()

    histories = defaultdict(list)
    for row in rows:
        histories[row["memory_id"]].append({
            "timestamp": float(row["timestamp"] or 0.0),
            "old_trust": float(row["old_trust"] or 0.0),
            "new_trust": float(row["new_trust"] or 0.0),
            "delta": float(row["new_trust"] or 0.0) - float(row["old_trust"] or 0.0),
            "reason": row["reason"] or "",
        })

    return dict(histories)


def load_memory_texts():
    """Load memory texts for display."""
    conn = sqlite3.connect(MEMORY_DB, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT memory_id, text, trust FROM memories").fetchall()
    conn.close()
    return {row["memory_id"]: {"text": (row["text"] or "")[:80], "trust": float(row["trust"] or 0)} for row in rows}


def count_oscillations(history):
    """Count direction changes in trust history.

    An oscillation = trust goes up then down, or down then up.
    Returns: number of direction changes, total entries, max swing.
    """
    if len(history) < 2:
        return 0, len(history), 0.0

    directions = []
    for entry in history:
        if entry["delta"] > 0.01:
            directions.append("up")
        elif entry["delta"] < -0.01:
            directions.append("down")
        # Skip near-zero changes

    if len(directions) < 2:
        return 0, len(history), 0.0

    changes = 0
    for i in range(1, len(directions)):
        if directions[i] != directions[i - 1]:
            changes += 1

    # Max swing: largest absolute trust delta in history
    max_swing = max(abs(e["delta"]) for e in history) if history else 0.0

    return changes, len(history), max_swing


def has_real_correction(history):
    """Check if this memory has any real (non-routine) correction."""
    for entry in history:
        reason = entry.get("reason", "")
        is_real = any(reason.startswith(prefix) for prefix in REAL_CORRECTION_PREFIXES)
        if entry["delta"] < -0.05 and is_real:
            return True
    return False


def has_any_correction_after(history, after_index):
    """Check if there's a real correction AFTER a certain point in history."""
    for entry in history[after_index:]:
        reason = entry.get("reason", "")
        is_real = any(reason.startswith(prefix) for prefix in REAL_CORRECTION_PREFIXES)
        if entry["delta"] < -0.05 and is_real:
            return True
    return False


def run():
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    p("=" * 60)
    p("EXPERIMENT #5b: Trust Oscillation as Correction Predictor")
    p("=" * 60)
    p(f"Memory DB: {MEMORY_DB}")
    p("Question: Do oscillating memories get corrected more?")
    p("=" * 60)

    # Load data
    p("\nLoading trust histories...")
    histories = load_trust_histories()
    p(f"  {len(histories)} memories have trust history")

    texts = load_memory_texts()

    # Compute oscillation for each memory
    p("\nComputing oscillations...")
    oscillation_data = {}
    for mid, history in histories.items():
        changes, total_entries, max_swing = count_oscillations(history)
        corrected = has_real_correction(history)

        # Predictive test: if oscillation happened in first half of history,
        # did correction happen in second half?
        midpoint = len(history) // 2
        early_changes, _, _ = count_oscillations(history[:midpoint])
        late_correction = has_any_correction_after(history, midpoint) if midpoint > 0 else False

        oscillation_data[mid] = {
            "oscillations": changes,
            "total_entries": total_entries,
            "max_swing": round(max_swing, 4),
            "corrected": corrected,
            "early_oscillation": early_changes > 0,
            "late_correction": late_correction,
            "text": texts.get(mid, {}).get("text", "?"),
            "current_trust": texts.get(mid, {}).get("trust", 0),
        }

    # Classify into groups
    stable = {k: v for k, v in oscillation_data.items() if v["oscillations"] == 0}
    single_shift = {k: v for k, v in oscillation_data.items() if v["oscillations"] == 1}
    oscillating = {k: v for k, v in oscillation_data.items() if v["oscillations"] >= 2}
    highly_oscillating = {k: v for k, v in oscillation_data.items() if v["oscillations"] >= 4}

    p(f"\n  Distribution:")
    p(f"    Stable (0 direction changes): {len(stable)}")
    p(f"    Single shift (1 change):      {len(single_shift)}")
    p(f"    Oscillating (2-3 changes):    {len(oscillating) - len(highly_oscillating)}")
    p(f"    Highly oscillating (4+):      {len(highly_oscillating)}")

    # Correlation: oscillation count vs correction rate
    p(f"\n  CORRECTION RATES BY OSCILLATION:")
    groups = [
        ("Stable (0)", stable),
        ("Single shift (1)", single_shift),
        ("Oscillating (2+)", oscillating),
        ("Highly oscillating (4+)", highly_oscillating),
    ]

    results = []
    for label, group in groups:
        if not group:
            p(f"    {label}: no memories")
            continue
        corrected_count = sum(1 for v in group.values() if v["corrected"])
        rate = corrected_count / len(group)
        results.append({"label": label, "count": len(group), "corrected": corrected_count, "rate": rate})
        p(f"    {label}: {corrected_count}/{len(group)} corrected ({rate:.1%})")

    # Predictive test: early oscillation → late correction
    p(f"\n  PREDICTIVE TEST (early oscillation -> late correction):")
    early_osc_yes = {k: v for k, v in oscillation_data.items() if v["early_oscillation"]}
    early_osc_no = {k: v for k, v in oscillation_data.items() if not v["early_oscillation"] and v["total_entries"] > 2}

    if early_osc_yes:
        late_corr_yes = sum(1 for v in early_osc_yes.values() if v["late_correction"])
        rate_yes = late_corr_yes / len(early_osc_yes)
        p(f"    Early oscillation YES: {late_corr_yes}/{len(early_osc_yes)} got late correction ({rate_yes:.1%})")
    else:
        rate_yes = 0
        p(f"    Early oscillation YES: no memories")

    if early_osc_no:
        late_corr_no = sum(1 for v in early_osc_no.values() if v["late_correction"])
        rate_no = late_corr_no / len(early_osc_no)
        p(f"    Early oscillation NO:  {late_corr_no}/{len(early_osc_no)} got late correction ({rate_no:.1%})")
    else:
        rate_no = 0
        p(f"    Early oscillation NO:  no memories")

    if rate_no > 0:
        pred_ratio = rate_yes / rate_no
        p(f"    PREDICTIVE RATIO: {pred_ratio:.2f}x")
    elif rate_yes > 0:
        pred_ratio = float("inf")
        p(f"    PREDICTIVE RATIO: inf (no late corrections in non-oscillating group)")
    else:
        pred_ratio = 0
        p(f"    PREDICTIVE RATIO: N/A (no corrections in either group)")

    # Show top oscillating memories
    top_osc = sorted(oscillation_data.items(), key=lambda x: x[1]["oscillations"], reverse=True)[:10]
    p(f"\n  TOP 10 MOST OSCILLATING MEMORIES:")
    for mid, data in top_osc:
        corr = "!" if data["corrected"] else " "
        p(f"    [{corr}] osc={data['oscillations']} entries={data['total_entries']} swing={data['max_swing']:.2f} trust={data['current_trust']:.2f} | {data['text']}")

    # Verdict
    p(f"\n{'='*60}")
    p("VERDICT")
    p(f"{'='*60}")

    if results and len(results) >= 2:
        stable_rate = results[0]["rate"] if results[0]["count"] > 0 else 0
        osc_rate = results[2]["rate"] if len(results) > 2 and results[2]["count"] > 0 else 0
        ratio = osc_rate / stable_rate if stable_rate > 0 else float("inf")

        p(f"  Stable correction rate:      {stable_rate:.1%}")
        p(f"  Oscillating correction rate:  {osc_rate:.1%}")
        p(f"  Ratio: {ratio:.2f}x")

        if ratio > 2.0:
            p(f"\n  FINDING: Oscillating memories are {ratio:.1f}x more likely to be corrected.")
            p(f"  Trust oscillation IS a correction predictor. Use it for the breathing loop.")
        elif ratio > 1.3:
            p(f"\n  FINDING: Weak but positive signal ({ratio:.1f}x).")
            p(f"  Oscillation has some predictive value, worth monitoring.")
        else:
            p(f"\n  FINDING: Oscillation does not predict corrections ({ratio:.1f}x).")
            p(f"  Corrections are driven by user input, not graph history.")

    if pred_ratio > 1.5:
        p(f"\n  TEMPORAL PREDICTION: Early oscillation predicts late correction ({pred_ratio:.1f}x).")
        p(f"  This is a genuine forecasting signal.")
    elif pred_ratio > 0 and pred_ratio != float("inf"):
        p(f"\n  TEMPORAL PREDICTION: Weak or no signal ({pred_ratio:.1f}x).")

    # --- TWO-AXIS CLASSIFIER: oscillation × final trust ---
    p(f"\n  TWO-AXIS CLASSIFIER (oscillation x final trust):")

    # Quadrants:
    # High osc + low trust = UNSTABLE (likely corrected)
    # High osc + high trust = SETTLED (survived oscillation)
    # Low osc + low trust = QUIET DECAY (drifted without contest)
    # Low osc + high trust = ANCHORED (stable, confident)

    quadrants = {
        "UNSTABLE (osc>=2, trust<0.5)": {},
        "SETTLED (osc>=2, trust>=0.5)": {},
        "QUIET_DECAY (osc<2, trust<0.5)": {},
        "ANCHORED (osc<2, trust>=0.5)": {},
    }

    for mid, data in oscillation_data.items():
        osc = data["oscillations"]
        trust = data["current_trust"]
        if osc >= 2 and trust < 0.5:
            quadrants["UNSTABLE (osc>=2, trust<0.5)"][mid] = data
        elif osc >= 2 and trust >= 0.5:
            quadrants["SETTLED (osc>=2, trust>=0.5)"][mid] = data
        elif osc < 2 and trust < 0.5:
            quadrants["QUIET_DECAY (osc<2, trust<0.5)"][mid] = data
        else:
            quadrants["ANCHORED (osc<2, trust>=0.5)"][mid] = data

    for label, group in quadrants.items():
        if not group:
            p(f"    {label}: no memories")
            continue
        corrected = sum(1 for v in group.values() if v["corrected"])
        rate = corrected / len(group)
        p(f"    {label}: {corrected}/{len(group)} corrected ({rate:.1%})")

    # The key comparison: UNSTABLE vs ANCHORED
    unstable = quadrants["UNSTABLE (osc>=2, trust<0.5)"]
    anchored = quadrants["ANCHORED (osc<2, trust>=0.5)"]
    if unstable and anchored:
        u_rate = sum(1 for v in unstable.values() if v["corrected"]) / len(unstable)
        a_rate = sum(1 for v in anchored.values() if v["corrected"]) / len(anchored)
        two_axis_ratio = u_rate / a_rate if a_rate > 0 else float("inf")
        p(f"\n    KEY: UNSTABLE vs ANCHORED = {two_axis_ratio:.1f}x")
        if two_axis_ratio > 3.93:
            p(f"    Two-axis ({two_axis_ratio:.1f}x) BEATS single-axis (3.9x)")
        else:
            p(f"    Two-axis ({two_axis_ratio:.1f}x) vs single-axis (3.9x)")

    log({
        "experiment": "oscillation_forecasting",
        "timestamp": time.time(),
        "distribution": {
            "stable": len(stable),
            "single_shift": len(single_shift),
            "oscillating": len(oscillating),
            "highly_oscillating": len(highly_oscillating),
        },
        "correction_rates": results,
        "predictive_ratio": pred_ratio if 'pred_ratio' in dir() else None,
    })

    p(f"\n  Log: {LOG_FILE}")


if __name__ == "__main__":
    run()
