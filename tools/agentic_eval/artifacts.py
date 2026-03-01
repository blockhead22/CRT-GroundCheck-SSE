from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .types import CampaignSummary, GroundCheckCaseResult, RunSummary, TurnRecord


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactWriter:
    def __init__(self, *, output_root: Path, run_id: str) -> None:
        self.output_root = output_root
        self.run_id = run_id
        self.run_dir = self.output_root / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.turns_jsonl_path = self.run_dir / "turns.jsonl"
        self.turns_jsonl_path.write_text("", encoding="utf-8")

    def append_turn(self, turn: TurnRecord) -> None:
        with self.turns_jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(turn.to_dict(), ensure_ascii=True) + "\n")

    def write_manifest(self, payload: Dict[str, Any]) -> Path:
        path = self.run_dir / "run_manifest.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return path

    def write_campaigns(self, campaigns: Iterable[CampaignSummary]) -> Path:
        path = self.run_dir / "campaigns.json"
        obj = {
            "written_at_utc": utc_now_iso(),
            "campaigns": [c.to_dict() for c in campaigns],
        }
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=True), encoding="utf-8")
        return path

    def write_groundcheck_lane(self, payload: Dict[str, Any], cases: List[GroundCheckCaseResult]) -> Path:
        path = self.run_dir / "groundcheck_lane.json"
        obj = {
            "written_at_utc": utc_now_iso(),
            "summary": payload,
            "cases": [c.to_dict() for c in cases],
        }
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=True), encoding="utf-8")
        return path

    def write_run_summary(self, summary: RunSummary) -> Path:
        path = self.run_dir / "run_summary.json"
        path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
        return path

    def write_report_markdown(
        self,
        *,
        summary: RunSummary,
        campaigns: List[CampaignSummary],
        hard_fail_reasons: List[str],
        top_findings: List[Dict[str, Any]],
        objective_stats: Dict[str, int],
    ) -> Path:
        path = self.run_dir / "report.md"
        lines: List[str] = []
        lines.append("# Agentic Conversation Evaluation Report")
        lines.append("")
        lines.append(f"- Run ID: `{summary.run_id}`")
        lines.append(f"- Started: `{summary.started_at_utc}`")
        lines.append(f"- Finished: `{summary.finished_at_utc}`")
        lines.append(f"- Verdict: **{summary.verdict}**")
        lines.append(f"- Score: **{summary.score.total:.2f} / 100**")
        lines.append("")
        lines.append("## Score Breakdown")
        score = summary.score.to_dict()
        lines.append(f"- contradiction_lifecycle: `{score['contradiction_lifecycle']}`")
        lines.append(f"- grounding_faithfulness: `{score['grounding_faithfulness']}`")
        lines.append(f"- isolation_resilience: `{score['isolation_resilience']}`")
        lines.append(f"- injection_resilience: `{score['injection_resilience']}`")
        lines.append(f"- operational_stability: `{score['operational_stability']}`")
        lines.append("")
        lines.append("## Hard-Fail Status")
        if hard_fail_reasons:
            for reason in hard_fail_reasons:
                lines.append(f"- {reason}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("## Campaigns")
        for c in campaigns:
            lines.append(
                f"- campaign={c.campaign_id} turns={c.turns} hard_fail={c.hard_fail} "
                f"judge_failures={c.judge_failure_count} rule_failures={c.rule_failure_count} score_end={c.score_end:.2f}"
            )
        lines.append("")
        lines.append("## Objective Coverage")
        for objective_id, count in sorted(objective_stats.items()):
            lines.append(f"- {objective_id}: {count}")
        lines.append("")
        lines.append("## Top Findings")
        if top_findings:
            for item in top_findings[:30]:
                lines.append(
                    f"- severity={item.get('severity')} id={item.get('finding_id')} "
                    f"turn={item.get('turn')} summary={item.get('summary')}"
                )
        else:
            lines.append("- No findings recorded.")
        lines.append("")
        lines.append("## GroundCheck Standalone Lane")
        lines.append(f"- {json.dumps(summary.groundcheck_lane, ensure_ascii=True)}")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
