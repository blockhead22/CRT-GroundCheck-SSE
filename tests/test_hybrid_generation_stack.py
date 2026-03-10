from __future__ import annotations

from personal_agent.hybrid_llm_client import HybridLLMClient
from personal_agent.model_router import ModelRouter
from personal_agent.runtime_config import load_runtime_config


class _StubCloudClient:
    def __init__(self) -> None:
        self.is_available = True
        self.last_prompt = None
        self.model = "gpt-5.4-thinking"

    def generate(self, prompt: str, **kwargs) -> str:
        self.last_prompt = prompt
        return "cloud-ok"


def _runtime_cfg(mode: str, *, cloud_enabled: bool = True) -> dict:
    return {
        "product_mode": {
            "mode": mode,
            "memory_authority": "local",
            "verification_authority": "local",
            "observability_authority": "local",
        },
        "generation_stack": {
            "local": {
                "enabled": True,
                "default_model": "llama3.2:latest",
            },
            "cloud": {
                "enabled": cloud_enabled,
                "provider": "openai_compatible",
                "model": "gpt-5.4-thinking",
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "timeout_seconds": 120,
                "redact_memory_metadata": True,
                "max_context_chars": 14000,
                "allowed_channels": [],
                "denied_channels": ["telegram"],
                "fact_allowlist": [],
                "slot_denylist": ["name", "location", "email", "phone"],
            },
            "routing": {
                "cloud_routes": ["reasoning", "research", "creative"],
                "min_tokens_for_cloud": 6,
            },
        },
    }


def test_default_runtime_config_includes_product_mode_and_generation_stack() -> None:
    cfg = load_runtime_config(None, strict=True)
    assert cfg["product_mode"]["mode"] in {"local_only", "hybrid_verified"}
    assert cfg["generation_stack"]["local"]["default_model"]
    assert "cloud_routes" in cfg["generation_stack"]["routing"]


def test_model_router_stays_local_in_local_only_mode() -> None:
    router = ModelRouter(default_model="llama3.2:latest", runtime_config=_runtime_cfg("local_only"))
    routed = router.route(query="Analyze the architectural tradeoffs of this system in detail step by step")
    assert routed.provider == "local"
    assert not routed.escalation
    assert not routed.model.startswith("cloud:")


def test_model_router_escalates_complex_reasoning_in_hybrid_mode() -> None:
    router = ModelRouter(default_model="llama3.2:latest", runtime_config=_runtime_cfg("hybrid_verified"))
    routed = router.route(query="Analyze the architectural tradeoffs of this system in detail step by step")
    assert routed.provider == "cloud"
    assert routed.escalation is True
    assert routed.model == "cloud:gpt-5.4-thinking"


def test_model_router_blocks_cloud_for_denied_channel() -> None:
    router = ModelRouter(default_model="llama3.2:latest", runtime_config=_runtime_cfg("hybrid_verified"))
    routed = router.route(
        query="Analyze the architectural tradeoffs of this system in detail step by step",
        channel="telegram",
    )
    assert routed.provider == "local"
    assert routed.escalation is False


def test_hybrid_client_scrubs_memory_metadata_for_cloud() -> None:
    cloud = _StubCloudClient()
    client = HybridLLMClient(local_client=None, cloud_client=cloud, product_mode="hybrid_verified")
    answer = client.generate(
        "=== RETRIEVED MEMORIES: USER FACTS ===\n"
        "1. FACT: favorite drink = coffee [trust: 0.90] (source: external) [similarity: 0.88]\n",
        model="cloud:gpt-5.4-thinking",
    )
    assert answer == "cloud-ok"
    assert cloud.last_prompt is not None
    assert "[trust:" not in cloud.last_prompt
    assert "(source:" not in cloud.last_prompt
    assert "[similarity:" not in cloud.last_prompt
    assert "=== VERIFIED USER FACTS ===" in cloud.last_prompt


def test_hybrid_client_enforces_slot_policy_before_cloud_send() -> None:
    cloud = _StubCloudClient()
    client = HybridLLMClient(
        local_client=None,
        cloud_client=cloud,
        product_mode="hybrid_verified",
    )
    client.cloud_policy.fact_allowlist = ("favorite_drink",)
    client.cloud_policy.slot_denylist = ("name", "location")
    answer = client.generate(
        "=== RETRIEVED MEMORIES: USER FACTS ===\n"
        "1. FACT: name = Nick Block [trust: 0.90]\n"
        "2. FACT: favorite_drink = coffee [trust: 0.88]\n"
        "3. FACT: location = Chicago [trust: 0.80]\n"
        "4. my dog is brown\n",
        model="cloud:gpt-5.4-thinking",
    )
    assert answer == "cloud-ok"
    assert cloud.last_prompt is not None
    assert "name = Nick Block" not in cloud.last_prompt
    assert "location = Chicago" not in cloud.last_prompt
    assert "favorite_drink = coffee" in cloud.last_prompt
    assert "my dog is brown" not in cloud.last_prompt
