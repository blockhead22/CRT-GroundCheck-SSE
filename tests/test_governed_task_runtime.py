from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_agent.db_utils import ThreadSessionDB
from personal_agent.governed_task import GovernedTask, GovernedTaskStatus, GovernedTaskWaitKind
from routes.tasks import router as tasks_router
import routes.tasks as tasks_module


def test_governed_task_checkpoint_and_suspend_adapters_use_durable_state(tmp_path: Path) -> None:
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    task = GovernedTask.new(thread_id="thread-a", objective="Refactor the file", max_iterations=6)
    created = db.create_governed_task(task)

    db.store_suspended_loop(
        "thread-a",
        {
            "objective": "Refactor the file",
            "steps_done": [{"tool": "search_code", "status": "ok"}],
            "question": "Should I update both files?",
            "orch_answer_so_far": "I found two candidate files.\n\n",
            "remaining_iterations": 4,
        },
    )
    active = db.get_active_governed_task("thread-a")
    assert active is not None
    assert active["task_id"] == created["task_id"]
    assert active["status"] == GovernedTaskStatus.AWAITING_USER.value
    assert active["wait_kind"] == GovernedTaskWaitKind.ASK_USER.value
    assert active["question"] == "Should I update both files?"
    assert db.get_suspended_loop("thread-a")["question"] == "Should I update both files?"
    compat_pending = db.get_pending_task("thread-a")
    assert compat_pending is not None
    assert compat_pending["task_id"] == created["task_id"]
    assert compat_pending["question"] == "Should I update both files?"

    db.clear_suspended_loop("thread-a")
    active = db.get_active_governed_task("thread-a")
    assert active is not None
    assert active["status"] == GovernedTaskStatus.RUNNING.value
    assert active["wait_kind"] is None

    db.store_pending_checkpoint(
        "thread-a",
        intent_data={"route": "task", "intent_type": "plan_create"},
        checkpoint_tier="plan",
        metadata={"prompt": "Approve the plan?"},
    )
    pending = db.get_pending_checkpoint("thread-a")
    assert pending is not None
    assert pending["checkpoint_tier"] == "plan"
    active = db.get_active_governed_task("thread-a")
    assert active is not None
    assert active["status"] == GovernedTaskStatus.AWAITING_CHECKPOINT.value
    assert active["wait_kind"] == GovernedTaskWaitKind.CHECKPOINT.value
    assert active["checkpoint_tier"] == "plan"

    db.clear_pending_checkpoint("thread-a")
    active = db.get_active_governed_task("thread-a")
    assert active is not None
    assert active["status"] == GovernedTaskStatus.RUNNING.value
    assert active["wait_kind"] is None


def test_governed_task_terminal_states_leave_no_active_task(tmp_path: Path) -> None:
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    task = GovernedTask.new(thread_id="thread-b", objective="Audit logs", max_iterations=3)
    created = db.create_governed_task(task)

    db.update_governed_task(created["task_id"], status=GovernedTaskStatus.NEEDS_FOLLOWUP.value, pending_followups=["Check the auth logs"])
    active = db.get_active_governed_task("thread-b")
    assert active is not None
    assert active["status"] == GovernedTaskStatus.NEEDS_FOLLOWUP.value
    assert active["pending_followups"] == ["Check the auth logs"]

    db.complete_governed_task(created["task_id"], "Done")
    assert db.get_active_governed_task("thread-b") is None


def test_create_governed_task_cancels_prior_active_task_for_thread(tmp_path: Path) -> None:
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    first = GovernedTask.new(thread_id="thread-b2", objective="First task", max_iterations=2)
    second = GovernedTask.new(thread_id="thread-b2", objective="Second task", max_iterations=4)

    first_record = db.create_governed_task(first)
    second_record = db.create_governed_task(second)

    assert db.get_active_governed_task("thread-b2")["task_id"] == second_record["task_id"]
    prior = db.get_governed_task(first_record["task_id"])
    assert prior is not None
    assert prior["status"] == GovernedTaskStatus.CANCELLED.value


def test_active_governed_task_api_returns_minimal_recovery_payload(tmp_path: Path) -> None:
    db = ThreadSessionDB(str(tmp_path / "thread_sessions.db"))
    task = GovernedTask.new(thread_id="thread-c", objective="Research a topic", max_iterations=5)
    db.create_governed_task(task)
    db.update_governed_task(
        task.task_id,
        status=GovernedTaskStatus.AWAITING_USER.value,
        wait_kind=GovernedTaskWaitKind.ASK_USER.value,
        question="Which source should I prioritize?",
        pending_followups=["Search the docs", "Search the web"],
    )

    app = FastAPI()
    app.include_router(tasks_router)
    original = tasks_module.get_thread_session_db
    tasks_module.get_thread_session_db = lambda: db
    try:
        client = TestClient(app)
        response = client.get("/api/tasks/active", params={"thread_id": "thread-c"})
        assert response.status_code == 200
        body = response.json()
        assert body["task"]["thread_id"] == "thread-c"
        assert body["task"]["status"] == GovernedTaskStatus.AWAITING_USER.value
        assert body["task"]["wait_kind"] == GovernedTaskWaitKind.ASK_USER.value
        assert body["task"]["question"] == "Which source should I prioritize?"
        assert body["task"]["pending_followups"] == ["Search the docs", "Search the web"]
    finally:
        tasks_module.get_thread_session_db = original
