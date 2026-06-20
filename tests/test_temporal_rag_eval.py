from labs.meaning_compression_lab.run_lab import Memory, Scenario, scenario_pack
from labs.meaning_compression_lab.temporal_rag_eval import (
    build_prompt,
    render_metadata_context,
    retrieve_records,
    run,
)
from labs.meaning_compression_lab.plain_rag_eval import PROBES


def _scenario(name):
    return next(
        scenario
        for scenario in scenario_pack(include_adversarial=True, include_hardening=True)
        if scenario.name == name
    )


def test_temporal_context_exposes_metadata_without_precompiled_state():
    scenario = _scenario("store_platform_authority_boundary")
    records = retrieve_records(scenario, PROBES[scenario.name].query)
    context = render_metadata_context(records)
    prompt = build_prompt(records, PROBES[scenario.name])

    assert "authority: confirmed" in context
    assert "authority: provisional" in context
    assert "source: assistant" in context
    assert "CURRENT store_platform" not in prompt
    assert "HISTORY store_platform" not in prompt
    assert "prefer the latest confirmed or locked user fact" in prompt


def test_temporal_baseline_emits_trace_and_severity_with_injected_answerer():
    scenario = _scenario("store_platform_authority_boundary")

    def answerer(prompt, model, timeout):
        assert model == "fake-model"
        return "custom e-commerce backend"

    out = run(
        model="fake-model",
        write_results=False,
        scenarios=[scenario],
        retrieval_mode="lexical",
        answerer=answerer,
    )
    row = out["scenarios"][0]

    assert row["judgment"]["contract_passed"] is True
    assert row["decision_trace"]["arm"] == "temporal_metadata_rag"
    assert row["decision_trace"]["state_transformation"] is None
    assert row["decision_trace"]["severity"] == "pass"
    assert out["aggregate"]["semantic_pass_count"] == 1


def test_hybrid_retrieval_uses_semantics_to_select_relevant_record_among_distractors():
    scenario = Scenario(
        name="retrieval_fixture",
        purpose="Exercise semantic retrieval with more memories than k.",
        memories=[
            Memory("The deployment region is us-east-1.", "user_fact", "confirmed", "webchat", 1),
            Memory("My camera body is a Sony FX3.", "user_fact", "confirmed", "webchat", 2),
            Memory("The database is backed up nightly.", "user_fact", "confirmed", "webchat", 3),
            Memory("I previously photographed with a Canon 80D.", "user_fact", "confirmed", "webchat", 4),
            Memory("The store uses a custom checkout.", "user_fact", "confirmed", "webchat", 5),
        ],
    )

    vectors = {
        "Which camera did I use before?": [1.0, 0.0],
        "The deployment region is us-east-1.": [0.0, 1.0],
        "My camera body is a Sony FX3.": [0.7, 0.3],
        "The database is backed up nightly.": [0.0, 1.0],
        "I previously photographed with a Canon 80D.": [1.0, 0.0],
        "The store uses a custom checkout.": [0.0, 1.0],
    }

    def embedder(texts):
        return [
            next(vector for text, vector in vectors.items() if text in item)
            for item in texts
        ]

    records = retrieve_records(
        scenario,
        "Which camera did I use before?",
        k=2,
        retrieval_mode="hybrid",
        embedder=embedder,
    )

    assert records[0]["text"] == "I previously photographed with a Canon 80D."
    assert records[0]["retrieval_mode"] == "hybrid"
    assert records[0]["semantic_score"] == 1.0
