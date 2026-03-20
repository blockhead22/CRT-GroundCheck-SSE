"""CRTSystem — wraps the real CRTEnhancedRAG for eval.

Requires a live LLM client.  In mock mode (llm_client=None), queries are
answered using trust-weighted retrieval only (no generation).

Usage:

    from eval.baselines.crt_system import CRTSystem
    system = CRTSystem(llm_client=your_anthropic_client)
    runner.run_scenario(scenario, system, seed=0)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


class CRTSystem:
    name = "CRT"

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        self._llm_client = llm_client
        self._config = config
        self._tmp_dir: Optional[tempfile.TemporaryDirectory] = None
        self._engine: Optional[Any] = None
        self._init_engine()

    def _init_engine(self) -> None:
        from personal_agent.crt_rag import CRTEnhancedRAG

        self._tmp_dir = tempfile.TemporaryDirectory(prefix="crt_eval_")
        db_dir = Path(self._tmp_dir.name)
        self._engine = CRTEnhancedRAG(
            memory_db=str(db_dir / "memory.db"),
            ledger_db=str(db_dir / "ledger.db"),
            profile_db=str(db_dir / "profile.db"),
            config=self._config,
            llm_client=self._llm_client,
        )

    def reset(self) -> None:
        """Discard engine + temp DBs; create fresh engine for next seed."""
        if self._tmp_dir is not None:
            try:
                self._tmp_dir.cleanup()
            except Exception:
                pass
        self._tmp_dir = None
        self._engine = None
        self._init_engine()

    def query(self, message: str, thread_id: str = "eval") -> Dict[str, Any]:
        if self._engine is None:
            self._init_engine()

        raw = self._engine.query(  # type: ignore[union-attr]
            user_query=message,
            thread_id=thread_id,
        )

        # Normalise keys to what the runner expects
        return {
            "answer": raw.get("answer") or raw.get("response") or "",
            "response_type": raw.get("response_type", "speech"),
            "gates_passed": bool(raw.get("gates_passed", False)),
            "gate_reason": str(raw.get("gate_reason") or ""),
            "contradiction_detected": bool(raw.get("contradiction_detected", False)),
            "confidence": float(raw.get("confidence") or 0.0),
            "intent_alignment": float(raw.get("intent_alignment") or 0.0),
            "memory_alignment": float(raw.get("memory_alignment") or 0.0),
            "best_prior_trust": raw.get("best_prior_trust"),
        }

    def __del__(self) -> None:
        if self._tmp_dir is not None:
            try:
                self._tmp_dir.cleanup()
            except Exception:
                pass
