from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ProjectPublic(BaseModel):
    project_id: str
    title: str
    progress: int
    status: str
    video_source: str | None
    created_at: datetime
    updated_at: datetime
    segment_assets_prefix: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None


class ProjectCreate(BaseModel):
    filename: str


class ProjectUpdate(BaseModel):
    project_id: str
    status: str
    video_source: str | None = None
    segment_assets_prefix: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None
