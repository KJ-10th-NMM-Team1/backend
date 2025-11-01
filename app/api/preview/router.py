# app/api/routes/upload.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from uuid import uuid4
from datetime import datetime
import os
from .model import PreviewCreateBody, PreviewCreateResponse, PreviewGetResponse, PreviewRecord, PreviewStatus


preview_router = APIRouter(prefix="/preview", tags=["preview"])

PREVIEWS: Dict[str, PreviewRecord] = {}

@preview_router.post(
        "/projects/{project_id}/languages/{lang_code}/segments/{segment_id}/preview",
        response_model=PreviewCreateResponse,
)
async def create_segment_preview(body: PreviewCreateBody):
    # 워커 미구현: 즉시 완료로 응답 (나중에 processing + queue 로 교체)
    video_url, audio_url = sample_urls()
    rec = PreviewRecord(
        id=str(uuid4()),
        project_id=body.project_id,
        language_code=body.lang_code,
        segment_id=body.segment_id,
        status="completed",
        video_url=video_url,
        audio_url=audio_url,
        updated_at=now_iso(),
    )
    PREVIEWS[rec.id] = rec
    return PreviewCreateResponse(
        previewId=rec.id,
        status=rec.status,
        videoUrl=rec.video_url,
        audioUrl=rec.audio_url,
        updatedAt=rec.updated_at,
    )

@preview_router.get("/preview/{preview_id}", response_model=PreviewGetResponse)
async def get_preview(preview_id: str):
    rec = PREVIEWS.get(preview_id)
    if not rec:
        raise HTTPException(status_code=404, detail="preview not found")
    return PreviewGetResponse(
        status=rec.status,
        videoUrl=rec.video_url,
        audioUrl=rec.audio_url,
        updatedAt=rec.updated_at,
    )



def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def sample_urls():
    # 환경변수 있으면 우선 사용 (예: presigned GET)
    v = os.getenv("SAMPLE_VIDEO_URL") or "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
    a = os.getenv("SAMPLE_AUDIO_URL") or "https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3"
    return v, a
