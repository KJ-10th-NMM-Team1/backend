"""
프로젝트 진행도 계산 서비스
"""
from typing import Optional
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


async def calculate_project_overall_progress(
    db,
    project_id: str
) -> int:
    """
    프로젝트 전체 진행도 계산

    모든 target_language의 평균 진행도를 반환

    Args:
        db: 데이터베이스 인스턴스
        project_id: 프로젝트 ID

    Returns:
        전체 진행도 (0-100)
    """
    try:
        # 모든 타겟 언어의 진행도 조회
        targets = await db["project_targets"].find(
            {"project_id": project_id}
        ).to_list(length=None)

        if not targets:
            logger.warning(f"No targets found for project {project_id}")
            return 0

        # 평균 진행도 계산
        total_progress = sum(t.get("progress", 0) for t in targets)
        overall_progress = total_progress // len(targets)

        logger.debug(
            f"Project {project_id} overall progress: {overall_progress}% "
            f"(targets: {len(targets)})"
        )

        return overall_progress

    except Exception as exc:
        logger.error(f"Failed to calculate overall progress for {project_id}: {exc}")
        return 0


async def get_project_progress_summary(
    db,
    project_id: str
) -> dict:
    """
    프로젝트 진행도 요약 정보 반환

    Returns:
        {
            "overall_progress": 60,
            "target_progresses": {
                "ko": {"progress": 100, "status": "completed"},
                "en": {"progress": 50, "status": "processing"},
                "ja": {"progress": 30, "status": "processing"}
            },
            "completed_count": 1,
            "total_count": 3
        }
    """
    try:
        # 모든 타겟 조회
        targets = await db["project_targets"].find(
            {"project_id": project_id}
        ).to_list(length=None)

        if not targets:
            return {
                "overall_progress": 0,
                "target_progresses": {},
                "completed_count": 0,
                "total_count": 0
            }

        # 타겟별 진행도 정리
        target_progresses = {}
        completed_count = 0

        for target in targets:
            lang_code = target.get("language_code")
            progress = target.get("progress", 0)
            status = target.get("status", "pending")

            target_progresses[lang_code] = {
                "progress": progress,
                "status": status
            }

            if status == "completed":
                completed_count += 1

        # 전체 진행도
        overall_progress = await calculate_project_overall_progress(db, project_id)

        return {
            "overall_progress": overall_progress,
            "target_progresses": target_progresses,
            "completed_count": completed_count,
            "total_count": len(targets)
        }

    except Exception as exc:
        logger.error(f"Failed to get progress summary for {project_id}: {exc}")
        return {
            "overall_progress": 0,
            "target_progresses": {},
            "completed_count": 0,
            "total_count": 0
        }