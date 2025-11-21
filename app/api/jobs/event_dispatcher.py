"""
Jobs API SSE 이벤트 발송 로직
"""

from datetime import datetime
from typing import Optional
from ..deps import DbDep
from ..pipeline.service import update_pipeline_stage
from ..pipeline.models import PipelineUpdate, PipelineStatus
from ..project.models import ProjectTargetStatus


async def dispatch_pipeline(project_id: str, update_payload):
    """파이프라인 상태 변경을 SSE로 브로드캐스트"""
    from ..pipeline.router import project_channels

    listeners = project_channels.get(project_id, set())
    event = {
        "project_id": project_id,
        "stage": update_payload.get("stage_id"),
        "status": update_payload.get("status", PipelineStatus.PROCESSING).value,
        "progress": update_payload.get("progress"),
        "timestamp": datetime.now().isoformat() + "Z",
    }
    for queue in list(listeners):
        await queue.put(event)


async def dispatch_target_update(
    project_id: str,
    language_code: str,
    target_status: ProjectTargetStatus,
    progress: int,
):
    """project_target 업데이트를 SSE로 브로드캐스트"""
    from ..pipeline.router import project_channels

    listeners = project_channels.get(project_id, set())
    event = {
        "project_id": project_id,
        "type": "target_update",
        "language_code": language_code,
        "status": target_status.value,
        "progress": progress,
        "timestamp": datetime.now().isoformat() + "Z",
    }
    for queue in list(listeners):
        await queue.put(event)


async def update_pipeline(db: DbDep, project_id: str, payload: dict):
    """파이프라인 디비 수정 및 SSE 이벤트 발송"""
    # 파이프라인 디비 수정
    await update_pipeline_stage(db, PipelineUpdate(**payload))
    # 파이프라인 SSE 큐에 추가
    await dispatch_pipeline(project_id, payload)
