"""Shared Pydantic models for modularized routes.

Phase 0 starts by moving new/extracted route models here. Existing models in
`crt_api.py` will be migrated incrementally.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str

