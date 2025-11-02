from datetime import datetime
from typing import List, Annotated
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
    start_point: float
    end_point: float

    # DetectingIssue 모델의 리스트를 임베딩
    # issues: List[DetectingIssue] = Field(default_factory=list)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


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

    # DetectingIssue 모델의 리스트를 임베딩
    issues: List[DetectingIssue] = Field(default_factory=list)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
