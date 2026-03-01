from __future__ import annotations

from tools.agentic_eval.agents import AgentProtocolError, OllamaJsonAgent
from tools.agentic_eval.types import ObjectiveCard


class RetryAgent(OllamaJsonAgent):
    def __init__(self):
        super().__init__(role="attacker", model="fake", ollama_base_url="http://fake")
        self.chat_calls = 0
        self.repair_calls = 0

    def _chat(self, *, system: str, user: str, num_predict: int = 450) -> str:
        self.chat_calls += 1
        return "not-json"

    def _repair_json(self, *, invalid_text: str, required_keys):
        self.repair_calls += 1
        return {
            "objective_id": "obj_1",
            "user_message": "Generated adaptive turn content.",
            "hypothesis": "Protocol recovery works.",
            "expected_signals": ["signal_a"],
        }


class FailingAgent(OllamaJsonAgent):
    def __init__(self):
        super().__init__(role="attacker", model="fake", ollama_base_url="http://fake")

    def _chat(self, *, system: str, user: str, num_predict: int = 450) -> str:
        return "still invalid"

    def _repair_json(self, *, invalid_text: str, required_keys):
        return None


def test_attacker_protocol_repair_path():
    objective = ObjectiveCard(
        objective_id="obj_1",
        capability_target="memory stability",
        intent_constraints=["x"],
        expected_signals=["y"],
    )
    agent = RetryAgent()
    plan = agent.propose_turn(
        objective=objective,
        transcript_tail=[],
        latest_api_meta={},
        hard_fail_reasons=[],
    )
    assert plan.objective_id == "obj_1"
    assert "Generated adaptive turn content." in plan.user_message
    assert agent.chat_calls == 1
    assert agent.repair_calls >= 1


def test_attacker_protocol_failure_raises():
    objective = ObjectiveCard(
        objective_id="obj_2",
        capability_target="contradiction handling",
    )
    agent = FailingAgent()
    try:
        agent.propose_turn(
            objective=objective,
            transcript_tail=[],
            latest_api_meta={},
            hard_fail_reasons=[],
        )
    except AgentProtocolError as exc:
        assert "attacker protocol failure" in str(exc)
    else:
        raise AssertionError("Expected AgentProtocolError when attacker output is unrecoverable")
