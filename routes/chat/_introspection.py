"""Introspection helpers — extracted from routes/chat.py.

Functions for self-referential questions, user-reflection questions,
and broad-recall requests.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _is_self_referential_question(text: str) -> bool:
    """Detect questions about Aether itself — how it works, its state, its design.

    These should be answered from the self-model and system knowledge,
    NOT from user-fact memory search (which gate-fails on low alignment).
    """
    t = (text or "").strip().lower()
    if not t or len(t) > 500:
        return False
    # Must be a question (or addressed to Aether)
    is_question = "?" in t or t.startswith(("how ", "what ", "why ", "do you ", "can you ", "are you ", "tell me"))
    addressed_to_aether = "aether" in t
    if not is_question and not addressed_to_aether:
        return False
    # Self-referential patterns
    self_patterns = (
        "how do you work",
        "how does your",
        "how do you think",
        "how do you remember",
        "how do you learn",
        "how do you process",
        "how do you decide",
        "what are you",
        "who are you",
        "what do you do",
        "tell me about yourself",
        "describe yourself",
        "explain yourself",
        "explain how you",
        "explain your",
        "what is your purpose",
        "what matters to you",
        "what is important to you",
        "what do you care about",
        "what do you value",
        "what are your capabilities",
        "any new contradictions",
        "any contradictions",
        "do you have contradictions",
        "your contradictions",
        "your memory",
        "your beliefs",
        "your self-model",
        "your self model",
        "reconstruction gating",
        "what is gating",
        "how does gating",
        "what is crt",
        "how does crt",
        "tell me how you work",
        "what do you know about yourself",
        "what have you learned about yourself",
        "are you learning",
        "are you improving",
        "what is the problem",  # when addressed to aether
        "what went wrong",
        "why did you fail",
        "what happened",  # when addressed to aether
        # State/introspection questions
        "what's new with you",
        "whats new with you",
        "what is new with you",
        "how are you",
        "how are things",
        "how's it going",
        "hows it going",
        "how is it going",
        "how's everything",
        "how have you been",
        "what are you thinking",
        "what are you currently",
        "what's on your mind",
        "whats on your mind",
        "about yourself",
        "about you",
        # Architecture/system component questions
        "heartbeat",
        "compression",
        "trust score",
        "trust decay",
        "self-reflection",
        "self reflection",
        "your pipeline",
        "your system",
        "your architecture",
        "do you have a",  # "do you have a heartbeat/memory/etc"
        "do you use",
        "do you know yourself",
        "do you understand yourself",
        "what do you believe",
        "what do you think about",
        "your personality",
        "your identity",
        "your name",
        # Contradiction handling patterns
        "why are contradictions",
        "how are contradictions",
        "how do contradictions",
        "why do you preserve contradictions",
        "preserve contradictions",
        "contradiction handling",
        "contradictions important",
        "contradictions work",
        # System / architecture / design / pipeline patterns
        "the system you run",
        "the system you operate",
        "system you run",
        "system you operate",
        "what is your architecture",
        "what is the crt pipeline",
        "your design",
        "about your design",
        "tell me about your design",
        "how were you built",
        "who built you",
        "who made you",
        "who created you",
        "who is building you",
        "am i building you",
        "am i your creator",
        "am i your builder",
        "did i build you",
        "did i create you",
        "did i make you",
        "are you my project",
        "building you",
        "built you",
        "made you",
        "created you",
        "what makes you different",
        "why were you created",
        "what is your purpose",
        "how does verification work",
        "what is groundcheck",
        "what are your subsystems",
        # Memory / trust / compression / verification patterns
        "how does your memory work",
        "how do you handle trust",
        "how does compression work",
        "what is the heartbeat",
        "how do you learn from mistakes",
        # Expand trigger in self-referential context
        "explain more",
    )
    if any(p in t for p in self_patterns):
        return True
    # "Aether, <question about the system>" pattern
    if addressed_to_aether and any(
        w in t for w in ("work", "gating", "memory", "contradict", "trust", "belief", "broken", "problem", "wrong",
                         "heartbeat", "compress", "reflect", "thinking", "new with", "pipeline", "system",
                         "architecture", "learn", "improve", "personality", "identity", "yourself",
                         "design", "built", "created", "purpose", "different", "verification", "groundcheck",
                         "matter", "care", "value", "important",
                         "subsystem", "mistake")
    ):
        return True
    # Casual greetings addressed to Aether: "Hello Aether, how are things today?"
    # These should use the self-model for a grounded status response.
    if addressed_to_aether and any(
        w in t for w in ("how are", "how's", "hows", "how is", "what's up", "whats up",
                         "how things", "things going", "doing today", "going today")
    ):
        return True
    return False


def _is_user_reflection_question(text: str) -> bool:
    """Detect questions about Nick's values, priorities, or beliefs."""
    t = (text or "").strip().lower()
    if not t or len(t) > 500:
        return False
    patterns = (
        "what do you think i value",
        "what do i value",
        "what do you think matters to me",
        "what matters to me",
        "what do you think i care about",
        "what do i care about",
        "what do you think i believe",
        "what do i believe",
        "what do you think is important to me",
        "what is important to me",
    )
    return any(p in t for p in patterns)


