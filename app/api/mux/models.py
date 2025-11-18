from pydantic import BaseModel
from typing import Optional, List


class SegmentInfo(BaseModel):
    """세그먼트 정보"""

    segment_id: Optional[str] = None
    start: float  # 시작 시간 (초)
    end: float  # 끝 시간 (초)
    audio_file: str  # 오디오 파일 S3 키 (예: "projects/xxx/interim/job_id/tts/segment_0000.wav")
    speaker: Optional[str] = None


class MuxRequest(BaseModel):
    """Mux 작업 요청 모델"""

    project_id: str
    video_key: str  # 원본 비디오 S3 키
    background_audio_key: str  # 배경음 S3 키
    segments: List[SegmentInfo]  # 세그먼트 정보 배열
    output_prefix: Optional[str] = None  # 출력 경로 prefix


class MuxResponse(BaseModel):
    """Mux 작업 응답 모델"""

    success: bool
    result_key: Optional[str] = None  # 최종 비디오 S3 키
    audio_key: Optional[str] = None  # 최종 오디오 S3 키
    message: Optional[str] = None
