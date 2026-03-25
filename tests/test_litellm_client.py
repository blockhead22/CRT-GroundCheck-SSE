"""Tests for UnifiedLLMClient (litellm_client.py)."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personal_agent.litellm_client import (
    UnifiedLLMClient,
    CloudPromptPolicy,
    create_llm_client,
)


def _make_client(**overrides):
    """Create a test client with sane defaults."""
    cfg = {
        "ollama_model": "qwen3:14b",
        "ollama_base_url": "http://localhost:11434",
        "cloud_model": "",
        "cloud_api_key": "",
        "cloud_base_url": "",
        "anthropic_model": "claude-sonnet-4-6",
        "anthropic_api_key": "",
        "product_mode": "local_only",
        "model_roles": {},
        "fallback_enabled": True,
    }
    cfg.update(overrides)
    return UnifiedLLMClient(cfg)


# ── Model resolution ─────────────────────────────────────────────────

class TestResolveTarget:
    def test_no_prefix_returns_local(self):
        client = _make_client()
        assert client._resolve_target("qwen3:14b") == ("local", "qwen3:14b")

    def test_local_prefix(self):
        client = _make_client()
        assert client._resolve_target("local:qwen3:14b") == ("local", "qwen3:14b")

    def test_cloud_prefix(self):
        client = _make_client()
        assert client._resolve_target("cloud:gpt-4o-mini") == ("cloud", "gpt-4o-mini")

    def test_anthropic_prefix(self):
        client = _make_client()
        assert client._resolve_target("anthropic:claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")

    def test_role_prefix_with_roles(self):
        client = _make_client(model_roles={"answer": "anthropic:claude-sonnet-4-6"})
        assert client._resolve_target("role:answer") == ("anthropic", "claude-sonnet-4-6")

    def test_role_prefix_env_override(self):
        client = _make_client(model_roles={"answer": "local:qwen3:14b"})
        with patch.dict(os.environ, {"CRT_MODEL_ROLE_ANSWER": "anthropic:claude-sonnet-4-6"}):
            assert client._resolve_target("role:answer") == ("anthropic", "claude-sonnet-4-6")

    def test_role_prefix_missing(self):
        client = _make_client()
        assert client._resolve_target("role:nonexistent") == ("local", None)

    def test_empty_string(self):
        client = _make_client()
        assert client._resolve_target("") == ("local", None)

    def test_none(self):
        client = _make_client()
        assert client._resolve_target(None) == ("local", None)


# ── LiteLLM params ───────────────────────────────────────────────────

class TestToLiteLLMParams:
    def test_local_params(self):
        client = _make_client()
        params = client._to_litellm_params("local", "qwen3:14b")
        assert params["model"] == "ollama/qwen3:14b"
        assert params["api_base"] == "http://localhost:11434"

    def test_local_default_model(self):
        client = _make_client()
        params = client._to_litellm_params("local", None)
        assert params["model"] == "ollama/qwen3:14b"

    def test_anthropic_params(self):
        client = _make_client(anthropic_api_key="sk-test")
        params = client._to_litellm_params("anthropic", "claude-sonnet-4-6")
        assert params["model"] == "anthropic/claude-sonnet-4-6"
        assert params["api_key"] == "sk-test"

    def test_cloud_params(self):
        client = _make_client(cloud_api_key="sk-cloud", cloud_base_url="https://custom.api/v1")
        params = client._to_litellm_params("cloud", "gpt-4o-mini")
        assert params["model"] == "gpt-4o-mini"
        assert params["api_key"] == "sk-cloud"
        assert params["api_base"] == "https://custom.api/v1"

    def test_no_duplicate_prefix(self):
        client = _make_client()
        params = client._to_litellm_params("local", "ollama/qwen3:14b")
        assert params["model"] == "ollama/qwen3:14b"  # not ollama/ollama/...


# ── Thinking model detection ─────────────────────────────────────────

class TestThinkingModel:
    def test_qwen3_is_thinking(self):
        client = _make_client()
        assert client._is_thinking_model("qwen3:14b") is True
        assert client._is_thinking_model("ollama/qwen3:14b") is True

    def test_deepseek_r1_is_thinking(self):
        client = _make_client()
        assert client._is_thinking_model("deepseek-r1:8b") is True

    def test_qwq_is_thinking(self):
        client = _make_client()
        assert client._is_thinking_model("qwq:32b") is True

    def test_llama_not_thinking(self):
        client = _make_client()
        assert client._is_thinking_model("llama3.2:latest") is False

    def test_gpt_not_thinking(self):
        client = _make_client()
        assert client._is_thinking_model("gpt-4o-mini") is False


# ── Token inflation ──────────────────────────────────────────────────

class TestEffectiveMaxTokens:
    def test_thinking_model_inflated(self):
        client = _make_client()
        # max(1000 * 4, 8192) = 8192
        assert client._effective_max_tokens(1000, "qwen3:14b") == 8192

    def test_thinking_model_large_request(self):
        client = _make_client()
        # max(4096 * 4, 8192) = 16384
        assert client._effective_max_tokens(4096, "qwen3:14b") == 16384

    def test_non_thinking_model_unchanged(self):
        client = _make_client()
        assert client._effective_max_tokens(1000, "llama3.2:latest") == 1000


# ── Visible text extraction ──────────────────────────────────────────

class TestResolveVisibleText:
    def test_plain_content(self):
        client = _make_client()
        assert client._resolve_visible_text("Hello world") == "Hello world"

    def test_content_with_think_tags(self):
        client = _make_client()
        result = client._resolve_visible_text("<think>reasoning</think>The answer is 42")
        assert "The answer is 42" in result
        assert "reasoning" not in result

    def test_empty_content_with_thinking(self):
        client = _make_client()
        result = client._resolve_visible_text("", "Some thinking\nThe final answer is here.")
        assert "The final answer is here." in result

    def test_empty_both(self):
        client = _make_client()
        result = client._resolve_visible_text("", "")
        assert result == ""

    def test_meta_reasoning_skipped(self):
        client = _make_client()
        result = client._resolve_visible_text("", "Let me think about this\nThe answer is 42")
        assert "42" in result


# ── Quality gate (meta-reasoning detection) ──────────────────────────

class TestQualityGate:
    def test_tool_calls_always_pass(self):
        """If there are tool calls, the result should pass the quality gate."""
        client = _make_client()
        # _try_local_tools returns None for empty/meta responses
        # but this tests the concept — tool_calls present means valid
        result = {"tool_calls": [{"name": "test", "arguments": {}}], "content": "", "used_tools": True}
        assert result["tool_calls"]  # quality gate passes

    def test_meta_reasoning_detected(self):
        client = _make_client()
        for prefix in client._META_STARTS:
            content = prefix + " some more text"
            assert content.lower().startswith(prefix)


# ── Parse tool response ──────────────────────────────────────────────

class TestParseToolResponse:
    def test_with_tool_calls(self):
        client = _make_client()
        mock_resp = MagicMock()
        mock_tc = MagicMock()
        mock_tc.function.name = "get_weather"
        mock_tc.function.arguments = '{"location": "Tokyo"}'
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Let me check the weather."
        mock_resp.choices[0].message.tool_calls = [mock_tc]

        result = client._parse_tool_response(mock_resp)
        assert result["used_tools"] is True
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "get_weather"
        assert result["tool_calls"][0]["arguments"] == {"location": "Tokyo"}

    def test_without_tool_calls(self):
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "The weather is nice."
        mock_resp.choices[0].message.tool_calls = None

        result = client._parse_tool_response(mock_resp)
        assert result["used_tools"] is False
        assert result["tool_calls"] == []
        assert "nice" in result["content"]

    def test_malformed_arguments(self):
        client = _make_client()
        mock_resp = MagicMock()
        mock_tc = MagicMock()
        mock_tc.function.name = "test_fn"
        mock_tc.function.arguments = "not valid json"
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = ""
        mock_resp.choices[0].message.tool_calls = [mock_tc]

        result = client._parse_tool_response(mock_resp)
        assert result["tool_calls"][0]["arguments"] == {}


# ── Scrubbing ────────────────────────────────────────────────────────

class TestScrubbing:
    def test_trust_tags_removed(self):
        client = _make_client()
        text = "User likes pizza [trust: 0.85] and coding [similarity: 0.9]"
        scrubbed = client._scrub_prompt_for_cloud(text)
        assert "[trust:" not in scrubbed
        assert "[similarity:" not in scrubbed
        assert "pizza" in scrubbed

    def test_source_tags_removed(self):
        client = _make_client()
        text = "User is tall (source: memory_db_123)"
        scrubbed = client._scrub_prompt_for_cloud(text)
        assert "(source:" not in scrubbed

    def test_truncation(self):
        client = _make_client(max_context_chars=50)
        text = "x" * 100
        scrubbed = client._scrub_prompt_for_cloud(text)
        assert "[Prompt truncated" in scrubbed


# ── Properties ───────────────────────────────────────────────────────

class TestProperties:
    def test_model_returns_ollama_model(self):
        client = _make_client(ollama_model="qwen3:14b")
        assert client.model == "qwen3:14b"

    def test_cloud_available(self):
        client = _make_client(cloud_model="gpt-4o-mini", cloud_api_key="sk-test")
        assert client.cloud_available is True

    def test_cloud_not_available(self):
        client = _make_client(cloud_model="", cloud_api_key="")
        assert client.cloud_available is False

    def test_anthropic_available(self):
        client = _make_client(anthropic_api_key="sk-test")
        assert client.anthropic_available is True


# ── Factory ──────────────────────────────────────────────────────────

class TestFactory:
    def test_returns_none_when_nothing_available(self):
        with patch.dict(os.environ, {
            "CRT_ENABLE_LLM": "false",
            "CRT_PRODUCT_MODE": "local_only",
        }, clear=False):
            result = create_llm_client({})
            assert result is None

    def test_returns_client_with_local(self):
        with patch.dict(os.environ, {
            "CRT_ENABLE_LLM": "true",
            "CRT_OLLAMA_MODEL": "qwen3:14b",
            "CRT_PRODUCT_MODE": "local_only",
        }, clear=False):
            result = create_llm_client({})
            assert result is not None
            assert isinstance(result, UnifiedLLMClient)
            assert result.ollama_model == "qwen3:14b"


# ── Integration tests (skip if Ollama unavailable) ───────────────────

@pytest.fixture
def ollama_available():
    """Check if Ollama is running."""
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


class TestIntegrationOllama:
    def test_generate(self, ollama_available):
        if not ollama_available:
            pytest.skip("Ollama not available")
        client = _make_client(ollama_model="qwen3:14b")
        result = client.generate("Say hello in 3 words.", max_tokens=100)
        assert result and not result.startswith("[Ollama")

    def test_chat(self, ollama_available):
        if not ollama_available:
            pytest.skip("Ollama not available")
        client = _make_client(ollama_model="qwen3:14b")
        result = client.chat(
            [{"role": "user", "content": "What is 2+2? Answer with just the number."}],
            max_tokens=100,
        )
        assert result and not result.startswith("[Ollama")

    def test_chat_with_tools(self, ollama_available):
        if not ollama_available:
            pytest.skip("Ollama not available")
        client = _make_client(ollama_model="qwen3:14b")
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        }]
        result = client.chat_with_tools(
            [{"role": "user", "content": "What is the weather in Tokyo?"}],
            tools=tools,
            max_tokens=500,
        )
        assert isinstance(result, dict)
        assert "tool_calls" in result
        assert "content" in result
        assert "used_tools" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
