"""Reconstruction fidelity hook (Holden integration point)."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import re

from personal_agent.crt_core import SSEMode


@dataclass
class ReconstructionFidelitySignal:
    fidelity: float
    loss: float
    compressed_text: str
    reconstructed_text: str


class ReconstructionFidelityEvaluator:
    """Heuristic round-trip evaluator.

    This intentionally provides a stable interface now and can be swapped with a
    learned compressor/reconstructor in DNNT later.
    """

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    @staticmethod
    def _compress(text: str, sse_mode: SSEMode) -> str:
        raw = (text or "").strip()
        if not raw:
            return ""

        if sse_mode == SSEMode.LOSSLESS:
            return raw

        if sse_mode == SSEMode.HYBRID:
            compact = re.sub(r"\s+", " ", raw).strip()
            compact = re.sub(r"([.!?]){2,}", r"\1", compact)
            return compact

        # COGNI style: keep first and last sentence as a summary shell.
        parts = re.split(r"(?<=[.!?])\s+", raw)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) <= 1:
            return parts[0] if parts else raw
        return f"{parts[0]} {parts[-1]}".strip()

    @staticmethod
    def _reconstruct(compressed: str, sse_mode: SSEMode) -> str:
        if sse_mode in {SSEMode.LOSSLESS, SSEMode.HYBRID}:
            return compressed
        return f"Summary reconstruction: {compressed}".strip()

    def evaluate(self, *, text: str, sse_mode: SSEMode) -> ReconstructionFidelitySignal:
        compressed = self._compress(text, sse_mode)
        reconstructed = self._reconstruct(compressed, sse_mode)

        reference = self._normalize(text)
        candidate = self._normalize(reconstructed)
        if not reference and not candidate:
            fidelity = 1.0
        else:
            fidelity = difflib.SequenceMatcher(None, reference, candidate).ratio()
        fidelity = max(0.0, min(1.0, float(fidelity)))

        return ReconstructionFidelitySignal(
            fidelity=fidelity,
            loss=1.0 - fidelity,
            compressed_text=compressed,
            reconstructed_text=reconstructed,
        )

