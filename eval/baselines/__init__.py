"""Baseline systems for CRT eval.

Import ALL_SYSTEMS for the full comparison matrix.
CRTSystem requires a running CRTEnhancedRAG instance and LLM client.
The other four baselines are self-contained (no LLM, no CRT).
"""

from eval.baselines.plain_rag import PlainRAGSystem
from eval.baselines.destructive_update import DestructiveUpdateSystem
from eval.baselines.no_ledger import NoLedgerSystem
from eval.baselines.no_trust_weighting import NoTrustWeightingSystem
from eval.baselines.no_background_learning import NoBackgroundLearningSystem

# CRTSystem is optional — omitted from ALL_SYSTEMS to avoid forcing LLM init.
# Add it manually: from eval.baselines.crt_system import CRTSystem
ALL_SYSTEMS = [
    PlainRAGSystem(),
    DestructiveUpdateSystem(),
    NoLedgerSystem(),
    NoTrustWeightingSystem(),
    NoBackgroundLearningSystem(),
]
