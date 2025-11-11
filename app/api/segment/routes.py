"""
세그먼트 및 번역 관련 API 라우터
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from ..deps import DbDep
from .service import SegmentService
import logging

logger = logging.getLogger(__name__)
segments_router = APIRouter(prefix="/segments", tags=["segments"])


@segments_router.get("/project/{project_id}")
async def get_segments_by_project(
    project_id: str,
    db: DbDep,
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100)
) -> List[dict]:
    """
    프로젝트 ID로 세그먼트 목록 조회

    - **project_id**: 프로젝트 ID
    - **skip**: 건너뛸 개수 (pagination)
    - **limit**: 최대 조회 개수
    """
    service = SegmentService(db)
    return await service.get_segments_by_project(project_id, skip, limit)


@segments_router.get("/project/{project_id}/count")
async def count_segments_by_project(
    project_id: str,
    db: DbDep
) -> dict:
    """프로젝트의 세그먼트 개수 조회"""
    service = SegmentService(db)
    count = await service.count_segments_by_project(project_id)
    return {"project_id": project_id, "count": count}


@segments_router.get("/project/{project_id}/translations")
async def get_translations_by_project(
    project_id: str,
    db: DbDep,
    language_code: Optional[str] = Query(None, description="언어 코드 필터"),
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100)
) -> List[dict]:
    """
    프로젝트의 모든 번역 조회

    - **project_id**: 프로젝트 ID
    - **language_code**: 언어 코드로 필터링 (선택)
    - **skip**: 건너뛸 개수
    - **limit**: 최대 조회 개수
    """
    service = SegmentService(db)
    return await service.get_translations_by_project(
        project_id, language_code, skip, limit
    )


@segments_router.get("/project/{project_id}/with-translations")
async def get_segments_with_translations(
    project_id: str,
    db: DbDep,
    language_code: Optional[str] = Query(None, description="언어 코드 필터"),
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=100)
) -> List[dict]:
    """
    프로젝트의 세그먼트와 번역을 함께 조회

    - **project_id**: 프로젝트 ID
    - **language_code**: 번역 언어 코드로 필터링 (선택)
    - **skip**: 건너뛸 개수
    - **limit**: 최대 조회 개수

    반환 형식:
    ```json
    [
        {
            "_id": "segment_id",
            "project_id": "...",
            "segment_index": 0,
            "speaker_tag": "SPEAKER_00",
            "start": 0.0,
            "end": 13.194,
            "source_text": "원본 텍스트",
            "translations": [
                {
                    "_id": "translation_id",
                    "language_code": "en",
                    "target_text": "번역된 텍스트",
                    "segment_audio_url": "..."
                }
            ]
        }
    ]
    ```
    """
    service = SegmentService(db)
    return await service.get_segments_with_translations(
        project_id, language_code, skip, limit
    )


@segments_router.get("/project/{project_id}/languages")
async def get_translation_languages(
    project_id: str,
    db: DbDep
) -> List[str]:
    """프로젝트에서 사용된 번역 언어 목록 조회"""
    service = SegmentService(db)
    return await service.get_translation_languages(project_id)


@segments_router.get("/{segment_id}")
async def get_segment_by_id(
    segment_id: str,
    db: DbDep
) -> dict:
    """세그먼트 ID로 단일 세그먼트 조회"""
    service = SegmentService(db)
    segment = await service.get_segment_by_id(segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return segment


@segments_router.get("/{segment_id}/translations")
async def get_translations_by_segment(
    segment_id: str,
    db: DbDep,
    language_code: Optional[str] = Query(None, description="언어 코드 필터")
) -> List[dict]:
    """
    세그먼트 ID로 번역 목록 조회

    - **segment_id**: 세그먼트 ID
    - **language_code**: 특정 언어 코드로 필터링 (선택)
    """
    service = SegmentService(db)
    return await service.get_translations_by_segment(segment_id, language_code)


@segments_router.put("/translation/{translation_id}")
async def update_translation(
    translation_id: str,
    db: DbDep,
    target_text: Optional[str] = None,
    segment_audio_url: Optional[str] = None
) -> dict:
    """
    번역 업데이트

    - **translation_id**: 번역 ID
    - **target_text**: 새로운 번역 텍스트 (선택)
    - **segment_audio_url**: 새로운 오디오 URL (선택)
    """
    if target_text is None and segment_audio_url is None:
        raise HTTPException(
            status_code=400,
            detail="At least one field (target_text or segment_audio_url) must be provided"
        )

    service = SegmentService(db)
    result = await service.update_translation(
        translation_id, target_text, segment_audio_url
    )

    if not result:
        raise HTTPException(status_code=404, detail="Translation not found")

    return result