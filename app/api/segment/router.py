from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi import Depends
from .segment_service import SegmentService
from .history_service import HistoryService
from .model import ResponseSegment, RequestSegment
from typing import List

segment_router = APIRouter(prefix="/segment", tags=["segment"])


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


@segment_router.patch("/{project_id}/save")
async def save_segment(
    request: RequestSegment, service: SegmentService = Depends(SegmentService)
):
    return await service.update_segment(request)
