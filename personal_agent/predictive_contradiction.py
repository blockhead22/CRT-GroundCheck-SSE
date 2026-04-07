"""Predictive Contradiction Detection -- Step 5

The foresight engine. Every other memory system is a rearview mirror.
This one looks through the windshield.

Core idea: two belief loci drifting toward each other in belief space
will eventually conflict. The system can see the collision before it happens
by tracking trajectories and extrapolating convergence.

Three signals:
  1. CENTER CONVERGENCE -- are the means getting closer?
  2. COVARIANCE EXPANSION -- is either locus widening (uncertainty growing)?
  3. OVERLAP TREND -- is the overlap integral increasing over time?

The combined signal → convergence score → urgency classification:
  - NONE: no convergence detected
  - WATCH: early signal, log and monitor
  - WARN: strong convergence, flag for attention
  - IMMINENT: collision likely, trigger NLI confirmation

Key finding from Step 4: In 384D, static overlap between distinct
Gaussians is near-zero (curse of dimensionality). But overlap TREND
is the right signal -- even tiny absolute overlaps, if increasing
geometrically, predict future conflict.
"""

import time
import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from enum import Enum

import numpy as np

from .memory_splats import (
    BeliefLocus, create_locus, create_locus_from_type,
    bhattacharyya_coefficient, bhattacharyya_distance,
    overlap_integral, kl_divergence, cosine_similarity,
    update_locus_with_evidence,
    MemorySplat, create_splat, create_splat_from_type,  # backwards compat aliases
    update_splat_with_evidence,  # backwards compat alias
)


# ---------------------------------------------------------------------------
# Urgency levels
# ---------------------------------------------------------------------------

class Urgency(Enum):
    NONE = "none"
    WATCH = "watch"
    WARN = "warn"
    IMMINENT = "imminent"


# ---------------------------------------------------------------------------
# Trajectory analysis
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryState:
    """Extracted trajectory features for a single belief locus."""
    center_velocity: Optional[np.ndarray]  # direction + speed of center drift
    center_speed: float                     # magnitude of velocity
    covariance_velocity: float              # rate of total uncertainty change
    is_widening: bool                       # uncertainty growing?
    is_tightening: bool                     # uncertainty shrinking?
    n_snapshots: int
    time_span: float                        # seconds between first and last snapshot


def extract_trajectory(splat: BeliefLocus, use_last_n: int = 5) -> Optional[TrajectoryState]:
    """Extract trajectory features from a belief locus's history.

    Uses weighted linear regression on the last N snapshots.
    More recent snapshots get more weight.
    """
    traj = splat.trajectory
    if len(traj) < 2:
        return None

    # Use last N snapshots
    recent = traj[-use_last_n:]
    n = len(recent)

    # Time axis (relative to first snapshot)
    times = np.array([s['timestamp'] - recent[0]['timestamp'] for s in recent])
    time_span = times[-1] - times[0]
    if time_span < 1e-6:
        return None

    # Normalize time to [0, 1] for numerical stability
    t_norm = times / time_span

    # Exponential weights: recent snapshots matter more
    weights = np.exp(np.linspace(-1, 0, n))
    weights /= weights.sum()

    # --- Center velocity via weighted linear regression ---
    # For each dimension: fit weighted line to mu_i(t)
    centers = np.array([s['mu'] for s in recent])  # (n, d)

    # Weighted least squares: beta = (X^T W X)^{-1} X^T W y
    # For 1D regression: beta = sum(w * t * y) / sum(w * t^2) (after centering)
    t_centered = t_norm - np.average(t_norm, weights=weights)

    # Vectorized across all dimensions
    numerator = np.sum(weights[:, None] * t_centered[:, None] *
                       (centers - np.average(centers, axis=0, weights=weights)), axis=0)
    denominator = np.sum(weights * t_centered ** 2)

    if denominator < 1e-10:
        center_velocity = np.zeros(splat.dim, dtype=np.float32)
    else:
        center_velocity = (numerator / denominator).astype(np.float32)

    # Scale velocity back to per-second (we normalized time to [0,1])
    center_velocity_per_sec = center_velocity / time_span
    center_speed = float(np.linalg.norm(center_velocity_per_sec))

    # --- Covariance velocity ---
    uncertainties = np.array([float(np.sum(s['sigma'])) for s in recent])

    unc_numerator = np.sum(weights * t_centered *
                          (uncertainties - np.average(uncertainties, weights=weights)))
    if denominator < 1e-10:
        cov_velocity = 0.0
    else:
        cov_velocity = float(unc_numerator / denominator) / time_span

    return TrajectoryState(
        center_velocity=center_velocity_per_sec,
        center_speed=center_speed,
        covariance_velocity=cov_velocity,
        is_widening=cov_velocity > 0,
        is_tightening=cov_velocity < 0,
        n_snapshots=n,
        time_span=time_span,
    )


