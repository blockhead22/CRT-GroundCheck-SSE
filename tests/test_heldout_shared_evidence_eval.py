from labs.meaning_compression_lab.heldout_cases import HELDOUT_CASES
from labs.meaning_compression_lab.heldout_shared_evidence_eval import (
    records_to_scenario,
    run,
    score_case,
)


def _embedder(texts):
    return [[1.0, float(index)] for index, _text in enumerate(texts)]


def test_records_are_the_exact_memory_packet_used_for_governed_state():
    case = HELDOUT_CASES[0]
    captured = {}

    def temporal_answerer(prompt, model, timeout):
        captured["temporal_prompt"] = prompt
        return "Marcus"

    def scaffold_answerer(scaffold, probe, model, timeout):
        captured["scaffold"] = scaffold
        return "Marcus"

    row = score_case(
        case,
        model="fake",
        timeout=1,
        retrieval_mode="lexical",
        temporal_answerer=temporal_answerer,
        scaffold_answerer=scaffold_answerer,
    )
    reconstructed = records_to_scenario(case, row["retrieved_records"])

    assert [memory.text for memory in reconstructed.memories] == [
        record["text"] for record in row["retrieved_records"]
    ]
    assert [memory.text for memory in reconstructed.memories] != [
        memory.text for memory in case.scenario.memories
    ]
    for record in row["retrieved_records"]:
        assert record["text"] in captured["temporal_prompt"]
    assert row["temporal_judgment"]["semantic_passed"] is True
    assert row["scaffold_judgment"]["semantic_passed"] is True


def test_runner_aggregates_both_arms_with_injected_answerers():
    case = HELDOUT_CASES[0]

    out = run(
        models=["fake-a", "fake-b"],
        cases=(case,),
        retrieval_mode="lexical",
        write_results=False,
        temporal_answerer=lambda prompt, model, timeout: "Daniel",
        scaffold_answerer=lambda scaffold, probe, model, timeout: "Marcus",
    )

    assert out["aggregate"]["total_case_count"] == 2
    assert out["aggregate"]["temporal_semantic"] == 0
    assert out["aggregate"]["hybrid_semantic"] == 2
    assert out["aggregate"]["semantic_delta_points"] == 100.0
    assert out["aggregate"]["models_where_hybrid_wins"] == 2
