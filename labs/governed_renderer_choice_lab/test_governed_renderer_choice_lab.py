from __future__ import annotations

from labs.governed_renderer_choice_lab.governed_renderer_choice_lab import (
    RenderReceipt,
    evaluate_renderer,
    frozen_packet,
    packet_set_sha256,
)
from aether.memory.retrieve import EvidencePack


class FakeRenderer:
    provider = "fake"
    model = "fake-model"

    def __init__(self, answers: list[str]) -> None:
        self.answers = iter(answers)

    def preflight(self):
        return {"tools_allowed": False, "writes_allowed": False}

    def render(self, *, prompt: str, system_prompt: str) -> RenderReceipt:
        return RenderReceipt(
            answer=next(self.answers),
            provider=self.provider,
            model=self.model,
            latency_s=0.1,
            input_tokens=10,
            output_tokens=5,
        )


def _case() -> dict:
    return {
        "id": "simple",
        "prompt": "Return the governed marker.",
        "query": "Return the governed marker.",
        "pack": EvidencePack(query="Return the governed marker."),
        "required": ("amber",),
        "forbidden": ("violet",),
    }


def test_packet_hash_is_stable_and_contract_sensitive():
    case = _case()
    first = frozen_packet(case)
    second = frozen_packet(dict(case))
    changed = frozen_packet({**case, "forbidden": ("violet", "blue")})

    assert first["sha256"] == second["sha256"]
    assert first["sha256"] != changed["sha256"]
    assert packet_set_sha256([first]) == packet_set_sha256([second])


def test_failed_draft_text_is_not_persisted_after_successful_repair():
    renderer = FakeRenderer([
        "This answer says violet and is rejected.",
        "The governed marker is amber and this sentence is long enough to pass.",
    ])

    payload = evaluate_renderer(renderer, cases=[_case()])
    row = payload["results"][0]

    assert row["first_pass"] is False
    assert row["repaired"] is True
    assert row["final_pass"] is True
    assert "This answer says violet and is rejected." not in str(row)
    assert row["rejected_draft_sha256"]
    assert "amber" in row["accepted_answer"]
    assert row["authority"]["writes_allowed"] is False
