from fastapi import APIRouter, HTTPException, status, Request
from typing import Any, Dict
import asyncio, json
from datetime import datetime
from sse_starlette.sse import EventSourceResponse
from collections import defaultdict
from app.api.deps import DbDep
from .service import get_pipeline_status, update_pipeline_stage
from .models import PipelineUpdate, ProjectPipeline
import logging

pipeline_router = APIRouter(prefix="/pipeline", tags=["Pipeline"])
logger = logging.getLogger(__name__)


@pipeline_router.get("/{project_id}/status", summary="파이프라인 상태 조회")
async def get_project_pipeline_status(project_id: str, db: DbDep) -> ProjectPipeline:
    """프로젝트의 현재 파이프라인 상태를 조회합니다."""
    return await get_pipeline_status(db, project_id)


@pipeline_router.post("/{project_id}/update", summary="파이프라인 단계 업데이트")
async def update_project_pipeline_stage(
    project_id: str, payload: PipelineUpdate, db: DbDep
) -> Dict[str, Any]:
    """파이프라인 단계의 상태를 업데이트합니다."""
    logger.info(f"pipline update: {project_id}")
    # payload의 project_id를 URL의 project_id로 덮어쓰기
    payload.project_id = project_id
    result = await update_pipeline_stage(db, payload)
    return {"success": result["success"]}


def _serialize_datetime(obj: Any) -> Any:
    """datetime 객체를 JSON 직렬화 가능한 문자열로 변환"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_datetime(item) for item in obj]
    return obj


project_channels = defaultdict(set)  # project_id -> events queue


@pipeline_router.get("/{project_id}/events")
async def pipeline_events(project_id: str, request: Request):
    queue = asyncio.Queue()
    project_channels[project_id].add(queue)

    async def event_generator():
        try:
            # 주기적인 하트비트를 위한 카운터
            heartbeat_interval = 30  # 30초마다 하트비트
            last_heartbeat = 0

            while True:
                # 클라이언트 연결 해제 확인
                if await request.is_disconnected():
                    logger.info(
                        f"Client disconnected from /events for project {project_id}"
                    )
                    break

                try:
                    # 타임아웃을 사용하여 queue.get() 무한 대기 방지
                    data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield {"event": "stage", "data": json.dumps(data)}
                    last_heartbeat = 0  # 데이터 전송 시 하트비트 카운터 리셋
                except asyncio.TimeoutError:
                    # 타임아웃 시 하트비트 전송 (연결 유지 확인)
                    last_heartbeat += 5
                    if last_heartbeat >= heartbeat_interval:
                        yield {
                            "event": "heartbeat",
                            "data": json.dumps(
                                {"timestamp": datetime.now().isoformat()}
                            ),
                        }
                        last_heartbeat = 0

        except asyncio.CancelledError:
            logger.info(f"Events stream cancelled for project {project_id}")
            raise
        except Exception as e:
            logger.error(f"Error in events stream for project {project_id}: {e}")
        finally:
            project_channels[project_id].discard(queue)
            # 채널에 리스너가 없으면 삭제하여 메모리 누수 방지
            if not project_channels[project_id]:
                del project_channels[project_id]
            logger.info(f"Cleaned up events connection for project {project_id}")

    return EventSourceResponse(event_generator())
