from personal_agent.crt_critic import CRTCritic


def test_dedupe_conflict_values_collapses_case_and_spacing_variants():
    values = ["nick block", "Nick  Block", "nick", "Nick", "NICK"]
    trusts = [0.7, 0.9, 0.6, 0.8, 0.75]

    out = CRTCritic._dedupe_conflict_values(values, trusts)

    # Expect canonical groups: "nick block" and "nick".
    norms = [item["norm"] for item in out]
    assert norms == ["nick block", "nick"]

    # Highest-trust representative should win for each canonical value.
    top = {item["norm"]: item for item in out}
    assert top["nick block"]["trust"] == 0.9
    assert top["nick"]["trust"] == 0.8

