from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class PipelineStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW = "review"


class PipelineStage(BaseModel):
    id: str
    status: PipelineStatus
    progress: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ProjectPipeline(BaseModel):
    project_id: str
    stages: List[PipelineStage]
    current_stage: str
    overall_progress: int


class PipelineUpdate(BaseModel):
    project_id: str
    stage_id: str
    status: PipelineStatus
    progress: Optional[int] = None
    error: Optional[str] = None
