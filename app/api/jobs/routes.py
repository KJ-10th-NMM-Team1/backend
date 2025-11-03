from fastapi import APIRouter

from ..deps import DbDep
from .models import JobRead, JobUpdateStatus
from .service import get_job, update_job_status
from ..pipeline.service import update_pipeline_stage
from ..pipeline.models import PipelineUpdate, PipelineStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
async def read_job(job_id: str, db: DbDep) -> JobRead:
    return await get_job(db, job_id)


@router.post("/{job_id}/status", response_model=JobRead)
async def set_job_status(job_id: str, payload: JobUpdateStatus, db: DbDep) -> JobRead:
    # job 상태 업데이트
    result = await update_job_status(db, job_id, payload)

    # 워커에서 보낸 metadata의 stage 정보로 파이프라인 업데이트
    if not payload.metadata or "stage" not in payload.metadata:
        return result

    stage = payload.metadata["stage"]
    project_id = result.project_id
    update_payload: dict[str, object] = {"project_id": project_id}

    # stage별 project 파이프라인 업데이트
    if stage == "downloaded":
        update_payload.update(
            stage_id="stt",
            status=PipelineStatus.PROCESSING,
            progress=0,
        )
    elif stage == "tts_prepare":
        update_payload.update(
            stage_id="tts",
            status=PipelineStatus.PROCESSING,
            progress=0,
        )
    elif stage == "completed":
        update_payload.update(
            stage_id="tts",
            status=PipelineStatus.COMPLETED,
            progress=100,
        )

    await update_pipeline_stage(db, PipelineUpdate(**update_payload))
    return result
