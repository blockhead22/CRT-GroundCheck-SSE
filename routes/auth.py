"""Auth route module – extracted from crt_api.py."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Header

import auth as auth_module
from routes.models import (
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthMeResponse,
    AuthUpdateProfileRequest,
    SyncChatRequest,
    SyncChatResponse,
    AuthUserResponse,
    ChatThreadModel,
)

router = APIRouter(prefix="/api/auth")


@router.post("/register", response_model=AuthLoginResponse)
def auth_register(req: AuthRegisterRequest):
    """Register a new user account."""
    try:
        user = auth_module.register_user(
            username=req.username,
            password=req.password,
            display_name=req.display_name,
        )
        if not user:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Create session
        session = auth_module.create_session(user.id)

        return AuthLoginResponse(
            ok=True,
            token=session.token,
            user=AuthUserResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                created_at=user.created_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthLoginResponse)
def auth_login(req: AuthLoginRequest):
    """Login with username and password."""
    try:
        user = auth_module.authenticate_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Create session
    session = auth_module.create_session(user.id)

    return AuthLoginResponse(
        ok=True,
        token=session.token,
        user=AuthUserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            created_at=user.created_at,
        ),
    )


@router.post("/logout")
def auth_logout(authorization: Optional[str] = Header(None)):
    """Logout and invalidate session."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if token:
        auth_module.delete_session(token)

    return {"ok": True}


@router.get("/me", response_model=AuthMeResponse)
def auth_me(authorization: Optional[str] = Header(None)):
    """Get current user info from session token."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        return AuthMeResponse(ok=False, user=None)

    user = auth_module.validate_session(token)
    if not user:
        return AuthMeResponse(ok=False, user=None)

    return AuthMeResponse(
        ok=True,
        user=AuthUserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            created_at=user.created_at,
        ),
    )


@router.patch("/update_profile")
def auth_update_profile(
    req: AuthUpdateProfileRequest,
    authorization: Optional[str] = Header(None),
):
    """Update the authenticated user's profile fields (e.g. display_name)."""
    user = _get_user_from_token(authorization)

    if req.display_name and req.display_name.strip():
        auth_module.update_user_display_name(user.id, req.display_name.strip())

    # Re-fetch user to return updated data.
    updated = auth_module.get_user_by_id(user.id)
    if not updated:
        updated = user

    return {
        "ok": True,
        "user": AuthUserResponse(
            id=updated.id,
            username=updated.username,
            display_name=updated.display_name,
            created_at=updated.created_at,
        ),
    }


@router.post("/sync-chats", response_model=SyncChatResponse)
def auth_sync_chats(req: SyncChatRequest, authorization: Optional[str] = Header(None)):
    """Sync chat threads for logged in user."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth_module.validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # Save threads
    threads_data = [
        {
            "id": t.id,
            "title": t.title,
            "messages": t.messages,
            "updatedAt": t.updatedAt,
        }
        for t in req.threads
    ]
    auth_module.save_user_threads(user.id, threads_data)

    return SyncChatResponse(ok=True, threads=threads_data)


@router.get("/load-chats", response_model=SyncChatResponse)
def auth_load_chats(authorization: Optional[str] = Header(None)):
    """Load chat threads for logged in user."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth_module.validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    threads = auth_module.load_user_threads(user.id)
    return SyncChatResponse(ok=True, threads=threads)


# ---------------------------------------------------------------------------
# User Settings (cloud toggles, preferences)
# ---------------------------------------------------------------------------


def _get_user_from_token(authorization: Optional[str]):
    """Extract and validate user from Bearer token.
    Falls back to default user (id=1) for single-user setups without active sessions.
    """
    if authorization is not None and not isinstance(authorization, str):
        authorization = str(authorization)
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if token:
        user = auth_module.validate_session(token)
        if user:
            return user
    # Fallback: single-user mode — return first user in DB
    try:
        user = auth_module.get_user_by_id(1)
        if user:
            return user
    except Exception:
        pass
    raise HTTPException(status_code=401, detail="Not authenticated")


@router.get("/settings")
def auth_get_settings(authorization: Optional[str] = Header(None)):
    """Return all settings for the authenticated user (merged with defaults)."""
    user = _get_user_from_token(authorization)
    settings = auth_module.get_user_settings(user.id)
    return {"ok": True, "settings": settings}


