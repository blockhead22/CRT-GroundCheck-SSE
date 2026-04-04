from __future__ import annotations

from typing import Optional


def is_strict_local_only_mode(
    uid: Optional[int] = 1,
    generation_mode: Optional[str] = None,
) -> bool:
    """Return whether runtime policy should forbid cloud generation/governance.

    This helper is intentionally lightweight so it can be used from background
    systems that do not have access to a request object.
    """
    try:
        import auth as _auth_local

        _uid_local = int(uid) if uid else 1
        _routing_mode = str(
            _auth_local.get_user_setting(_uid_local, "routing_mode", "") or ""
        ).strip().lower()
        _cloud_escalation = str(
            _auth_local.get_user_setting(
                _uid_local, "cloud_escalation_policy", "conservative"
            )
            or "conservative"
        ).strip().lower()
        _effective_generation = str(
            generation_mode
            or _auth_local.get_user_setting(_uid_local, "generation_mode", "")
            or ""
        ).strip().lower()
        if _effective_generation == "local_network":
            _effective_generation = "local"
        return _routing_mode == "local_only" or (
            _effective_generation in ("local", "local_network", "local_only")
            and _cloud_escalation == "local_only"
        )
    except Exception:
        return False


def is_cloud_governance_allowed(
    uid: Optional[int] = 1,
    generation_mode: Optional[str] = None,
) -> bool:
    return not is_strict_local_only_mode(uid=uid, generation_mode=generation_mode)
