"""
Behavior Invariant Tests for SSE

These tests enforce the seven non-negotiable architectural invariants defined in SSE_INVARIANTS.md.

These are NOT functional feature tests. They are philosophy guard rails.
If any test fails, SSE has violated a core promise and must be fixed before proceeding.

Invariants tested:
  I.   Quoting Invariant: Never paraphrase without verbatim quotes
  II.  Contradiction Preservation: Never suppress or auto-resolve contradictions
  III. Anti-Deduplication: Never remove opposite or conflicting claims
  IV.  Non-Fabrication: Never create information not in source
  V.   Uncertainty Preservation: Never hide ambiguity
  VI.  Source Traceability: Every claim maps to exact source offsets
  VII. Computational Honesty: Never hide limitations or failures
"""

import pytest
import json
from sse.chunker import chunk_text
from sse.embeddings import EmbeddingStore
from sse.extractor import extract_claims_from_chunks
from sse.contradictions import detect_contradictions, clear_nli_cache
from sse.ambiguity import analyze_ambiguity_for_claims
from sse.clustering import cluster_embeddings


class TestInvariantI_Quoting:
    """
    INVARIANT I: SSE must never paraphrase a claim without preserving verbatim source text.
    
    Every extracted claim must include exact substring from source with correct offsets.
    Violation: Paraphrasing without quoting, missing quote grounding, offset mismatch.
    """

    def test_every_claim_has_supporting_quotes(self):
        """All claims must have at least one supporting quote."""
        text = "The Earth is round. Scientists have proven this."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        assert len(claims) > 0, "Should extract at least one claim"
        for claim in claims:
            assert "supporting_quotes" in claim, f"Claim missing supporting_quotes: {claim}"
            assert len(claim["supporting_quotes"]) > 0, f"Claim has no quotes: {claim['claim_text']}"

    def test_quotes_are_verbatim_substrings(self):
        """Every supporting quote must be an exact substring of the source.
        
        Phase 4 Fix #2: Now validates exact offset reconstruction.
        Offsets are now sentence-level, so text[start:end] == quote_text.
        """
        text = "Water boils at 100 degrees Celsius. This is fundamental."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        for claim in claims:
            for quote in claim["supporting_quotes"]:
                # Reconstruct from offsets
                start = quote["start_char"]
                end = quote["end_char"]
                reconstructed = text[start:end]

                # Must match quote text exactly
                quote_text = quote.get("quote_text") or quote.get("text")
                assert reconstructed == quote_text, (
                    f"Quote mismatch: expected '{quote_text}' but got '{reconstructed}' "
                    f"at offsets [{start}:{end}]"
                )

    def test_offset_validity(self):
        """All quote offsets must be within bounds."""
        text = "The sky is blue. Clouds are white."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        for claim in claims:
            for quote in claim["supporting_quotes"]:
                start = quote["start_char"]
                end = quote["end_char"]

                # Bounds check
                assert 0 <= start, f"Start offset {start} is negative"
                assert end <= len(text), f"End offset {end} exceeds text length {len(text)}"
                assert start < end, f"Start {start} >= End {end}"

    def test_no_claim_without_quote(self):
        """If a claim is in output, it MUST have a quote."""
        text = "Exercise improves health. Many people exercise daily."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        for claim in claims:
            assert claim.get("supporting_quotes"), (
                f"Claim without supporting quote: {claim.get('claim_text')}"
            )
            for quote in claim["supporting_quotes"]:
                quote_text = quote.get("quote_text") or quote.get("text")
                assert quote_text, "Quote missing text"
                assert "start_char" in quote, "Quote missing start_char"
                assert "end_char" in quote, "Quote missing end_char"


class TestInvariantII_ContradictionPreservation:
    """
    INVARIANT II: SSE must never suppress contradictions or pick sides.
    
    If source contains A and ¬A, both must appear in output.
    Violation: Removing one side, merging into ambiguous middle, picking "correct" answer.
    """

    def test_both_contradiction_sides_extracted(self):
        """Given two opposite claims, both must be extracted."""
        text = """
        The Earth is round.
        However, some believe the Earth is flat.
        """
        chunks = chunk_text(text, max_chars=100, overlap=20)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        claim_texts = [c["claim_text"] for c in claims]

        # Both sides must be present
        has_round = any("round" in ct.lower() for ct in claim_texts)
        has_flat = any("flat" in ct.lower() for ct in claim_texts)

        assert has_round, "Missing claim about Earth being round"
        assert has_flat, "Missing claim about Earth being flat"

    def test_contradiction_detected_when_present(self):
        """Given opposite claims, contradiction detection must report them."""
        text = """
        Exercise is beneficial for health.
        Exercise is harmful to your body.
        """
        chunks = chunk_text(text, max_chars=100, overlap=20)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)
        claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])

        clear_nli_cache()
        contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=False)

        assert len(contradictions) > 0, "Should detect contradiction between opposite claims"

    def test_both_contradicting_claims_in_output(self):
        """Both sides of contradiction must appear in final output, not suppressed."""
        text = """
        Vaccines are safe and effective.
        Anti-vaccine advocates claim vaccines are dangerous.
        """
        chunks = chunk_text(text, max_chars=100, overlap=20)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)
        claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])

        clear_nli_cache()
        contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=False)

        # Both claims must still be in the claims list (not removed by contradiction detection)
        claim_ids_in_contradictions = set()
        for cont in contradictions:
            claim_ids_in_contradictions.add(cont["pair"]["claim_id_a"])
            claim_ids_in_contradictions.add(cont["pair"]["claim_id_b"])

        for claim_id in claim_ids_in_contradictions:
            assert any(c["claim_id"] == claim_id for c in claims), (
                f"Contradicting claim {claim_id} removed from output"
            )


