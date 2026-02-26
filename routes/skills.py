"""Skill lifecycle route module."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Request

from routes.models import (
    SkillDiscoverRequest,
    SkillDiscoverResponse,
    SkillInstallRequest,
    SkillLifecycleResponse,
    SkillsListResponse,
    SkillRecordModel,
    SkillTrustRequest,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _registry(request: Request):
    registry = getattr(request.app.state, "skill_registry", None)
    if registry is None:
        raise HTTPException(status_code=500, detail="Skill registry not initialized")
    return registry


def _to_model(item: Dict[str, Any]) -> SkillRecordModel:
    return SkillRecordModel(
        name=str(item.get("name") or ""),
        description=str(item.get("description") or ""),
        source_path=item.get("source_path"),
        install_path=item.get("install_path"),
        version=item.get("version"),
        trust_level=str(item.get("trust_level") or "untrusted"),
        enabled=bool(item.get("enabled")),
        installed=bool(item.get("installed")),
        metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
        discovered_at=item.get("discovered_at"),
        last_installed_at=item.get("last_installed_at"),
        updated_at=item.get("updated_at"),
    )


@router.get("", response_model=SkillsListResponse)
def list_skills(request: Request) -> SkillsListResponse:
    reg = _registry(request)
    items = [_to_model(i) for i in reg.list_skills()]
    return SkillsListResponse(items=items, total=len(items))


@router.post("/discover", response_model=SkillDiscoverResponse)
def discover_skills(payload: SkillDiscoverRequest, request: Request) -> SkillDiscoverResponse:
    reg = _registry(request)
    roots = payload.roots if payload.roots else None
    found = [_to_model(i) for i in reg.discover_skills(roots=roots)]
    return SkillDiscoverResponse(discovered=found, count=len(found))


@router.post("/install", response_model=SkillLifecycleResponse)
def install_skill(payload: SkillInstallRequest, request: Request) -> SkillLifecycleResponse:
    reg = _registry(request)
    try:
        saved = reg.install_skill(
            name=payload.name,
            source_path=payload.source_path,
            enabled=bool(payload.enabled),
            trust_level=payload.trust_level,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SkillLifecycleResponse(ok=True, skill=_to_model(saved))


@router.post("/{skill_name}/update", response_model=SkillLifecycleResponse)
def update_skill(skill_name: str, request: Request) -> SkillLifecycleResponse:
    reg = _registry(request)
    try:
        saved = reg.update_skill(skill_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SkillLifecycleResponse(ok=True, skill=_to_model(saved))


@router.post("/{skill_name}/enable", response_model=SkillLifecycleResponse)
def enable_skill(skill_name: str, request: Request) -> SkillLifecycleResponse:
    reg = _registry(request)
    try:
        saved = reg.set_enabled(skill_name, True)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SkillLifecycleResponse(ok=True, skill=_to_model(saved))


@router.post("/{skill_name}/disable", response_model=SkillLifecycleResponse)
def disable_skill(skill_name: str, request: Request) -> SkillLifecycleResponse:
    reg = _registry(request)
    try:
        saved = reg.set_enabled(skill_name, False)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SkillLifecycleResponse(ok=True, skill=_to_model(saved))


@router.post("/{skill_name}/trust", response_model=SkillLifecycleResponse)
def set_skill_trust(
    skill_name: str,
    payload: SkillTrustRequest,
    request: Request,
) -> SkillLifecycleResponse:
    reg = _registry(request)
    try:
        saved = reg.set_trust_level(skill_name, payload.trust_level)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SkillLifecycleResponse(ok=True, skill=_to_model(saved))


@router.delete("/{skill_name}", response_model=SkillLifecycleResponse)
def uninstall_skill(
    skill_name: str,
    request: Request,
    remove_files: bool = Query(default=True),
) -> SkillLifecycleResponse:
    reg = _registry(request)
    try:
        saved = reg.uninstall_skill(skill_name, remove_files=remove_files)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SkillLifecycleResponse(ok=True, skill=_to_model(saved))
