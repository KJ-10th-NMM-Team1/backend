"""
프로젝트 진행도 이벤트 디스패처
"""
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import asyncio

from .models import (
    ProgressEvent,
    ProgressEventType,
    TaskStatus,
    get_progress_for_stage
)

logger = logging.getLogger(__name__)


async def broadcast_progress_event(
    event_type: ProgressEventType,
    project_id: str,
    target_lang: Optional[str] = None,
    status: TaskStatus = TaskStatus.PROCESSING,
    progress: Optional[int] = None,
    stage: Optional[str] = None,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    project_title: Optional[str] = None,
):
    """
    진행도 이벤트를 브로드캐스트

    Args:
        event_type: 이벤트 타입
        project_id: 프로젝트 ID
        target_lang: 타겟 언어 코드 (선택)
        status: 작업 상태
        progress: 진행도 (0-100)
        stage: 현재 단계
        message: 메시지
        metadata: 추가 메타데이터
        project_title: 프로젝트 제목 (선택)
    """
    from .router import global_event_channels, project_event_channels

    # stage에서 진행도와 표시 이름 추출
    stage_name = None
    if stage and not progress:
        progress, stage_name = get_progress_for_stage(stage)

    # 이벤트 데이터 구성
    event_data = {
        "eventType": event_type.value,
        "projectId": project_id,
        "status": status.value,
        "progress": progress or 0,
        "timestamp": datetime.now().isoformat() + "Z",
    }

    if project_title:
        event_data["projectTitle"] = project_title
    if target_lang:
        event_data["targetLang"] = target_lang
    if stage:
        event_data["stage"] = stage
    if stage_name:
        event_data["stageName"] = stage_name
    if message:
        event_data["message"] = message
    if metadata:
        event_data["metadata"] = metadata

    # 이벤트 객체
    event = {
        "event": event_type.value,
        "data": event_data
    }

    # 로그
    logger.info(
        f"Broadcasting {event_type.value} for project {project_id}"
        f"{f' (lang: {target_lang})' if target_lang else ''}: "
        f"status={status.value}, progress={progress}%, stage={stage}"
    )

    # 1. 프로젝트별 구독자에게 전송
    project_listeners = list(project_event_channels.get(project_id, set()))
    dead_project_queues = []
    for queue in project_listeners:
        try:
            # 큐가 가득 차면 즉시 실패 (죽은 연결로 간주)
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"Queue full for project listener, marking as dead")
            dead_project_queues.append(queue)
        except Exception as e:
            logger.error(f"Failed to send event to project listener: {e}")
            dead_project_queues.append(queue)

    # 죽은 큐 제거
    for dead_queue in dead_project_queues:
        project_event_channels.get(project_id, set()).discard(dead_queue)

    # 2. 글로벌 구독자에게 전송
    global_listeners = list(global_event_channels)
    dead_global_queues = []
    for queue in global_listeners:
        try:
            # 큐가 가득 차면 즉시 실패 (죽은 연결로 간주)
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"Queue full for global listener, marking as dead")
            dead_global_queues.append(queue)
        except Exception as e:
            logger.error(f"Failed to send event to global listener: {e}")
            dead_global_queues.append(queue)

    # 죽은 큐 제거
    for dead_queue in dead_global_queues:
        global_event_channels.discard(dead_queue)

    logger.debug(
        f"Event sent to {len(project_listeners) - len(dead_project_queues)} project listeners "
        f"and {len(global_listeners) - len(dead_global_queues)} global listeners. "
        f"Removed {len(dead_project_queues) + len(dead_global_queues)} dead connections"
    )


async def dispatch_project_progress(
    project_id: str,
    progress: int,
    message: Optional[str] = None,
    project_title: Optional[str] = None,
):
    """
    프로젝트 전체 진행도 업데이트

    Args:
        project_id: 프로젝트 ID
        progress: 전체 진행도 (0-100)
        message: 메시지
        project_title: 프로젝트 제목
    """
    await broadcast_progress_event(
        event_type=ProgressEventType.PROJECT_PROGRESS,
        project_id=project_id,
        status=TaskStatus.PROCESSING if progress < 100 else TaskStatus.COMPLETED,
        progress=progress,
        message=message,
        project_title=project_title,
    )


