# app/api/preview/router.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Tuple

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException

from app.config.s3 import s3
from ..deps import DbDep
from .model import (
    PreviewCreateBody,
    PreviewCreateResponse,
    PreviewGetResponse,
    PreviewStatus,
)


preview_router = APIRouter(prefix="/preview", tags=["preview"])
editor_preview_router = APIRouter(prefix="/editor", tags=["preview"])

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")


async def _create_segment_preview(
    project_id: str,
    lang_code: str,
    segment_id: str,
    body: PreviewCreateBody,
    db: DbDep,
) -> PreviewCreateResponse:
    _validate_payload_consistency(body, project_id, lang_code, segment_id)
    preview_id = _build_preview_id(project_id, lang_code, segment_id)
    status, video_url, audio_url, updated_at = await _resolve_segment_assets(
        db, project_id, segment_id
    )
    return PreviewCreateResponse(
        previewId=preview_id,
        status=status,
        videoUrl=video_url,
        audioUrl=audio_url,
        updatedAt=updated_at,
    )


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


async def _resolve_segment_assets(
    db: DbDep, project_id: str, segment_id: str
) -> Tuple[PreviewStatus, Optional[str], Optional[str], str]:
    project = await _load_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    segment = _find_segment(project, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="segment not found")

    assets = segment.get("assets") or {}
    video_key = segment.get("video_key") or assets.get("video_key")
    mix_key = segment.get("mix_key") or assets.get("mix_key")
    tts_key = segment.get("tts_key") or assets.get("tts_key")

    video_url = _presign(video_key) if video_key else None
    audio_source_key = mix_key or tts_key
    audio_url = _presign(audio_source_key) if audio_source_key else None

    if not video_url and not audio_url:
        return "failed", None, None, now_iso()

    return "completed", video_url, audio_url, now_iso()


async def _load_project(db: DbDep, project_id: str) -> Optional[dict]:
    try:
        object_id = ObjectId(project_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="invalid project_id") from exc
    return await db["projects"].find_one({"_id": object_id})


def _find_segment(project: dict, segment_id: str) -> Optional[dict]:
    segments = project.get("segments") or []
    for segment in segments:
        if str(segment.get("segment_id")) == segment_id:
            return segment
    return None


def _presign(key: Optional[str], *, expires_in: int = 900) -> Optional[str]:
    if not key:
        return None
    if not AWS_S3_BUCKET:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET not configured")
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AWS_S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception as exc:  # boto3 can raise multiple error types
        raise HTTPException(
            status_code=500, detail=f"failed to presign url for {key}"
        ) from exc


def _build_preview_id(project_id: str, lang_code: str, segment_id: str) -> str:
    return f"{project_id}:{lang_code}:{segment_id}"


def _parse_preview_id(preview_id: str) -> Tuple[str, str, str]:
    parts = preview_id.split(":")
    if len(parts) != 3:
        raise ValueError("invalid preview id")
    return parts[0], parts[1], parts[2]


def _validate_payload_consistency(
    body: PreviewCreateBody,
    project_id: str,
    lang_code: str,
    segment_id: str,
) -> None:
    if body.project_id and body.project_id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch")
    if body.lang_code and body.lang_code != lang_code:
        raise HTTPException(status_code=400, detail="lang_code mismatch")
    if body.segment_id and body.segment_id != segment_id:
        raise HTTPException(status_code=400, detail="segment_id mismatch")


@preview_router.post(
    "/projects/{project_id}/languages/{lang_code}/segments/{segment_id}/preview",
    response_model=PreviewCreateResponse,
)
async def create_segment_preview(
    project_id: str,
    lang_code: str,
    segment_id: str,
    body: PreviewCreateBody,
    db: DbDep,
) -> PreviewCreateResponse:
    return await _create_segment_preview(project_id, lang_code, segment_id, body, db)


@editor_preview_router.post(
    "/projects/{project_id}/languages/{lang_code}/segments/{segment_id}/preview",
    response_model=PreviewCreateResponse,
)
async def create_segment_preview_editor(
    project_id: str,
    lang_code: str,
    segment_id: str,
    body: PreviewCreateBody,
    db: DbDep,
) -> PreviewCreateResponse:
    return await _create_segment_preview(project_id, lang_code, segment_id, body, db)


@preview_router.get("/preview/{preview_id}", response_model=PreviewGetResponse)
async def get_preview(preview_id: str, db: DbDep) -> PreviewGetResponse:
    return await _get_preview(preview_id, db)


@editor_preview_router.get("/preview/{preview_id}", response_model=PreviewGetResponse)
async def get_preview_editor(preview_id: str, db: DbDep) -> PreviewGetResponse:
    return await _get_preview(preview_id, db)


async def _get_preview(preview_id: str, db: DbDep) -> PreviewGetResponse:
    try:
        project_id, _, segment_id = _parse_preview_id(preview_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status, video_url, audio_url, updated_at = await _resolve_segment_assets(
        db, project_id, segment_id
    )
    return PreviewGetResponse(
        status=status,
        videoUrl=video_url,
        audioUrl=audio_url,
        updatedAt=updated_at,
    )
