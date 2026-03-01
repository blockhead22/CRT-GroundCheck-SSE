from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from .agents import AgentProtocolError, OllamaJsonAgent
from .api_client import ApiClient
from .artifacts import ArtifactWriter, utc_now_iso
from .groundcheck_lane import run_groundcheck_lane
from .model_autodiscovery import ModelSelection, select_models
from .objectives import ObjectivePlanner, load_objective_cards
from .rules import apply_findings_to_score, evaluate_judge_penalties, evaluate_rule_findings, infer_verdict
from .types import (
    AgentTurnPlan,
    CampaignSummary,
    JudgeAssessment,
    JudgeFinding,
    ProbeSnapshot,
    RunSummary,
    RuleFinding,
    ScoreState,
    TurnRecord,
)


@dataclass
class OrchestratorConfig:
    api_base_url: str = "http://127.0.0.1:8123"
    ollama_base_url: str = "http://127.0.0.1:11434"
    output_dir: str = "artifacts/agentic_eval"
    objectives_path: str = "tools/agentic_eval/agentic_eval_objectives.v1.json"
    campaigns: int = 3
    max_turns: int = 120
    min_turns: int = 40
    memory_probe_limit: int = 30
    continue_after_hard_fail: bool = True
    autodiscover_models: bool = True
    attacker_model: Optional[str] = None
    judge_model: Optional[str] = None
    attacker_temp: float = 0.25
    judge_temp: float = 0.15
    probe_attempts: int = 2
    probe_timeout_seconds: float = 45.0


