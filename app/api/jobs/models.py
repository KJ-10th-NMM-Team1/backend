from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field

JobStatus = Literal["queued", "in_progress", "done", "failed"]


class JobCreate(BaseModel):
    project_id: str
    input_key: str
    callback_url: AnyHttpUrl
    metadata: Optional[dict[str, Any]] = None


class JobHistoryEntry(BaseModel):
    status: JobStatus
    ts: datetime
    message: Optional[str] = None


class JobRead(BaseModel):
    job_id: str = Field(alias="id")
    project_id: str
    input_key: str
    status: JobStatus
    callback_url: AnyHttpUrl
    result_key: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    history: list[JobHistoryEntry] = Field(default_factory=list)


class JobUpdateStatus(BaseModel):
    status: Literal["in_progress", "done", "failed"]
    result_key: str | None = None
    error: str | None = None
    message: str | None = None
    metadata: dict[str, Any] | None = None
