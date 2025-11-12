import logging
from app.api.jobs.service import start_job, start_jobs_for_targets
from app.api.pipeline.models import PipelineStatus, PipelineUpdate
from app.api.pipeline.service import update_pipeline_stage
from app.api.project.models import ProjectUpdate, ProjectThumbnail
from app.api.project.service import ProjectService
from app.config.db import make_db
from app.utils.job_utils import process_project_jobs

logger = logging.getLogger(__name__)

# 워커 전용 Mongo 클라이언트 (API와 분리)
worker_db = make_db()
project_service = ProjectService(worker_db)


async def finalize_ingest(
    project_id: str,
    object_key: str,
    thumbnail: ProjectThumbnail | None = None,
    duration_seconds: int | None = None,
) -> None:
    update_payload = ProjectUpdate(
        project_id=project_id,
        status="uploaded",
        video_source=object_key,
        thumbnail=thumbnail,
        duration_seconds=duration_seconds,
    )
    project = await project_service.update_project(payload=update_payload)

    # 공통 job 처리 로직 사용
    await process_project_jobs(
        project=project,
        project_id=project_id,
        project_service=project_service,
        start_job=start_job,
        start_jobs_for_targets=start_jobs_for_targets,
        db=worker_db,
        context="finalize_ingest"
    )

    # pipeline -> project_target 으로 변경 (이미 start_jobs_for_targets에서 처리됨)