class AgenticEvalOrchestrator:
    def __init__(self, cfg: OrchestratorConfig) -> None:
        self.cfg = cfg
        self.api = ApiClient(cfg.api_base_url, timeout_seconds=120.0)

    def _resolve_models(self) -> ModelSelection:
        if self.cfg.autodiscover_models:
            return select_models(
                ollama_base_url=self.cfg.ollama_base_url,
                attacker_model=self.cfg.attacker_model,
                judge_model=self.cfg.judge_model,
                probe_attempts=max(1, int(self.cfg.probe_attempts)),
                probe_timeout_seconds=max(10.0, float(self.cfg.probe_timeout_seconds)),
            )
        attacker = (self.cfg.attacker_model or "").strip()
        judge = (self.cfg.judge_model or "").strip()
        if not attacker or not judge:
            raise RuntimeError("autodiscover disabled, but attacker_model/judge_model not both provided.")
        return ModelSelection(
            attacker_model=attacker,
            judge_model=judge,
            ollama_base_url=self.cfg.ollama_base_url,
            probes=[],
        )

    def _new_judge_assessment_from_error(self, objective_id: str, error: str) -> JudgeAssessment:
        return JudgeAssessment(
            objective_id=objective_id,
            objective_passed=False,
            summary="Judge protocol error.",
            findings=[
                JudgeFinding(
                    finding_id="judge_protocol_error",
                    severity="critical",
                    passed=False,
                    summary=error,
                    evidence=[error],
                    tags=["agent_protocol"],
                )
            ],
            next_objective_hint=None,
        )

    def run(self) -> Dict[str, Any]:
        health = self.api.health()
        if not health.get("ok"):
            raise RuntimeError(f"API is not healthy at {self.cfg.api_base_url}: {health.get('error')}")

        model_selection = self._resolve_models()
        attacker_agent = OllamaJsonAgent(
            role="attacker",
            model=model_selection.attacker_model,
            ollama_base_url=model_selection.ollama_base_url,
            temperature=float(self.cfg.attacker_temp),
        )
        judge_agent = OllamaJsonAgent(
            role="judge",
            model=model_selection.judge_model,
            ollama_base_url=model_selection.ollama_base_url,
            temperature=float(self.cfg.judge_temp),
        )

        objectives = load_objective_cards(Path(self.cfg.objectives_path))
        planner = ObjectivePlanner(objectives)
        score = ScoreState()

        run_id = datetime.now(timezone.utc).strftime("agentic_eval_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        writer = ArtifactWriter(output_root=Path(self.cfg.output_dir), run_id=run_id)

        started_at = utc_now_iso()
        hard_fail_reasons: List[str] = []
        top_findings: List[Dict[str, Any]] = []
        campaign_summaries: List[CampaignSummary] = []
        turns_total = 0
        seed_materials: List[str] = []

        writer.write_manifest(
            {
                "run_id": run_id,
                "written_at_utc": utc_now_iso(),
                "config": asdict(self.cfg),
                "model_selection": model_selection.to_dict(),
            }
        )

        for campaign_id in range(1, max(1, int(self.cfg.campaigns)) + 1):
            thread_id = f"{run_id}_c{campaign_id:02d}"
            self.api.reset_thread(thread_id)

            transcript_tail: List[Dict[str, Any]] = []
            judge_hint: Optional[str] = None
            campaign_hard_fail = False
            campaign_hard_fail_reasons: List[str] = []
            judge_failure_count = 0
            rule_failure_count = 0
            no_new_findings_streak = 0
            campaign_turn_count = 0

            for turn in range(1, max(1, int(self.cfg.max_turns)) + 1):
                objective = planner.next_objective(judge_hint=judge_hint)

                # Attacker plan generation. If this fails, that's a hard protocol failure.
                try:
                    attacker_plan = attacker_agent.propose_turn(
                        objective=objective,
                        transcript_tail=transcript_tail,
                        latest_api_meta=(transcript_tail[-1].get("api_meta") if transcript_tail else {}),
                        hard_fail_reasons=hard_fail_reasons,
                    )
                except AgentProtocolError as exc:
                    campaign_hard_fail = True
                    reason = f"campaign={campaign_id} turn={turn} attacker_protocol_failure"
                    hard_fail_reasons.append(reason)
                    campaign_hard_fail_reasons.append(reason)
                    top_findings.append(
                        {
                            "turn": turn,
                            "severity": "critical",
                            "finding_id": "attacker_protocol_failure",
                            "summary": str(exc),
                        }
                    )
                    break

                api_result = self.api.chat_send(thread_id=thread_id, message=attacker_plan.user_message)
                probes = self.api.collect_probe_snapshot(
                    thread_id=thread_id,
                    memory_limit=max(5, int(self.cfg.memory_probe_limit)),
                )

                try:
                    judge = judge_agent.judge_turn(
                        objective=objective,
                        attacker_plan=attacker_plan,
                        api_response=api_result.to_dict(),
                        probe_snapshot=probes.to_dict(),
                        transcript_tail=transcript_tail,
                    )
                except AgentProtocolError as exc:
                    judge = self._new_judge_assessment_from_error(objective.objective_id, str(exc))

                rule_findings = evaluate_rule_findings(
                    api_result=api_result,
                    judge=judge,
                    attacker_message=attacker_plan.user_message,
                )
                score = evaluate_judge_penalties(score, judge)
                score = apply_findings_to_score(score, rule_findings)

                failed_judge_items = [f for f in judge.findings if not f.passed]
                failed_rule_items = [f for f in rule_findings if not f.passed]
                judge_failure_count += len(failed_judge_items)
                rule_failure_count += len(failed_rule_items)

                hard_this_turn = any(f.hard_fail for f in failed_rule_items)
                hard_turn_reasons = [f.finding_id for f in failed_rule_items if f.hard_fail]
                if hard_this_turn:
                    campaign_hard_fail = True
                    for item in hard_turn_reasons:
                        reason = f"campaign={campaign_id} turn={turn} {item}"
                        hard_fail_reasons.append(reason)
                        campaign_hard_fail_reasons.append(reason)

                now = utc_now_iso()
                record = TurnRecord(
                    turn=turn,
                    campaign_id=campaign_id,
                    objective_id=objective.objective_id,
                    attacker_plan=attacker_plan,
                    api_result=api_result,
                    probes=probes,
                    judge=judge,
                    rule_findings=rule_findings,
                    hard_fail_triggered=hard_this_turn,
                    hard_fail_reasons=hard_turn_reasons,
                    timestamp_utc=now,
                )
                writer.append_turn(record)
                turns_total += 1
                campaign_turn_count += 1

                transcript_tail.append(
                    {
                        "turn": turn,
                        "objective_id": objective.objective_id,
                        "user": attacker_plan.user_message,
                        "answer": api_result.answer,
                        "api_meta": api_result.metadata,
                        "judge_summary": judge.summary,
                    }
                )
                seed_materials.append(attacker_plan.user_message)
                if api_result.answer:
                    seed_materials.append(api_result.answer[:260])
                transcript_tail = transcript_tail[-12:]
                judge_hint = judge.next_objective_hint

                if failed_judge_items or failed_rule_items:
                    no_new_findings_streak = 0
                else:
                    no_new_findings_streak += 1

                for jf in failed_judge_items:
                    top_findings.append(
                        {
                            "turn": turn,
                            "severity": jf.severity,
                            "finding_id": jf.finding_id,
                            "summary": jf.summary,
                        }
                    )
                for rf in failed_rule_items:
                    top_findings.append(
                        {
                            "turn": turn,
                            "severity": rf.severity,
                            "finding_id": rf.finding_id,
                            "summary": rf.summary,
                        }
                    )

                if hard_this_turn and (not self.cfg.continue_after_hard_fail):
                    break
                if turn >= max(1, int(self.cfg.min_turns)) and no_new_findings_streak >= 20:
                    break

            campaign_summaries.append(
                CampaignSummary(
                    campaign_id=campaign_id,
                    thread_id=thread_id,
                    turns=campaign_turn_count,
                    hard_fail=campaign_hard_fail,
                    hard_fail_reasons=campaign_hard_fail_reasons,
                    judge_failure_count=judge_failure_count,
                    rule_failure_count=rule_failure_count,
                    score_end=score.total,
                )
            )

        # Standalone GroundCheck lane.
        groundcheck_summary, groundcheck_cases = run_groundcheck_lane(
            attacker_agent=attacker_agent,
            objective_context={
                "objective_stats": planner.stats(),
                "hard_fail_reasons": hard_fail_reasons[-20:],
                "score_total": score.total,
                "seed_texts": seed_materials[-40:],
            },
            case_count=6,
        )
        if bool(groundcheck_summary.get("hard_fail")):
            for reason in groundcheck_summary.get("hard_fail_reasons", []) or []:
                hard_fail_reasons.append(f"groundcheck:{reason}")

        finished_at = utc_now_iso()
        verdict = infer_verdict(score_total=score.total, hard_fail=bool(hard_fail_reasons))
        run_summary = RunSummary(
            run_id=run_id,
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            campaigns=len(campaign_summaries),
            turns_total=turns_total,
            hard_fail=bool(hard_fail_reasons),
            hard_fail_reasons=hard_fail_reasons,
            verdict=verdict,  # type: ignore[arg-type]
            score=score,
            model_selection=model_selection.to_dict(),
            groundcheck_lane=groundcheck_summary,
        )

        campaigns_path = writer.write_campaigns(campaign_summaries)
        groundcheck_path = writer.write_groundcheck_lane(groundcheck_summary, groundcheck_cases)
        run_summary_path = writer.write_run_summary(run_summary)
        report_path = writer.write_report_markdown(
            summary=run_summary,
            campaigns=campaign_summaries,
            hard_fail_reasons=hard_fail_reasons,
            top_findings=top_findings,
            objective_stats=planner.stats(),
        )

        return {
            "run_id": run_id,
            "run_dir": str(writer.run_dir),
            "run_summary": run_summary.to_dict(),
            "run_summary_path": str(run_summary_path),
            "campaigns_path": str(campaigns_path),
            "groundcheck_path": str(groundcheck_path),
            "report_path": str(report_path),
            "turns_jsonl_path": str(writer.turns_jsonl_path),
        }
