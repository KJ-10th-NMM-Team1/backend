from pydantic import BaseModel, Field, BeforeValidator
from typing import Optional, Annotated
from bson import ObjectId
from datetime import datetime

PyObjectId = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]


class VoiceSampleCreate(BaseModel):
    """음성 샘플 생성 요청"""

    name: str = Field(..., min_length=1, description="샘플 이름")
    description: Optional[str] = Field(None, description="샘플 설명")
    is_public: bool = Field(default=False, description="공개 여부")
    file_path_wav: str = Field(..., description="S3 파일 경로 (mp3 또는 wav)")
    audio_sample_url: Optional[str] = Field(None, description="미리듣기용 음성 URL")
    prompt_text: Optional[str] = Field(None, description="STT로 추출한 프롬프트 텍스트")


class VoiceSamplePrepareUpload(BaseModel):
    """음성 샘플 업로드 준비 요청"""

    filename: str = Field(..., description="파일명")
    content_type: str = Field(
        ..., description="Content-Type (audio/mpeg, audio/wav 등)"
    )


class VoiceSampleFinishUpload(BaseModel):
    """음성 샘플 업로드 완료 요청"""

    name: str = Field(..., min_length=1, description="샘플 이름")
    description: Optional[str] = Field(None, description="샘플 설명")
    is_public: bool = Field(default=False, description="공개 여부")
    object_key: str = Field(..., description="S3에 업로드된 파일의 object_key")


class VoiceSampleUpdate(BaseModel):
    """음성 샘플 업데이터 요청"""

    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    audio_sample_url: Optional[str] = None
    prompt_text: Optional[str] = None


class VoiceSampleOut(BaseModel):
    """음성 샘플 응답"""

    sample_id: PyObjectId = Field(alias="_id")
    owner_id: PyObjectId
    name: str
    description: Optional[str] = None
    is_public: bool
    file_path_wav: str
    audio_sample_url: Optional[str] = None
    created_at: datetime
    is_favorite: bool = Field(default=False, description="현재 사용자의 즐겨찾기 여부")
    prompt_text: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class VoiceSampleListResponse(BaseModel):
    """음성 샘플 목록 응답"""

    samples: list[VoiceSampleOut]
    total: int


class TestSynthesisRequest(BaseModel):
    """테스트 합성 요청"""

    file_path_wav: str = Field(..., description="S3에 저장된 원본 wav 파일 경로")
    text: str = Field(..., min_length=1, description="합성할 텍스트")
    target_lang: str = Field(default="ko", description="대상 언어 (ko, en, ja)")


class TestSynthesisResponse(BaseModel):
    """테스트 합성 응답"""

    job_id: str = Field(..., description="작업 ID (polling용)")
    status: str = Field(default="queued", description="작업 상태")
