from datetime import datetime, timezone
from fastapi import HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import tempfile
import logging
import asyncio
import os

from ..deps import DbDep
from .model import (
    ResponseSegment,
    RequestSegment,
    SegmentSplitResponseItem,
    MergeSegmentResponse,
    SegmentUpdateData,
    UpdateSegmentsResponse,
)
from ..project.models import (
    SegmentTranslationResponse,
    ProjectSegmentCreate,
    SegmentTranslationCreate,
)
from app.utils.audio import (
    download_audio_from_s3,
    split_audio_with_ffmpeg,
    upload_audio_to_s3,
    merge_audio_with_ffmpeg,
)

logger = logging.getLogger(__name__)
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "dupilot-dev-media")


class SegmentService:
    def __init__(self, db: DbDep):
        self.db = db
        self.collection_name = "projects"
        self.collection = db.get_collection(self.collection_name)
        self.segment_collection = db.get_collection("project_segments")
        self.projection = {
            "segments": 1,
            "editor_id": 1,
            "segment_assets_prefix": 1,
            "target_lang": 1,
            "source_lang": 1,
            "video_source": 1,
        }
        self.translation_collection = db.get_collection("segment_translations")

    async def test_save_segment(self, request: RequestSegment, db_name: str):
        project_oid = ObjectId(request.project_id)
        collection = self.db.get_collection(db_name)
        doc = request.model_dump(by_alias=True)
        doc["_id"] = project_oid
        result = await collection.insert_one(doc)
        return str(result.inserted_id)

    async def delete_segments_by_project(self, project_id: ObjectId) -> int:
        result = await self.segment_collection.delete_many({"project_id": project_id})
        return result.deleted_count

    async def insert_segments_from_metadata(
        self,
        project_id: str | ObjectId,
        segments_meta: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        project_oid = self._as_object_id(str(project_id))
        now = datetime.now()
        docs: list[dict[str, Any]] = []

        for index, raw in enumerate(segments_meta or []):
            normalized = self._normalize_segment_for_store(raw or {}, index=index)
            normalized.update(
                {
                    "project_id": project_oid,
                    "segment_index": index,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            docs.append(normalized)

        if docs:
            await self.segment_collection.insert_many(docs)

        return docs

    async def find_all_segment(self, project_id: Optional[str] = None):
        query: Dict[str, Any] = {}
        if project_id:
            object_id = self._as_object_id(project_id)
            query["_id"] = object_id

        project_docs = await self.collection.find(query, self.projection).to_list(
            length=None
        )

        all_segments: List[ResponseSegment] = []

        for project_doc in project_docs:
            project_id = project_doc["_id"]
            editor_id = project_doc.get("editor_id")
            segments = project_doc.get("segments") or []
            for segment_data in segments:
                segment_data = dict(segment_data)
                segment_data["_id"] = project_id
                segment_data.setdefault("editor_id", editor_id)
                all_segments.append(ResponseSegment(**segment_data))

        return all_segments

    async def update_segment(self, request: RequestSegment):
        result = await self.collection.update_one(
            {"_id": request.project_id, "segment_id": request.segment_id},
            {"$set": {"translate_context": request.translate_context}},
        )
        return result

    def _as_object_id(self, project_id: str) -> ObjectId:
        try:
            return ObjectId(project_id)
        except InvalidId as exc:
            raise HTTPException(status_code=400, detail="invalid project_id") from exc

    async def _load_project(self, project_id: str) -> Tuple[Dict[str, Any], ObjectId]:
        object_id = self._as_object_id(project_id)
        project = await self.collection.find_one({"_id": object_id}, self.projection)
        if not project:
            raise HTTPException(status_code=404, detail="project not found")
        return project, object_id

    async def get_project_segment(
        self, project_id: str, segment_id: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any], int, ObjectId]:
        project, object_id = await self._load_project(project_id)

        segment = await self.segment_collection.find_one(
            {"segment_id": ObjectId(segment_id), "project_id": object_id}
        )

        return project, dict(segment), segment["segment_index"], object_id
        raise HTTPException(status_code=404, detail="segment not found")

    async def set_segment_translation(
        self,
        project_object_id: ObjectId,
        segment_index: int,
        text: str,
        *,
        editor_id: Optional[str] = None,
    ) -> None:
        set_fields: Dict[str, Any] = {
            f"segments.{segment_index}.translate_context": text,
        }
        if editor_id:
            set_fields[f"segments.{segment_index}.editor_id"] = editor_id

        await self.collection.update_one(
            {"_id": project_object_id},
            {"$set": set_fields},
        )

    def _normalize_segment_for_store(
        self,
        segment: dict[str, Any],
        *,
        index: int,
    ) -> dict[str, Any]:
        def _float_or_none(value: Any) -> float | None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        segment_id = segment.get("seg_id")
        try:
            segment_oid = ObjectId(segment_id)
        except (InvalidId, TypeError):
            segment_oid = ObjectId()

        issues = segment.get("issues") or []
        if not isinstance(issues, list):
            issues = [issues]

        normalized: dict[str, Any] = {
            "segment_id": segment_oid,
            "segment_text": segment.get("seg_txt", ""),
            "translate_context": segment.get("trans_txt", ""),
            "score": segment.get("score"),
            "editor_id": segment.get("editor_id"),
            "start_point": _float_or_none(segment.get("start")) or 0.0,
            "end_point": _float_or_none(segment.get("end")) or 0.0,
            "issues": issues,
            "sub_langth": _float_or_none(segment.get("sub_langth")),
            # "order": segment.get("order", index),
        }

        assets = segment.get("assets")
        if isinstance(assets, dict):
            normalized["assets"] = assets

        for key in ("source_key", "bgm_key", "tts_key", "mix_key", "video_key"):
            value = segment.get(key)
            if value:
                normalized[key] = value

        return normalized

    async def get_project_segment_translations(
        self,
        project_id: str,
        language_code: str,
    ) -> list[SegmentTranslationResponse]:
        # project_oid = ObjectId(project_id)
        segments = await self.segment_collection.find(
            {"project_id": project_id}
        ).to_list(None)

        print("segments:", segments)

        if not segments:
            return []

        # segment_id는 문자열로 저장되어 있으므로 문자열 배열로 만들기
        segment_ids = [str(seg["_id"]) for seg in segments]

        translations = await self.translation_collection.find(
            {"segment_id": {"$in": segment_ids}, "language_code": language_code}
        ).to_list(None)

        print("translations:", translations)

        # translation_map의 키도 문자열로
        translation_map = {doc["segment_id"]: doc for doc in translations}

        result = []
        for seg in segments:
            segment_id_str = str(seg["_id"])  # 문자열로 변환
            merged = {
                "id": seg["_id"],
                **seg,
                **translation_map.get(segment_id_str, {}),  # 문자열 키로 조회
                "language_code": language_code,
            }
            result.append(SegmentTranslationResponse(**merged))

        return result

    async def create_project_segment(
        self,
        project_id: str,
        payload: ProjectSegmentCreate,
    ) -> str:
        project_oid = ObjectId(project_id)
        now = datetime.now(timezone.utc)

        doc = payload.model_dump(exclude_none=True)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        doc["project_id"] = project_oid

        result = await self.segment_collection.insert_one(doc)
        return str(result.inserted_id)

    async def create_segment_translation(
        self,
        project_id: str,
        segment_id: str,
        payload: SegmentTranslationCreate,
    ) -> str:
        project_oid = ObjectId(project_id)
        segment_oid = ObjectId(segment_id)

        segment = await self.segment_collection.find_one(
            {"_id": segment_oid, "project_id": project_oid},
            {"_id": 1},
        )
        if not segment:
            raise HTTPException(status_code=404, detail="segment not found")

        now = datetime.now(timezone.utc)
        doc = payload.model_dump(exclude_none=True)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        # segment_id는 문자열로 저장 (일관성 유지)
        doc["segment_id"] = str(segment_oid)
        doc["project_id"] = project_oid

        result = await self.translation_collection.insert_one(doc)
        return str(result.inserted_id)

    async def split_segment(
        self, segment_id: str, language_code: str, split_time: float
    ) -> List[SegmentSplitResponseItem]:
        """
        세그먼트를 두 개로 분할합니다.

        Args:
            segment_id: 분할할 세그먼트의 ID (project_segments)
            language_code: 타겟 언어 코드
            split_time: 분할 시점 (초 단위)

        Returns:
            분할된 두 개의 세그먼트 정보 리스트
        """
        # 1. 세그먼트 조회 (시간 정보를 위해)
        try:
            segment_oid = ObjectId(segment_id)
        except (InvalidId, TypeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid segment_id") from exc

        segment = await self.segment_collection.find_one({"_id": segment_oid})
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

        # 2. 번역 정보 조회 (오디오 URL을 위해)
        translation = await self.translation_collection.find_one(
            {"segment_id": segment_id, "language_code": language_code}
        )

        if not translation:
            raise HTTPException(
                status_code=404,
                detail=f"Translation not found for segment {segment_id} and language {language_code}",
            )

        # 3. 오디오 파일 정보 확인
        source_key = translation.get("segment_audio_url")
        if not source_key:
            raise HTTPException(
                status_code=400, detail="Translation does not have audio file"
            )

        start_time = float(segment.get("start", 0))
        end_time = float(segment.get("end", 0))
        total_duration = end_time - start_time

        # 3. split_time 검증
        if split_time <= 0 or split_time >= total_duration:
            raise HTTPException(
                status_code=400,
                detail=f"split_time must be between 0 and {total_duration}",
            )

        # 4. 임시 파일 경로 설정
        tmp_input_path = None
        tmp_output1_path = None
        tmp_output2_path = None

        try:
            # 5. S3에서 원본 오디오 다운로드
            tmp_input_path = await download_audio_from_s3(source_key)
            if not tmp_input_path:
                raise HTTPException(
                    status_code=500, detail="Failed to download audio from S3"
                )

            # 6. 임시 출력 파일 생성
            suffix = Path(source_key).suffix or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file1:
                tmp_output1_path = Path(tmp_file1.name)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file2:
                tmp_output2_path = Path(tmp_file2.name)

            # 7. FFmpeg로 오디오 분할
            success, error_msg = await asyncio.to_thread(
                split_audio_with_ffmpeg,
                str(tmp_input_path),
                str(tmp_output1_path),
                str(tmp_output2_path),
                float(split_time),
            )

            if not success:
                raise HTTPException(
                    status_code=500, detail=f"Failed to split audio: {error_msg}"
                )

            # 8. S3에 업로드할 키 생성
            segment_index = segment.get("segment_index", 0)
            base_path = Path(source_key).parent

            # part1과 part2에 고유한 이름 부여
            from uuid import uuid4

            part1_key = str(
                base_path / f"segment_{segment_index}_part1_{uuid4()}{suffix}"
            )
            part2_key = str(
                base_path / f"segment_{segment_index}_part2_{uuid4()}{suffix}"
            )

            # 9. S3에 업로드
            upload1_success = await upload_audio_to_s3(tmp_output1_path, part1_key)
            upload2_success = await upload_audio_to_s3(tmp_output2_path, part2_key)

            if not upload1_success or not upload2_success:
                raise HTTPException(
                    status_code=500, detail="Failed to upload split audio to S3"
                )

            # 10. DB 업데이트: 기존 세그먼트 업데이트
            now = datetime.now(timezone.utc)

            # 기존 세그먼트 업데이트 (part1)
            await self.segment_collection.update_one(
                {"_id": segment_oid},
                {
                    "$set": {
                        "end": start_time + split_time,
                        "updated_at": now,
                    }
                },
            )

            # 기존 번역 업데이트 (part1)
            await self.translation_collection.update_one(
                {"segment_id": segment_id, "language_code": language_code},
                {
                    "$set": {
                        "segment_audio_url": part1_key,
                        "updated_at": now,
                    }
                },
            )

            # 11. DB에 새 세그먼트 생성 (part2)
            new_segment_doc = {
                "project_id": segment.get("project_id"),
                "segment_index": segment.get("segment_index", 0) + 0.5,  # 중간 인덱스
                "speaker_tag": segment.get("speaker_tag", ""),
                "start": start_time + split_time,
                "end": end_time,
                "source_text": segment.get("source_text", ""),
                "is_verified": False,
                "created_at": now,
                "updated_at": now,
            }
            new_segment_result = await self.segment_collection.insert_one(
                new_segment_doc
            )
            new_segment_id = str(new_segment_result.inserted_id)

            # 새 번역 생성 (part2)
            new_translation_doc = {
                "segment_id": new_segment_id,
                "language_code": language_code,
                "target_text": translation.get("target_text", ""),
                "segment_audio_url": part2_key,
                "created_at": now,
                "updated_at": now,
            }
            await self.translation_collection.insert_one(new_translation_doc)

            # 12. 응답 생성
            response = [
                SegmentSplitResponseItem(
                    id=segment_id,  # 기존 ID 유지
                    start=start_time,
                    end=start_time + split_time,
                    audio_url=part1_key,
                ),
                SegmentSplitResponseItem(
                    id=new_segment_id,  # 새로 생성된 ID
                    start=start_time + split_time,
                    end=end_time,
                    audio_url=part2_key,
                ),
            ]

            return response

        finally:
            # 11. 임시 파일 정리
            for tmp_path in [tmp_input_path, tmp_output1_path, tmp_output2_path]:
                if tmp_path and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception as exc:
                        logger.warning(f"Failed to delete temp file {tmp_path}: {exc}")

    async def merge_segments(
        self, segment_ids: list[str], language_code: str
    ) -> MergeSegmentResponse:
        """
        여러 세그먼트를 하나로 병합합니다.

        Args:
            segment_ids: 병합할 세그먼트 ID 목록 (project_segments)
            language_code: 타겟 언어 코드

        Returns:
            병합된 세그먼트 정보
        """
        # 1. 세그먼트 ID 검증
        if len(segment_ids) < 2:
            raise HTTPException(
                status_code=400, detail="At least 2 segments are required for merging"
            )

        # 2. 모든 세그먼트 조회 (시간 정보를 위해)
        segment_oids = []
        for seg_id in segment_ids:
            try:
                segment_oids.append(ObjectId(seg_id))
            except (InvalidId, TypeError) as exc:
                raise HTTPException(
                    status_code=400, detail=f"Invalid segment_id: {seg_id}"
                ) from exc

        segments = await self.segment_collection.find(
            {"_id": {"$in": segment_oids}}
        ).to_list(None)

        if len(segments) != len(segment_ids):
            raise HTTPException(
                status_code=404,
                detail=f"Some segments not found. Expected {len(segment_ids)}, found {len(segments)}",
            )

        # 3. 세그먼트를 시작 시간 순으로 정렬
        segments.sort(key=lambda s: float(s.get("start", 0)))

        # 4. 각 세그먼트의 번역 정보 조회 (오디오 URL을 위해)
        translations = []
        for seg_id in segment_ids:
            translation = await self.translation_collection.find_one(
                {"segment_id": seg_id, "language_code": language_code}
            )

            if not translation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Translation not found for segment {seg_id} and language {language_code}",
                )

            if not translation.get("segment_audio_url"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Translation for segment {seg_id} does not have audio file",
                )

            translations.append(translation)

        # 5. 세그먼트가 같은 프로젝트인지 확인
        project_ids = {str(seg.get("project_id")) for seg in segments}
        if len(project_ids) > 1:
            raise HTTPException(
                status_code=400,
                detail="All segments must belong to the same project",
            )

        # 6. 번역 정보를 세그먼트 순서대로 정렬
        # segments는 이미 start 시간 순으로 정렬되어 있음
        # translation도 같은 순서로 정렬
        segment_id_to_translation = {t["segment_id"]: t for t in translations}
        sorted_translations = []
        for seg in segments:
            seg_id_str = str(seg["_id"])
            if seg_id_str in segment_id_to_translation:
                sorted_translations.append(segment_id_to_translation[seg_id_str])

        # 7. 임시 파일 경로 설정
        tmp_input_paths: list[Path] = []
        tmp_output_path = None

        try:
            # 8. 각 세그먼트의 오디오를 S3에서 다운로드
            for translation in sorted_translations:
                source_key = translation.get("segment_audio_url")
                tmp_path = await download_audio_from_s3(source_key)
                if not tmp_path:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to download audio for translation {translation['_id']}",
                    )
                tmp_input_paths.append(tmp_path)

            # 9. 임시 출력 파일 생성
            first_source_key = sorted_translations[0].get("segment_audio_url")
            suffix = Path(first_source_key).suffix or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_output_path = Path(tmp_file.name)

            # 10. FFmpeg로 오디오 병합
            success, error_msg = await asyncio.to_thread(
                merge_audio_with_ffmpeg,
                [str(p) for p in tmp_input_paths],
                str(tmp_output_path),
            )

            if not success:
                raise HTTPException(
                    status_code=500, detail=f"Failed to merge audio: {error_msg}"
                )

            # 11. S3에 업로드할 키 생성
            base_path = Path(first_source_key).parent
            from uuid import uuid4

            merged_key = str(base_path / f"merged_segment_{uuid4()}{suffix}")

            # 12. S3에 업로드
            upload_success = await upload_audio_to_s3(tmp_output_path, merged_key)
            if not upload_success:
                raise HTTPException(
                    status_code=500, detail="Failed to upload merged audio to S3"
                )

            # 13. DB 업데이트: 첫 번째 세그먼트를 병합된 세그먼트로 업데이트
            start_time = float(segments[0].get("start", 0))
            end_time = float(segments[-1].get("end", 0))
            now = datetime.now(timezone.utc)

            first_segment = segments[0]
            first_segment_id = str(first_segment["_id"])

            # 병합된 source_text 생성 (모든 세그먼트의 텍스트 결합)
            merged_source_text = " ".join(
                [seg.get("source_text", "") for seg in segments]
            )

            # 첫 번째 세그먼트 업데이트
            await self.segment_collection.update_one(
                {"_id": first_segment["_id"]},
                {
                    "$set": {
                        "end": end_time,
                        "source_text": merged_source_text,
                        "updated_at": now,
                    }
                },
            )

            # 14. 첫 번째 세그먼트의 번역 업데이트
            # 모든 번역의 target_text 결합
            merged_target_text = " ".join(
                [t.get("target_text", "") for t in sorted_translations]
            )

            # 기존 번역이 있으면 업데이트, 없으면 생성
            await self.translation_collection.update_one(
                {"segment_id": first_segment_id, "language_code": language_code},
                {
                    "$set": {
                        "target_text": merged_target_text,
                        "segment_audio_url": merged_key,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "created_at": now,
                    },
                },
                upsert=True,
            )

            # 15. 나머지 세그먼트들 삭제 (첫 번째 제외)
            remaining_segment_oids = segment_oids[1:]  # 첫 번째 제외
            remaining_segment_ids = segment_ids[1:]  # 첫 번째 제외

            if remaining_segment_oids:
                await self.segment_collection.delete_many(
                    {"_id": {"$in": remaining_segment_oids}}
                )

                # 삭제된 세그먼트들의 모든 번역 삭제
                await self.translation_collection.delete_many(
                    {"segment_id": {"$in": remaining_segment_ids}}
                )

            # 16. 응답 생성
            response = MergeSegmentResponse(
                id=first_segment_id,
                start=start_time,
                end=end_time,
                audio_url=merged_key,
                source_text=merged_source_text,
                target_text=merged_target_text,
            )

            return response

        finally:
            # 14. 임시 파일 정리
            for tmp_path in tmp_input_paths:
                if tmp_path and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception as exc:
                        logger.warning(f"Failed to delete temp file {tmp_path}: {exc}")

            if tmp_output_path and tmp_output_path.exists():
                try:
                    tmp_output_path.unlink()
                except Exception as exc:
                    logger.warning(
                        f"Failed to delete temp file {tmp_output_path}: {exc}"
                    )

    async def update_segments_bulk(
        self,
        project_id: str,
        language_code: str,
        segments_data: list[SegmentUpdateData],
    ) -> UpdateSegmentsResponse:
        """
        프로젝트의 여러 세그먼트를 일괄 업데이트합니다.

        Args:
            project_id: 프로젝트 ID
            language_code: 타겟 언어 코드
            segments_data: 업데이트할 세그먼트 데이터 목록

        Returns:
            업데이트 결과
        """
        # 1. 프로젝트 ID 검증
        try:
            project_oid = ObjectId(project_id)
        except (InvalidId, TypeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid project_id") from exc

        # 2. 프로젝트 존재 확인
        project = await self.collection.find_one({"_id": project_oid})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        now = datetime.now(timezone.utc)
        updated_count = 0

        # 3. 각 세그먼트 업데이트
        for segment_data in segments_data:
            try:
                segment_oid = ObjectId(segment_data.id)
            except (InvalidId, TypeError):
                logger.warning(f"Invalid segment_id: {segment_data.id}, skipping")
                continue

            # 4. project_segments 컬렉션 업데이트할 필드 구성
            segment_update_fields: Dict[str, Any] = {}

            if segment_data.start is not None:
                segment_update_fields["start"] = segment_data.start
            if segment_data.end is not None:
                segment_update_fields["end"] = segment_data.end
            if segment_data.speaker_tag is not None:
                segment_update_fields["speaker_tag"] = segment_data.speaker_tag
            if segment_data.source_text is not None:
                segment_update_fields["source_text"] = segment_data.source_text

            # 5. project_segments 업데이트
            if segment_update_fields:
                segment_update_fields["updated_at"] = now
                result = await self.segment_collection.update_one(
                    {"_id": segment_oid, "project_id": project_oid},
                    {"$set": segment_update_fields},
                )
                if result.matched_count > 0:
                    updated_count += 1

            # 6. segment_translations 컬렉션 업데이트할 필드 구성
            translation_update_fields: Dict[str, Any] = {}

            if segment_data.target_text is not None:
                translation_update_fields["target_text"] = segment_data.target_text
            if segment_data.playbackRate is not None:
                translation_update_fields["playback_rate"] = segment_data.playbackRate

            # 7. segment_translations 업데이트 (있으면 업데이트, 없으면 생성)
            if translation_update_fields:
                translation_update_fields["updated_at"] = now
                await self.translation_collection.update_one(
                    {"segment_id": segment_data.id, "language_code": language_code},
                    {
                        "$set": translation_update_fields,
                        "$setOnInsert": {
                            "segment_id": segment_data.id,
                            "language_code": language_code,
                            "created_at": now,
                        },
                    },
                    upsert=True,
                )

        return UpdateSegmentsResponse(
            success=True,
            message=f"Successfully updated {updated_count} segments",
            updated_count=updated_count,
        )