# ---------------------------------------------------------------------------
# Pairwise convergence analysis
# ---------------------------------------------------------------------------

@dataclass
class ConvergenceResult:
    """Full analysis of whether two belief loci are heading toward conflict."""
    splat_a_id: str
    splat_b_id: str

    # Current state
    current_cosine: float
    current_overlap: float
    current_center_distance: float

    # Convergence signals
    center_convergence_rate: float    # how fast centers are approaching (per sec)
    overlap_growth_rate: float        # how fast overlap is increasing (per sec)
    covariance_expansion_a: float     # is A getting more uncertain?
    covariance_expansion_b: float     # is B getting more uncertain?

    # Predictions
    predicted_cosine_5step: Optional[float]   # predicted cosine in 5 time-steps
    predicted_overlap_5step: Optional[float]  # predicted overlap in 5 time-steps
    time_to_collision: Optional[float]        # estimated seconds until conflict threshold

    # Verdict
    urgency: Urgency
    convergence_score: float  # 0-1, composite signal
    explanation: str


def analyze_convergence(
    a: BeliefLocus,
    b: BeliefLocus,
    # Thresholds
    cosine_conflict_threshold: float = 0.7,
    overlap_watch_threshold: float = 1e-6,
    convergence_watch_threshold: float = 0.3,
    convergence_warn_threshold: float = 0.6,
    convergence_imminent_threshold: float = 0.85,
) -> ConvergenceResult:
    """The main prediction engine.

    Analyzes two belief loci trajectories and predicts whether they're
    heading toward a contradiction.
    """
    # --- Current state ---
    current_cos = cosine_similarity(a, b)
    current_overlap = overlap_integral(a, b)
    current_dist = float(np.linalg.norm(a.mu - b.mu))

    # --- Extract trajectories ---
    traj_a = extract_trajectory(a)
    traj_b = extract_trajectory(b)

    # Default values when trajectory is unavailable
    center_convergence = 0.0
    overlap_growth = 0.0
    cov_exp_a = 0.0
    cov_exp_b = 0.0
    predicted_cos = None
    predicted_overlap = None
    time_to_collision = None

    if traj_a is not None and traj_b is not None:
        # --- Signal 1: Center convergence rate ---
        # Project both velocity vectors onto the line connecting the centers
        ab_direction = b.mu - a.mu
        ab_dist = np.linalg.norm(ab_direction)
        if ab_dist > 1e-8:
            ab_unit = ab_direction / ab_dist
            # Positive = A moving toward B
            a_approach = float(np.dot(traj_a.center_velocity, ab_unit))
            # Positive = B moving toward A (note: negative direction)
            b_approach = float(np.dot(traj_b.center_velocity, -ab_unit))
            # Total approach rate
            center_convergence = a_approach + b_approach

        # --- Signal 2: Covariance expansion ---
        cov_exp_a = traj_a.covariance_velocity
        cov_exp_b = traj_b.covariance_velocity

        # --- Signal 3: Overlap trend ---
        # Compute overlap at historical snapshots
        n_shared = min(len(a.trajectory), len(b.trajectory))
        if n_shared >= 2:
            overlaps = []
            times = []
            for i in range(max(0, n_shared - 5), n_shared):
                snap_a = BeliefLocus("tmp", a.trajectory[i]['mu'],
                                     a.trajectory[i]['sigma'], a.trajectory[i]['alpha'])
                snap_b = BeliefLocus("tmp", b.trajectory[i]['mu'],
                                     b.trajectory[i]['sigma'], b.trajectory[i]['alpha'])
                overlaps.append(overlap_integral(snap_a, snap_b))
                times.append(a.trajectory[i]['timestamp'])

            if len(overlaps) >= 2 and (times[-1] - times[0]) > 1e-6:
                # Weighted linear fit on overlap trend
                dt_total = times[-1] - times[0]
                overlap_growth = (overlaps[-1] - overlaps[0]) / dt_total

            # Predict overlap 5 steps ahead
            if len(overlaps) >= 2:
                step_size = (times[-1] - times[0]) / max(1, len(times) - 1)
                predicted_overlap = overlaps[-1] + overlap_growth * step_size * 5
                predicted_overlap = max(0.0, min(1.0, predicted_overlap))

        # --- Predict cosine ---
        # Use trajectory to predict where centers will be
        avg_dt = traj_a.time_span / max(1, traj_a.n_snapshots - 1)
        future_a = a.mu + traj_a.center_velocity * avg_dt * 5
        future_b = b.mu + traj_b.center_velocity * avg_dt * 5
        na = np.linalg.norm(future_a)
        nb = np.linalg.norm(future_b)
        if na > 1e-8 and nb > 1e-8:
            predicted_cos = float(np.dot(future_a, future_b) / (na * nb))

        # --- Time to collision estimate ---
        if center_convergence > 1e-8 and current_dist > 0:
            # At current convergence rate, when do centers meet?
            time_to_collision = current_dist / center_convergence

    # --- Composite convergence score ---
    # Normalize each signal to [0, 1] and combine.
    #
    # Key insight: we need to normalize by TIME STEP, not per-second.
    # If snapshots are 1 day apart, per-second rates are tiny but
    # per-step rates may be significant. Use fractional distance
    # closed per step instead.
    scores = []

    # Signal 1: Center convergence -- what fraction of the distance
    # has been closed over the trajectory window?
    if traj_a is not None and traj_b is not None and current_dist > 1e-8:
        # How much distance was closed per step?
        dist_closed_per_sec = center_convergence
        n_steps = min(traj_a.n_snapshots, traj_b.n_snapshots)
        time_per_step = traj_a.time_span / max(1, n_steps - 1) if n_steps > 1 else 1.0
        dist_closed_total = dist_closed_per_sec * traj_a.time_span
        # What fraction of original distance was closed?
        original_dist = current_dist + max(0, dist_closed_total)
        if original_dist > 1e-8:
            frac_closed = dist_closed_total / original_dist
        else:
            frac_closed = 0.0
        center_score = min(1.0, max(0.0, frac_closed))
    else:
        center_score = 0.0
    scores.append(center_score * 0.35)  # 35% weight

    # Signal 2: Overlap growth -- use log-ratio of newest vs oldest overlap
    if traj_a is not None and traj_b is not None:
        n_shared = min(len(a.trajectory), len(b.trajectory))
        if n_shared >= 3:
            # Compare oldest and newest overlap in the window
            snap_old_a = BeliefLocus("t", a.trajectory[-n_shared]['mu'],
                                     a.trajectory[-n_shared]['sigma'],
                                     a.trajectory[-n_shared]['alpha'])
            snap_old_b = BeliefLocus("t", b.trajectory[-n_shared]['mu'],
                                     b.trajectory[-n_shared]['sigma'],
                                     b.trajectory[-n_shared]['alpha'])
            old_overlap = max(1e-30, overlap_integral(snap_old_a, snap_old_b))
            new_overlap = max(1e-30, current_overlap)
            log_ratio = math.log(new_overlap / old_overlap)
            # Normalize: 10 orders of magnitude growth -> score 1.0
            overlap_score = min(1.0, max(0.0, log_ratio / 23))  # ln(10^10) ~ 23
        else:
            overlap_score = 0.0
    else:
        overlap_score = 0.0
    scores.append(overlap_score * 0.25)  # 25% weight

    # Signal 3: Covariance expansion
    cov_score = 0.0
    if cov_exp_a > 0:
        cov_score += 0.5
    if cov_exp_b > 0:
        cov_score += 0.5
    scores.append(cov_score * 0.15)  # 15% weight

    # Signal 4: Topic relatedness (high cosine = same territory)
    topic_score = max(0.0, min(1.0, current_cos))
    scores.append(topic_score * 0.25)  # 25% weight

    convergence_score = sum(scores)

    # --- Urgency classification ---
    if convergence_score >= convergence_imminent_threshold:
        urgency = Urgency.IMMINENT
    elif convergence_score >= convergence_warn_threshold:
        urgency = Urgency.WARN
    elif convergence_score >= convergence_watch_threshold:
        urgency = Urgency.WATCH
    else:
        urgency = Urgency.NONE

    # --- Explanation ---
    parts = []
    if center_convergence > 0:
        parts.append(f"centers approaching at {center_convergence:.4f}/s")
    if overlap_growth > 0:
        parts.append(f"overlap growing at {overlap_growth:.2e}/s")
    if cov_exp_a > 0:
        parts.append(f"A widening ({cov_exp_a:.2f}/s)")
    if cov_exp_b > 0:
        parts.append(f"B widening ({cov_exp_b:.2f}/s)")
    if time_to_collision is not None and time_to_collision > 0:
        if time_to_collision < 3600:
            parts.append(f"estimated collision in {time_to_collision:.0f}s")
        else:
            parts.append(f"estimated collision in {time_to_collision/3600:.1f}h")

    if urgency == Urgency.NONE:
        explanation = "No convergence detected"
        if parts:
            explanation += f" ({'; '.join(parts)})"
    else:
        explanation = f"{urgency.value.upper()}: {'; '.join(parts)}"

    return ConvergenceResult(
        splat_a_id=a.memory_id,
        splat_b_id=b.memory_id,
        current_cosine=current_cos,
        current_overlap=current_overlap,
        current_center_distance=current_dist,
        center_convergence_rate=center_convergence,
        overlap_growth_rate=overlap_growth,
        covariance_expansion_a=cov_exp_a,
        covariance_expansion_b=cov_exp_b,
        predicted_cosine_5step=predicted_cos,
        predicted_overlap_5step=predicted_overlap,
        time_to_collision=time_to_collision,
        urgency=urgency,
        convergence_score=convergence_score,
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Memory store scanner -- batch convergence analysis
# ---------------------------------------------------------------------------

@dataclass
class ConvergenceAlert:
    """A flagged pair that needs attention."""
    result: ConvergenceResult
    priority: float  # higher = more urgent


def scan_for_convergence(
    splats: List[BeliefLocus],
    min_cosine: float = 0.2,   # only check related pairs
    min_urgency: Urgency = Urgency.WATCH,
) -> List[ConvergenceAlert]:
    """Scan all pairs of belief loci for convergence.

    Pre-filters by cosine similarity (unrelated pairs can't converge
    into contradiction). Returns alerts sorted by priority.

    For N splats, this is O(N^2) in the worst case.
    Pre-filter by cosine reduces the constant factor.
    For < 10K memories, this is fast enough.
    """
    alerts = []
    n = len(splats)

    for i in range(n):
        for j in range(i + 1, n):
            # Quick cosine pre-filter
            cos = cosine_similarity(splats[i], splats[j])
            if cos < min_cosine:
                continue

            result = analyze_convergence(splats[i], splats[j])

            if _urgency_rank(result.urgency) >= _urgency_rank(min_urgency):
                alerts.append(ConvergenceAlert(
                    result=result,
                    priority=result.convergence_score,
                ))

    # Sort by priority (highest first)
    alerts.sort(key=lambda a: a.priority, reverse=True)
    return alerts


def _urgency_rank(u: Urgency) -> int:
    return {Urgency.NONE: 0, Urgency.WATCH: 1, Urgency.WARN: 2, Urgency.IMMINENT: 3}[u]


# ---------------------------------------------------------------------------
# Simulation: demonstrate predictive detection
# ---------------------------------------------------------------------------

def simulate_belief_drift():
    """Simulate two beliefs that gradually drift toward conflict.

    Scenario: Person starts with "I enjoy my work" and separately
    has "I need more free time." Over time, work intensifies and
    these beliefs converge toward contradiction.
    """
    print("=" * 70)
    print("PREDICTIVE CONTRADICTION DETECTION -- Belief Drift Simulation")
    print("=" * 70)

    np.random.seed(42)
    d = 384

    # Base embedding directions (correlated but distinct)
    work_dir = np.random.randn(d).astype(np.float32)
    work_dir /= np.linalg.norm(work_dir)

    # "Free time" is related but different -- cosine ~ 0.3-0.5
    noise = np.random.randn(d).astype(np.float32) * 0.8
    freetime_dir = work_dir + noise
    freetime_dir /= np.linalg.norm(freetime_dir)

    print(f"\n  Base cosine (work vs freetime): {float(np.dot(work_dir, freetime_dir)):.4f}")

    # Create initial splats
    work_splat = create_locus_from_type(
        "enjoy_work", work_dir.copy(),
        "I enjoy my work", "belief", 0.8
    )
    freetime_splat = create_locus_from_type(
        "need_freetime", freetime_dir.copy(),
        "I need more free time", "belief", 0.7
    )

    print(f"\n  --- DRIFT SIMULATION (20 steps) ---")
    print(f"  {'Step':>4} | {'Cosine':>7} | {'Overlap':>10} | {'Conv.Score':>10} | {'Urgency':>10} | Notes")
    print(f"  {'-'*4}-+-{'-'*7}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+--------")

    for step in range(20):
        # Simulate gradual drift:
        # Work belief shifts toward stress (moves in freetime direction)
        # Freetime belief gets more intense (widens + shifts toward work)
        drift_rate = 0.02 + step * 0.003  # accelerating drift

        # Work splat drifts toward freetime territory
        work_splat.mu += drift_rate * (freetime_splat.mu - work_splat.mu)
        work_splat.mu /= np.linalg.norm(work_splat.mu)  # stay on unit sphere

        # Work splat uncertainty grows (belief under pressure)
        if step > 5:
            work_splat.sigma *= 1.02

        # Freetime splat slowly drifts toward work territory too
        freetime_splat.mu += drift_rate * 0.5 * (work_splat.mu - freetime_splat.mu)
        freetime_splat.mu /= np.linalg.norm(freetime_splat.mu)

        # Snapshot
        # Fake timestamps spread across "days"
        fake_time = time.time() + step * 86400  # 1 day per step
        work_splat.trajectory.append({
            'mu': work_splat.mu.copy(),
            'sigma': work_splat.sigma.copy(),
            'alpha': work_splat.alpha,
            'timestamp': fake_time,
        })
        freetime_splat.trajectory.append({
            'mu': freetime_splat.mu.copy(),
            'sigma': freetime_splat.sigma.copy(),
            'alpha': freetime_splat.alpha,
            'timestamp': fake_time,
        })

        # Analyze convergence
        result = analyze_convergence(work_splat, freetime_splat)

        notes = ""
        if step == 0:
            notes = "<-- baseline"
        elif result.urgency == Urgency.WATCH and step > 0:
            notes = "<-- first watch signal"
        elif result.urgency == Urgency.WARN:
            notes = "<-- WARNING"
        elif result.urgency == Urgency.IMMINENT:
            notes = "<-- IMMINENT CONFLICT"

        print(f"  {step:4d} | {result.current_cosine:7.4f} | "
              f"{result.current_overlap:10.2e} | "
              f"{result.convergence_score:10.4f} | "
              f"{result.urgency.value:>10} | {notes}")

    # Final analysis
    print(f"\n  --- FINAL CONVERGENCE ANALYSIS ---")
    final = analyze_convergence(work_splat, freetime_splat)
    print(f"  {final.explanation}")
    if final.predicted_cosine_5step:
        print(f"  Predicted cosine (5 steps ahead): {final.predicted_cosine_5step:.4f}")
    if final.predicted_overlap_5step:
        print(f"  Predicted overlap (5 steps ahead): {final.predicted_overlap_5step:.2e}")
    if final.time_to_collision:
        days = final.time_to_collision / 86400
        print(f"  Estimated time to collision: {days:.1f} days")

    return work_splat, freetime_splat


def simulate_stable_beliefs():
    """Control case: two beliefs that are related but NOT converging."""
    print(f"\n{'='*70}")
    print("CONTROL: Stable Related Beliefs (should NOT trigger)")
    print("=" * 70)

    np.random.seed(123)
    d = 384

    base = np.random.randn(d).astype(np.float32)
    base /= np.linalg.norm(base)

    noise = np.random.randn(d).astype(np.float32) * 0.5
    related = base + noise
    related /= np.linalg.norm(related)

    splat_a = create_locus_from_type("stable_a", base, "I like hiking", "preference")
    splat_b = create_locus_from_type("stable_b", related, "Nature is calming", "belief")

    print(f"\n  Base cosine: {float(np.dot(base, related)):.4f}")
    print(f"  {'Step':>4} | {'Cosine':>7} | {'Conv.Score':>10} | {'Urgency':>10}")
    print(f"  {'-'*4}-+-{'-'*7}-+-{'-'*10}-+-{'-'*10}")

    for step in range(15):
        # Both beliefs jitter randomly but don't converge
        splat_a.mu += np.random.randn(d).astype(np.float32) * 0.005
        splat_a.mu /= np.linalg.norm(splat_a.mu)
        splat_b.mu += np.random.randn(d).astype(np.float32) * 0.005
        splat_b.mu /= np.linalg.norm(splat_b.mu)

        fake_time = time.time() + step * 86400
        splat_a.trajectory.append({
            'mu': splat_a.mu.copy(), 'sigma': splat_a.sigma.copy(),
            'alpha': splat_a.alpha, 'timestamp': fake_time,
        })
        splat_b.trajectory.append({
            'mu': splat_b.mu.copy(), 'sigma': splat_b.sigma.copy(),
            'alpha': splat_b.alpha, 'timestamp': fake_time,
        })

        result = analyze_convergence(splat_a, splat_b)
        print(f"  {step:4d} | {result.current_cosine:7.4f} | "
              f"{result.convergence_score:10.4f} | {result.urgency.value:>10}")


def simulate_sudden_reversal():
    """A belief that suddenly reverses -- the covariance should explode."""
    print(f"\n{'='*70}")
    print("SUDDEN REVERSAL: Belief flips direction (covariance should spike)")
    print("=" * 70)

    np.random.seed(77)
    d = 384

    direction = np.random.randn(d).astype(np.float32)
    direction /= np.linalg.norm(direction)

    splat = create_locus_from_type("reversing", direction.copy(),
                                   "I want to stay at this company", "belief", 0.9)

    print(f"\n  {'Step':>4} | {'Avg Sigma':>10} | {'Cov Velocity':>12} | {'Alpha':>6} | Notes")
    print(f"  {'-'*4}-+-{'-'*10}-+-{'-'*12}-+-{'-'*6}-+------")

    for step in range(15):
        fake_time = time.time() + step * 86400

        if step < 5:
            # Confirming evidence
            nearby = direction + np.random.randn(d).astype(np.float32) * 0.02
            nearby /= np.linalg.norm(nearby)
            update_locus_with_evidence(splat, nearby, weight=0.1)
            notes = "confirming"
        elif step == 5:
            # REVERSAL: contradicting evidence
            opposite = -direction + np.random.randn(d).astype(np.float32) * 0.1
            opposite /= np.linalg.norm(opposite)
            update_locus_with_evidence(splat, opposite, weight=0.3)
            notes = "<-- REVERSAL"
        elif step < 10:
            # More contradicting evidence
            opposite = -direction + np.random.randn(d).astype(np.float32) * 0.1
            opposite /= np.linalg.norm(opposite)
            update_locus_with_evidence(splat, opposite, weight=0.15)
            notes = "contradicting"
        else:
            # Settling into new belief
            new_dir = -direction + np.random.randn(d).astype(np.float32) * 0.02
            new_dir /= np.linalg.norm(new_dir)
            update_locus_with_evidence(splat, new_dir, weight=0.1)
            notes = "settling"

        splat.trajectory.append({
            'mu': splat.mu.copy(), 'sigma': splat.sigma.copy(),
            'alpha': splat.alpha, 'timestamp': fake_time,
        })

        traj = extract_trajectory(splat)
        cov_vel = traj.covariance_velocity if traj else 0.0

        print(f"  {step:4d} | {splat.avg_uncertainty:10.6f} | "
              f"{cov_vel:12.6f} | {splat.alpha:6.3f} | {notes}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"D:\CRT\compression_lab")

    # Scenario 1: Gradual drift toward conflict
    simulate_belief_drift()

    # Scenario 2: Stable beliefs (control -- should NOT trigger)
    simulate_stable_beliefs()

    # Scenario 3: Sudden reversal (covariance explosion)
    simulate_sudden_reversal()

    print(f"\n{'='*70}")
    print("PREDICTIVE CONTRADICTION DETECTION -- ALL SCENARIOS COMPLETE")
    print(f"{'='*70}")
