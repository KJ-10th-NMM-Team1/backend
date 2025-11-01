from pydantic import BaseModel
from typing import Optional, Literal, Dict


PreviewStatus = Literal["pending", "processing", "completed", "failed"]

class PreviewCreateBody(BaseModel):
    text: str
    project_id: str
    lang_code: str
    segment_id: str

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