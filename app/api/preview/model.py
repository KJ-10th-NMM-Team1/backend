from pydantic import BaseModel
from typing import Literal, Optional


PreviewStatus = Literal["pending", "processing", "completed", "failed"]


class PreviewCreateBody(BaseModel):
    text: str
    project_id: Optional[str] = None
    lang_code: Optional[str] = None
    segment_id: Optional[str] = None


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
