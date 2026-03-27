"""
Immune Agents for CRT/Aether

Autonomous monitors that enforce constitutional laws at runtime.
Each agent watches a specific boundary and fires when a violation occurs.

Agents:
- SpeechLeakDetector:        Enforces Law 1 ("Speech cannot upgrade belief")
- TemplateDetector:          Enforces Law 2 ("Low variance does not imply high confidence")
- PrematureResolutionGuard:  Enforces Law 3 ("Contradiction must be preserved before resolution")
- MemoryCorruptionGuard:     Enforces Law 4 ("Degraded reconstruction cannot silently overwrite trusted memory")
- GapAuditor:                Enforces Law 5 ("Outward confidence must be bounded by internal support")
"""

from .template_detector import TemplateDetector, Classification, DetectionResult

from .speech_leak_detector import SpeechLeakDetector, Verdict, VerdictType

from .premature_resolution_guard import (
    PrematureResolutionGuard,
    Contradiction,
    Disposition,
    ResolutionAction,
    VerdictAction,
)

from .memory_corruption_guard import (
    MemoryCorruptionGuard,
    Memory,
    OverwriteAction,
    OverwriteReason,
    OverwriteVerdict,
)

from .gap_auditor import (
    GapAuditor,
    ResponseAudit,
    GapVerdict,
    Severity,
    Action,
    Trend,
)

__all__ = [
    "TemplateDetector",
    "Classification",
    "DetectionResult",
    "SpeechLeakDetector",
    "Verdict",
    "VerdictType",
    "PrematureResolutionGuard",
    "Contradiction",
    "Disposition",
    "ResolutionAction",
    "VerdictAction",
    "MemoryCorruptionGuard",
    "Memory",
    "OverwriteAction",
    "OverwriteReason",
    "OverwriteVerdict",
    "GapAuditor",
    "ResponseAudit",
    "GapVerdict",
    "Severity",
    "Action",
    "Trend",
]
