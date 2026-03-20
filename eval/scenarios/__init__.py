from eval.scenarios.contradiction_stress import ContradictionStressScenario
from eval.scenarios.correction_recovery import CorrectionRecoveryScenario
from eval.scenarios.noise_drift import NoiseDriftScenario
from eval.scenarios.hallucination_probe import HallucinationProbeScenario

ALL_SCENARIOS = [
    ContradictionStressScenario(),
    CorrectionRecoveryScenario(),
    NoiseDriftScenario(),
    HallucinationProbeScenario(),
]
