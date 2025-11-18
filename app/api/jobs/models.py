from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, ConfigDict

JobStatus = Literal["queued", "in_progress", "done", "failed"]


class JobCreate(BaseModel):
    project_id: str
    input_key: Optional[str] = None
    callback_url: AnyHttpUrl
    metadata: Optional[dict[str, Any]] = None
    task: Optional[str] = None
    task_payload: Optional[dict[str, Any]] = None
    target_lang: Optional[str] = None  # 타겟 언어 코드 추가
    source_lang: Optional[str] = None  # 원본 언어 코드 추가
    is_replace_voice_samples: Optional[bool] = True # 음성샘플 자동 추천 여부



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
    target_lang: Optional[str] = None  # 타겟 언어 코드 추가
    created_at: datetime
    updated_at: datetime
    history: list[JobHistoryEntry] = Field(default_factory=list)
    source_lang: Optional[str] = None  # 원본 언어 코드 추가
    is_replace_voice_samples: Optional[bool] = True # 음성샘플 자동 추천 여부


class JobUpdateMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    stage: Literal[
        "downloaded",
        "stt_completed",
        "mt_prepare",
        "mt_completed",
        "tts_prepare",
        "tts_completed",
        "pre_tts_prepare",
        "pre_tts_completed",
        "completed",
        "failed",
        "segment_mix_started",
        "segment_mix_completed",
        "segment_tts_completed",
        "segment_tts_started",
    ]
    segments_count: Optional[int] = None
    metadata_key: Optional[str] = None
    result_key: Optional[str] = None
    target_lang: Optional[str] = None
    source_lang: Optional[str] = None
    input_key: Optional[str] = None
    segment_assets_prefix: Optional[str] = None
    segments: Optional[list[dict[str, Any]]] = None
    segment: Optional[dict[str, Any]] = None
    is_replace_voice_samples: Optional[bool] = True # 음성샘플 자동 추천 여부


class JobUpdateStatus(BaseModel):
    status: Literal["in_progress", "done", "failed"]
    result_key: str | None = None
    error: str | None = None
    message: str | None = None
    metadata: JobUpdateMetadata | dict[str, Any] | None = None
