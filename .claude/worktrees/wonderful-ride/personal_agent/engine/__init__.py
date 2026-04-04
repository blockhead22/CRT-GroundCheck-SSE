"""Engine modules for CRT orchestration and DNNT integration hooks."""

from .anchors import AnchorSystem, DEFAULT_ANCHOR_TRUTHS
from .resonance import ResonanceScorer, ResonanceSignal
from .reconstruction import ReconstructionFidelityEvaluator, ReconstructionFidelitySignal
from .degradation import DegradationDetector, DegradationAssessment
from .collapse_trails import CollapseTrailLogger, get_collapse_trail_logger

__all__ = [
    "AnchorSystem",
    "DEFAULT_ANCHOR_TRUTHS",
    "ResonanceScorer",
    "ResonanceSignal",
    "ReconstructionFidelityEvaluator",
    "ReconstructionFidelitySignal",
    "DegradationDetector",
    "DegradationAssessment",
    "CollapseTrailLogger",
    "get_collapse_trail_logger",
]