@router.patch("/settings")
def auth_update_settings(
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Upsert settings. Accepts a flat {key: value} dict."""
    user = _get_user_from_token(authorization)

    # Whitelist of allowed setting keys
    allowed_keys = {
        "cloud_slot_classification",
        "cloud_nli_contradiction",
        "cloud_reflection_validation",
        "cloud_escalation_policy",
        "cloud_confidence_threshold",
        "cloud_daily_limit_multiplier",
        # Claude (Tier 2/3) settings
        "cloud_claude_enabled",
        "cloud_claude_generation",
        "cloud_claude_reflection",
        "cloud_claude_daily_limit",
        "cloud_claude_max_tokens",
        # Primary generation mode
        "generation_mode",
        "cloud_model_openai",
        "cloud_model_claude",
    }

    updated = {}
    for key, value in body.items():
        if key in allowed_keys:
            auth_module.set_user_setting(user.id, key, str(value))
            updated[key] = str(value)

    return {"ok": True, "updated": updated}


@router.get("/cloud-usage")
def auth_cloud_usage(authorization: Optional[str] = Header(None)):
    """Return CloudFeatureService usage stats including Claude metrics."""
    _get_user_from_token(authorization)  # auth check

    try:
        from personal_agent.cloud_features import get_cloud_feature_service
        svc = get_cloud_feature_service()
        if svc is None:
            return {"ok": True, "usage": {}, "message": "Cloud features not initialized"}
        usage = svc.get_usage_summary()
        # Add Claude-specific metrics
        daily = svc.get_daily_counts()
        claude_gen = daily.get("claude_generation", {"used": 0, "limit": 0})
        claude_ref = daily.get("claude_reflection", {"used": 0, "limit": 0})
        claude_calls_today = claude_gen.get("used", 0) + claude_ref.get("used", 0)
        claude_gen_bucket = svc.usage.get("claude_generation", {})
        claude_ref_bucket = svc.usage.get("claude_reflection", {})
        claude_tokens_today = (
            (claude_gen_bucket.get("est_tokens", 0) if isinstance(claude_gen_bucket, dict) else 0)
            + (claude_ref_bucket.get("est_tokens", 0) if isinstance(claude_ref_bucket, dict) else 0)
        )
        # Read configured daily limit from user settings
        try:
            user = _get_user_from_token(authorization)
            claude_daily_limit = int(auth_module.get_user_setting(user.id, "cloud_claude_daily_limit", "20") or "20")
        except Exception:
            claude_daily_limit = 20
        usage["claude_calls_today"] = claude_calls_today
        usage["claude_daily_limit"] = claude_daily_limit
        usage["claude_tokens_today"] = claude_tokens_today
        usage["claude_available"] = svc._cookie_available()
        return {"ok": True, "usage": usage}
    except Exception as e:
        return {"ok": True, "usage": {}, "message": str(e)}


@router.get("/cloud-usage-history")
def auth_cloud_usage_history(
    authorization: Optional[str] = Header(None),
    limit: int = 50,
    feature: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Return the last N cloud usage entries from SQLite, with optional filters.

    Query params:
        limit: max rows (1-500, default 50)
        feature: filter by feature name (slot_classification, nli_contradiction, reflection_validation)
        start_date: ISO date lower bound (e.g. 2026-03-22)
        end_date: ISO date upper bound (e.g. 2026-03-22)
    """
    _get_user_from_token(authorization)  # auth check

    try:
        from personal_agent.cloud_usage_logger import get_cloud_usage_logger
        ul = get_cloud_usage_logger()
        entries = ul.get_history(
            limit=limit,
            feature=feature,
            start_date=start_date,
            end_date=end_date,
        )
        return {"ok": True, "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"ok": False, "entries": [], "count": 0, "error": str(e)}


@router.get("/cloud-usage-summary")
def auth_cloud_usage_summary(
    authorization: Optional[str] = Header(None),
    date: Optional[str] = None,
):
    """Return aggregated daily summary of cloud usage.

    Query params:
        date: ISO date string (e.g. 2026-03-22). Defaults to today UTC.
    """
    _get_user_from_token(authorization)  # auth check

    try:
        from personal_agent.cloud_usage_logger import get_cloud_usage_logger
        ul = get_cloud_usage_logger()
        summary = ul.get_daily_summary(date_str=date)
        return {"ok": True, "summary": summary}
    except Exception as e:
        return {"ok": False, "summary": {}, "error": str(e)}

