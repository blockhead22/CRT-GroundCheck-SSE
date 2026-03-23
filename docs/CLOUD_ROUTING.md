# 3-Tier Cloud Routing & Escalation

CRT uses a local-first generation architecture. The control layer (memory, verification, trust, governance) always runs locally. Only raw text generation can optionally route to cloud providers for higher-quality output.

Reference: `personal_agent/hybrid_llm_client.py`, `personal_agent/cloud_features.py`

## The Three Tiers

### Tier 0: Local (Ollama)

- **Provider:** Local Ollama instance
- **Default model:** Configured via `CRT_OLLAMA_MODEL` env var (fallback: `llama3.2:latest`)
- **Cost:** Free (runs on local hardware)
- **Latency:** Depends on hardware, typically 1-5s for generation
- **Privacy:** Full — no data leaves the machine

All prompts go to local by default. No prompt scrubbing is needed.

### Tier 1: Cloud (OpenAI-compatible)

- **Provider:** Any OpenAI-compatible API endpoint
- **Default model:** Configured via `CRT_CLOUD_MODEL` or `generation_stack.cloud.model` in runtime config
- **Cost:** Per-token pricing (tracked by `CloudFeatureService`)
- **Privacy:** Prompts are scrubbed before sending (trust metadata removed, PII slots denied)

Tier 1 is used for:
- **Slot classification** — Classifying user statements into memory slots (up to 10/day default)
- **NLI contradiction detection** — Checking if two facts contradict (up to 10/day default)
- **Fallback for Tier 2** — When Anthropic is unavailable, Tier 1 handles reflection validation

### Tier 2: Anthropic (Claude)

- **Provider:** Anthropic API (direct SDK)
- **Default model:** Configured via `CRT_ANTHROPIC_MODEL` or `generation_stack.anthropic.model` (fallback: `claude-sonnet-4-6`)
- **Cost:** Per-token pricing, rate-limited
- **Privacy:** Same scrubbing as Tier 1

Tier 2 is preferred for:
- **Reflection validation** — Validating self-model updates against evidence (up to 3/day default)
- **Complex reasoning** — When `role:answer` is configured to route to Anthropic

## Escalation Logic

### Model Resolution

The `HybridLLMClient._resolve_target()` method resolves model strings with provider prefixes:

```
"anthropic:claude-sonnet-4-6"  -> (provider="anthropic", model="claude-sonnet-4-6")
"cloud:gpt-4o"                 -> (provider="cloud", model="gpt-4o")
"local:qwen3:14b"              -> (provider="local", model="qwen3:14b")
"role:answer"                  -> looks up model_roles["answer"], re-resolves
plain string                   -> (provider="local", model=string)
```

Role-based resolution is the primary escalation mechanism. Env var overrides are supported:
```
CRT_MODEL_ROLE_ANSWER=anthropic:claude-sonnet-4-6
```

### Fallback Chain

When a provider is unavailable, the system falls back gracefully:

1. **Anthropic rate limited** -> Falls back to local, records the fallback event
2. **Cloud unavailable** -> Falls back to local
3. **Local unavailable** -> Tries cloud client if available
4. **Nothing available** -> Returns `[No LLM available]`

For cloud features specifically:

1. **Reflection validation:** Try Tier 2 (Claude) first, fall back to Tier 1 (OpenAI)
2. **Slot classification:** Tier 1 only (OpenAI gpt-4o-mini)
3. **NLI contradiction:** Tier 1 only (OpenAI gpt-4o-mini)

### Prompt Scrubbing for Cloud

Before any prompt is sent to Tier 1 or Tier 2, `_scrub_prompt_for_cloud()` applies:

1. **Metadata removal:** Trust scores (`[trust: 0.85]`), similarity scores, source annotations are stripped
2. **PII filtering:** User fact slots on the deny list are replaced with `[User facts withheld by cloud policy]`. Default deny list includes: name, pronouns, location, address, email, phone, employer, title, first_language
3. **Truncation:** Prompt is capped at `max_context_chars` (default: 14,000)
4. **Section renaming:** Internal section headers are renamed to neutral labels

## User Controls

### Runtime Config Settings

In `crt_runtime_config.json` under `generation_stack`:

```json
{
  "cloud": {
    "enabled": false,
    "provider": "openai_compatible",
    "model": "gpt-4o-mini",
    "api_key_env": "OPENAI_API_KEY",
    "timeout_seconds": 120,
    "redact_memory_metadata": true,
    "max_context_chars": 14000,
    "slot_denylist": ["name", "pronouns", "location", "email", "phone"]
  },
  "anthropic": {
    "enabled": false,
    "model": "claude-sonnet-4-6",
    "api_key_env": "ANTHROPIC_API_KEY",
    "rate_limits": {
      "rpm": 50,
      "tpd": 1000000
    }
  }
}
```

### Product Mode

The `product_mode.mode` config controls the overall routing strategy:

- **`local_only`** (default) — All generation stays local. Cloud features disabled.
- **`hybrid_verified`** — Cloud generation enabled with local verification. Memory/verification authority stays local.

### Daily Budgets

`CloudFeatureService` enforces per-feature daily limits:

| Feature | Default Daily Limit |
|---------|-------------------|
| Slot classification | 10 calls |
| NLI contradiction | 10 calls |
| Reflection validation | 3 calls |

These can be scaled via `set_limit_multiplier()`. A multiplier of 2.0 doubles all limits.

## Cost Tracking

`CloudFeatureService` tracks in-memory usage stats:

```python
usage = {
    "slot_classification": {"calls": 5, "est_tokens": 1250},
    "nli_contradiction": {"calls": 3, "est_tokens": 600},
    "reflection_validation": {"calls": 1, "est_tokens": 400},
    "total_cost_est": 0.00065,
}
```

Estimated costs per call:
- Slot classification: ~$0.000075 (250 tokens at gpt-4o-mini rates)
- NLI contradiction: ~$0.00006 (200 tokens)
- Reflection validation: ~$0.0002 (400 tokens, Tier 1 fallback)

Usage resets daily. Stats are available via `get_usage_summary()`.

### Rate Limiting (Anthropic)

When the Anthropic client is initialized, a `PersonalRateLimiter` is created with:
- RPM limit: 50 requests/minute (configurable via `CRT_ANTHROPIC_RPM`)
- TPD limit: 1,000,000 tokens/day (configurable via `CRT_ANTHROPIC_TPD`)

If rate limited, the system falls back to local and records the event.
