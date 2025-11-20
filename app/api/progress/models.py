"""
프로젝트 진행도 관련 모델
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal, Dict, Any
from enum import Enum


class TaskStatus(str, Enum):
    """작업 상태"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressEventType(str, Enum):
    """진행도 이벤트 타입"""

    PROJECT_PROGRESS = "project-progress"  # 프로젝트 전체 진행도
    TARGET_PROGRESS = "target-progress"  # 타겟 언어별 진행도
    STAGE_UPDATE = "stage-update"  # 단계 변경
    TASK_COMPLETED = "task-completed"  # 작업 완료
    TASK_FAILED = "task-failed"  # 작업 실패
    HEARTBEAT = "heartbeat"  # 연결 유지


class ProgressEvent(BaseModel):
    """진행도 이벤트 데이터"""

    event_type: ProgressEventType
    project_id: str
    project_title: Optional[str] = None  # 프로젝트 제목
    target_lang: Optional[str] = None
    status: TaskStatus
    progress: int  # 0-100
    stage: Optional[str] = None  # 현재 단계
    stage_name: Optional[str] = None  # 단계 이름 (표시용)
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.now()


class StageInfo(BaseModel):
    """작업 단계 정보"""

    stage_id: str
    stage_name: str
    progress_range: tuple[int, int]  # (시작%, 종료%)


# 작업 단계별 진행도 매핑
STAGE_PROGRESS_MAP = {
    # STT 관련 (0-20%)
    "starting": StageInfo(
        stage_id="starting", stage_name="작업 시작", progress_range=(0, 1)
    ),
    "asr_started": StageInfo(
        stage_id="asr_started", stage_name="음성 인식 시작", progress_range=(1, 5)
    ),
    "asr_completed": StageInfo(
        stage_id="asr_completed", stage_name="음성 인식 완료", progress_range=(5, 20)
    ),
    # 번역 관련 (20-35%)
    "translation_started": StageInfo(
        stage_id="translation_started", stage_name="번역 시작", progress_range=(20, 21)
    ),
    "translation_completed": StageInfo(
        stage_id="translation_completed",
        stage_name="번역 완료",
        progress_range=(21, 35),
    ),
    # TTS 관련 (35-70%)
    "tts_started": StageInfo(
        stage_id="tts_started", stage_name="음성 합성 시작", progress_range=(35, 36)
    ),
    "tts_completed": StageInfo(
        stage_id="tts_completed", stage_name="음성 합성 완료", progress_range=(36, 85)
    ),
    # 비디오 처리 (70-100%)
    "mux_started": StageInfo(
        stage_id="mux_started", stage_name="비디오 처리 시작", progress_range=(85, 86)
    ),
    "done": StageInfo(stage_id="done", stage_name="완료", progress_range=(86, 100)),
    # 실패
    "failed": StageInfo(stage_id="failed", stage_name="실패", progress_range=(0, 0)),
}


def get_progress_for_stage(stage: str) -> tuple[int, str]:
    """
    단계에 따른 진행도와 표시 이름을 반환

    Returns:
        (진행도%, 단계 표시 이름)
    """
    stage_info = STAGE_PROGRESS_MAP.get(stage)
    if not stage_info:
        return (0, stage)

    # 각 단계의 종료 진행도를 반환
    return (stage_info.progress_range[1], stage_info.stage_name)
