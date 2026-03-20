"""Long-horizon eval harness for CRT/Aether.

Usage — quick run:

    from eval.runner import EvalRunner, EvalConfig
    from eval.scenarios import ALL_SCENARIOS
    from eval.baselines import ALL_SYSTEMS

    cfg = EvalConfig(n_turns=500, seeds=[0, 1, 2])
    matrix = EvalRunner(cfg).run_matrix(ALL_SCENARIOS, ALL_SYSTEMS)

    from eval.report import generate_report
    generate_report(matrix, output_dir=Path("eval_results"))

Usage — single scenario:

    from eval.runner import EvalRunner, EvalConfig
    from eval.scenarios.contradiction_stress import ContradictionStressScenario
    from eval.baselines.crt_system import CRTSystem

    runner = EvalRunner(EvalConfig(n_turns=200, seeds=[0]))
    records = runner.run_scenario(ContradictionStressScenario(), CRTSystem(), seed=0)
"""

from eval.base_scenario import EvalSystem, TurnSpec, TurnRecord, BaseScenario  # noqa: F401
from eval.metrics import compute_all, MetricsBundle  # noqa: F401
