from __future__ import annotations

from types import SimpleNamespace

from routes.chat_provider_routing import build_request_llm_client, resolve_effective_generation_mode
from routes.models import ChatSendRequest


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeBaseClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.anthropic_api_key = "anthropic-key"
        self.cloud_api_key = "openai-key"
        self.anthropic_model = "claude-sonnet-4-20250514"
        self.cloud_model = "gpt-4o-mini"
        self.model_roles = {}
        self.recorded_anthropic = 0

    def _check_anthropic_rate_limit(self) -> bool:
        return True

    def _record_anthropic_usage(self, tokens: int = 0) -> None:
        self.recorded_anthropic += 1

    def _resolve_visible_text(self, content: str, thinking: str = "") -> str:
        return content or thinking

    def _call(self, provider, model_name, messages, max_tokens, temperature, tools=None, stream=False, scrub=False):
        self.calls.append((provider, model_name))
        if provider == "anthropic" and model_name == "claude-sonnet-4-20250514":
            raise RuntimeError("claude unavailable")
        if tools:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="",
                            tool_calls=[
                                SimpleNamespace(
                                    function=SimpleNamespace(name="memory_recall", arguments='{"query":"name"}')
                                )
                            ],
                        )
                    )
                ]
            )
        return _FakeResponse(f"{provider}:{model_name}")

    def _stream_provider(self, provider, model_name, messages, max_tokens, temperature, scrub=False):
        self.calls.append((provider, model_name))
        if provider == "anthropic" and model_name == "claude-sonnet-4-20250514":
            yield ("content", "[stream error: claude unavailable]")
            return
        yield ("content", f"{provider}:{model_name}")

    def _parse_tool_response(self, response):
        tool_calls = []
        for tc in response.choices[0].message.tool_calls:
            tool_calls.append({"name": tc.function.name, "arguments": {"query": "name"}})
        return {
            "tool_calls": tool_calls,
            "content": "",
            "used_tools": True,
        }


class _FakeOpenAIService:
    is_available = True

    def generate(self, prompt, system=None, max_tokens=500, temperature=0.7, model=None):
        return f"openai-service:{model}"


class _FakeCloudService:
    def __init__(self) -> None:
        self.openai = _FakeOpenAIService()

    def _openai_available(self):
        return True

    def _cookie_available(self):
        return True

    def _call_cookie_text(self, system, prompt, max_tokens=4096, feature="unknown", model="claude"):
        return f"claude-service:{model}"


def _build_request(client: _FakeBaseClient):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(get_llm_client=lambda: client)))


def test_effective_generation_mode_prefers_request_override(monkeypatch) -> None:
    monkeypatch.setattr("auth.get_user_setting", lambda uid, key, default="": "cloud_openai")

    mode = resolve_effective_generation_mode(
        ChatSendRequest(thread_id="t1", message="hi", generation_mode="cloud_claude"),
        1,
    )

    assert mode == "cloud_claude"


def test_cloud_claude_falls_back_to_openai_without_local() -> None:
    base = _FakeBaseClient()
    request = _build_request(base)
    req = ChatSendRequest(
        thread_id="t1",
        message="hi",
        generation_mode="cloud_claude",
        cloud_model_claude="claude-sonnet-4-20250514",
        cloud_model_openai="gpt-4o-mini",
    )

    client = build_request_llm_client(request, req, 1)
    text = client.chat([{"role": "user", "content": "hello"}], model="role:fast")

    assert text == "cloud:gpt-4o-mini"
    assert base.calls == [
        ("anthropic", "claude-sonnet-4-20250514"),
        ("cloud", "gpt-4o-mini"),
    ]


def test_cloud_openai_tools_fall_back_to_claude_without_local() -> None:
    base = _FakeBaseClient()
    request = _build_request(base)
    req = ChatSendRequest(
        thread_id="t1",
        message="hi",
        generation_mode="cloud_openai",
        cloud_model_claude="claude-sonnet-4-20250514",
        cloud_model_openai="gpt-4o-mini",
    )

    client = build_request_llm_client(request, req, 1)
    result = client.chat_with_tools(
        [{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "memory_recall"}}],
    )

    assert result["used_tools"] is True
    assert result["generation_source"] == "openai"
    assert base.calls == [("cloud", "gpt-4o-mini")]


def test_cloud_text_uses_cloud_feature_service_when_base_keys_absent(monkeypatch) -> None:
    base = _FakeBaseClient()
    base.anthropic_api_key = ""
    base.cloud_api_key = ""
    request = _build_request(base)
    req = ChatSendRequest(
        thread_id="t1",
        message="hi",
        generation_mode="cloud_claude",
        cloud_model_claude="claude-sonnet-4-5",
        cloud_model_openai="gpt-4o-mini",
    )
    monkeypatch.setattr("personal_agent.cloud_features.get_cloud_feature_service", lambda: _FakeCloudService())

    client = build_request_llm_client(request, req, 1)
    text = client.chat([{"role": "user", "content": "hello"}], model="role:fast")

    assert text == "claude-service:claude-sonnet-4-5"
    assert base.calls == []
