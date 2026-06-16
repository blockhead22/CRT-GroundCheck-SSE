"""Modular route registration for CRT API."""

from ._fastapi_compat import patch_starlette_router_lifecycle_kwargs

patch_starlette_router_lifecycle_kwargs()

from .register import register_routes

__all__ = ["register_routes"]
