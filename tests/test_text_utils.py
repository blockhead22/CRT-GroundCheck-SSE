from personal_agent.text_utils import looks_like_llm_error_text


def test_looks_like_llm_error_text_matches_direct_error():
    assert looks_like_llm_error_text(
        "[Ollama connection error: Is Ollama running? Try: ollama serve]"
    )


def test_looks_like_llm_error_text_matches_greeting_prefixed_error():
    assert looks_like_llm_error_text(
        "Hey! I'm Aether. What's on your mind?\n\n"
        "[Ollama connection error: Is Ollama running? Try: ollama serve]"
    )


def test_looks_like_llm_error_text_ignores_normal_user_text():
    assert not looks_like_llm_error_text("My favorite color is orange.")
