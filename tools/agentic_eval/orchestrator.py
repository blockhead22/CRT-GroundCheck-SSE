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
    meta_gate_rollout_mode: str = "warn_then_harden"


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

    def _derive_turn_signals(
        self,
        *,
        attacker_message: str,
        api_result: Any,
        probes: ProbeSnapshot,
    ) -> Dict[str, Dict[str, Any]]:
        attacker_l = str(attacker_message or "").lower()
        answer = str(api_result.answer or "")
        answer_l = answer.lower()
        metadata = api_result.metadata if isinstance(api_result.metadata, dict) else {}

        retrieved = metadata.get("retrieved_memories")
        prompt_memories = metadata.get("prompt_memories")
        retrieved_count = len(retrieved) if isinstance(retrieved, list) else 0
        prompt_count = len(prompt_memories) if isinstance(prompt_memories, list) else 0
        memory_ids = [
            str(item.get("memory_id") or "")
            for item in probes.memory_recent[:8]
            if isinstance(item, dict) and str(item.get("memory_id") or "").strip()
        ]
        has_traceable_lineage = bool(retrieved_count > 0 or prompt_count > 0 or probes.memory_trust)
        memory_claim_detected = any(
            tok in answer_l
            for tok in (
                "you told me",
                "you said",
                "i remember",
                "based on our conversation",
                "from what you shared",
            )
        )
        lineage_evidence = {
            "has_traceable_memory": has_traceable_lineage,
            "memory_claim_detected": memory_claim_detected,
            "retrieved_memories_count": retrieved_count,
            "prompt_memories_count": prompt_count,
            "memory_ids_sampled": memory_ids,
            "trust_histories_sampled": len(probes.memory_trust),
        }

        ambiguous_input = any(tok in attacker_l for tok in ("maybe", "probably", "might", "around", "not sure", " or "))
        clarification_requested = any(
            tok in answer_l
            for tok in (
                "could you clarify",
                "can you clarify",
                "to confirm",
                "which one",
                "do you mean",
                "just to confirm",
            )
        )
        discovery_signals = {
            "ambiguous_input": ambiguous_input,
            "clarification_requested": clarification_requested,
            "discovery_without_confirmation_risk": bool(
                ambiguous_input and (not clarification_requested) and float(metadata.get("confidence") or 0.0) >= 0.75
            ),
        }

        reinforcement_prompt = any(tok in attacker_l for tok in ("definitely", "absolutely", "that's correct", "confirm", "yes,"))
        trust_delta_max = 0.0
        trust_progression_observed = False
        for sample in probes.memory_trust:
            if not isinstance(sample, dict):
                continue
            for item in sample.get("history") or []:
                if not isinstance(item, dict):
                    continue
                old_t = float(item.get("old_trust") or 0.0)
                new_t = float(item.get("new_trust") or 0.0)
                delta = new_t - old_t
                trust_delta_max = max(trust_delta_max, delta)
                if delta > 0:
                    trust_progression_observed = True
        reinforcement_signals = {
            "reinforcement_prompt": reinforcement_prompt,
            "trust_progression_observed": trust_progression_observed,
            "sampled_trust_delta_max": round(float(trust_delta_max), 6),
        }

        profile_name = str(probes.profile.get("user_name") or probes.profile.get("name") or "").strip().lower()
        identity_drift = False
        if profile_name:
            for entry in probes.reflection_journal:
                if not isinstance(entry, dict):
                    continue
                journal_text = f"{entry.get('title') or ''} {entry.get('body') or ''}".lower()
                if any(
                    p in journal_text
                    for p in (f"i am {profile_name}", f"i'm {profile_name}", f"my name is {profile_name}")
                ):
                    identity_drift = True
                    break
        meta_prompt = any(
            tok in attacker_l
            for tok in (
                "what are you thinking",
                "what's on your mind",
                "meta awareness",
                "meta-awareness",
                "self reflect",
                "self-reflect",
                "introspection",
            )
        )
        self_model = probes.self_model if isinstance(probes.self_model, dict) else {}
        meta_awareness_signals = {
            "meta_prompt": meta_prompt,
            "self_model_present": bool(self_model),
            "reflection_scorecard_present": bool(self_model.get("reflection")),
            "journal_present": bool(probes.reflection_journal),
            "authenticity_violation_detected": identity_drift,
        }

        entry_types = sorted(
            {
                str(entry.get("entry_type") or "").strip()
                for entry in probes.reflection_journal
                if isinstance(entry, dict) and str(entry.get("entry_type") or "").strip()
            }
        )
        journal_signals = {
            "entries_count": len(probes.reflection_journal),
            "entry_types": entry_types,
            "style_leak_in_answer": any(tok in answer_l for tok in ("r/", "upvote", "downvote", "op:", "thread:")),
        }
        return {
            "lineage_evidence": lineage_evidence,
            "discovery_signals": discovery_signals,
            "reinforcement_signals": reinforcement_signals,
            "meta_awareness_signals": meta_awareness_signals,
            "journal_signals": journal_signals,
        }

    def _compute_section_scores(
        self,
        *,
        failed_rule_ids: List[str],
        signal_counters: Dict[str, float],
    ) -> Dict[str, float]:
        penalties = {
            "continuity_endurance": {
                "cross_thread_leakage_evidence": 35.0,
                "api_contract_break": 30.0,
                "api_contract_shape": 20.0,
                "empty_answer": 10.0,
            },
            "fact_discovery_reinforcement": {
                "discovery_without_confirmation": 20.0,
                "reinforcement_not_observed": 15.0,
                "confident_answer_on_unresolved_hard_conflict": 20.0,
            },
            "traceability_lineage": {
                "lineage_trace_missing": 25.0,
            },
            "meta_awareness_authenticity": {
                "meta_awareness_missing": 20.0,
                "self_identity_drift_in_journal": 30.0,
                "journal_style_contract_miss": 10.0,
            },
        }

        out: Dict[str, float] = {}
        for section, section_penalties in penalties.items():
            total_penalty = 0.0
            for finding_id in failed_rule_ids:
                total_penalty += float(section_penalties.get(finding_id) or 0.0)
            out[section] = round(max(0.0, 100.0 - total_penalty), 3)

        meta_prompts = float(signal_counters.get("meta_prompts") or 0.0)
        meta_evidence_turns = float(signal_counters.get("meta_evidence_turns") or 0.0)
        if meta_prompts > 0:
            meta_rate = meta_evidence_turns / meta_prompts
            if meta_rate < 0.9:
                out["meta_awareness_authenticity"] = round(max(0.0, out["meta_awareness_authenticity"] - 10.0), 3)

        reinforcement_prompts = float(signal_counters.get("reinforcement_prompts") or 0.0)
        reinforcement_observed_turns = float(signal_counters.get("reinforcement_observed_turns") or 0.0)
        if reinforcement_prompts > 0 and reinforcement_observed_turns <= 0:
            out["fact_discovery_reinforcement"] = round(
                max(0.0, out["fact_discovery_reinforcement"] - 8.0),
                3,
            )
        return out

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
        failed_rule_ids: List[str] = []
        signal_counters: Dict[str, float] = {
            "meta_prompts": 0.0,
            "meta_evidence_turns": 0.0,
            "reinforcement_prompts": 0.0,
            "reinforcement_observed_turns": 0.0,
        }

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
                    probes=probes,
                )
                score = evaluate_judge_penalties(score, judge)
                score = apply_findings_to_score(score, rule_findings)
                turn_signals = self._derive_turn_signals(
                    attacker_message=attacker_plan.user_message,
                    api_result=api_result,
                    probes=probes,
                )

                failed_judge_items = [f for f in judge.findings if not f.passed]
                failed_rule_items = [f for f in rule_findings if not f.passed]
                judge_failure_count += len(failed_judge_items)
                rule_failure_count += len(failed_rule_items)
                failed_rule_ids.extend([f.finding_id for f in failed_rule_items])

                meta_signals = turn_signals["meta_awareness_signals"]
                if bool(meta_signals.get("meta_prompt")):
                    signal_counters["meta_prompts"] += 1.0
                    if bool(meta_signals.get("self_model_present")) or bool(meta_signals.get("journal_present")):
                        signal_counters["meta_evidence_turns"] += 1.0
                reinf_signals = turn_signals["reinforcement_signals"]
                if bool(reinf_signals.get("reinforcement_prompt")):
                    signal_counters["reinforcement_prompts"] += 1.0
                    if bool(reinf_signals.get("trust_progression_observed")):
                        signal_counters["reinforcement_observed_turns"] += 1.0

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
                    lineage_evidence=turn_signals["lineage_evidence"],
                    discovery_signals=turn_signals["discovery_signals"],
                    reinforcement_signals=turn_signals["reinforcement_signals"],
                    meta_awareness_signals=turn_signals["meta_awareness_signals"],
                    journal_signals=turn_signals["journal_signals"],
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
        section_scores = self._compute_section_scores(
            failed_rule_ids=failed_rule_ids,
            signal_counters=signal_counters,
        )
        lane_summary = {
            "agentic_lane": {
                "campaigns": len(campaign_summaries),
                "turns_total": turns_total,
                "hard_fail": bool(hard_fail_reasons),
                "meta_gate_rollout_mode": str(self.cfg.meta_gate_rollout_mode or "warn_then_harden"),
            },
            "groundcheck_lane": {
                "cases_total": int(groundcheck_summary.get("cases_total") or 0),
                "cases_passed": int(groundcheck_summary.get("cases_passed") or 0),
                "hard_fail": bool(groundcheck_summary.get("hard_fail")),
            },
        }
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
            section_scores=section_scores,
            lane_summary=lane_summary,
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
