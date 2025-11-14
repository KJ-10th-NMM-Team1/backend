from datetime import datetime
from typing import Any, Dict, List, Annotated, Optional
from pydantic import BaseModel, Field, BeforeValidator
from bson import ObjectId

# 1. MongoDB ObjectId를 위한 Pydantic 헬퍼 클래스
PyObjectId = Annotated[
    str,  # 👈 최종 변환될 타입은 'str'입니다.
    BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v),
]


class DetectingIssue(BaseModel):
    issue_id: PyObjectId
    editor_id: PyObjectId | None = None  # 👈 Optional
    issue_context: str | None = None  # 👈 service.py에서 $lookup으로 추가한 필드

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True  # PyObjectId 같은 커스텀 타입 허용
        json_encoders = {ObjectId: str}  # JSON 반환 시 ObjectId를 문자열로 변환


class ResponseSegment(BaseModel):
    project_id: PyObjectId = Field(alias="_id")  # 👈 service.py에서 주입
    segment_id: PyObjectId

    # --- Optional Fields ---
    segment_text: str
    score: float
    editor_id: PyObjectId
    translate_context: str
    sub_langth: float

    # --- Required Fields (시간 정보는 필수라고 가정) ---
    start_point: float
    end_point: float
    seg_id: int
    seg_txt: str
    start: float
    end: float
    length: float
    editor: str | None = None
    trans_txt: str | None = None
    # assets: List[]
    source_key: str | None = None
    bgm_key: str | None = None
    tts_key: str | None = None
    mix_key: str | None = None
    video_key: str | None = None

    # DetectingIssue 모델의 리스트를 임베딩
    # issues: List[DetectingIssue] = Field(default_factory=list)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        extra = "allow"


class RequestSegment(BaseModel):
    project_id: PyObjectId = Field(alias="_id")  # 👈 service.py에서 주입
    segment_id: PyObjectId

    # --- Optional Fields ---
    segment_text: str
    score: float
    editor_id: PyObjectId
    translate_context: str
    sub_langth: float

    # --- Required Fields (시간 정보는 필수라고 가정) ---
    start_point: float
    end_point: float
    seg_id: int
    seg_txt: str
    start: float
    end: float
    length: float
    editor: str
    trans_txt: str
    # assets: List[]
    source_key: str | None = None
    bgm_key: str | None = None
    tts_key: str | None = None
    mix_key: str | None = None
    video_key: str | None = None

    # DetectingIssue 모델의 리스트를 임베딩
    # issues: List[DetectingIssue] = Field(default_factory=list)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class SegmentRetranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    editor_id: PyObjectId | None = None


class SegmentRetranslateResponse(BaseModel):
    job_id: PyObjectId
    segment_id: PyObjectId
    segment_index: int
    status: str


class TranslateSegmentRequest(BaseModel):
    """세그먼트 번역 요청 모델"""

    target_lang: str
    src_lang: Optional[str] = None
    source_text: Optional[str] = None  # 프론트엔드에서 수정한 source_text
