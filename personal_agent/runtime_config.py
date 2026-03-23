from __future__ import annotations

import json
import os
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from personal_agent.schema_validation import format_errors, load_schema, validate_instance


_DEFAULT_CONFIG: Dict[str, Any] = {
    # Background jobs: queue + worker + optional idle scheduler.
    # This powers async research, promotion proposals, and auto-resolution attempts.
    "background_jobs": {
        "enabled": False,
        "jobs_db_path": "artifacts/crt_jobs.db",
        "artifacts_dir": "artifacts",
        "worker_interval_seconds": 2,
        # When enabled, the scheduler can enqueue jobs while chat is idle.
        "idle_scheduler_enabled": False,
        "idle_seconds": 120,
        # Conservative by default: only attempt auto-resolution when explicitly enabled.
        "auto_resolve_contradictions_enabled": False,
        # Web research can be privacy-surprising; keep off unless explicitly enabled.
        "auto_web_research_enabled": False,
    },

    # OpenClaw-style governance for autonomous tool use.
    # This is enforced at tool execution time in the agent loop.
    "agent_tool_policy": {
        "enabled": True,
        "default_allow": True,
        "global_max_calls_per_run": 24,
        "tools": {
            "execute_code": {
                "enabled": True,
                "require_approval": True,
                "max_calls_per_run": 2,
                "allowed_channels": [],
                "denied_channels": [],
                "allowed_users": [],
                "denied_users": [],
            },
            "store_memory": {
                "enabled": True,
                "require_approval": True,
                "max_calls_per_run": 4,
                "allowed_channels": [],
                "denied_channels": [],
                "allowed_users": [],
                "denied_users": [],
            },
            "search_web": {
                "enabled": True,
                "require_approval": False,
                "max_calls_per_run": 6,
                "allowed_channels": [],
                "denied_channels": [],
                "allowed_users": [],
                "denied_users": [],
            },
            "read_file": {
                "enabled": True,
                "require_approval": False,
                "max_calls_per_run": 20,
                "allowed_channels": [],
                "denied_channels": [],
                "allowed_users": [],
                "denied_users": [],
            },
            "list_files": {
                "enabled": True,
                "require_approval": False,
                "max_calls_per_run": 20,
                "allowed_channels": [],
                "denied_channels": [],
                "allowed_users": [],
                "denied_users": [],
            },
        },
    },
    
    # Time-based greeting system: personalized greetings based on time since last interaction.
    # Generates contextual greetings like "Welcome back! It's been 3 days since we last chatted."
    "greeting": {
        "enabled": True,
        # Greeting style: "time_based" (considers absence duration), "time_of_day", or "simple"
        "style": "time_based",
        # Minimum absence (seconds) before showing a "welcome back" greeting
        # Default: 1 hour (3600 seconds). Set to 0 to always greet.
        "min_absence_for_greeting": 3600,
        # Customizable greeting templates. Available variables:
        # - {name}: User's first name (or "there" if unknown)
        # - {name_suffix}: ", Name" or "" if unknown (for natural suffixes)
        # - {time_delta}: Human-readable time since last interaction (e.g., "2 hours", "3 days")
        "templates": {
            "new_user": "Hey! I'm Aether. What's on your mind?",
            "returning_minutes": "Welcome back!",
            "returning_hours": "Welcome back! It's been {time_delta} since we last chatted.",
            "returning_days": "Hey {name}! It's been {time_delta}. Good to see you again!",
            "returning_weeks": "It's been a while, {name}! ({time_delta}) Welcome back.",
            "morning": "Good morning{name_suffix}!",
            "afternoon": "Good afternoon{name_suffix}!",
            "evening": "Good evening{name_suffix}!",
            "night": "Hello{name_suffix}!",
        },
    },
    
    # Response variation: Prevent repetitive answers to repeated queries.
    # When user asks the same slot question multiple times, vary the response style.
    "response_variation": {
        "enabled": True,
        # Number of recent messages to check for repetition
        "window_size": 5,
        # Only apply to slot-based queries (name, employer, etc.)
        "slot_queries_only": True,
        # Alternative response templates per slot
        "slot_templates": {
            "name": [
                "{value}",
                "Your name is {value}.",
                "Still {value}!",
                "You're {value}.",
                "{value}, as you told me.",
            ],
            "employer": [
                "{value}",
                "You work at {value}.",
                "Still {value}!",
                "{value}, according to what you've told me.",
            ],
            "location": [
                "{value}",
                "You're in {value}.",
                "You said {value}.",
            ],
            "default": [
                "{value}",
                "That would be {value}.",
                "{value}, as I recall.",
            ],
        },
    },

    # Product mode: where generation happens versus where authority lives.
    "product_mode": {
        "mode": "local_only",
        "memory_authority": "local",
        "verification_authority": "local",
        "observability_authority": "local",
    },

    # Provider stack for generation. The control layer remains local.
    "generation_stack": {
        "local": {
            "enabled": True,
            "default_model": "llama3.2:latest",
        },
        "cloud": {
            "enabled": False,
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
            "slot_denylist": [
                "name",
                "pronouns",
                "location",
                "address",
                "email",
                "phone",
                "employer",
                "title",
                "first_language",
            ],
        },
        "routing": {
            "cloud_routes": ["reasoning", "research", "creative"],
            "min_tokens_for_cloud": 16,
        },
    },

    # Escalation policy: smart tier routing with circuit breaker.
    # Decides when to skip local Ollama and route directly to cloud based on
    # recent failure history and query characteristics.
    "escalation_policy": {
        "enabled": True,
        "circuit_breaker": {
            "trip_threshold": 3,            # consecutive failures before skip
            "window_seconds": 600,          # 10 min failure window
            "cooldown_local_seconds": 300,  # 5 min cooldown for local
            "cooldown_cloud_seconds": 120,  # 2 min cooldown for cloud tiers
        },
        "query_routing": {
            "token_threshold_for_cloud": 6000,  # estimated tokens
            "gate_boost_threshold": 0.10,       # from reflection loop
        },
    },

    # Optional handoff from CRT to a local OpenClaw gateway/CLI for longer
    # research or tool-heavy work. This is conservative by default.
    "openclaw_handoff": {
        "enabled": False,
        "agent_id": "main",
        "session_prefix": "crt",
        "timeout_seconds": 120,
        "allowed_channels": ["telegram", "webchat"],
        "denied_channels": [],
        "inject_crt_context": True,
        "include_api_guide": True,
        "max_fact_items": 8,
        "auto_keywords": [
            "moltbook",
            "join moltbook",
            "openclaw",
            "research",
            "investigate",
            "look up",
            "search for",
            "find latest",
            "browse",
            "compare",
            "summarize",
            "github",
            "git hub",
            "repo",
            "repository",
            "pull request",
            "issue",
            "documentation",
            "docs for",
            "check website",
            "visit",
            "weather",
            "price of",
            "what changed",
        ],
    },
    
    "learned_suggestions": {
        "enabled": True,
        "emit_metadata": True,
        "emit_ab": True,
        "print_in_stress_test": False,
        "write_jsonl": True,
        "jsonl_include_full_answer": False,
    },
    "provenance": {
        # When enabled, CRT may add a short provenance footer to user-facing answers.
        "enabled": True,
        # Optional second-pass sanity check against widely-known public facts.
        # Keep this conservative; it should produce warnings, not "truth picking".
        "world_check": {
            "enabled": False,
            "max_tokens": 140,
        },
    },

    # Settings for the reflection/training loop that turns accepted suggestions into a lightweight model.
    "reflection": {
        "artifacts_dir": "artifacts",
        "out_model_path": "artifacts/learned_suggestions.latest.joblib",
        "min_examples": 50,
        "max_runs": 0,
    },

    # Reflection journal style controls.
    # `style_mode` applies only to reflection/journal content by default.
    "journal_behavior": {
        "style_mode": "reddit_thread",
        "apply_to_self_text": False,
        "enforce_authentic_self_reflection": True,
        "allowed_future_styles": [
            "reddit_thread",
            "structured_notes",
            "compact_reflection",
        ],
    },

    # Dev-facing: periodic trainâ†’evalâ†’publish loop for the suggestion-only model.
    # Safe by design: it only updates a model used for *recommendations*, not beliefs.
    "training_loop": {
        "enabled": False,
        # "thread" trains from personal_agent/crt_memory_<thread>.db + crt_ledger_<thread>.db
        # "artifacts" trains from reflection.artifacts_dir containing crt_stress_memory.*.db pairs
        "source": "thread",
        "thread_id": "default",
        "interval_seconds": 300,
        "run_on_startup": True,
        # Optional publish gates
        "min_train_examples": 20,
        "min_eval_examples": 20,
        "min_eval_accuracy": None,
        "max_prefer_latest_rate": None,
    },

    # DNNT background retraining loop (distills trusted traces into local model updates).
    "dnnt_retraining": {
        "enabled": False,
        "poll_interval_seconds": 1800,
        "poll_interval_sec": 180,
        "min_new_examples": 24,
        "max_examples_per_cycle": 512,
        "max_steps_per_cycle": 200,
        "batch_size": 8,
        "learning_rate": 0.0002,
        "output_dir": "models/dnnt",
        "collected_examples_path": "data/dnnt_collected_training_data.jsonl",
        "collapse_trails_db_path": "personal_agent/crt_collapse_trails.db",
        "active_learning_db_path": "personal_agent/active_learning.db",
        "state_path": "data/dnnt_background_state.json",
    },

    # When enabled, uncertainty responses include a layperson-friendly explanation
    # that the assistant might be wrong due to conflicting information.
    "conflict_warning": {
        "enabled": True,
    },

    # Deterministic, non-chat-backed answers for questions about the assistant itself.
    # Product-facing: customize these strings in crt_runtime_config.json.
    "assistant_profile": {
        "enabled": True,
        "responses": {
            "occupation": (
                "I'm an AI assistant system. My role is to keep memory, contradiction checks, "
                "verification, routing, and observability under local control while helping with questions and tasks."
            ),
            "purpose": (
                "I'm a verified agent designed to help with questions and tasks while keeping memory, "
                "contradiction handling, and verification grounded in a local control layer."
            ),
            "identity": (
                "I'm Aether, a verified AI assistant system. My memory, contradiction checks, "
                "verification, routing, and observability stay under the local CRT control layer. "
                "Depending on configuration, generation may use a local or cloud model."
            ),
            "background_general": (
                "I don't have personal experiences or a human backgroundâ€”I'm an AI system. "
                "I can still help with information, planning, and examples, and I keep memory and verification under local control."
            ),
            "background_filmmaking": (
                "I don't have a personal background or real-world experience in filmmakingâ€”I'm an AI system. "
                "I can still help with filmmaking concepts, writing, planning, and feedback if you tell me what you're working on."
            ),
        },
    },

    # Deterministic safe path: third-person questions that refer to the user by name.
    # Product-facing: customize these strings in crt_runtime_config.json.
    "user_named_reference": {
        "enabled": True,
        "responses": {
            "known_work_prefix": "From our chat, I only know this about your work:",
            "ask_to_store": "If you want, tell me your current job title/occupation in one line and I'll store it as a fact.",
            "unknown": "I don't have a reliable stored memory of your occupation/job yet â€” if you tell me, I can remember it going forward.",
        },
    },

    # First-run onboarding: prompt the user for a few basics after a memory wipe.
    # This is intentionally editable/configurable via crt_runtime_config.json.
    "onboarding": {
        "enabled": True,
        "auto_run_when_memory_empty": True,
        # Each question should store as either FACT: slot = value or PREF: slot = value.
        "questions": [
            {"slot": "name", "kind": "fact", "prompt": "What name should I call you?"},
            {"slot": "pronouns", "kind": "fact", "prompt": "What pronouns should I use for you? (optional)"},
            {"slot": "title", "kind": "fact", "prompt": "What's your job title/role? (optional)"},
            {"slot": "employer", "kind": "fact", "prompt": "Who do you work for? (optional)"},
            {"slot": "location", "kind": "fact", "prompt": "Where are you located? (optional)"},
            {"slot": "communication_style", "kind": "pref", "prompt": "How should I communicate? (e.g., concise, detailed, direct)"},
            {"slot": "goals", "kind": "pref", "prompt": "What are you hoping to use this assistant for?"},
        ],
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _is_strict_validation_enabled(strict: Optional[bool]) -> bool:
    if strict is not None:
        return bool(strict)
    raw = os.environ.get("CRT_STRICT_SCHEMA_VALIDATION", "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _validate_runtime_config_or_raise(cfg: Dict[str, Any]) -> None:
    schema = load_schema("crt_runtime_config.v1.schema.json")
    errors = validate_instance(cfg, schema)
    if errors:
        raise ValueError(
            "CRT runtime config failed schema validation (crt_runtime_config.v1.schema.json):\n"
            + format_errors(errors)
        )


def _validate_runtime_config(cfg: Dict[str, Any], *, strict: bool) -> Optional[str]:
    try:
        _validate_runtime_config_or_raise(cfg)
        return None
    except Exception as exc:
        if strict:
            raise
        return str(exc)


def load_runtime_config(config_path: Optional[str] = None, *, strict: Optional[bool] = None) -> Dict[str, Any]:
    """Load CRT runtime config.

    Resolution order:
    1) explicit config_path
    2) env var CRT_RUNTIME_CONFIG_PATH
    3) repo-root file ./crt_runtime_config.json if it exists

    If nothing exists / parse fails, returns defaults.
    """

    strict_enabled = _is_strict_validation_enabled(strict)

    candidate = config_path or os.environ.get("CRT_RUNTIME_CONFIG_PATH")

    if candidate:
        path = Path(candidate)
        if path.exists() and path.is_file():
            try:
                merged = _deep_merge(_DEFAULT_CONFIG, json.loads(path.read_text(encoding="utf-8-sig")))
                err = _validate_runtime_config(merged, strict=strict_enabled)
                if err:
                    warnings.warn(err, RuntimeWarning)
                    return dict(_DEFAULT_CONFIG)
                return merged
            except Exception:
                if strict_enabled:
                    raise
                return dict(_DEFAULT_CONFIG)
        return dict(_DEFAULT_CONFIG)

    # Prefer resolving relative to the repo (personal_agent/..), then CWD.
    module_default = Path(__file__).resolve().parents[1] / "crt_runtime_config.json"
    for candidate_path in (module_default, Path.cwd() / "crt_runtime_config.json"):
        if candidate_path.exists() and candidate_path.is_file():
            try:
                merged = _deep_merge(_DEFAULT_CONFIG, json.loads(candidate_path.read_text(encoding="utf-8-sig")))
                err = _validate_runtime_config(merged, strict=strict_enabled)
                if err:
                    warnings.warn(err, RuntimeWarning)
                    return dict(_DEFAULT_CONFIG)
                return merged
            except Exception:
                if strict_enabled:
                    raise
                return dict(_DEFAULT_CONFIG)

    # Validate defaults too (schema may evolve).
    err = _validate_runtime_config(dict(_DEFAULT_CONFIG), strict=strict_enabled)
    if err:
        warnings.warn(err, RuntimeWarning)
    return dict(_DEFAULT_CONFIG)


@lru_cache(maxsize=32)
def _get_runtime_config_cached(resolved_path: str, cwd: str, strict_enabled: bool) -> Dict[str, Any]:
    # Note: we include cwd in the cache key because default resolution
    # searches Path.cwd() / crt_runtime_config.json.
    if resolved_path:
        return load_runtime_config(resolved_path, strict=strict_enabled)
    return load_runtime_config(None, strict=strict_enabled)


def get_runtime_config(config_path: Optional[str] = None, *, strict: Optional[bool] = None) -> Dict[str, Any]:
    """Return CRT runtime config with safe caching.

    Cache key incorporates the resolved config path (explicit arg or
    CRT_RUNTIME_CONFIG_PATH) and the current working directory.
    """

    resolved_path = (config_path or os.environ.get("CRT_RUNTIME_CONFIG_PATH") or "").strip()
    cwd = str(Path.cwd())
    strict_enabled = _is_strict_validation_enabled(strict)
    return _get_runtime_config_cached(resolved_path, cwd, strict_enabled)


def clear_runtime_config_cache() -> None:
    """Clear cached runtime config.

    Primarily useful in tests that mutate CRT_RUNTIME_CONFIG_PATH.
    """

    _get_runtime_config_cached.cache_clear()


