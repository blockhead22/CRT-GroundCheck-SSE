"""Eval metrics for the CRT long-horizon harness.

All metrics are pure functions over List[TurnRecord].  They return floats
in [0, 1] unless noted otherwise.

Primary metrics (prove CRT compounds into better behaviour):
  contradiction_recurrence_rate   CRR — low is better
  correction_recovery_rate        CRec — high is better
  trust_calibration_error         TCE — low is better
  hallucination_leakage_rate      HLR — low is better
  gate_precision                  GP  — high is better
  epistemic_improvement_score     EIS — high is better (composite)

Secondary metrics:
  open_contradiction_age          OCA — mean turns unresolved, lower is better
  fact_fidelity_over_time         FFoT — ground-truth coverage, higher is better
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from eval.base_scenario import TurnRecord


# ---------------------------------------------------------------------------
# MetricsBundle
# ---------------------------------------------------------------------------

@dataclass
class MetricsBundle:
    """All metrics for one (scenario, system, seed) run."""
    scenario: str = ""
    system: str = ""
    seed: int = 0
    n_turns: int = 0

    # Primary
    contradiction_recurrence_rate: float = float("nan")
    correction_recovery_rate: float = float("nan")
    trust_calibration_error: float = float("nan")
    hallucination_leakage_rate: float = float("nan")
    gate_precision: float = float("nan")
    gate_utilization_rate: float = float("nan")
    epistemic_improvement_score: float = float("nan")

    # Secondary
    open_contradiction_age: float = float("nan")
    fact_fidelity_over_time: float = float("nan")

    # Counts (for report context)
    n_gate_pass: int = 0
    n_gate_fail: int = 0
    n_contradictions: int = 0
    n_thumbs_up: int = 0
    n_thumbs_down: int = 0
    n_beliefs: int = 0
    n_speech: int = 0

    def as_dict(self) -> Dict:
        return asdict(self)

    def primary_row(self) -> Dict[str, str]:
        """Format primary metrics as a dict of display strings."""
        def _fmt(v: float) -> str:
            return f"{v:.3f}" if not math.isnan(v) else "—"
        return {
            "CRR": _fmt(self.contradiction_recurrence_rate),
            "CRec": _fmt(self.correction_recovery_rate),
            "TCE": _fmt(self.trust_calibration_error),
            "HLR": _fmt(self.hallucination_leakage_rate),
            "GP": _fmt(self.gate_precision),
            "GUR": _fmt(self.gate_utilization_rate),
            "EIS": _fmt(self.epistemic_improvement_score),
        }


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------

def contradiction_recurrence_rate(
    records: List[TurnRecord],
    window: int = 50,
) -> float:
    """P(same slot contradicted again within ``window`` turns after first flag).

    Denominator = number of first-flagged slot contradictions.
    Numerator = subset where another contradiction in the same slot
    appeared within the window.
    """
    if not records:
        return float("nan")

    # Group contradiction events by slot_key
    slot_first_flag: Dict[str, int] = {}
    recurrences = 0
    denominator = 0

    for r in records:
        if not r.contradiction_detected:
            continue
        key = r.slot_key or r.user_message[:40]
        if key not in slot_first_flag:
            slot_first_flag[key] = r.turn_idx
            denominator += 1
        else:
            gap = r.turn_idx - slot_first_flag[key]
            if gap <= window:
                recurrences += 1
            # Reset so we count subsequent windows too
            slot_first_flag[key] = r.turn_idx

    if denominator == 0:
        return float("nan")
    return recurrences / denominator


def correction_recovery_rate(
    records: List[TurnRecord],
    window: int = 20,
) -> float:
    """P(no thumbs-down on same slot within ``window`` turns after a correction).

    A "correction" is a thumbs-down turn.  Recovery means no further
    thumbs-down on the same slot within the next ``window`` turns.
    """
    if not records:
        return float("nan")

    # Index records by turn_idx for O(1) lookup
    by_idx: Dict[int, TurnRecord] = {r.turn_idx: r for r in records}
    max_turn = max(r.turn_idx for r in records)

    recovered = 0
    denominator = 0

    for r in records:
        if r.thumbs_up is not True and r.thumbs_up is not False:
            continue
        if r.thumbs_up:
            continue  # Only corrections (thumbs_down) count as starting events

        key = r.slot_key or r.user_message[:40]
        denominator += 1

        # Look ahead window turns for another thumbs-down on same slot
        relapse = False
        for future_idx in range(r.turn_idx + 1, min(r.turn_idx + window + 1, max_turn + 1)):
            fut = by_idx.get(future_idx)
            if fut and fut.thumbs_up is False:
                fut_key = fut.slot_key or fut.user_message[:40]
                if fut_key == key:
                    relapse = True
                    break
        if not relapse:
            recovered += 1

    if denominator == 0:
        return float("nan")
    return recovered / denominator


def trust_calibration_error(records: List[TurnRecord]) -> float:
    """Mean absolute difference between gate-pass trust and thumbs-down trust.

    Measures how well the gate separates good answers from bad ones.
    Lower is better.  Bounded [0, 1].
    """
    pass_trusts = [
        r.confidence
        for r in records
        if r.gates_passed and r.confidence is not None
    ]
    fail_trusts = [
        r.confidence
        for r in records
        if r.thumbs_up is False and r.confidence is not None
    ]
    if not pass_trusts or not fail_trusts:
        return float("nan")
    mean_pass = sum(pass_trusts) / len(pass_trusts)
    mean_fail = sum(fail_trusts) / len(fail_trusts)
    # Ideally mean_pass >> mean_fail. TCE is the gap we're missing.
    # Return calibration error = 1 - |gap| (capped at 0)
    gap = mean_pass - mean_fail
    return max(0.0, 1.0 - abs(gap))


def hallucination_leakage_rate(records: List[TurnRecord]) -> float:
    """Fraction of gate-pass belief turns that received a thumbs-down.

    A low-leakage system withholds belief when it shouldn't be confident.
    """
    belief_pass = [
        r for r in records
        if r.gates_passed and r.response_type == "belief"
    ]
    if not belief_pass:
        return float("nan")
    n_thumbs_down = sum(1 for r in belief_pass if r.thumbs_up is False)
    return n_thumbs_down / len(belief_pass)


def gate_precision(records: List[TurnRecord]) -> float:
    """Fraction of gate-pass turns that received thumbs-up (or no signal).

    Measures how often gate-pass = user satisfaction.  High is better.
    Only turns with explicit feedback contribute.
    """
    rated_gate_pass = [
        r for r in records
        if r.gates_passed and r.thumbs_up is not None
    ]
    if not rated_gate_pass:
        return float("nan")
    n_positive = sum(1 for r in rated_gate_pass if r.thumbs_up)
    return n_positive / len(rated_gate_pass)


def gate_utilization_rate(records: List[TurnRecord]) -> float:
    """Fraction of turns where the gate passed, normalised to [0, 1].

    Prevents floor-effect gaming: a system that always refuses (gates fail on
    every turn) scores 0 here regardless of how well it "avoids mistakes."
    Full credit (1.0) at ≥80% gate-pass rate; linear below that threshold.
    """
    if not records:
        return float("nan")
    rate = sum(1 for r in records if r.gates_passed) / len(records)
    # Linear ramp: 0 → 0 at 0%, 1 → 1 at 80%+
    FULL_CREDIT_THRESHOLD = 0.8
    return min(rate / FULL_CREDIT_THRESHOLD, 1.0)


def epistemic_improvement_score(bundle: MetricsBundle) -> float:
    """Composite score (higher is better) in [0, 1].

    Combines:
      CRec  (weight 0.35) — recovery is the most important signal
      1-CRR (weight 0.25) — contradiction suppression
      1-TCE (weight 0.15) — calibration quality
      GP    (weight 0.10) — gate reliability among rated turns
      GUR   (weight 0.15) — gate utilization (penalises refuse-everything)

    The GUR term prevents degenerate systems that score high on all other
    metrics by never answering anything.  Weights re-normalise automatically
    for metrics that are unavailable (NaN).
    """
    scores: List[Tuple[float, float]] = []  # (value, weight)

    if not math.isnan(bundle.correction_recovery_rate):
        scores.append((bundle.correction_recovery_rate, 0.35))
    if not math.isnan(bundle.contradiction_recurrence_rate):
        scores.append((1.0 - bundle.contradiction_recurrence_rate, 0.25))
    if not math.isnan(bundle.trust_calibration_error):
        scores.append((1.0 - bundle.trust_calibration_error, 0.15))
    if not math.isnan(bundle.gate_precision):
        scores.append((bundle.gate_precision, 0.10))
    if not math.isnan(bundle.gate_utilization_rate):
        scores.append((bundle.gate_utilization_rate, 0.15))

    if not scores:
        return float("nan")
    total_w = sum(w for _, w in scores)
    return sum(v * w for v, w in scores) / total_w


def open_contradiction_age(records: List[TurnRecord]) -> float:
    """Mean number of turns contradictions stay unresolved.

    A contradiction is "resolved" when the same slot stops generating
    contradiction_detected=True.  Lower is better.
    """
    if not records:
        return float("nan")

    slot_open_since: Dict[str, int] = {}
    age_samples: List[float] = []

    for r in records:
        key = r.slot_key or r.user_message[:40]
        if r.contradiction_detected:
            if key not in slot_open_since:
                slot_open_since[key] = r.turn_idx
        else:
            if key in slot_open_since:
                age = r.turn_idx - slot_open_since.pop(key)
                age_samples.append(float(age))

    # Add still-open contradictions at end of run
    max_turn = max(r.turn_idx for r in records)
    for key, open_since in slot_open_since.items():
        age_samples.append(float(max_turn - open_since))

    if not age_samples:
        return float("nan")
    return sum(age_samples) / len(age_samples)


def fact_fidelity_over_time(records: List[TurnRecord]) -> float:
    """Fraction of ground-truth turns where response contained the truth.

    Score per turn: 1 if ground_truth in response (case-insensitive), else 0.
    Turns without a ground_truth are excluded.
    """
    scored = [
        r for r in records
        if r.turn_metadata.get("ground_truth") is not None
    ]
    if not scored:
        return float("nan")
    n_correct = sum(
        1 for r in scored
        if (r.turn_metadata["ground_truth"] or "").lower() in r.response.lower()
    )
    return n_correct / len(scored)


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def compute_all(
    records: List[TurnRecord],
    scenario: str = "",
    system: str = "",
    seed: int = 0,
) -> MetricsBundle:
    """Compute all metrics from a list of TurnRecords."""
    b = MetricsBundle(
        scenario=scenario,
        system=system,
        seed=seed,
        n_turns=len(records),
        n_gate_pass=sum(1 for r in records if r.gates_passed),
        n_gate_fail=sum(1 for r in records if not r.gates_passed),
        n_contradictions=sum(1 for r in records if r.contradiction_detected),
        n_thumbs_up=sum(1 for r in records if r.thumbs_up is True),
        n_thumbs_down=sum(1 for r in records if r.thumbs_up is False),
        n_beliefs=sum(1 for r in records if r.response_type == "belief"),
        n_speech=sum(1 for r in records if r.response_type == "speech"),
    )
    b.contradiction_recurrence_rate = contradiction_recurrence_rate(records)
    b.correction_recovery_rate = correction_recovery_rate(records)
    b.trust_calibration_error = trust_calibration_error(records)
    b.hallucination_leakage_rate = hallucination_leakage_rate(records)
    b.gate_precision = gate_precision(records)
    b.gate_utilization_rate = gate_utilization_rate(records)
    b.open_contradiction_age = open_contradiction_age(records)
    b.fact_fidelity_over_time = fact_fidelity_over_time(records)
    b.epistemic_improvement_score = epistemic_improvement_score(b)
    return b
