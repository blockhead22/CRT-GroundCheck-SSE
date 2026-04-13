"""Response expansion helpers extracted from routes/chat.py."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from personal_agent.reflection_system import ReflectionResult
from personal_agent.text_utils import strip_thinking_tags as _strip_thinking_tags

from ._constants import _EXPAND_TRIGGERS
from ._preferences import _format_style_instruction


def _user_requested_expansion(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(t == trigger or t.startswith(trigger + " ") for trigger in _EXPAND_TRIGGERS)


def _should_expand_response(
    question: str,
    response: str,
    reflection_result: Optional[ReflectionResult],
    verbosity_pref: Optional[str],
) -> Tuple[bool, Optional[str]]:
    if not response:
        return False, None
    if verbosity_pref == "concise":
        return False, None
    if _user_requested_expansion(question):
        return True, "user_requested"
    if reflection_result and reflection_result.suggested_action in ("refine", "re-query"):
        return True, f"reflection_{reflection_result.suggested_action}"
    if verbosity_pref == "verbose" and len(response) < 1400:
        return True, "preference_verbose"
    return False, None


def _build_expansion_prompt(
    question: str,
    response: str,
    known_facts: str,
    reflection_result: Optional[ReflectionResult],
) -> str:
    parts = [
        "You are expanding a draft answer after a self-check.",
        "Rules:",
        "- Do not repeat the original answer verbatim.",
        "- Add missing details, examples, or concrete steps when useful.",
        "- If you are unsure, say what is uncertain instead of guessing.",
        "",
        f"Question:\n{question}",
        "",
        f"Draft answer:\n{response}",
    ]
    if known_facts:
        parts.append("")
        parts.append(f"Known facts:\n{known_facts}")
    if reflection_result:
        parts.append("")
        parts.append(
            f"Self-assessment: confidence={reflection_result.confidence_label}, "
            f"suggested_action={reflection_result.suggested_action}"
        )
    parts.append("")
    parts.append("Provide an expanded answer:")
    return "\n".join(parts)


def _generate_expansion(
    llm_client: Any,
    question: str,
    response: str,
    known_facts: str,
    style_profile: Optional[Dict[str, Any]],
    reflection_result: Optional[ReflectionResult],
    personality_profile: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if not llm_client:
        return None
    style_instruction = _format_style_instruction(style_profile, personality_profile)
    system_lines = [
        "You are a careful assistant expanding a response after a self-check.",
        "Keep additions grounded in known facts. Avoid speculation.",
    ]
    if style_instruction:
        system_lines.append(style_instruction)
    system_prompt = " ".join(system_lines)
    prompt = _build_expansion_prompt(question, response, known_facts, reflection_result)
    expansion = llm_client.generate(prompt, system=system_prompt, max_tokens=420, temperature=0.4)
    if not isinstance(expansion, str):
        return None
    expansion = _strip_thinking_tags(expansion).strip()
    if not expansion or expansion.startswith("[Ollama error") or expansion.startswith("[Ollama connection error"):
        return None
    # Strip model meta-preamble that leaks from instruction-following models
    expansion = re.sub(
        r"^(Okay[,.]?\s+)?(here'?s?\s+)?(an?\s+)?(expanded|expanded version|expansion)[^:\n]*[:\n]+\s*",
        "",
        expansion,
        flags=re.IGNORECASE,
    ).lstrip()
    expansion = re.sub(
        r"^(Okay[,.]?\s+)(I'?ll|let me|the user|based on)[^\n]*\n+",
        "",
        expansion,
        flags=re.IGNORECASE,
    ).lstrip()
    if not expansion:
        return None
    return expansion


def _chunk_text(text: str, chunk_size: int = 320) -> List[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
