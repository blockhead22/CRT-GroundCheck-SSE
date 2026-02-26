from __future__ import annotations

from types import SimpleNamespace

from personal_agent.ollama_client import OllamaClient


class _FakeClient:
    def __init__(self, response):
        self._response = response

    def chat(self, **kwargs):  # noqa: ANN003
        return self._response


def _client_with_response(response) -> OllamaClient:
    client = object.__new__(OllamaClient)
    client.model = "fake-model"
    client._client = _FakeClient(response)
    return client


def test_generate_does_not_leak_thinking_when_content_short():
    response = SimpleNamespace(
        message=SimpleNamespace(
            content="Hi!",
            thinking="Internal reasoning that should never be exposed to users.",
        )
    )
    client = _client_with_response(response)
    out = client.generate("hello")
    assert out == "Hi!"


def test_generate_returns_fallback_when_only_thinking_exists():
    response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            thinking="Long internal chain-of-thought with no final answer.",
        )
    )
    client = _client_with_response(response)
    out = client.generate("hello")
    assert "internal reasoning" not in out.lower()
    assert "final answer" in out.lower()


def test_generate_extracts_visible_text_outside_think_block():
    response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            thinking="<think>hidden planning</think>\nVisible final line.",
        )
    )
    client = _client_with_response(response)
    out = client.generate("hello")
    assert out == "Visible final line."

