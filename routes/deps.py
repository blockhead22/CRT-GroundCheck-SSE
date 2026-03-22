"""Shared dependency contracts for modular route handlers.

Route modules use ``request.app.state`` to access shared singletons that
``create_app()`` wires up.  The helpers here provide typed, reusable FastAPI
``Depends()`` callables so individual route files stay clean.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from fastapi import Header, Query, Request

from personal_agent.crt_rag import CRTEnhancedRAG
from personal_agent.text_utils import sanitize_thread_id  # noqa: F401 – re-exported

logger = logging.getLogger(__name__)


def resolve_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract the authenticated user ID from the Bearer token, or None.

    This is a lightweight helper intended for use as a FastAPI dependency
    or as a plain function called from route handlers.  It returns None
    when no valid session exists so that callers can fall back gracefully
    to thread-scoped behaviour for anonymous / legacy requests.
    """
    # Handle both plain strings and FastAPI Header objects
    if authorization is not None and not isinstance(authorization, str):
        authorization = str(authorization)
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    if not token:
        return None
    try:
        import auth as auth_module
        user = auth_module.validate_session(token)
        if user is not None:
            return str(user.id)
    except Exception:
        pass
    return None


# sanitize_thread_id imported from personal_agent.text_utils (re-exported above)


# ---------------------------------------------------------------------------
# Typed accessors for app.state
# ---------------------------------------------------------------------------

def get_engine(request: Request, thread_id: str) -> CRTEnhancedRAG:
    """Resolve the CRTEnhancedRAG engine for *thread_id* via app.state."""
    return request.app.state.get_engine(thread_id)


def get_engine_from_query(request: Request, thread_id: str = Query(default="default")) -> CRTEnhancedRAG:
    """FastAPI-compatible dependency that reads thread_id from query params."""
    tid = sanitize_thread_id(thread_id)
    return request.app.state.get_engine(tid)


def get_training_loop(request: Request):
    """Return the shared ``CRTTrainingLoop`` instance."""
    return request.app.state.training_loop


def get_jobs_worker(request: Request):
    """Return the shared ``CRTJobsWorker`` instance."""
    return request.app.state.jobs_worker


def get_idle_scheduler(request: Request):
    """Return the ``CRTIdleScheduler`` instance."""
    return request.app.state.idle_scheduler


def get_scheduled_tasks_db_path(request: Request) -> str:
    return request.app.state.scheduled_tasks_db_path


def get_jobs_db_path(request: Request) -> str:
    return request.app.state.jobs_db_path


def get_llm_client(request: Request):
    """Return the shared ``OllamaClient`` (may be ``None`` if disabled)."""
    return request.app.state.get_llm_client()


def get_collapse_logger(request: Request):
    return request.app.state.collapse_logger


def get_doc_map(request: Request) -> Dict[str, Dict[str, Any]]:
    return request.app.state.doc_map


def get_turn_number(request: Request, thread_id: str) -> int:
    return request.app.state.get_turn_number(thread_id)


def increment_turn(request: Request, thread_id: str) -> int:
    return request.app.state.increment_turn(thread_id)


def thread_db_paths(request: Request, thread_id: str) -> tuple[str, str]:
    return request.app.state.thread_db_paths(thread_id)

