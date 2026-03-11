from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.crt_core import MemorySource
from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.db_utils import ThreadSessionDB
from routes import chat as chat_routes
from routes.models import ChatSendResponse


class FakeLLM:
    def generate(self, prompt: str, max_tokens: int = 1000, stream: bool = False):
        return "OK"


@pytest.fixture()
def rag(tmp_path: Path) -> CRTEnhancedRAG:
    mem_db = tmp_path / "mem.db"
    led_db = tmp_path / "ledger.db"
    profile_db = tmp_path / "profile.db"
    return CRTEnhancedRAG(
        memory_db=str(mem_db),
        ledger_db=str(led_db),
        profile_db=str(profile_db),
        llm_client=FakeLLM(),
    )


def _parse_sse_events(raw_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in raw_text.splitlines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


def test_continuity_augmented_text_does_not_trigger_contradiction_spam(rag: CRTEnhancedRAG):
    before = len(rag.ledger.get_open_contradictions(limit=200))
    rag.query("My name is Nick Block.")
    augmented = (
        "hello\n\n"
        "[CONTINUITY INSTRUCTION] Treat this as a follow-up.\n"
        "[RECENT CONVERSATION CONTEXT]\n"
        "User: My name is Aether\n"
        "Assistant: Thanks."
    )

    out = rag.query(augmented)

    assert out.get("contradiction_detected") is False
    after = len(rag.ledger.get_open_contradictions(limit=200))
    assert after == before


def test_nickname_history_query_bypasses_contradiction_prompt(rag: CRTEnhancedRAG):
    rag.query("My name is Nick Block.")
    rag.query("Call me Nicky.")

    out = rag.query("what other nicknames did i say i had?")
    ans = (out.get("answer") or "").lower()

    # Name history queries no longer return via deterministic template —
    # the name data is injected as context and the model responds naturally.
    # The answer should still contain the name variants.
    assert "nick" in ans, f"Expected 'nick' in answer: {ans[:200]}"


def test_continuity_helper_avoids_short_message_contamination():
    history = [
        {"role": "user", "content": "What were the top three highlights?"},
        {"role": "assistant", "content": "I can summarize those highlights."},
    ]

    unchanged = chat_routes._augment_query_with_continuity(
        message="hello",
        history_messages=history,
    )
    assert unchanged == "hello"

    augmented = chat_routes._augment_query_with_continuity(
        message="tell me the highlights",
        history_messages=history,
    )
    assert "[RECENT CONVERSATION CONTEXT]" in augmented


def test_continuity_helper_treats_provenance_and_what_else_as_followups():
    history = [
        {"role": "user", "content": "What is my favorite drink?"},
        {"role": "assistant", "content": "Coffee"},
    ]

    augmented_provenance = chat_routes._augment_query_with_continuity(
        message="how do you know?",
        history_messages=history,
    )
    augmented_more = chat_routes._augment_query_with_continuity(
        message="what else?",
        history_messages=history,
    )

    assert "[RECENT CONVERSATION CONTEXT]" in augmented_provenance
    assert "[RECENT CONVERSATION CONTEXT]" in augmented_more


def test_recent_slot_provenance_uses_last_detected_slot():
    class _SessionDB:
        def get_recent_queries(self, thread_id: str, window: int = 6):
            return [
                {
                    "query_text": "What is my favorite color?",
                    "detected_slot": "favorite_color",
                    "response_text": "orange",
                    "timestamp": 2.0,
                }
            ]

    class _Source:
        value = "user"

    class _MemoryItem:
        def __init__(self, text: str, trust: float, timestamp: float):
            self.text = text
            self.trust = trust
            self.timestamp = timestamp
            self.source = _Source()
            self.deprecated = False

    class _Memory:
        def _load_all_memories(self):
            return [_MemoryItem("My favorite color is orange.", 0.7, 5.0)]

    class _Engine:
        def __init__(self):
            self.memory = _Memory()

    answer = chat_routes._answer_recent_slot_provenance(
        engine=_Engine(),
        session_db=_SessionDB(),
        thread_id="t1",
    )

    assert answer is not None
    assert "favorite color is orange" in answer.lower()
    assert "trust: 0.70" in answer


def test_stream_uses_shared_pipeline_and_surfaces_thinking(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(chat_routes.router)

    def fake_shared_pipeline(req, request) -> ChatSendResponse:
        return ChatSendResponse(
            answer="Final streamed answer.",
            response_type="speech",
            gates_passed=True,
            gate_reason="ok",
            session_id="s1",
            metadata={"thinking": "Step A. Step B."},
        )

    monkeypatch.setattr(chat_routes, "_run_shared_chat_pipeline", fake_shared_pipeline)
    client = TestClient(app)

    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "stream_t", "message": "hi"},
    )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    event_types = [e.get("type") for e in events]

    assert "thinking_start" in event_types
    assert "thinking_end" in event_types
    assert "token" in event_types
    assert "done" in event_types
    assert "error" not in event_types

    done = next(e for e in events if e.get("type") == "done")
    assert done.get("content") == "Final streamed answer."
    assert done.get("metadata", {}).get("gate_reason") == "ok"


