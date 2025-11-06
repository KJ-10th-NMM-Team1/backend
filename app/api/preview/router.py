# app/api/preview/router.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config.s3 import s3
from ..deps import DbDep
from .model import (
    PreviewCreateBody,
    PreviewCreateResponse,
    PreviewGetResponse,
    PreviewStatus,
)

# 재번역시 세그먼트 TTS 잡 enqueue
from app.api.jobs.service import start_segment_tts_job

preview_router = APIRouter(prefix="/preview", tags=["preview"])
editor_preview_router = APIRouter(prefix="/editor", tags=["preview"])

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")


# ---------- 공통 유틸 ----------
def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


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
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"failed to presign url for {key}"
        ) from exc


def _s3_exists(key: Optional[str]) -> bool:
    if not key:
        return False
    try:
        s3.head_object(Bucket=AWS_S3_BUCKET, Key=key)
        return True
    except Exception:
        return False


def _build_preview_id(project_id: str, lang_code: str, segment_id: str) -> str:
    return f"{project_id}:{lang_code}:{segment_id}"


def _parse_preview_id(preview_id: str) -> Tuple[str, str, str]:
    parts = preview_id.split(":")
    if len(parts) != 3:
        raise ValueError("invalid preview id")
    return parts[0], parts[1], parts[2]


async def _load_project(db: DbDep, project_id: str) -> Optional[dict]:
    try:
        pid = ObjectId(project_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="invalid project_id") from exc
    return await db["projects"].find_one({"_id": pid})


async def _load_segment_doc(
    db: DbDep, project_id: str, seg_id_or_index: str
) -> Optional[dict]:
    """
    segments 컬렉션에서 세그먼트 한 건을 찾아온다.
    우선순위: (_id == seg) → (segment_id == seg) → (segment_id == ObjectId(seg)) → (segment_index == int(seg))
    """
    try:
        pid = ObjectId(project_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="invalid project_id") from exc

    coll = db["segments"]

    # 1) _id 일치
    try:
        seg_oid = ObjectId(seg_id_or_index)
        doc = await coll.find_one({"_id": seg_oid, "project_id": pid})
        if doc:
            return doc
    except InvalidId:
        pass

    # 2) segment_id 문자열
    doc = await coll.find_one({"segment_id": seg_id_or_index, "project_id": pid})
    if doc:
        return doc

    # 3) segment_id ObjectId
    try:
        seg_oid2 = ObjectId(seg_id_or_index)
        doc = await coll.find_one({"segment_id": seg_oid2, "project_id": pid})
        if doc:
            return doc
    except InvalidId:
        pass

    # 4) segment_index 정수
    try:
        idx = int(seg_id_or_index)
        doc = await coll.find_one({"segment_index": idx, "project_id": pid})
        if doc:
            return doc
    except (TypeError, ValueError):
        pass

    return None


def _extract_asset_keys(seg: dict) -> Dict[str, Optional[str]]:
    assets = seg.get("assets") or {}
    return {
        "mix": seg.get("mix_key") or assets.get("mix_key"),
        "tts": seg.get("tts_key") or assets.get("tts_key"),
        "video": seg.get("video_key") or assets.get("video_key"),
        "bgm": seg.get("bgm_key") or assets.get("bgm_key"),
        "source": seg.get("source_key") or assets.get("source_key"),
    }


def _build_prefix_keys(
    prefix: Optional[str], index: Optional[int]
) -> Dict[str, Optional[str]]:
    if not prefix or index is None:
        return {"mix": None, "tts": None, "video": None, "bgm": None, "source": None}
    base = f"{index:04d}"
    p = prefix.rstrip("/")
    return {
        "mix": f"{p}/{base}_mix.wav",
        "tts": f"{p}/{base}_tts.wav",
        "video": f"{p}/{base}_video.mp4",
        "bgm": f"{p}/{base}_bgm.wav",
        "source": f"{p}/{base}_source.wav",
    }


# ---------- 프리뷰(기존) ----------
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


