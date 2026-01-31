"""Pydantic models and API endpoints for heartbeat system."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class HeartbeatConfigRequest(BaseModel):
    """Request to update heartbeat config for a thread."""
    enabled: bool = Field(default=True)
    every: int = Field(default=1800, description="Interval in seconds (e.g., 1800 for 30m)")
    target: str = Field(default="none", description="'none' (silent), 'last' (last channel), or channel name")
    active_hours_start: Optional[int] = Field(default=None, description="Hour of day (0-23)")
    active_hours_end: Optional[int] = Field(default=None)
    timezone: str = Field(default="UTC")
    model: Optional[str] = Field(default=None, description="Override LLM model for heartbeat")
    max_tokens: int = Field(default=500)
    temperature: float = Field(default=0.7)
    dry_run: bool = Field(default=False, description="If true, simulate without executing")


class HeartbeatConfigResponse(BaseModel):
    """Response with current heartbeat config."""
    thread_id: str
    config: Dict[str, Any]
    last_run: Optional[float] = None
    last_summary: Optional[str] = None


class HeartbeatAction(BaseModel):
    """A single action taken by heartbeat."""
    action_type: str  # "post", "comment", "vote", "none"
    target_id: Optional[str] = None
    content: Optional[str] = None
    vote_direction: Optional[str] = None
    reason: str = ""
    executed: bool = False


class HeartbeatRunResponse(BaseModel):
    """Response from running a heartbeat."""
    thread_id: str
    ran_successfully: bool
    timestamp: float
    decision_summary: str
    actions: List[HeartbeatAction] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
    error: Optional[str] = None


class HeartbeatHistoryItem(BaseModel):
    """One entry in heartbeat run history."""
    timestamp: float
    summary: str
    success: bool
    action_count: int


class HeartbeatHistoryResponse(BaseModel):
    """Response with heartbeat history for a thread."""
    thread_id: str
    history: List[HeartbeatHistoryItem]
    total_runs: int


class HeartbeatMDRequest(BaseModel):
    """Request to update HEARTBEAT.md."""
    content: str = Field(min_length=1, max_length=10000)


class HeartbeatMDResponse(BaseModel):
    """Response with current HEARTBEAT.md content."""
    content: Optional[str] = None
    last_modified: Optional[float] = None
    path: str = "HEARTBEAT.md"
