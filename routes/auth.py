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
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth_module.validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if req.display_name and req.display_name.strip():
        auth_module.update_user_display_name(user.id, req.display_name.strip())

    # Re-fetch user to return updated data.
    updated = auth_module.validate_session(token)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to fetch updated user")

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

