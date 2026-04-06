"""Route registration entrypoint."""

from fastapi import FastAPI

from .agent import router as agent_router
from .auth import router as auth_router
from .chat import router as chat_router
from .contradictions import router as contradictions_router
from .copilot import router as copilot_router
from .jobs import router as jobs_router
from .learning import router as learning_router
from .logs import router as logs_router, install_log_handler
from .memory import router as memory_router
from .misc import router as misc_router
from .notifications import router as notifications_router
from .scheduled_tasks import router as scheduled_tasks_router
from .skills import router as skills_router
from .tasks import router as tasks_router
from .threads import router as threads_router
from .action_receipts import router as action_receipts_router
from .commitments import router as commitments_router
from .slot_discovery import router as slot_discovery_router
from .desktop import router as desktop_router
from .intents import router as intents_router
from .plans import router as plans_router
from .tooling import router as tooling_router
from .analysis import router as analysis_router
from .ingest import router as ingest_router
from .ambient import router as ambient_router
from .compaction import router as compaction_router
from .gpt_logs import router as gpt_logs_router
from .ws import router as ws_router
from .agent_runs import router as agent_runs_router


def register_routes(app: FastAPI) -> None:
    """Register modular routers on the app."""
    install_log_handler()
    app.include_router(ambient_router)
    app.include_router(compaction_router)
    app.include_router(gpt_logs_router)
    app.include_router(ingest_router)
    app.include_router(analysis_router)
    app.include_router(plans_router)
    app.include_router(tooling_router)
    app.include_router(desktop_router)
    app.include_router(intents_router)
    app.include_router(action_receipts_router)
    app.include_router(commitments_router)
    app.include_router(slot_discovery_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(memory_router)
    app.include_router(contradictions_router)
    app.include_router(copilot_router)
    app.include_router(learning_router)
    app.include_router(jobs_router)
    app.include_router(tasks_router)
    app.include_router(threads_router)
    app.include_router(scheduled_tasks_router)
    app.include_router(notifications_router)
    app.include_router(skills_router)
    app.include_router(agent_router)
    app.include_router(misc_router)
    app.include_router(logs_router)
    app.include_router(agent_runs_router)
    app.include_router(ws_router)
