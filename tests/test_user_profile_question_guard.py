import sqlite3
from pathlib import Path

from personal_agent.user_profile import GlobalUserProfile


def test_user_profile_skips_questions_and_assistant_name(tmp_path: Path) -> None:
    db_path = tmp_path / "profile.db"
    profile = GlobalUserProfile(db_path=str(db_path), use_llm_extraction=False)

    skipped = profile.update_from_text(
        "How do you remember you are Aether and I am Nick?",
        thread_id="thread_q",
    )
    assert skipped == {"updated": {}, "replaced": {}}

    updated = profile.update_from_text(
        "You are Aether. I am Nick.",
        thread_id="thread_a",
    )
    assert updated.get("updated", {}).get("name") == "Nick"
    assert "assistant_name" not in (updated.get("updated") or {})

    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT slot, value FROM user_profile_multi WHERE active = 1 ORDER BY slot"
        ).fetchall()

    assert ("name", "Nick") in rows
    assert all(slot != "assistant_name" for slot, _ in rows)
