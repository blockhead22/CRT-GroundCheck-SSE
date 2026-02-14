"""Route registration entrypoint."""

from fastapi import FastAPI

from .agent import router as agent_router
from .auth import router as auth_router
from .chat import router as chat_router
from .contradictions import router as contradictions_router
from .copilot import router as copilot_router
from .jobs import router as jobs_router
from .learning import router as learning_router
from .memory import router as memory_router
from .misc import router as misc_router
from .scheduled_tasks import router as scheduled_tasks_router
from .threads import router as threads_router


def register_routes(app: FastAPI) -> None:
    """Register modular routers on the app."""
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(memory_router)
    app.include_router(contradictions_router)
    app.include_router(copilot_router)
    app.include_router(learning_router)
    app.include_router(jobs_router)
    app.include_router(threads_router)
    app.include_router(scheduled_tasks_router)
    app.include_router(agent_router)
    app.include_router(misc_router)