def test_stream_think_fallback_no_thinking_still_completes(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(chat_routes.router)

    def fake_shared_pipeline(req, request) -> ChatSendResponse:
        return ChatSendResponse(
            answer="No thinking payload.",
            response_type="speech",
            gates_passed=True,
            gate_reason="ok",
            session_id="s2",
            metadata={},
        )

    monkeypatch.setattr(chat_routes, "_run_shared_chat_pipeline", fake_shared_pipeline)
    client = TestClient(app)

    resp = client.post(
        "/api/chat/stream",
        json={"thread_id": "stream_t2", "message": "hi"},
    )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    event_types = [e.get("type") for e in events]
    assert "error" not in event_types
    done = next(e for e in events if e.get("type") == "done")
    assert done.get("content") == "No thinking payload."


def test_architecture_detector_ignores_about_me_memory_submission():
    msg = (
        'Here is an about me "Nick Block is a web developer, filmmaker, and print shop maker. '
        "He's also developing CRT (Cognitive Reflective Transformer) under Aeteros.\""
    )
    assert chat_routes._is_architecture_explanation_request(msg) is False


def test_architecture_detector_still_routes_specific_technical_questions():
    msg = "Can you explain CRT architecture, reconstruction gates, and contradiction ledger?"
    assert chat_routes._is_architecture_explanation_request(msg) is True


def test_bare_web_search_command_reuses_previous_user_question(tmp_path: Path):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    tid = "tg_1"
    db.get_or_create_session(tid)
    db.record_query(
        thread_id=tid,
        query_text="can you check if dji mic 2 transmitter uses 3.5mm lav input?",
        response_text="pending",
        detected_slot=None,
    )
    rewritten = chat_routes._resolve_bare_web_search_command(
        message="use duck duck go and web search",
        session_db=db,
        thread_id=tid,
    )
    assert rewritten.startswith("search the web for ")
    assert "dji mic 2 transmitter uses 3.5mm" in rewritten.lower()


def test_bare_web_search_command_preserves_specific_duckduckgo_question(tmp_path: Path):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    tid = "tg_2"
    db.get_or_create_session(tid)
    msg = "can you check if dji mic 2 transmitter uses 3.5mm lav input using duckduckgo"
    rewritten = chat_routes._resolve_bare_web_search_command(
        message=msg,
        session_db=db,
        thread_id=tid,
    )
    assert rewritten == msg


def test_bare_web_search_command_avoids_double_prefix_for_existing_search_query(tmp_path: Path):
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    tid = "tg_3"
    db.get_or_create_session(tid)
    db.record_query(
        thread_id=tid,
        query_text="search the web for dji mic 2 transmitter lav input",
        response_text="pending",
        detected_slot=None,
    )
    rewritten = chat_routes._resolve_bare_web_search_command(
        message="use web search",
        session_db=db,
        thread_id=tid,
    )
    assert rewritten == "search the web for dji mic 2 transmitter lav input"


def test_workplan_direct_answer_for_item_queries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_path = tmp_path / "groundcheck.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            text TEXT,
            trust REAL,
            source TEXT,
            timestamp REAL,
            namespace TEXT,
            created_at TEXT
        )
        """
    )
    now = time.time()
    text = (
        "Current work plan for Aether: Items 3 (preference extraction from chat), "
        "4 (heartbeat news monitoring), 8 (personality state machine), "
        "9 (background reflection), 10 (DNNT retraining), "
        "11 (multi-model routing), 12 (email integration)."
    )
    cur.execute(
        """
        INSERT INTO memories (id, thread_id, text, trust, source, timestamp, namespace, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("m1", "copilot_session", text, 0.7, "user", now, "global", "2026-02-25 18:50:37"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("GROUNDCHECK_DB", str(db_path))

    out = chat_routes._try_answer_workplan_question("what is item 4 from that work plan?")
    assert out is not None
    assert "heartbeat news monitoring" in str(out.get("answer", "")).lower()

    out2 = chat_routes._try_answer_workplan_question("what are items 9 and 10?")
    assert out2 is not None
    ans2 = str(out2.get("answer", "")).lower()
    assert "background reflection" in ans2
    assert "dnnt retraining" in ans2


def test_workplan_direct_answer_falls_back_to_crt_memory(rag: CRTEnhancedRAG):
    text = (
        "Current work plan for Aether: Items 3 (preference extraction from chat), "
        "4 (heartbeat news monitoring), 8 (personality state machine)."
    )
    rag.memory.store_memory(
        text=text,
        confidence=0.95,
        source=MemorySource.USER,
        context={"kind": "test_workplan"},
        thread_id="default",
    )

    out = chat_routes._try_answer_workplan_question(
        "what is number 4 from the current work plan?",
        engine=rag,
        thread_id="default",
    )
    assert out is not None
    assert "heartbeat news monitoring" in str(out.get("answer", "")).lower()


def test_mcp_tools_direct_answer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_path = tmp_path / "groundcheck.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            text TEXT,
            trust REAL,
            source TEXT,
            timestamp REAL,
            namespace TEXT,
            created_at TEXT
        )
        """
    )
    now = time.time()
    mcp_text = (
        "MCP TOOLS EXPANSION IDEAS — Feb 15 2026. New tools to build: "
        "cogniforge_compress (compress embedding to 192d), "
        "crt_search_code_context (what files was I editing when working on X), "
        "crt_project_memory (namespace-scoped per project), "
        "crt_topic_drift (track rising/fading topics across sessions)."
    )
    cur.execute(
        """
        INSERT INTO memories (id, thread_id, text, trust, source, timestamp, namespace, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("mcp1", "default", mcp_text, 0.7, "user", now, "global", "2026-02-15 16:57:09"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("GROUNDCHECK_DB", str(db_path))

    out = chat_routes._try_answer_mcp_tools_question("from mcp tools expansion ideas, name one tool idea")
    assert out is not None
    assert str(out.get("answer", "")).lower() in {
        "cogniforge_compress",
        "crt_search_code_context",
        "crt_project_memory",
        "crt_topic_drift",
    }

    out2 = chat_routes._try_answer_mcp_tools_question(
        "in mcp tools expansion ideas, which tool tracks rising or fading topics?"
    )
    assert out2 is not None
    assert "crt_topic_drift" in str(out2.get("answer", "")).lower()


def test_synthesis_filters_low_signal_memory_noise(rag: CRTEnhancedRAG):
    rag.memory.store_memory(
        text="I'm letting you know some info about myself",
        confidence=0.9,
        source=MemorySource.USER,
        context={"kind": "noise"},
        thread_id="default",
    )
    rag.memory.store_memory(
        text="My name is Nick Block and I build websites and films.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"kind": "profile"},
        thread_id="default",
    )

    out = rag.query("What do you know about me?", thread_id="default")
    ans = str(out.get("answer") or "").lower()
    assert "my name is nick block" in ans
    assert "letting you know some info about myself" not in ans


def test_synthesis_uses_profile_facts_when_retrieval_is_sparse(rag: CRTEnhancedRAG):
    # Seed structured profile without writing corresponding memory items.
    rag.user_profile.update_from_text("My name is Nick Block.", thread_id="default")

    out = rag.query("what do you know about me?", thread_id="default")
    ans = str(out.get("answer") or "").lower()

    assert "i don't have specific profile facts captured yet" not in ans
    assert ("fact: name = nick block" in ans) or ("nick block" in ans)


def test_synthesis_profile_fallback_is_thread_scoped(rag: CRTEnhancedRAG):
    current_thread = "thread_current"
    other_thread = "thread_other"

    # Seed unrelated profile facts in another thread.
    rag.user_profile.update_from_text("I am 34 years old.", thread_id=other_thread)
    rag.user_profile.update_from_text("I drink dark roast coffee.", thread_id=other_thread)
    rag.user_profile.update_from_text("I left Microsoft.", thread_id=other_thread)

    # Seed the current thread with the actual identity cue.
    rag.user_profile.update_from_text("My name is Nick Block.", thread_id=current_thread)

    out = rag.query("Who am I and what do you know about me?", thread_id=current_thread)
    ans = str(out.get("answer") or "").lower()

    assert "nick block" in ans
    assert "34" not in ans
    assert "dark roast" not in ans
    assert "left:microsoft" not in ans


def test_slot_augmentation_profile_facts_are_thread_scoped(rag: CRTEnhancedRAG):
    current_thread = "thread_current_slot"
    other_thread = "thread_other_slot"

    rag.user_profile.update_from_text("I work at Google.", thread_id=other_thread)
    rag.user_profile.update_from_text("I work at The Printing Lair.", thread_id=current_thread)

    out = rag.query("Where do I work?", thread_id=current_thread)
    retrieved_text = " ".join(
        str(mem.get("text") or "")
        for mem in (out.get("retrieved_memories") or [])
        if isinstance(mem, dict)
    ).lower()

    assert "printing lair" in retrieved_text
    assert "google" not in retrieved_text


def test_20_turn_continuity_profile_workplan_and_web_search(
    rag: CRTEnhancedRAG,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    tid = "nick_continuity_20"
    session_db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    session_db.get_or_create_session(tid)

    # Seed rich profile + plan memories, plus noisy lines that must be filtered.
    rag.memory.store_memory(
        text="My name is Nick Block. I am a web developer, filmmaker, and print shop maker through The Printing Lair.",
        confidence=0.95,
        source=MemorySource.USER,
        context={"kind": "profile_seed"},
        thread_id=tid,
    )
    rag.memory.store_memory(
        text=(
            "Current work plan for Aether: Items 3 (preference extraction from chat), "
            "4 (heartbeat news monitoring), 8 (personality state machine), "
            "9 (background reflection), 10 (DNNT retraining), "
            "11 (multi-model routing), 12 (email integration)."
        ),
        confidence=0.95,
        source=MemorySource.USER,
        context={"kind": "plan_seed"},
        thread_id=tid,
    )
    rag.memory.store_memory(
        text="I'm letting you know some info about myself",
        confidence=0.9,
        source=MemorySource.USER,
        context={"kind": "noise"},
        thread_id=tid,
    )
    rag.memory.store_memory(
        text="You should know some of my history. Like my career history.?!",
        confidence=0.88,
        source=MemorySource.USER,
        context={"kind": "noise"},
        thread_id=tid,
    )

    monkeypatch.setattr(
        rag,
        "_run_web_search",
        lambda query: [
            {
                "title": "DJI Mic 2 transmitter guide",
                "url": "https://example.com/dji-mic-2-transmitter-guide",
                "snippet": "The transmitter has a 3.5mm TRS input for external lav mics.",
            },
            {
                "title": "DJI Mic 2 FAQ",
                "url": "https://example.com/dji-mic-2-faq",
                "snippet": "External lavaliers plug into the transmitter 3.5mm input.",
            },
        ],
    )

    def run_turn(message: str) -> Dict[str, str]:
        effective = chat_routes._resolve_bare_web_search_command(
            message=message,
            session_db=session_db,
            thread_id=tid,
        )
        direct = chat_routes._try_answer_workplan_question(
            effective,
            engine=rag,
            thread_id=tid,
        )
        if direct:
            answer = str(direct.get("answer") or "")
        else:
            out = rag.query(effective, thread_id=tid)
            answer = str(out.get("answer") or "")

        session_db.record_query(
            thread_id=tid,
            query_text=message,
            response_text=answer,
            detected_slot=None,
        )
        return {
            "message": message,
            "effective": effective,
            "answer": answer,
        }

    turns = [
        "What do you know about me?",
        'what was the current work plan if we finished "3 (preference extraction from chat)" what is number 4',
        "what are items 9 and 10?",
        "what comes next after item 10?",
        "can you check and see if they use the 3.5mm for lav mics on the actual mic part not the receiver",
        "use duck duck go and web search",
        "can you check and see if they use the 3.5mm for lav mics on the actual mic part not the receiver. using duckduckgo",
        "what do you know about me now?",
        "what is item 12?",
        "what is number 4 again?",
        "search the web for dji mic 2 transmitter lav input",
        "use web search",
        "what are items 3 and 4?",
        "what is next after item 11?",
        "what do you know about me?",
        "can you look up latest camera mic connector info using duckduckgo",
        "use duckduckgo and web search",
        "what is item 8 from the current work plan?",
        "what is item 9 from the current work plan?",
        "what is item 10 from the current work plan?",
    ]

    transcript = [run_turn(t) for t in turns]

    assert len(transcript) == 20
    assert all((row["answer"] or "").strip() for row in transcript)

    # Turn 1: rich profile recall, noise filtered.
    t1 = transcript[0]["answer"].lower()
    assert "nick block" in t1
    assert "letting you know some info about myself" not in t1
    assert "you should know some of my history" not in t1

    # Work-plan continuity across multiple follow-ups.
    assert "heartbeat news monitoring" in transcript[1]["answer"].lower()
    t3 = transcript[2]["answer"].lower()
    assert "background reflection" in t3
    assert "dnnt retraining" in t3
    assert "multi-model routing" in transcript[3]["answer"].lower()
    assert "email integration" in transcript[8]["answer"].lower()
    assert "heartbeat news monitoring" in transcript[9]["answer"].lower()
    assert "preference extraction from chat" in transcript[12]["answer"].lower()
    assert "heartbeat news monitoring" in transcript[12]["answer"].lower()
    assert "email integration" in transcript[13]["answer"].lower()
    assert "personality state machine" in transcript[17]["answer"].lower()
    assert "background reflection" in transcript[18]["answer"].lower()
    assert "dnnt retraining" in transcript[19]["answer"].lower()

    # Bare web-search command should reuse previous substantive question.
    assert transcript[5]["effective"].lower().startswith("search the web for ")
    assert "3.5mm for lav mics" in transcript[5]["effective"].lower()
    assert "sources:" in transcript[5]["answer"].lower()
    assert "https://example.com/dji-mic-2-transmitter-guide" in transcript[5]["answer"]

    # Explicit DuckDuckGo query should preserve message and still return citations.
    assert transcript[6]["effective"] == turns[6]
    assert "sources:" in transcript[6]["answer"].lower()
    assert "https://example.com/dji-mic-2-transmitter-guide" in transcript[6]["answer"]

    # Repeated bare search command later should map to the latest substantive web question.
    assert transcript[11]["effective"].lower().startswith("search the web for ")
    assert "dji mic 2 transmitter lav input" in transcript[11]["effective"].lower()
    assert "search the web for search the web for" not in transcript[11]["effective"].lower()
    assert transcript[16]["effective"].lower().startswith("search the web for ")
    assert "latest camera mic connector info" in transcript[16]["effective"].lower()
