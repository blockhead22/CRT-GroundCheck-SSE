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
            "new_user": "Hello! I'm your AI assistant. I'm here to help you with questions and tasks.",
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

    # Dev-facing: periodic train→eval→publish loop for the suggestion-only model.
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
                "I'm an AI assistant (a software system). I don't have a human occupation, "
                "but my role is to help with questions, writing, and problem-solving."
            ),
            "purpose": (
                "I'm an AI assistant designed to help you think, write, and get tasks done. "
                "I can use our chat context when it's provided, and I try to be explicit when I'm uncertain."
            ),
            "identity": "I'm an AI assistant (a software system) designed to help with information and tasks.",
            "background_general": (
                "I don't have personal experiences or a human background—I'm an AI system. "
                "I can still help with information, planning, and examples if you tell me what you need."
            ),
            "background_filmmaking": (
                "I don't have a personal background or real-world experience in filmmaking—I'm an AI system. "
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
            "unknown": "I don't have a reliable stored memory of your occupation/job yet — if you tell me, I can remember it going forward.",
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
                merged = _deep_merge(_DEFAULT_CONFIG, json.loads(path.read_text(encoding="utf-8")))
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
                merged = _deep_merge(_DEFAULT_CONFIG, json.loads(candidate_path.read_text(encoding="utf-8")))
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