async def _resolve_segment_assets(
    db: DbDep, project_id: str, segment_id: str
) -> Tuple[PreviewStatus, Optional[str], Optional[str], str]:
    project = await _load_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    seg = await _load_segment_doc(db, project_id, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="segment not found")

    prefix = project.get("segment_assets_prefix")
    seg_index = seg.get("segment_index")

    # (a) prefix + index 패턴 키 우선 확인
    pref_keys = _build_prefix_keys(prefix, seg_index)
    audio_key = (
        pref_keys["mix"]
        if _s3_exists(pref_keys["mix"])
        else (pref_keys["tts"] if _s3_exists(pref_keys["tts"]) else None)
    )
    video_key = pref_keys["video"] if _s3_exists(pref_keys["video"]) else None
    if audio_key or video_key:
        return "completed", _presign(video_key), _presign(audio_key), now_iso()

    # (b) 세그먼트 문서 키
    seg_keys = _extract_asset_keys(seg)
    audio_key2 = seg_keys["mix"] or seg_keys["tts"]
    video_key2 = seg_keys["video"]
    has_audio = _s3_exists(audio_key2) if audio_key2 else False
    has_video = _s3_exists(video_key2) if video_key2 else False
    if has_audio or has_video:
        return (
            "completed",
            _presign(video_key2 if has_video else None),
            _presign(audio_key2 if has_audio else None),
            now_iso(),
        )

    # (c) 아직 생성 전 → processing
    return ("processing" if prefix else "failed"), None, None, now_iso()


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
    _validate_payload_consistency(body, project_id, lang_code, segment_id)
    status, video_url, audio_url, updated_at = await _resolve_segment_assets(
        db, project_id, segment_id
    )
    return PreviewCreateResponse(
        previewId=_build_preview_id(project_id, lang_code, segment_id),
        status=status,
        videoUrl=video_url,
        audioUrl=audio_url,
        updatedAt=updated_at,
    )


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
    return await create_segment_preview(project_id, lang_code, segment_id, body, db)


@preview_router.get("/preview/{preview_id}", response_model=PreviewGetResponse)
async def get_preview(preview_id: str, db: DbDep) -> PreviewGetResponse:
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


@editor_preview_router.get("/preview/{preview_id}", response_model=PreviewGetResponse)
async def get_preview_editor(preview_id: str, db: DbDep) -> PreviewGetResponse:
    return await get_preview(preview_id, db)


# ---------- 재번역(세그먼트만 TTS) ----------
class RetranslateBody(BaseModel):
    text: str = Field(min_length=1, description="새 번역 텍스트")


class RetranslateResponse(BaseModel):
    job_id: str
    segment_id: str
    segment_index: int
    status: Literal["queued", "in_progress", "done", "failed"]


@editor_preview_router.put(
    "/projects/{project_id}/segments/{segment_id}/retranslate",
    response_model=RetranslateResponse,
)
async def retranslate_segment(
    project_id: str,
    segment_id: str,
    body: RetranslateBody,
    db: DbDep,
) -> RetranslateResponse:
    """
    1) segments 컬렉션에서 세그먼트 로드
    2) translate_context 업데이트
    3) segment_tts 잡 enqueue (SQS)
    """
    project = await _load_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    seg = await _load_segment_doc(db, project_id, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="segment not found")

    # translate_context 저장
    try:
        await db["segments"].update_one(
            {"_id": seg["_id"]},
            {
                "$set": {
                    "translate_context": body.text,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        seg["translate_context"] = body.text  # enqueue에 넘길 최신값 반영
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"failed to update segment: {exc}"
        ) from exc

    # SQS: segment_tts 잡 enqueue
    job = await start_segment_tts_job(
        db,
        project=project,
        segment_index=int(seg.get("segment_index") or 0),
        segment=seg,
        text=body.text,
    )

    # 응답
    seg_id_resp = (
        str(seg.get("segment_id"))
        if seg.get("segment_id") is not None
        else str(seg["_id"])
    )
    return RetranslateResponse(
        job_id=job.job_id,
        segment_id=seg_id_resp,
        segment_index=int(seg.get("segment_index") or 0),
        status=job.status,  # 보통 'queued'
    )
