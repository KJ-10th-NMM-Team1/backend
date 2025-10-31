from datetime import datetime
from typing import List, Annotated
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator

# --- ObjectId 헬퍼 ---
PyObjectId = Annotated[
    str,
    BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]

class IssueModel(BaseModel):
    """Segment 내부의 개별 이슈 (Embeded Document)"""
    issue_id: PyObjectId
    editor_id: PyObjectId
    
    # model_config: Pydantic 설정
    model_config = ConfigDict(
        populate_by_name=True, # 별칭(alias) 사용 허용
        from_attributes=True   # ORM 객체에서도 데이터 로드 허용 (motor 등 사용 시 유용)
    )

class SegmentModel(BaseModel):
    """프로젝트 내부의 세그먼트 (Embeded Document)"""
    segment_id: PyObjectId
    segment_text: str
    score: float
    start_point: float
    end_point: float
    editor_id: PyObjectId
    translate_context: str
    sub_langth: float
    issues: List[IssueModel] # IssueModel을 리스트로 포함 (Nested)
    
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class ProjectModel(BaseModel):
    """메인 프로젝트 문서 (Collection)"""
    id: PyObjectId = Field(alias="_id") 
    
    video_source: str
    audio_source: str
    created_at: datetime
    updated_at: datetime
    editor_id: PyObjectId
    segments: List[SegmentModel] 
    
    model_config = ConfigDict(
        populate_by_name=True, # '_id' 별칭을 사용하기 위해 필수
        from_attributes=True
    )

