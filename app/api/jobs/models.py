from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field

JobStatus = Literal["queued", "in_progress", "done", "failed"]


class JobCreate(BaseModel):
    project_id: str
    input_key: Optional[str] = None
    callback_url: AnyHttpUrl
    metadata: Optional[dict[str, Any]] = None
    task: Optional[str] = None
    task_payload: Optional[dict[str, Any]] = None


class JobHistoryEntry(BaseModel):
    status: JobStatus
    ts: datetime
    message: Optional[str] = None


class JobRead(BaseModel):
    job_id: str = Field(alias="id")
    project_id: str
    input_key: Optional[str] = None
    status: JobStatus
    callback_url: AnyHttpUrl
    result_key: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    task: Optional[str] = None
    task_payload: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    history: list[JobHistoryEntry] = Field(default_factory=list)


class JobUpdateMetadata(BaseModel):
    stage: Literal[
        "downloaded",
        "stt_completed",
        "mt_prepare",
        "mt_completed",
        "tts_prepare",
        "tts_completed",
    ]
    segments_count: int
    metadata_key: str
    result_key: str
    target_lang: str
    source_lang: str
    input_key: str
    segment_assets_prefix: str


class JobUpdateStatus(BaseModel):
    status: Literal["in_progress", "done", "failed"]
    result_key: str | None = None
    error: str | None = None
    message: str | None = None
    metadata: JobUpdateMetadata | None = None
