"""Compatibility patches for FastAPI/Starlette version skew."""

from __future__ import annotations

import inspect


def patch_starlette_router_lifecycle_kwargs() -> None:
    """Drop FastAPI lifecycle kwargs unsupported by newer Starlette Router."""
    try:
        from starlette.routing import Router
    except Exception:
        return

    original_init = Router.__init__
    if getattr(original_init, "_crt_lifecycle_compat", False):
        return

    try:
        accepted = set(inspect.signature(original_init).parameters)
    except (TypeError, ValueError):
        return

    unsupported = {"on_startup", "on_shutdown", "lifespan"} - accepted
    if not unsupported:
        return

    def _compat_init(self, *args, **kwargs):
        on_startup = kwargs.get("on_startup")
        on_shutdown = kwargs.get("on_shutdown")
        for key in unsupported:
            kwargs.pop(key, None)
        result = original_init(self, *args, **kwargs)
        if "on_startup" in unsupported and not hasattr(self, "on_startup"):
            self.on_startup = list(on_startup or [])
        if "on_shutdown" in unsupported and not hasattr(self, "on_shutdown"):
            self.on_shutdown = list(on_shutdown or [])
        return result

    _compat_init._crt_lifecycle_compat = True
    Router.__init__ = _compat_init
