"""
프로젝트 진행도 글로벌 이벤트 엔드포인트
"""

from fastapi import APIRouter, Request, Query
from sse_starlette.sse import EventSourceResponse
from typing import Optional, Set
import asyncio
import json
from datetime import datetime
import logging
from collections import defaultdict

from .models import ProgressEventType

progress_router = APIRouter(prefix="/progress", tags=["Progress"])
logger = logging.getLogger(__name__)

# 글로벌 이벤트 채널 (모든 클라이언트가 구독)
# 각 Queue는 하나의 클라이언트 연결을 나타냄
global_event_channels: Set[asyncio.Queue] = set()

# 프로젝트별 이벤트 채널 (특정 프로젝트만 구독)
# key: project_id, value: Set[Queue]
project_event_channels = defaultdict(set)

# 통계 정보
stats = {
    "total_connections": 0,
    "active_connections": 0,
    "total_events_sent": 0,
}


@progress_router.get("/events")
async def progress_events(
    request: Request,
    project_id: Optional[str] = Query(
        None, description="특정 프로젝트만 구독 (없으면 전체)"
    ),
):
    """
    프로젝트 진행도 이벤트를 SSE로 스트리밍

    Query Parameters:
    - project_id: 특정 프로젝트만 구독하려면 지정 (선택사항)

    Event Types:
    - project-progress: 프로젝트 전체 진행도 업데이트
    - target-progress: 타겟 언어별 진행도 업데이트
    - stage-update: 작업 단계 변경
    - task-completed: 작업 완료
    - task-failed: 작업 실패
    - heartbeat: 연결 유지 확인

    Event Data Format:
    {
        "eventType": "target-progress",
        "projectId": "project_123",
        "targetLang": "ko",
        "status": "processing",
        "progress": 35,
        "stage": "translation_completed",
        "stageName": "번역 완료",
        "message": "번역이 완료되었습니다",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    queue = asyncio.Queue(maxsize=100)  # 큐 크기 제한 추가

    # 구독 설정
    if project_id:
        # 특정 프로젝트만 구독
        project_event_channels[project_id].add(queue)
        logger.info(
            f"New SSE connection for project {project_id}. "
            f"Project listeners: {len(project_event_channels[project_id])}"
        )
    else:
        # 전체 이벤트 구독
        global_event_channels.add(queue)
        logger.info(
            f"New global SSE connection. Total global listeners: {len(global_event_channels)}"
        )

    # 통계 업데이트
    stats["total_connections"] += 1
    stats["active_connections"] += 1

    async def event_generator():
        try:
            # 연결 즉시 초기 상태 전송
            yield {
                "event": "connected",
                "data": json.dumps(
                    {
                        "message": f"Connected to progress events"
                        + (f" for project {project_id}" if project_id else " (global)"),
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
            }

            # 하트비트 관련 변수
            heartbeat_interval = 30  # 30초마다 하트비트
            last_heartbeat = 0

            while True:
                # 클라이언트 연결 해제 확인
                if await request.is_disconnected():
                    logger.info(
                        f"Client disconnected from progress events"
                        f"{f' for project {project_id}' if project_id else ' (global)'}"
                    )
                    break

                try:
                    # 큐에서 이벤트 가져오기 (1초 타임아웃으로 단축)
                    event_data = await asyncio.wait_for(queue.get(), timeout=1.0)

                    # 연결 해제 재확인 (이벤트 전송 전)
                    if await request.is_disconnected():
                        logger.info("Client disconnected before sending event")
                        break

                    # 이벤트 타입과 데이터 추출
                    event_type = event_data.get("event", "message")
                    data = event_data.get("data", {})

                    # 통계 업데이트
                    stats["total_events_sent"] += 1

                    # SSE 형식으로 전송
                    yield {
                        "event": event_type,
                        "data": json.dumps(data, ensure_ascii=False, default=str),
                    }

                    last_heartbeat = 0  # 데이터 전송 시 하트비트 카운터 리셋

                except asyncio.TimeoutError:
                    # 타임아웃 시 하트비트 전송
                    last_heartbeat += 1  # 1초씩 증가
                    if last_heartbeat >= heartbeat_interval:
                        yield {
                            "event": str(ProgressEventType.HEARTBEAT),
                            "data": json.dumps(
                                {
                                    "timestamp": datetime.now().isoformat(),
                                    "stats": {
                                        "activeConnections": stats[
                                            "active_connections"
                                        ],
                                        "totalEventsSent": stats["total_events_sent"],
                                    },
                                }
                            ),
                        }
                        last_heartbeat = 0

        except asyncio.CancelledError:
            logger.info(
                f"Progress events stream cancelled"
                f"{f' for project {project_id}' if project_id else ' (global)'}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Error in progress events stream"
                f"{f' for project {project_id}' if project_id else ' (global)'}: {e}"
            )
            # 에러 이벤트 전송
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": str(e), "timestamp": datetime.now().isoformat()}
                ),
            }
        finally:
            # 정리 작업
            stats["active_connections"] -= 1

            if project_id:
                project_event_channels[project_id].discard(queue)
                # 채널에 리스너가 없으면 삭제하여 메모리 누수 방지
                if not project_event_channels[project_id]:
                    del project_event_channels[project_id]
                logger.info(
                    f"Cleaned up connection for project {project_id}. "
                    f"Remaining project listeners: {len(project_event_channels.get(project_id, set()))}"
                )
            else:
                global_event_channels.discard(queue)
                logger.info(
                    f"Cleaned up global connection. "
                    f"Remaining global listeners: {len(global_event_channels)}"
                )

    return EventSourceResponse(
        event_generator(),
        ping=15,  # 15초마다 ping 전송하여 연결 유지 및 끊김 감지
    )


@progress_router.get("/stats")
async def get_progress_stats():
    """
    진행도 이벤트 시스템 통계 조회
    """
    return {
        "total_connections": stats["total_connections"],
        "active_connections": stats["active_connections"],
        "global_listeners": len(global_event_channels),
        "project_listeners": sum(
            len(listeners) for listeners in project_event_channels.values()
        ),
        "monitored_projects": list(project_event_channels.keys()),
        "total_events_sent": stats["total_events_sent"],
    }


@progress_router.get("/{project_id}")
async def get_project_progress(project_id: str, db):
    """
    프로젝트 진행도 현재 상태 조회

    Returns:
        {
            "overall_progress": 60,
            "target_progresses": {
                "ko": {"progress": 100, "status": "completed"},
                "en": {"progress": 50, "status": "processing"},
                "ja": {"progress": 30, "status": "processing"}
            },
            "completed_count": 1,
            "total_count": 3
        }
    """
    from .service import get_project_progress_summary

    return await get_project_progress_summary(db, project_id)
