from datetime import datetime
from typing import Any, Dict, List, Optional, Annotated
from enum import Enum
from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, Field

PyObjectId = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]


class ProjectCreate(BaseModel):
    title: str
    owner_id: str
    sourceType: str  # 'file' | 'youtube'
    youtubeUrl: Optional[str] = None
    fileName: Optional[str] = None
    fileSize: Optional[int] = None
    speakerCount: int
    detectAutomatically: bool
    sourceLanguage: Optional[str] = None
    targetLanguages: List[str]


class ProjectThumbnail(BaseModel):
    kind: str  # "s3" or "external"
    key: str | None = None
    url: str | None = None


class ProjectBase(BaseModel):
    owner_id: str
    title: str
    status: str  # uploading | uploaded | processing | completed | failed
    source_type: str  # 'file' | 'youtube'
    video_source: str | None = None
    source_language: Optional[str] = None
    created_at: datetime
    duration_seconds: Optional[int] = None


class ProjectPublic(ProjectBase):
    project_id: str
    thumbnail: ProjectThumbnail | None = None
    glosary_id: Optional[str] = None
    # segments: Optional[List[Dict[str, Any]]] = None


class ProjectCreateResponse(BaseModel):
    project_id: str


class ProjectUpdate(BaseModel):
    project_id: str
    status: str | None = None
    video_source: str | None = None
    thumbnail: ProjectThumbnail | None = None
    segment_assets_prefix: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None
    owner_id: str | None = None
    source_language: Optional[str] = None
    title: Optional[str] = None
    duration_seconds: Optional[int] = None


class ProjectTargetStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectTargetCreate(BaseModel):
    project_id: str
    language_code: str
    status: ProjectTargetStatus = ProjectTargetStatus.PENDING
    progress: int = 0


class ProjectTarget(BaseModel):
    target_id: PyObjectId = Field(validation_alias="_id")
    project_id: str
    language_code: str
    status: ProjectTargetStatus
    progress: int

class ProjectOut(BaseModel):
    id: PyObjectId = Field(validation_alias="_id")
    title: str
    status: str
    video_source: str | None
    thumbnail: ProjectThumbnail | None = None
    created_at: datetime
    duration_seconds: Optional[int] | None = None
    # segment_assets_prefix: Optional[str] = None
    # segments: Optional[List[Dict[str, Any]]] = None
    # owner_id: str
    issue_count: int = 0  # 새로 집계한 값을 넣기 위한 필드
    targets: list[ProjectTarget] = Field(default_factory=list)