async def dispatch_target_progress(
    project_id: str,
    target_lang: str,
    stage: str,
    status: Optional[TaskStatus] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db = None,  # DB 인스턴스 (전체 진행도 계산용)
    project_title: Optional[str] = None,
):
    """
    타겟 언어별 진행도 업데이트

    타겟 언어 진행도 이벤트를 발송하고,
    프로젝트 전체 진행도도 자동으로 계산하여 발송합니다.

    Args:
        project_id: 프로젝트 ID
        target_lang: 타겟 언어 코드
        stage: 현재 단계
        status: 작업 상태 (기본값: PROCESSING)
        progress: 진행도 (stage에서 자동 계산 가능)
        message: 메시지
        metadata: 추가 메타데이터
        db: 데이터베이스 인스턴스 (전체 진행도 계산용)
        project_title: 프로젝트 제목
    """
    # stage에 따른 기본 상태 설정
    if not status:
        if stage == "done":
            status = TaskStatus.COMPLETED
        elif stage == "failed":
            status = TaskStatus.FAILED
        else:
            status = TaskStatus.PROCESSING

    # 1. 타겟 언어별 진행도 이벤트 발송
    await broadcast_progress_event(
        event_type=ProgressEventType.TARGET_PROGRESS,
        project_id=project_id,
        target_lang=target_lang,
        status=status,
        progress=progress,
        stage=stage,
        message=message,
        metadata=metadata,
        project_title=project_title,
    )

    # 2. 프로젝트 전체 진행도 계산 및 발송
    if db is not None:
        try:
            from .service import calculate_project_overall_progress

            overall_progress = await calculate_project_overall_progress(db, project_id)

            # 전체 진행도 이벤트 발송
            await dispatch_project_progress(
                project_id=project_id,
                progress=overall_progress,
                message=f"전체 진행도: {overall_progress}%",
                project_title=project_title,
            )

        except Exception as exc:
            logger.error(f"Failed to calculate/dispatch overall progress: {exc}")


async def dispatch_stage_update(
    project_id: str,
    target_lang: Optional[str],
    stage: str,
    message: Optional[str] = None,
):
    """
    작업 단계 변경 이벤트

    Args:
        project_id: 프로젝트 ID
        target_lang: 타겟 언어 코드
        stage: 새로운 단계
        message: 메시지
    """
    await broadcast_progress_event(
        event_type=ProgressEventType.STAGE_UPDATE,
        project_id=project_id,
        target_lang=target_lang,
        status=TaskStatus.PROCESSING,
        stage=stage,
        message=message,
    )


async def dispatch_task_completed(
    project_id: str,
    target_lang: str,
    message: Optional[str] = None,
    result_key: Optional[str] = None,
):
    """
    작업 완료 이벤트

    Args:
        project_id: 프로젝트 ID
        target_lang: 타겟 언어 코드
        message: 완료 메시지
        result_key: 결과 파일 키
    """
    metadata = {"resultKey": result_key} if result_key else None

    await broadcast_progress_event(
        event_type=ProgressEventType.TASK_COMPLETED,
        project_id=project_id,
        target_lang=target_lang,
        status=TaskStatus.COMPLETED,
        progress=100,
        message=message or f"{target_lang} 작업이 완료되었습니다",
        metadata=metadata,
    )


async def dispatch_task_failed(
    project_id: str,
    target_lang: str,
    error: str,
    stage: Optional[str] = None,
):
    """
    작업 실패 이벤트

    Args:
        project_id: 프로젝트 ID
        target_lang: 타겟 언어 코드
        error: 에러 메시지
        stage: 실패한 단계
    """
    await broadcast_progress_event(
        event_type=ProgressEventType.TASK_FAILED,
        project_id=project_id,
        target_lang=target_lang,
        status=TaskStatus.FAILED,
        progress=0,
        stage=stage,
        message=f"작업 실패: {error}",
        metadata={"error": error},
    )