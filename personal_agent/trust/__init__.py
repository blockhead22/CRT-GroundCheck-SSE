"""trust subpackage — trust evolution, decay, and recalibration.

Re-exports all public symbols so callers can do:
    from personal_agent.trust import compute_grounding_score, run_trust_decay_pass, ...
"""

from .evolution import (
    compute_grounding_score,
    should_express_uncertainty,
    generate_uncertain_response,
)
from .decay import (
    DECAY_RATE,
    REINFORCE_BOOST,
    CORRECTION_BOOST,
    TRUST_FLOOR,
    TRUST_CEILING,
    GRACE_PERIOD_DAYS,
    MIN_PASS_INTERVAL_SECS,
    run_trust_decay_pass,
    reinforce_memory,
)
from .recalibration import (
    KIND_BASE,
    recalibrate,
)

__all__ = [
    # evolution
    "compute_grounding_score",
    "should_express_uncertainty",
    "generate_uncertain_response",
    # decay
    "DECAY_RATE",
    "REINFORCE_BOOST",
    "CORRECTION_BOOST",
    "TRUST_FLOOR",
    "TRUST_CEILING",
    "GRACE_PERIOD_DAYS",
    "MIN_PASS_INTERVAL_SECS",
    "run_trust_decay_pass",
    "reinforce_memory",
    # recalibration
    "KIND_BASE",
    "recalibrate",
]