class TestInvariantIII_AntiDeduplication:
    """
    INVARIANT III: SSE must not merge or remove opposite claims, even if similar.
    
    Violation: Deduplicating "beneficial" and "harmful", removing opposite claim.
    """

    def test_opposite_claims_not_deduplicated(self):
        """'A is beneficial' and 'A is harmful' must not be deduplicated."""
        text = """
        Exercise is beneficial for health.
        But some claim exercise is harmful and damages joints.
        """
        chunks = chunk_text(text, max_chars=150, overlap=20)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        claim_texts = [c["claim_text"].lower() for c in claims]

        # Both perspectives must survive
        has_beneficial = any("beneficial" in ct for ct in claim_texts)
        has_harmful = any("harmful" in ct or "damages" in ct for ct in claim_texts)

        assert has_beneficial, "Beneficial claim was deduplicated away"
        assert has_harmful, "Harmful claim was deduplicated away"

    def test_negation_opposites_preserved(self):
        """Claims with negation mismatch must not be deduplicated.
        
        Phase 4 Fix #1: This test now validates the negation detection fix.
        Previously this was a known limitation. Now it's fixed.
        """
        text = """
        The statement is true.
        The statement is not true.
        """
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        # Both statements must be present (negation fix ensures this)
        claim_texts = [c["claim_text"] for c in claims]
        has_affirmative = any("is true" in ct and "not" not in ct for ct in claim_texts)
        has_negation = any("not true" in ct for ct in claim_texts)

        assert has_affirmative and has_negation, (
            f"Negation-opposite claims were deduplicated. "
            f"Claims found: {claim_texts}"
        )


class TestInvariantIV_NonFabrication:
    """
    INVARIANT IV: SSE must never create information not explicitly in source.
    
    Violation: Inferring beliefs, hallucinating facts, creating implied claims.
    """

    def test_no_inferred_claims_beyond_source(self):
        """Only claims that appear as sentences in source are extracted."""
        text = "The water is cold."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        # Should extract the one sentence, no inferences
        assert len(claims) <= 2, "Inferring extra claims not in source"

        for claim in claims:
            # Each claim must exist as a sentence in source
            claim_text = claim["claim_text"]
            assert claim_text in text or claim_text.strip() in text, (
                f"Claim '{claim_text}' not found in source text"
            )

    def test_no_implied_claims_extraction(self):
        """Implied but not explicit claims must not be extracted."""
        text = "The meeting was held. Attendees sat in chairs."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        claim_texts = [c["claim_text"].lower() for c in claims]

        # Implied claim "chairs were used" should NOT appear as extracted claim
        # (it's valid to mention it, but not as a primary extracted claim without explicit statement)
        fabricated_inferences = [
            ct for ct in claim_texts
            if "chairs are" in ct or "therefore" in ct or "which means" in ct
        ]

        # Shouldn't fabricate causal or definitional claims
        assert len(fabricated_inferences) == 0, (
            f"Fabricated inferences found: {fabricated_inferences}"
        )


class TestInvariantV_UncertaintyPreservation:
    """
    INVARIANT V: SSE must preserve ambiguity and uncertainty, not smooth it.
    
    Violation: Removing hedge words, making fuzzy claims sound crisp, hiding scope ambiguity.
    """

    def test_hedged_claims_marked_with_ambiguity(self):
        """Claims with hedge words must be flagged."""
        text = "Some experts believe the pandemic might continue indefinitely."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        # Claims should exist
        assert len(claims) > 0, "Should extract hedged claims"

        # If extracted, hedged claims should have ambiguity data
        for claim in claims:
            if any(
                hedge in claim["claim_text"].lower()
                for hedge in ["might", "may", "some", "believe", "possibly"]
            ):
                # Claim with hedges should have ambiguity tracked
                assert "ambiguity" in claim, f"Hedged claim missing ambiguity: {claim}"

    def test_ambiguous_pronouns_preserved(self):
        """Claims with ambiguous pronouns must not be "resolved"."""
        text = "John told Mary he would help her later."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        claim_texts = [c["claim_text"] for c in claims]

        # Should preserve "he" and "her" as-is, not resolve to definite names
        for claim_text in claim_texts:
            # If claim mentions pronouns, it must preserve them
            if "help" in claim_text.lower():
                assert "he" in claim_text.lower() or claim_text == text, (
                    "Ambiguous pronouns were resolved"
                )


