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
    result = await update_job_status(db, job_id, payload)
    
    # 워커에서 보낸 metadata의 stage 정보로 파이프라인 업데이트
    if payload.metadata and "stage" in payload.metadata:
        stage = payload.metadata["stage"]
        project_id = result.project_id
        
        # stage별 파이프라인 업데이트
        if stage == "downloaded":
            await update_pipeline_stage(
                db,
                PipelineUpdate(
                    project_id=project_id,
                    stage_id="stt",
                    status=PipelineStatus.PROCESSING,
                    progress=0,
                ),
            )
        elif stage == "tts_prepare":
            await update_pipeline_stage(
                db,
                PipelineUpdate(
                    project_id=project_id,
                    stage_id="tts",
                    status=PipelineStatus.PROCESSING,
                    progress=0,
                ),
            )
        elif stage == "completed":
            await update_pipeline_stage(
                db,
                PipelineUpdate(
                    project_id=project_id,
                    stage_id="tts",
                    status=PipelineStatus.COMPLETED,
                    progress=100,
                ),
            )
    
    return result
