"""
Issues 서비스 로직
"""
import logging
from datetime import datetime
from typing import Optional
from bson import ObjectId

from ..deps import DbDep
from .models import IssueCreate, IssueOut, IssueType, IssueSeverity

logger = logging.getLogger(__name__)


class IssueService:
    """이슈 관리 서비스"""

    def __init__(self, db: DbDep):
        self.db = db
        self.collection = db.get_collection("issues")

    async def create_issue(self, issue_data: IssueCreate) -> str:
        """
        이슈를 생성합니다.

        Args:
            issue_data: 이슈 생성 데이터

        Returns:
            생성된 이슈의 ID
        """
        doc = issue_data.model_dump()
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def create_issues_from_metadata(
        self,
        project_id: str,
        language_code: str,
        segment_translation_id: str,
        issues_data: dict,
    ) -> list[str]:
        """
        메타데이터의 issues 정보에서 이슈를 생성합니다.

        Args:
            project_id: 프로젝트 ID
            language_code: 타겟 언어 코드
            segment_translation_id: 세그먼트 번역 ID
            issues_data: 메타데이터의 issues 객체
                {
                    "q": {"stt": null, "tts": 86, "sync": -5, "voice": 70},
                    "spk": false
                }

        Returns:
            생성된 이슈 ID 리스트
        """
        created_issue_ids = []

        # q (quality) 객체 처리
        q_data = issues_data.get("q", {})
        if q_data:
            # STT 품질 이슈
            stt_score = q_data.get("stt")
            if stt_score is not None and stt_score <= 70:
                issue = IssueCreate(
                    segment_translation_id=segment_translation_id,
                    project_id=project_id,
                    language_code=language_code,
                    issue_type=IssueType.STT_QUALITY,
                    severity=self._get_quality_severity(stt_score),
                    score=stt_score,
                    details={"message": f"STT quality score is low: {stt_score}"},
                )
                issue_id = await self.create_issue(issue)
                created_issue_ids.append(issue_id)
                logger.info(
                    f"Created STT quality issue: project_id={project_id}, "
                    f"segment_translation_id={segment_translation_id}, score={stt_score}"
                )

            # TTS 품질 이슈
            tts_score = q_data.get("tts")
            if tts_score is not None and tts_score <= 70:
                issue = IssueCreate(
                    segment_translation_id=segment_translation_id,
                    project_id=project_id,
                    language_code=language_code,
                    issue_type=IssueType.TTS_QUALITY,
                    severity=self._get_quality_severity(tts_score),
                    score=tts_score,
                    details={"message": f"TTS quality score is low: {tts_score}"},
                )
                issue_id = await self.create_issue(issue)
                created_issue_ids.append(issue_id)
                logger.info(
                    f"Created TTS quality issue: project_id={project_id}, "
                    f"segment_translation_id={segment_translation_id}, score={tts_score}"
                )

            # Sync 길이 차이 이슈
            sync_diff = q_data.get("sync")
            if sync_diff is not None and abs(sync_diff) >= 10:
                issue = IssueCreate(
                    segment_translation_id=segment_translation_id,
                    project_id=project_id,
                    language_code=language_code,
                    issue_type=IssueType.SYNC_DURATION,
                    severity=self._get_sync_severity(abs(sync_diff)),
                    diff=sync_diff,
                    details={
                        "message": f"Duration difference is too large: {sync_diff}s"
                    },
                )
                issue_id = await self.create_issue(issue)
                created_issue_ids.append(issue_id)
                logger.info(
                    f"Created sync duration issue: project_id={project_id}, "
                    f"segment_translation_id={segment_translation_id}, diff={sync_diff}"
                )

        # spk (speaker identification) 처리
        spk_failed = issues_data.get("spk")
        if spk_failed is True:
            issue = IssueCreate(
                segment_translation_id=segment_translation_id,
                project_id=project_id,
                language_code=language_code,
                issue_type=IssueType.SPEAKER_IDENTIFICATION,
                severity=IssueSeverity.MEDIUM,
                details={"message": "Speaker identification failed, using default voice"},
            )
            issue_id = await self.create_issue(issue)
            created_issue_ids.append(issue_id)
            logger.info(
                f"Created speaker identification issue: project_id={project_id}, "
                f"segment_translation_id={segment_translation_id}"
            )

        return created_issue_ids

    async def get_issues_by_project(
        self, project_id: str, language_code: Optional[str] = None
    ) -> list[IssueOut]:
        """
        프로젝트의 이슈 목록을 조회합니다.

        Args:
            project_id: 프로젝트 ID
            language_code: 타겟 언어 코드 (선택사항)

        Returns:
            이슈 목록
        """
        query = {"project_id": project_id}
        if language_code:
            query["language_code"] = language_code

        issues = await self.collection.find(query).to_list(None)
        return [IssueOut.model_validate(issue) for issue in issues]

    async def get_issues_by_segment_translation(
        self, segment_translation_id: str
    ) -> list[IssueOut]:
        """
        특정 세그먼트 번역의 이슈 목록을 조회합니다.

        Args:
            segment_translation_id: 세그먼트 번역 ID

        Returns:
            이슈 목록
        """
        issues = await self.collection.find(
            {"segment_translation_id": segment_translation_id}
        ).to_list(None)
        return [IssueOut.model_validate(issue) for issue in issues]

    async def update_issue(self, issue_id: str, resolved: bool) -> bool:
        """
        이슈를 업데이트합니다.

        Args:
            issue_id: 이슈 ID
            resolved: 해결 여부

        Returns:
            업데이트 성공 여부
        """
        try:
            issue_oid = ObjectId(issue_id)
        except Exception:
            return False

        result = await self.collection.update_one(
            {"_id": issue_oid},
            {"$set": {"resolved": resolved, "updated_at": datetime.now()}},
        )
        return result.modified_count > 0

    async def delete_issues_by_project(self, project_id: str) -> int:
        """
        프로젝트의 모든 이슈를 삭제합니다.

        Args:
            project_id: 프로젝트 ID

        Returns:
            삭제된 이슈 수
        """
        result = await self.collection.delete_many({"project_id": project_id})
        return result.deleted_count

    async def delete_issues_by_segment_translation(
        self, segment_translation_id: str
    ) -> int:
        """
        특정 세그먼트 번역의 모든 이슈를 삭제합니다.

        Args:
            segment_translation_id: 세그먼트 번역 ID

        Returns:
            삭제된 이슈 수
        """
        result = await self.collection.delete_many(
            {"segment_translation_id": segment_translation_id}
        )
        return result.deleted_count

    def _get_quality_severity(self, score: float) -> IssueSeverity:
        """
        품질 점수에 따른 심각도를 결정합니다.

        Args:
            score: 품질 점수 (0-100)

        Returns:
            심각도
        """
        if score < 50:
            return IssueSeverity.HIGH
        elif score < 65:
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW

    def _get_sync_severity(self, diff: float) -> IssueSeverity:
        """
        길이 차이에 따른 심각도를 결정합니다.

        Args:
            diff: 길이 차이 (초 단위, 절대값)

        Returns:
            심각도
        """
        if diff >= 20:
            return IssueSeverity.HIGH
        elif diff >= 15:
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW
