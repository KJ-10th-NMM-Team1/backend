from fastapi import APIRouter
from datetime import datetime

from ..deps import DbDep
from .models import JobRead, JobUpdateStatus
from .service import get_job, update_job_status
from ..pipeline.service import update_pipeline_stage
from ..pipeline.models import PipelineUpdate, PipelineStatus
from ..translate.service import suggestion_by_project
from app.api.pipeline.router import project_channels
from ..segment.segment_service import SegmentService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
async def read_job(job_id: str, db: DbDep) -> JobRead:
    return await get_job(db, job_id)


async def dispatch_pipeline(project_id: str, update_payload):
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


async def update_pipeline(db, project_id, payload):
    # 파이프라인 디비 수정
    await update_pipeline_stage(db, PipelineUpdate(**payload))
    # 파이프라인 SSE 큐에 추가
    await dispatch_pipeline(project_id, payload)


async def pretts_complete_processing(db, project_id, segments):
    # 세그먼트 Insert_many
    segment_service = SegmentService(db)
    await segment_service.insert_segments_from_metadata(project_id, segments)

    # rag processing - 50
    rag_payload = {
        "project_id": project_id,
        "stage_id": "rag",
        "status": PipelineStatus.PROCESSING,
        "progress": 50,
    }
    await update_pipeline(db, project_id, rag_payload)

    # rag 실행
    try:
        # project_id의 세그먼트에 대해 이슈생성
        await suggestion_by_project(db, project_id)
    except Exception:
        rag_payload["status"] = PipelineStatus.FAILED
        rag_payload["progress"] = 0
        await update_pipeline(db, project_id, rag_payload)
        raise
    else:
        rag_payload["status"] = PipelineStatus.COMPLETED
        rag_payload["progress"] = 100
    return rag_payload


@router.post("/{job_id}/status", response_model=JobRead)
async def set_job_status(job_id: str, payload: JobUpdateStatus, db: DbDep) -> JobRead:
    # job 상태 업데이트
    result = await update_job_status(db, job_id, payload)

    metadata = None
    if payload.metadata is not None:
        if payload.metadata is not None:
            metadata = (
                payload.metadata.model_dump()
                if hasattr(payload.metadata, "model_dump")
                else payload.metadata
            )

    # state 없을 때 리턴
    if not metadata or "stage" not in metadata:
        return result

    stage = metadata["stage"]
    project_id = result.project_id
    update_payload: dict[str, object] = {
        "project_id": project_id,
        "status": PipelineStatus.PROCESSING,
    }

    # stage별, project 파이프라인 업데이트
    if stage == "downloaded":  # s3에서 불러오기 완료 (stt 시작)
        update_payload.update(
            stage_id="stt",
            progress=0,
        )
    elif stage == "stt_completed":  # stt 완료
        update_payload.update(
            stage_id="stt",
            progress=100,
            status=PipelineStatus.COMPLETED,
        )

    elif stage == "mt_prepare":
        update_payload.update(
            stage_id="mt",
            progress=0,
        )
    elif stage == "mt_completed":  # mt 완료
        update_payload.update(
            stage_id="mt",
            progress=100,
            status=PipelineStatus.COMPLETED,
        )
        await update_pipeline(db, project_id, update_payload)

        update_payload = {
            "project_id": project_id,
            "stage_id": "rag",
            "status": PipelineStatus.PROCESSING,
            "progress": 0,
        }
    elif stage == "tts_completed":  # pre-tts 완료
        segments = metadata.get("segments", [])
        update_payload = await pretts_complete_processing(db, project_id, segments)
    elif stage == "tts2_prepare":  # tts2: 최종 tts
        update_payload.update(
            stage_id="tts",
            progress=0,
        )
    elif stage == "tts2_completed":
        update_payload.update(
            stage_id="tts",
            progress=100,
            status=PipelineStatus.COMPLETED,
        )

    if update_payload.get("stage_id"):
        await update_pipeline(db, project_id, update_payload)

    return result
