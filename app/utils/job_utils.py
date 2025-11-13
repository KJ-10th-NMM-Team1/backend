"""
Job 처리 관련 유틸리티 함수들
"""
import logging
from typing import Optional

from app.utils.project_utils import extract_language_codes

logger = logging.getLogger(__name__)


async def process_project_jobs(
    project,
    project_id: str,
    project_service,
    start_job,
    start_jobs_for_targets,
    db,
    context: str = "process"
) -> None:
    """
    프로젝트의 타겟 언어에 따라 job을 생성하는 공통 로직

    Args:
        project: 프로젝트 객체
        project_id: 프로젝트 ID
        project_service: ProjectService 인스턴스
        start_job: 단일 job 생성 함수
        start_jobs_for_targets: 다중 job 생성 함수
        db: 데이터베이스 연결
        context: 호출 컨텍스트 (로깅용)
    """
    # 프로젝트의 타겟 언어들 가져오기
    targets = await project_service.get_targets_by_project(project_id)

    if targets:
        # 유틸 함수로 언어 코드 추출
        target_languages = extract_language_codes(targets)

        if target_languages:
            # 타겟 언어별로 job 생성
            jobs = await start_jobs_for_targets(project, target_languages, db)
           
        else:
            # 타겟 언어가 없으면 기존 방식 사용
            logger.warning(
                f"[{context}] No target languages found for project {project_id}, "
                f"using single job"
            )
            await start_job(project, db)
    else:
        # 타겟이 없으면 기존 방식 사용
        await start_job(project, db)