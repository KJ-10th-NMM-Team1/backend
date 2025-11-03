from fastapi import APIRouter

from ..deps import DbDep
from .models import JobRead, JobUpdateStatus
from .service import get_job, update_job_status
from ..pipeline.service import update_pipeline_stage
from ..pipeline.models import PipelineUpdate, PipelineStatus
from ..translate.service import suggestion_by_project

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
async def read_job(job_id: str, db: DbDep) -> JobRead:
    return await get_job(db, job_id)


@router.post("/{job_id}/status", response_model=JobRead)
async def set_job_status(job_id: str, payload: JobUpdateStatus, db: DbDep) -> JobRead:
    # job 상태 업데이트
    result = await update_job_status(db, job_id, payload)

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
        )
    elif stage == "tts_prepare":  # mt 완료
        update_payload.update(
            stage_id="tts",
            progress=0,
        )
        # project의 세그먼트들에 이슈생성
        await suggestion_by_project(db, project_id)

    elif stage == "completed":  # tts 완료
        update_payload.update(
            stage_id="tts",
            status=PipelineStatus.COMPLETED,
            progress=100,
        )

    await update_pipeline_stage(db, PipelineUpdate(**update_payload))
    return result
