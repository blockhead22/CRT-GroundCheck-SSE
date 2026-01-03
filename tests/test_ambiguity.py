from sse.ambiguity import hedge_score, analyze_ambiguity_for_claims


def test_hedge_score():
    assert hedge_score("The sky might be blue.") > 0
    assert hedge_score("The sky is blue.") == 0


def test_ambiguity_analysis():
    claims = [
        {"claim_id": "c1", "claim_text": "The sun might be bright.", "supporting_quotes": [{"quote_text": "The sun might be bright."}]},
    ]
    analyze_ambiguity_for_claims(claims)
    assert claims[0]['ambiguity']['hedge_score'] > 0
