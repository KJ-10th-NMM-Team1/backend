from app.api.jobs.service import start_job
from app.api.pipeline.models import PipelineStatus, PipelineUpdate
from app.api.pipeline.service import update_pipeline_stage
from app.api.project.models import ProjectUpdate, ProjectThumbnail
from app.api.project.service import ProjectService
from app.config.db import make_db

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
    await start_job(project, worker_db)

    # pipeline -> project_target 으로 변경
    # await update_pipeline_stage(
    #     worker_db,
    #     PipelineUpdate(
    #         project_id=project_id,
    #         stage_id="upload",
    #         status=PipelineStatus.COMPLETED,
    #         progress=100,
    #     ),
    # )
