"""
Issues 관련 모델들
"""
from datetime import datetime
from typing import Optional, Annotated
from enum import Enum
from pydantic import BaseModel, Field, BeforeValidator
from bson import ObjectId


PyObjectId = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]


class IssueType(str, Enum):
    """이슈 타입"""
    STT_QUALITY = "stt_quality"  # STT 품질 이슈
    TTS_QUALITY = "tts_quality"  # TTS 품질 이슈
    SYNC_DURATION = "sync_duration"  # 길이 차이 이슈
    SPEAKER_IDENTIFICATION = "speaker_identification"  # 화자 식별 실패 이슈


class IssueSeverity(str, Enum):
    """이슈 심각도"""
    LOW = "low"  # 경고
    MEDIUM = "medium"  # 주의
    HIGH = "high"  # 심각


class IssueBase(BaseModel):
    """이슈 기본 모델"""
    segment_translation_id: str  # segment_translations의 _id
    project_id: str
    language_code: str
    issue_type: IssueType
    severity: IssueSeverity
    score: Optional[float] = None  # 품질 점수 (stt, tts의 경우)
    diff: Optional[float] = None  # 길이 차이 (sync의 경우)
    details: Optional[dict] = None  # 추가 정보
    resolved: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class IssueCreate(IssueBase):
    """이슈 생성 모델"""
    pass


class IssueOut(IssueBase):
    """이슈 출력 모델"""
    id: PyObjectId = Field(validation_alias="_id")


class IssueUpdate(BaseModel):
    """이슈 업데이트 모델"""
    resolved: Optional[bool] = None
    details: Optional[dict] = None
