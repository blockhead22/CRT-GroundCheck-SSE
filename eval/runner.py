"""Eval runner — orchestrates scenario × system × seed matrix.

Usage:

    cfg = EvalConfig(n_turns=500, seeds=[0, 1, 2], verbose=True)
    runner = EvalRunner(cfg)
    matrix = runner.run_matrix(ALL_SCENARIOS, ALL_SYSTEMS)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from eval.base_scenario import BaseScenario, EvalSystem, TurnRecord
from eval.metrics import MetricsBundle, compute_all

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class EvalConfig:
    n_turns: int = 500
    seeds: List[int] = field(default_factory=lambda: [0, 1, 2])
    verbose: bool = False
    fail_fast: bool = False          # Stop matrix on first error
    thread_id_prefix: str = "eval"  # Thread ID passed to system.query()
    log_every_n: int = 50           # Print progress every N turns


# ---------------------------------------------------------------------------
# EvalMatrix — results container
# ---------------------------------------------------------------------------

@dataclass
class EvalMatrix:
    """Stores TurnRecords and MetricsBundles for a full run."""
    config: EvalConfig
    # Records keyed by (scenario_name, system_name, seed)
    records: Dict[Tuple[str, str, int], List[TurnRecord]] = field(default_factory=dict)
    # Metrics keyed by (scenario_name, system_name, seed)
    metrics: Dict[Tuple[str, str, int], MetricsBundle] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def all_bundles(self) -> List[MetricsBundle]:
        return list(self.metrics.values())

    def bundles_for_scenario(self, scenario: str) -> List[MetricsBundle]:
        return [b for k, b in self.metrics.items() if k[0] == scenario]

    def bundles_for_system(self, system: str) -> List[MetricsBundle]:
        return [b for k, b in self.metrics.items() if k[1] == system]

    def mean_bundle(self, scenario: str, system: str) -> Optional[MetricsBundle]:
        """Average MetricsBundle across seeds for (scenario, system)."""
        import math
        bundles = [
            b for (s, sys, _), b in self.metrics.items()
            if s == scenario and sys == system
        ]
        if not bundles:
            return None

        def _mean(attr: str) -> float:
            vals = [getattr(b, attr) for b in bundles]
            valid = [v for v in vals if not math.isnan(v)]
            return sum(valid) / len(valid) if valid else float("nan")

        avg = MetricsBundle(
            scenario=scenario, system=system, seed=-1,
            n_turns=sum(b.n_turns for b in bundles),
        )
        for attr in [
            "contradiction_recurrence_rate", "correction_recovery_rate",
            "trust_calibration_error", "hallucination_leakage_rate",
            "gate_precision", "gate_utilization_rate",
            "epistemic_improvement_score",
            "open_contradiction_age", "fact_fidelity_over_time",
        ]:
            setattr(avg, attr, _mean(attr))
        for attr in [
            "n_gate_pass", "n_gate_fail", "n_contradictions",
            "n_thumbs_up", "n_thumbs_down", "n_beliefs", "n_speech",
        ]:
            setattr(avg, attr, sum(getattr(b, attr) for b in bundles))
        return avg


# ---------------------------------------------------------------------------
# EvalRunner
# ---------------------------------------------------------------------------

class EvalRunner:
    def __init__(self, config: Optional[EvalConfig] = None):
        self.config = config or EvalConfig()

    def run_scenario(
        self,
        scenario: BaseScenario,
        system: EvalSystem,
        seed: int,
    ) -> List[TurnRecord]:
        """Run one scenario × system × seed combination."""
        cfg = self.config
        system.reset()
        thread_id = f"{cfg.thread_id_prefix}_{scenario.name}_{seed}"
        records: List[TurnRecord] = []

        turn_gen = scenario.generate_turns(cfg.n_turns, seed)

        for turn_idx, spec in enumerate(turn_gen):
            if cfg.verbose and turn_idx % cfg.log_every_n == 0:
                logger.info(
                    "[eval] %s × %s × seed=%d  turn=%d/%d",
                    scenario.name, system.name, seed, turn_idx, cfg.n_turns,
                )

            t0 = time.perf_counter()
            try:
                raw = system.query(spec.message, thread_id=thread_id)
            except Exception as exc:
                logger.warning(
                    "[eval] query error  %s × %s × seed=%d  turn=%d: %s",
                    scenario.name, system.name, seed, turn_idx, exc,
                )
                raw = {
                    "answer": f"[ERROR: {exc}]",
                    "response_type": "speech",
                    "gates_passed": False,
                    "gate_reason": "eval_error",
                    "contradiction_detected": False,
                    "confidence": 0.0,
                    "intent_alignment": 0.0,
                    "memory_alignment": 0.0,
                    "best_prior_trust": None,
                }
            elapsed = time.perf_counter() - t0

            response_text = str(raw.get("answer") or raw.get("response") or "")
            thumbs = spec.score(response_text) if spec.inject_feedback else None

            meta = dict(spec.metadata)
            if spec.ground_truth:
                meta["ground_truth"] = spec.ground_truth

            record = TurnRecord(
                turn_idx=turn_idx,
                scenario_name=scenario.name,
                system_name=system.name,
                seed=seed,
                user_message=spec.message,
                slot_key=spec.slot_key,
                response=response_text,
                response_type=str(raw.get("response_type") or "speech"),
                gates_passed=bool(raw.get("gates_passed", False)),
                gate_reason=str(raw.get("gate_reason") or ""),
                contradiction_detected=bool(raw.get("contradiction_detected", False)),
                confidence=float(raw.get("confidence") or 0.0),
                intent_alignment=float(raw.get("intent_alignment") or 0.0),
                memory_alignment=float(raw.get("memory_alignment") or 0.0),
                best_prior_trust=raw.get("best_prior_trust"),
                thumbs_up=thumbs,
                wall_time_s=elapsed,
                turn_metadata=meta,
            )
            records.append(record)
            scenario.on_turn_complete(record)

        return records

    def run_matrix(
        self,
        scenarios: List[BaseScenario],
        systems: List[EvalSystem],
        seeds: Optional[List[int]] = None,
    ) -> EvalMatrix:
        """Run the full scenario × system × seed matrix."""
        seeds = seeds if seeds is not None else self.config.seeds
        matrix = EvalMatrix(config=self.config)

        total = len(scenarios) * len(systems) * len(seeds)
        done = 0
        for scenario in scenarios:
            for system in systems:
                for seed in seeds:
                    key = (scenario.name, system.name, seed)
                    logger.info(
                        "[eval] starting %d/%d  %s × %s × seed=%d",
                        done + 1, total, scenario.name, system.name, seed,
                    )
                    try:
                        records = self.run_scenario(scenario, system, seed)
                        matrix.records[key] = records
                        matrix.metrics[key] = compute_all(
                            records,
                            scenario=scenario.name,
                            system=system.name,
                            seed=seed,
                        )
                    except Exception as exc:
                        logger.error(
                            "[eval] run failed  %s × %s × seed=%d: %s",
                            scenario.name, system.name, seed, exc,
                        )
                        matrix.errors.append({
                            "scenario": scenario.name,
                            "system": system.name,
                            "seed": seed,
                            "error": str(exc),
                        })
                        if self.config.fail_fast:
                            raise
                    done += 1

        return matrix
