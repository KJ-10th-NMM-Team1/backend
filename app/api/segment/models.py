"""
Segment 관련 모델들
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Annotated
from pydantic import BeforeValidator


PyObjectId = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]


class SegmentTranslationCreate(BaseModel):
    """segment_translations 컬렉션 생성 모델"""
    segment_id: str
    language_code: str
    target_text: str
    segment_audio_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SegmentTranslationOut(BaseModel):
    """segment_translations 출력 모델"""
    id: PyObjectId = Field(validation_alias="_id")
    segment_id: str
    language_code: str
    target_text: str
    segment_audio_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime