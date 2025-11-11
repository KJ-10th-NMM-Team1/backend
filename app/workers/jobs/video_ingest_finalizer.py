import logging
from app.api.jobs.service import start_job, start_jobs_for_targets
from app.api.pipeline.models import PipelineStatus, PipelineUpdate
from app.api.pipeline.service import update_pipeline_stage
from app.api.project.models import ProjectUpdate, ProjectThumbnail
from app.api.project.service import ProjectService
from app.config.db import make_db

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

    # 프로젝트의 타겟 언어들 가져오기
    targets = await project_service.get_targets_by_project(project_id)
    if targets:
        target_languages = [target.get("language_code") for target in targets if target.get("language_code")]
        if target_languages:
            # 타겟 언어별로 job 생성
            jobs = await start_jobs_for_targets(project, target_languages, worker_db)
            logger.info(f"Created {len(jobs)} jobs for project {project_id} in finalize_ingest")
        else:
            # 타겟 언어가 없으면 기존 방식 사용
            logger.warning(f"No target languages found for project {project_id}, using single job")
            await start_job(project, worker_db)
    else:
        # 타겟이 없으면 기존 방식 사용
        logger.warning(f"No targets found for project {project_id}, using single job")
        await start_job(project, worker_db)

    # pipeline -> project_target 으로 변경 (이미 start_jobs_for_targets에서 처리됨)
