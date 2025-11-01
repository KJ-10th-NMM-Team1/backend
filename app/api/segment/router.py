from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi import Depends
from .service import SegmentService
from .model import ResponseSegment
from typing import List

segment_router = APIRouter(prefix="/segment", tags=["segment"])

@segment_router.get('/', response_model=List[ResponseSegment])
async def get_segment_all(service: SegmentService = Depends(SegmentService)):
    find_list = await service.find_all_segment()
    return find_list





