from datetime import datetime
from pydantic import BaseModel


class ProjectPublic(BaseModel):
    project_id: str
    title: str
    progress: int
    status: str
    video_source: str | None
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    filename: str


class ProjectUpdate(BaseModel):
    project_id: str
    status: str
    video_source: str | None = None
