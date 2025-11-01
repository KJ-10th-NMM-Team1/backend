# backend/app/router/editor_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal, Dict
from datetime import datetime
from uuid import uuid4
import os

PreviewStatus = Literal["pending", "processing", "completed", "failed"]

class PreviewCreateBody(BaseModel):
    text: str

class PreviewRecord(BaseModel):
    id: str
    project_id: str
    language_code: str
    segment_id: str
    status: PreviewStatus
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    updated_at: str

class PreviewGetResponse(BaseModel):
    status: PreviewStatus
    videoUrl: Optional[str] = None
    audioUrl: Optional[str] = None
    updatedAt: Optional[str] = None

class PreviewCreateResponse(BaseModel):
    previewId: Optional[str] = None
    status: PreviewStatus
    videoUrl: Optional[str] = None
    audioUrl: Optional[str] = None
    updatedAt: Optional[str] = None

editor_router = APIRouter()

# 아주 단순한 인메모리 저장 (실서버에서는 Redis/DB 권장)
PREVIEWS: Dict[str, PreviewRecord] = {}

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def sample_urls():
    # 환경변수 있으면 우선 사용 (예: presigned GET)
    v = os.getenv("SAMPLE_VIDEO_URL") or "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
    a = os.getenv("SAMPLE_AUDIO_URL") or "https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3"
    return v, a

@editor_router.post(
    "/projects/{project_id}/languages/{lang_code}/segments/{segment_id}/preview",
    response_model=PreviewCreateResponse,
)
async def create_segment_preview(project_id: str, lang_code: str, segment_id: str, body: PreviewCreateBody):
    # 워커 미구현: 즉시 완료로 응답 (나중에 processing + queue 로 교체)
    video_url, audio_url = sample_urls()
    rec = PreviewRecord(
        id=str(uuid4()),
        project_id=project_id,
        language_code=lang_code,
        segment_id=segment_id,
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

@editor_router.get("/preview/{preview_id}", response_model=PreviewGetResponse)
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
