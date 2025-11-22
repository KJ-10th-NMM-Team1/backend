"""
Jobs API 공통 유틸리티 함수
"""
import logging
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def find_segment_id_from_metadata(
    db: AsyncIOMotorDatabase,
    project_id: str,
    metadata: dict,
) -> Optional[str]:
    """
    metadata에서 단일 segment_id를 찾습니다. (하위 호환성 유지)

    1. metadata.segment_id 우선
    2. metadata.segments[0].index로 project_segments에서 조회

    Args:
        db: Database connection
        project_id: 프로젝트 ID
        metadata: 콜백 metadata

    Returns:
        segment_id (str) 또는 None
    """
    result = await find_segment_ids_from_metadata(db, project_id, metadata)
    return result[0] if result else None


async def find_segment_ids_from_metadata(
    db: AsyncIOMotorDatabase,
    project_id: str,
    metadata: dict,
) -> list[str]:
    """
    metadata에서 여러 segment_id를 찾습니다.

    1. metadata.segment_id가 있으면 단일 항목 리스트 반환
    2. metadata.segments 배열의 각 segment_id 또는 index로 조회

    Args:
        db: Database connection
        project_id: 프로젝트 ID
        metadata: 콜백 metadata

    Returns:
        segment_id 리스트
    """
    segment_ids = []

    # metadata에서 segment_id 직접 가져오기 (단일)
    segment_id = metadata.get("segment_id")
    if segment_id:
        segment_ids.append(segment_id)
        return segment_ids

    # segments 배열에서 찾기
    segments_result = metadata.get("segments", [])
    if not segments_result:
        return segment_ids

    try:
        project_oid = (
            ObjectId(project_id) if isinstance(project_id, str) else project_id
        )

        for seg_result in segments_result:
            # segment_id가 직접 있으면 사용
            seg_id = seg_result.get("segment_id")
            if seg_id:
                segment_ids.append(seg_id)
                continue

            # index로 찾기
            segment_index = seg_result.get("index")
            if segment_index is None:
                continue

            segment_doc = await db["project_segments"].find_one(
                {
                    "project_id": project_oid,
                    "segment_index": segment_index,
                }
            )

            if segment_doc:
                segment_ids.append(str(segment_doc["_id"]))

    except Exception as exc:
        logger.error(f"Error finding segments from metadata: {exc}")

    return segment_ids


async def validate_segment_exists(
    db: AsyncIOMotorDatabase,
    segment_id: str,
) -> Optional[dict]:
    """
    segment_id가 유효하고 존재하는지 확인합니다.

    Args:
        db: Database connection
        segment_id: 세그먼트 ID

    Returns:
        segment document 또는 None
    """
    try:
        segment_oid = ObjectId(segment_id)
    except Exception as exc:
        logger.error(
            f"Invalid segment_id format: {segment_id}, error: {exc}"
        )
        return None

    segment_doc = await db["project_segments"].find_one({"_id": segment_oid})

    if not segment_doc:
        logger.warning(f"Segment not found: {segment_id}")
        return None

    return segment_doc


def extract_error_message(metadata: dict, default: str = "Operation failed") -> str:
    """
    metadata에서 에러 메시지를 추출합니다.

    Args:
        metadata: 콜백 metadata
        default: 기본 에러 메시지

    Returns:
        에러 메시지 문자열
    """
    return metadata.get("error") or default


def convert_to_object_id(id_value: str | ObjectId) -> ObjectId:
    """
    문자열 또는 ObjectId를 ObjectId로 변환합니다.

    Args:
        id_value: 변환할 ID

    Returns:
        ObjectId
    """
    if isinstance(id_value, str):
        return ObjectId(id_value)
    return id_value
