from pathlib import Path

from labs.causal_evidence_receipt_lab.grok_transport_adaptation import (
    GrokTwoTurnTransport,
)


def test_transport_changes_only_max_turn_allowance(tmp_path: Path):
    renderer = GrokTwoTurnTransport()
    base = GrokTwoTurnTransport.__mro__[1].command(
        renderer,
        prompt="synthetic prompt",
        system_prompt="synthetic system",
        cwd=tmp_path,
    )
    adapted = renderer.command(
        prompt="synthetic prompt",
        system_prompt="synthetic system",
        cwd=tmp_path,
    )

    marker = base.index("--max-turns")
    assert base[marker + 1] == "1"
    assert adapted[marker + 1] == "2"
    assert base[: marker + 1] == adapted[: marker + 1]
    assert base[marker + 2 :] == adapted[marker + 2 :]
    for required in (
        "--no-memory",
        "--no-subagents",
        "--disable-web-search",
        "--disallowed-tools",
        "--sandbox",
        "read-only",
    ):
        assert required in adapted