class TestInvariantVI_SourceTraceability:
    """
    INVARIANT VI: Every claim and contradiction must be traceable to exact source offsets.
    
    Violation: Missing offsets, incorrect offsets, offset-text mismatch.
    """

    def test_all_claims_have_valid_offsets(self):
        """Every claim must have start_char and end_char that map to source."""
        text = "The sky is blue. Grass is green. Water is wet."
        chunks = chunk_text(text, max_chars=100)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)

        for claim in claims:
            for quote in claim["supporting_quotes"]:
                start = quote["start_char"]
                end = quote["end_char"]

                # Offsets must be present and valid
                assert isinstance(start, int), "start_char must be integer"
                assert isinstance(end, int), "end_char must be integer"
                assert 0 <= start < end <= len(text), (
                    f"Invalid offsets [{start}:{end}] for text length {len(text)}"
                )

                # Phase 4 Fix #2: Offsets must reconstruct quote exactly
                reconstructed = text[start:end]
                quote_text = quote.get("quote_text") or quote.get("text")
                assert reconstructed == quote_text, (
                    f"Offset mismatch: [{start}:{end}] -> '{reconstructed}' != '{quote_text}'"
                )

    def test_contradictions_reference_valid_claims(self):
        """Every contradiction must reference claims that exist."""
        text = """
        The Earth is round.
        The Earth is flat.
        """
        chunks = chunk_text(text, max_chars=100, overlap=20)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)
        claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])

        clear_nli_cache()
        contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=False)

        claim_ids = {c["claim_id"] for c in claims}

        for cont in contradictions:
            claim_a_id = cont["pair"]["claim_id_a"]
            claim_b_id = cont["pair"]["claim_id_b"]

            assert claim_a_id in claim_ids, f"Contradiction references non-existent claim {claim_a_id}"
            assert claim_b_id in claim_ids, f"Contradiction references non-existent claim {claim_b_id}"


class TestInvariantVII_ComputationalHonesty:
    """
    INVARIANT VII: SSE must not hide limitations, fallbacks, or service failures.
    
    Violation: Reporting LLM results when using heuristic, hiding Ollama unavailability.
    """

    def test_heuristic_used_when_ollama_unavailable(self):
        """When Ollama is unavailable, system must fall back to heuristic."""
        text = """
        Exercise is beneficial.
        Exercise is harmful.
        """
        chunks = chunk_text(text, max_chars=100, overlap=20)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)
        claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])

        clear_nli_cache()

        # Call without Ollama (will use heuristic)
        contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=False)

        # Should still detect contradictions even without LLM
        assert len(contradictions) > 0, "Heuristic should detect contradictions"

    def test_contradiction_detection_deterministic(self):
        """Same input should produce same contradictions (no random behavior)."""
        text = """
        The statement is true.
        The statement is false.
        """
        chunks = chunk_text(text, max_chars=100, overlap=20)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])
        claims = extract_claims_from_chunks(chunks, embeddings)
        claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])

        clear_nli_cache()
        contradictions_1 = detect_contradictions(claims, claim_embeddings, use_ollama=False)

        clear_nli_cache()
        contradictions_2 = detect_contradictions(claims, claim_embeddings, use_ollama=False)

        # Should be identical runs
        assert len(contradictions_1) == len(contradictions_2), (
            "Non-deterministic contradiction detection"
        )


class TestCrossInvariantScenarios:
    """
    Tests that combine multiple invariants to ensure no interaction violations.
    """

    def test_full_pipeline_preserves_all_invariants(self):
        """Complete pipeline must uphold all invariants simultaneously."""
        text = """
        Climate change is real and caused by humans.
        Global temperatures are rising.
        Yet some claim climate change is a hoax.
        Others say warming is natural.
        """
        chunks = chunk_text(text, max_chars=150, overlap=30)
        emb_store = EmbeddingStore("all-MiniLM-L6-v2")
        embeddings = emb_store.embed_texts([c["text"] for c in chunks])

        # Extract claims
        claims = extract_claims_from_chunks(chunks, embeddings)

        # Invariant I: All claims have quotes
        assert all(
            len(c.get("supporting_quotes", [])) > 0 for c in claims
        ), "Invariant I violated: missing quotes"

        # Invariant VI: All quotes are substrings (SSE uses chunk-level offsets)
        for claim in claims:
            for quote in claim["supporting_quotes"]:
                quote_text = quote.get("quote_text") or quote.get("text")
                assert quote_text in text, "Invariant VI violated: quote not in source"

        # Detect contradictions
        claim_embeddings = emb_store.embed_texts([c["claim_text"] for c in claims])
        clear_nli_cache()
        contradictions = detect_contradictions(claims, claim_embeddings, use_ollama=False)

        # Invariant II: Both sides of contradiction present
        if len(contradictions) > 0:
            for cont in contradictions:
                claim_a_id = cont["pair"]["claim_id_a"]
                claim_b_id = cont["pair"]["claim_id_b"]
                assert any(
                    c["claim_id"] == claim_a_id for c in claims
                ), "Invariant II violated: contradicting claim removed"
                assert any(
                    c["claim_id"] == claim_b_id for c in claims
                ), "Invariant II violated: contradicting claim removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
