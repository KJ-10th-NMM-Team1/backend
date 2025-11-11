"""
세그먼트 및 번역 관련 서비스
"""
from typing import Optional, List
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


class SegmentService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.segments_collection = db["project_segments"]
        self.translations_collection = db["segment_translations"]

    async def get_segments_by_project(
        self,
        project_id: str,
        skip: int = 0,
        limit: Optional[int] = None
    ) -> List[dict]:
        """프로젝트 ID로 세그먼트 목록 조회"""
        try:
            query = {"project_id": project_id}
            cursor = self.segments_collection.find(query).sort("segment_index", 1).skip(skip)

            if limit:
                cursor = cursor.limit(limit)

            segments = []
            async for segment in cursor:
                segment["_id"] = str(segment["_id"])
                segments.append(segment)

            logger.info(f"Found {len(segments)} segments for project {project_id}")
            return segments

        except Exception as exc:
            logger.error(f"Failed to get segments for project {project_id}: {exc}")
            raise

    async def get_segment_by_id(self, segment_id: str) -> Optional[dict]:
        """세그먼트 ID로 단일 세그먼트 조회"""
        try:
            segment = await self.segments_collection.find_one(
                {"_id": ObjectId(segment_id)}
            )
            if segment:
                segment["_id"] = str(segment["_id"])
            return segment

        except Exception as exc:
            logger.error(f"Failed to get segment {segment_id}: {exc}")
            raise

    async def count_segments_by_project(self, project_id: str) -> int:
        """프로젝트의 세그먼트 개수 조회"""
        try:
            count = await self.segments_collection.count_documents(
                {"project_id": project_id}
            )
            return count

        except Exception as exc:
            logger.error(f"Failed to count segments for project {project_id}: {exc}")
            raise

    async def get_translations_by_segment(
        self,
        segment_id: str,
        language_code: Optional[str] = None
    ) -> List[dict]:
        """세그먼트 ID로 번역 목록 조회"""
        try:
            query = {"segment_id": segment_id}
            if language_code:
                query["language_code"] = language_code

            cursor = self.translations_collection.find(query)

            translations = []
            async for translation in cursor:
                translation["_id"] = str(translation["_id"])
                translations.append(translation)

            return translations

        except Exception as exc:
            logger.error(f"Failed to get translations for segment {segment_id}: {exc}")
            raise

    async def get_translations_by_project(
        self,
        project_id: str,
        language_code: Optional[str] = None,
        skip: int = 0,
        limit: Optional[int] = None
    ) -> List[dict]:
        """프로젝트의 모든 번역 조회 (세그먼트 정보와 함께)"""
        try:
            # 먼저 프로젝트의 모든 세그먼트 ID 가져오기
            segments = await self.get_segments_by_project(project_id)
            # segment_id는 문자열로 저장되어 있으므로 문자열 배열로 만들기
            segment_ids = [str(seg["_id"]) for seg in segments]

            # segment_index로 정렬을 위한 매핑 (키도 문자열로)
            seg_index_map = {str(seg["_id"]): seg["segment_index"] for seg in segments}

            # 번역 조회
            query = {"segment_id": {"$in": segment_ids}}
            if language_code:
                query["language_code"] = language_code

            cursor = self.translations_collection.find(query).skip(skip)

            if limit:
                cursor = cursor.limit(limit)

            translations = []
            async for translation in cursor:
                translation["_id"] = str(translation["_id"])
                # segment_index 추가
                if translation["segment_id"] in seg_index_map:
                    translation["segment_index"] = seg_index_map[translation["segment_id"]]
                translations.append(translation)

            # segment_index로 정렬
            translations.sort(key=lambda x: x.get("segment_index", 0))

            logger.info(
                f"Found {len(translations)} translations for project {project_id}"
                f"{f' with language {language_code}' if language_code else ''}"
            )
            return translations

        except Exception as exc:
            logger.error(f"Failed to get translations for project {project_id}: {exc}")
            raise

    async def get_segments_with_translations(
        self,
        project_id: str,
        language_code: Optional[str] = None,
        skip: int = 0,
        limit: Optional[int] = None
    ) -> List[dict]:
        """프로젝트의 세그먼트와 번역을 함께 조회"""
        try:
            # 세그먼트 조회
            segments = await self.get_segments_by_project(project_id, skip, limit)

            # 각 세그먼트에 대한 번역 조회 (segment_id는 문자열로)
            for segment in segments:
                translations = await self.get_translations_by_segment(
                    str(segment["_id"]),  # 문자열로 변환
                    language_code
                )
                segment["translations"] = translations

            return segments

        except Exception as exc:
            logger.error(f"Failed to get segments with translations for project {project_id}: {exc}")
            raise

    async def get_translation_languages(self, project_id: str) -> List[str]:
        """프로젝트에서 사용된 번역 언어 목록 조회"""
        try:
            # 프로젝트의 세그먼트 ID들 가져오기
            segments = await self.get_segments_by_project(project_id)
            # segment_id는 문자열로 저장되어 있으므로 문자열 배열로 만들기
            segment_ids = [str(seg["_id"]) for seg in segments]

            # distinct로 언어 코드 조회
            languages = await self.translations_collection.distinct(
                "language_code",
                {"segment_id": {"$in": segment_ids}}
            )

            return languages

        except Exception as exc:
            logger.error(f"Failed to get translation languages for project {project_id}: {exc}")
            raise

    async def update_translation(
        self,
        translation_id: str,
        target_text: Optional[str] = None,
        segment_audio_url: Optional[str] = None
    ) -> Optional[dict]:
        """번역 업데이트"""
        try:
            from datetime import datetime

            update_data = {"updated_at": datetime.now()}
            if target_text is not None:
                update_data["target_text"] = target_text
            if segment_audio_url is not None:
                update_data["segment_audio_url"] = segment_audio_url

            result = await self.translations_collection.find_one_and_update(
                {"_id": ObjectId(translation_id)},
                {"$set": update_data},
                return_document=True
            )

            if result:
                result["_id"] = str(result["_id"])

            return result

        except Exception as exc:
            logger.error(f"Failed to update translation {translation_id}: {exc}")
            raise