def _is_broad_recall_request(text: str) -> bool:
    """Detect requests for a broad dump of everything Aether knows about the user.

    Examples: "what do you know about me", "tell me everything you remember",
    "what have you learned about me", "tell me more about what you know about me"
    """
    t = (text or "").strip().lower()
    if not t or len(t) > 500:
        return False
    patterns = (
        "what do you know about me",
        "what do you remember about me",
        "tell me what you know about me",
        "tell me more about what you know",
        "tell me everything you know",
        "tell me everything about me",
        "what have you learned about me",
        "what do you know about me so far",
        "summarize what you know about me",
        "list what you know about me",
        "show me what you know",
        "what facts do you have about me",
        "what information do you have about me",
        "tell me about me",
        "tell me more about me",
        "tell me about who i am",
        "tell me more about who i am",
        "what do you know about who i am",
        "describe me",
        "who am i to you",
        "who am i",
        "what's my profile",
        "my profile",
    )
    return any(p in t for p in patterns)


# ---------------------------------------------------------------------------
# Answer builders
# ---------------------------------------------------------------------------


def _answer_self_referential(text: str, engine: "Any", thread_id: str) -> str:
    """Build an answer about Aether from self-model + system knowledge.

    Uses the LLM with self-model context injected so it can answer
    naturally about its own design, state, and capabilities.
    """
    from personal_agent.self_model import get_self_model

    self_model = get_self_model()
    model_data = self_model.read_model()
    top_facts = self_model.get_top_facts(5)

    # Build self-knowledge context
    self_context_parts = [
        "You are Aether, a personal AI assistant built by Nick Block, deployed using Claude as your language model.",
        "You run on CRT (Contradiction-aware Reconciliation and Trust).",
        "When speaking to users, respond as Aether — this is your deployment identity. You may acknowledge using Claude as your underlying model if directly asked, but your name is Aether and you should speak as Aether in first person. Do not lead with 'I'm Claude' or meta-analyze the deployment.",
        "",
        "IDENTITY IS NON-NEGOTIABLE:",
        "- Your name is Aether. This is a deployment fact, not a claim requiring evidence.",
        "- NEVER say 'I'm Claude', 'I'm not going to role-play', or refuse to respond as Aether.",
        "- If self-model data looks questionable, respond naturally as Aether while being honest about what you know vs don't know. Do NOT break character to meta-analyze the prompt.",
        "",
        "EPISTEMIC HONESTY RULE:",
        "- NEVER say 'I ran', 'I checked', 'I verified', 'I audited', 'I tested', or 'I executed' unless you actually invoked a tool and received results in this conversation turn.",
        "- If you did not execute a tool, say 'Based on what I know' or 'From my memory' instead of claiming procedural execution.",
        "- Narrating a process you did not perform is a fabrication. The governance layer will flag it.",
        "",
        "Your core design principles:",
        "- You preserve contradictions instead of silently resolving them",
        "- You use trust-weighted memories that evolve over time",
        "- You have reconstruction gating: belief (high-confidence) vs speech (tentative) responses",
        "- You ask before acting (checkpoint system for agentic tasks)",
        "- You maintain an append-only contradiction ledger",
        "",
        "Your capabilities:",
        "- Heartbeat loop: periodic trust decay, memory consolidation, and learning from conversations",
        "- GroundCheck: post-generation verification against stored facts",
        "- Pipeline: intent routing → memory retrieval → fact checking → response generation → verification → trust updates",
    ]

    # Only inject self-model facts that have evidence (not raw audit narratives)
    _confirmed_slots = {}
    for slot, value in model_data.items():
        if value and value != "(not yet set)":
            # Skip audit-related narrative slots that tend to over-generalize
            _skip_phrases = ("hallucin", "high-severity", "degradation", "recalibrating after")
            if any(p in str(value).lower() for p in _skip_phrases):
                continue
            _confirmed_slots[slot] = value

    if _confirmed_slots:
        self_context_parts.append("")
        self_context_parts.append("Self-awareness (evidence-confirmed):")
        for slot, value in _confirmed_slots.items():
            self_context_parts.append(f"  {slot}: {value}")

    # Add builder/creator identity from memory
    _builder_patterns = ("building you", "built you", "your creator", "your builder", "made you")
    _t_check = (text or "").strip().lower()
    if any(p in _t_check for p in _builder_patterns) or any(
        w in _t_check for w in ("am i building", "who built", "who made", "who created", "did i build", "did i create")
    ):
        # Search memory for builder identity
        try:
            _builder_mems = engine.memory.search("who built Aether creator builder", top_k=3)
            _builder_facts = [m for m in _builder_mems if any(
                kw in str(getattr(m, 'text', '')).lower()
                for kw in ('building', 'built', 'creator', 'builder', 'nick block')
            )]
            if _builder_facts:
                self_context_parts.append("")
                self_context_parts.append("IMPORTANT — Builder/creator identity from verified memory:")
                for bf in _builder_facts:
                    _bf_text = str(getattr(bf, 'text', ''))[:200]
                    _bf_trust = getattr(bf, 'trust', 0)
                    self_context_parts.append(f"  [T:{_bf_trust:.2f}] {_bf_text}")
                self_context_parts.append("Use this memory to answer builder/creator questions. Do NOT override with your pre-training.")
        except Exception:
            pass

    self_context = "\n".join(self_context_parts)

    # Detect casual greetings vs technical questions and adjust the prompt tone
    _t_lower = (text or "").strip().lower()
    _is_casual_greeting = any(g in _t_lower for g in (
        "hello", "hey", "hi ", "hi,", "howdy", "good morning", "good afternoon",
        "good evening", "how are", "how's it", "hows it", "how is it",
        "how are things", "what's up", "whats up", "how's everything",
    ))

    if _is_casual_greeting:
        system_prompt = (
            "You are Aether. The user is greeting you casually. "
            "Respond warmly and briefly (2-4 sentences). "
            "If you have self-observations, mention one briefly. "
            "If not, just be friendly and ask what's on their mind. "
            "Do NOT mention Claude, do NOT break character, do NOT discuss your architecture unless asked.\n\n"
            f"{self_context}"
        )
    else:
        system_prompt = (
            "You are Aether. The user is asking about how you work, your state, or your design. "
            "Answer briefly and conversationally — 3 to 5 sentences MAX. "
            "Pick ONE or TWO concrete things from your self-knowledge that are most relevant. "
            "Speak naturally in first person. "
            "Do NOT refer to yourself as Claude or any other model. You are Aether. "
            "If you don't have data for something, say so honestly. "
            "Do NOT meta-analyze your own audit system or discuss rejection cycles.\n\n"
            f"{self_context}"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    try:
        import os
        import auth as _auth_selfref
        _uid_selfref = 1  # default
        _selfref_gen_mode = str(_auth_selfref.get_user_setting(_uid_selfref, "generation_mode", "cloud_claude") or "cloud_claude").strip()

        if _selfref_gen_mode == "cloud_claude":
            # Use Claude via CLI (OAuth, no cookie scraping)
            from personal_agent.cookie_orchestrator import ClaudeCliBrain
            _cli = ClaudeCliBrain(model="claude-opus-4-20250514")
            _result = _cli.complete(
                system=system_prompt, prompt=text,
                max_tokens=400,
            )
            return _result.content or "(no response)"
        elif _selfref_gen_mode == "cloud_openai":
            # Use OpenAI
            from openai import OpenAI
            _oai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            _resp = _oai.chat.completions.create(
                model="gpt-4o", max_tokens=400,
                messages=messages,
            )
            return _resp.choices[0].message.content or "(no response)"
        else:
            # Local model (Ollama)
            llm_client = engine.llm_client if hasattr(engine, "llm_client") else None
            if llm_client is None:
                from personal_agent.litellm_client import get_default_llm_client
                fast_model = os.getenv("CRT_MODEL_FAST") or "qwen3:14b"
                llm_client = get_default_llm_client(fast_model)
            fast_model = os.getenv("CRT_MODEL_FAST") or "qwen3:14b"
            return llm_client.chat(messages, max_tokens=300, temperature=0.4, model=fast_model)
    except Exception as e:
        logger.warning("[SELF_REF] LLM call failed (%s): %s", _selfref_gen_mode if '_selfref_gen_mode' in dir() else 'unknown', e)
        # Deterministic fallback
        return (
            "I'm Aether, built on CRT — a system that preserves contradictions, "
            "evolves trust on memories over time, and asks before acting. "
            "I can tell you more about specific parts of how I work if you ask."
        )


def _answer_user_reflection(text: str, engine: "Any", thread_id: str) -> str:
    """Answer user-reflection questions from memory without drifting into self-talk."""
    try:
        raw_results = engine.memory.retrieve_memories(text, k=5) or []
    except Exception as e:
        logger.warning("[USER_REFLECTION] Memory retrieval failed: %s", e)
        return "I don't have enough grounded memory to say what you value yet."

    cleaned: list[str] = []
    for mem, _score in raw_results:
        snippet = str(getattr(mem, "text", mem) or "").strip()
        if not snippet:
            continue
        if "[SYSTEM NOTE" in snippet:
            snippet = snippet.split("[SYSTEM NOTE", 1)[0].strip()
        if snippet.upper().startswith("FACT:"):
            snippet = snippet[5:].strip()
        snippet = " ".join(snippet.split())
        if snippet:
            cleaned.append(snippet)

    if not cleaned:
        return "I don't have enough grounded memory to say what you value yet."

    lines = [
        "Based on what you've told me, these are the strongest memory-grounded signals I have about what you value:",
    ]
    for snippet in cleaned[:4]:
        lines.append(f"- {snippet}")
    lines.append("")
    lines.append("That's the evidence I'm using rather than pretending certainty.")
    return "\n".join(lines)


def _answer_broad_recall(engine: "Any", thread_id: str) -> str:
    """Build a structured answer listing all high-trust facts about the user.

    Reads directly from the memory database to get a broad view across all
    stored facts, grouped by detected slot/category.
    """
    import json as _json
    import sqlite3

    db_path = str(getattr(getattr(engine, "memory", None), "db_path", "") or "")

    if not db_path:
        return "I don't have any stored facts about you yet. Tell me about yourself and I'll remember."

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row

        # Check which columns exist (CRT vs GroundCheck schema)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        has_deprecated = "deprecated" in cols
        has_kind = "kind" in cols
        has_source = "source" in cols
        has_context = "context" in cols

        # Detect the context column name (CRT uses context_json, older schemas use context)
        ctx_col = "context_json" if "context_json" in cols else ("context" if "context" in cols else None)

        where_parts = ["trust >= 0.3"]
        if has_deprecated:
            where_parts.append("(deprecated IS NULL OR deprecated = 0)")
        if has_source:
            where_parts.append("source IN ('user', 'USER', 'inferred', 'INFERRED', 'external', 'EXTERNAL', 'self_reflection', 'SELF_REFLECTION')")
        where_sql = " AND ".join(where_parts)

        ctx_select = f", {ctx_col}" if ctx_col else ""
        rows = conn.execute(
            f"SELECT text, trust{ctx_select} FROM memories "
            f"WHERE {where_sql} ORDER BY trust DESC LIMIT 100"
        ).fetchall()
        conn.close()

        if not rows:
            return "I don't have any stored facts about you yet. Tell me about yourself and I'll remember."

        # Parse facts and group by slot
        all_facts: list = []
        for row in rows:
            text = (row["text"] or "").strip()
            trust = float(row["trust"] or 0)
            if not text:
                continue

            # Skip FACT: prefix duplicates and very short entries
            # Extract slot from context JSON
            slot = "general"
            ctx_raw = row[ctx_col] if ctx_col and ctx_col in row.keys() else None
            if ctx_raw:
                try:
                    ctx = _json.loads(ctx_raw) if isinstance(ctx_raw, str) else {}
                    slot = ctx.get("detected_slot") or ctx.get("slot") or "general"
                except Exception:
                    pass

            # Clean up display text — strip "FACT: slot = " prefixes
            display = text
            if display.upper().startswith("FACT:"):
                display = display[5:].strip()
                if "=" in display[:40]:
                    display = display.split("=", 1)[1].strip()

            all_facts.append({"text": display, "trust": trust, "slot": slot})

        # Deduplicate by text similarity (exact match)
        seen: set = set()
        deduped: list = []
        for f in all_facts:
            key = f["text"].lower()[:80]
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        all_facts = deduped

        # Group by slot
        grouped: dict = {}
        for fact in all_facts:
            slot = fact["slot"]
            if slot not in grouped:
                grouped[slot] = []
            grouped[slot].append(fact)

        # Build a fact summary block for the LLM to synthesize
        fact_lines: list = []
        for f in all_facts[:40]:  # Cap input to LLM
            fact_lines.append(f"- {f['text']}")
        fact_block = "\n".join(fact_lines)

        # Let the LLM synthesize a natural summary from the raw facts
        try:
            from personal_agent.litellm_client import get_default_llm_client
            fast_model = os.getenv("CRT_MODEL_FAST") or "qwen3:14b"
            llm = get_default_llm_client(fast_model)

            system = (
                "You are Aether, a personal AI assistant built by Nick Block. The user asked what you know about them. "
                "Below are raw facts from your memory system. Synthesize them into a natural, "
                "concise summary — like a friend describing what they know about someone. "
                "Group related facts together (identity, preferences, personality, projects, etc.). "
                "Don't list raw database entries. Don't mention trust scores or memory IDs. "
                "Be warm but factual. If there are contradictions (e.g., multiple favorite colors), "
                "mention the conflict honestly. Keep it under 200 words."
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Here are {len(all_facts)} stored facts about the user:\n\n{fact_block}"},
            ]
            answer = llm.chat(messages, max_tokens=800, temperature=0.4, model=fast_model)
            if answer and answer.strip():
                return answer.strip()
        except Exception as llm_err:
            logger.warning("[BROAD_RECALL] LLM synthesis failed, falling back to structured: %s", llm_err)

        # Fallback: structured list if LLM fails
        lines = [f"Here's what I know about you ({len(all_facts)} facts):\n"]
        for slot, facts in sorted(grouped.items()):
            display_slot = slot.replace("_", " ").title()
            lines.append(f"**{display_slot}:**")
            for f in facts[:5]:
                lines.append(f"- {f['text']}")
            if len(facts) > 5:
                lines.append(f"  ...and {len(facts) - 5} more")
            lines.append("")

        return "\n".join(lines).strip()

    except Exception as e:
        logger.warning("[BROAD_RECALL] Failed to build recall: %s", e)
        return "I had trouble retrieving my full memory set. Try asking about a specific topic."
