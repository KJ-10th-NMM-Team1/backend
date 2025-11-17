from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from .segment_service import SegmentService
from .history_service import HistoryService
from .model import (
    RequestSegment,
    ResponseSegment,
    SegmentRetranslateRequest,
    SegmentRetranslateResponse,
    SegmentSplitRequest,
    SegmentSplitResponse,
    MergeSegmentsRequest,
    MergeSegmentResponse,
)
from typing import List
from ..deps import DbDep
from ..jobs.service import start_segment_tts_job

segment_router = APIRouter(prefix="/segment", tags=["segment"])
editor_segment_router = APIRouter(prefix="/editor/projects", tags=["segment"])


@segment_router.get("/{project_id}", response_model=List[ResponseSegment])
async def get_segment_all(
    project_id: str, service: SegmentService = Depends(SegmentService)
):
    find_list = await service.find_all_segment(project_id)
    return find_list


@segment_router.put("/{project_id}/history", response_model=str)
async def segment_history(
    request: RequestSegment, history_service: HistoryService = Depends(HistoryService)
):
    try:
        return await history_service.insert_one_history(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@segment_router.post("/{project_id}/test/save", response_model=str)
async def segment_test_save(
    request: RequestSegment, segment_service: SegmentService = Depends(SegmentService)
):
    try:
        return await segment_service.test_save_segment(request, db_name="segments")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@segment_router.patch("/{project_id}/save", response_model=None)
async def save_segment(
    request: RequestSegment, service: SegmentService = Depends(SegmentService)
):
    return await service.update_segment(request)


@editor_segment_router.put(
    "/{project_id}/segments/{segment_id}/retranslate",
    response_model=SegmentRetranslateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retranslate_segment(
    project_id: str,
    segment_id: str,
    payload: SegmentRetranslateRequest,
    db: DbDep,
    service: SegmentService = Depends(SegmentService),
):
    project, segment, index, project_object_id = await service.get_project_segment(
        project_id, segment_id
    )

    await service.set_segment_translation(
        project_object_id,
        index,
        payload.text,
        editor_id=payload.editor_id,
    )

    segment["translate_context"] = payload.text
    if payload.editor_id:
        segment["editor_id"] = payload.editor_id

    job = await start_segment_tts_job(
        db,
        project=project,
        segment_index=index,
        segment=segment,
        text=payload.text,
    )

    return SegmentRetranslateResponse(
        job_id=job.job_id,
        segment_id=segment_id,
        segment_index=index,
        status=job.status,
    )


@segment_router.post("/split", response_model=SegmentSplitResponse)
async def split_segment(
    payload: SegmentSplitRequest,
    service: SegmentService = Depends(SegmentService),
):
    """
    세그먼트를 두 개로 분할합니다.

    - **segment_id**: 분할할 세그먼트의 ID (project_segments)
    - **language_code**: 타겟 언어 코드 (예: ko, en, ja)
    - **split_time**: 분할 시점 (초 단위)

    Returns:
        분할된 두 개의 세그먼트 정보 (각각의 ID, 시작/종료 시간, 오디오 URL)

    Notes:
        - segment_id와 language_code로 segment_translations에서 오디오를 찾습니다
        - 해당 언어의 TTS 오디오를 분할합니다
    """
    segments = await service.split_segment(
        payload.segment_id, payload.language_code, payload.split_time
    )
    return SegmentSplitResponse(segments=segments)


@segment_router.post("/merge", response_model=MergeSegmentResponse)
async def merge_segments(
    payload: MergeSegmentsRequest,
    service: SegmentService = Depends(SegmentService),
):
    """
    여러 세그먼트를 하나로 병합합니다.

    - **segment_ids**: 병합할 세그먼트 ID 목록 (최소 2개 이상, project_segments)
    - **language_code**: 타겟 언어 코드 (예: ko, en, ja)

    Returns:
        병합된 세그먼트 정보 (ID, 시작/종료 시간, 오디오 URL)

    Notes:
        - 세그먼트는 시작 시간 순으로 자동 정렬됩니다
        - 모든 세그먼트가 같은 프로젝트에 속해야 합니다
        - segment_ids와 language_code로 segment_translations에서 오디오를 찾습니다
        - 해당 언어의 TTS 오디오들을 병합합니다
    """
    return await service.merge_segments(payload.segment_ids, payload.language_code)
