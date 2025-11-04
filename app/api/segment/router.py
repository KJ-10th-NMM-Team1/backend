from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from .segment_service import SegmentService
from .history_service import HistoryService
from .model import (
    RequestSegment,
    ResponseSegment,
    SegmentRetranslateRequest,
    SegmentRetranslateResponse,
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
    find_list = await service.find_segment(project_id)
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
        return await segment_service.save_segment(request, db_name="segments")
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
