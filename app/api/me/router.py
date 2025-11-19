from fastapi import APIRouter, Depends, Query, status
from typing import Optional
from ..auth.service import get_current_user_from_cookie
from ..auth.model import UserOut
from ..deps import DbDep
from ..voice_samples.service import VoiceSampleService
from ..voice_samples.models import VoiceSampleListResponse

me_router = APIRouter(prefix="/me", tags=["Me"])


# User Voices 엔드포인트
@me_router.post(
    "/voices/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_voice_to_my_library(
    db: DbDep,
    sample_id: str,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    """보이스를 내 라이브러리에 추가"""
    service = VoiceSampleService(db)
    await service.add_to_my_voices(sample_id, current_user)
    return None


@me_router.delete(
    "/voices/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_voice_from_my_library(
    db: DbDep,
    sample_id: str,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    """내 라이브러리에서 보이스 제거"""
    service = VoiceSampleService(db)
    await service.remove_from_my_voices(sample_id, current_user)
    return None


@me_router.get(
    "/voices",
    response_model=VoiceSampleListResponse,
)
async def get_my_voices(
    db: DbDep,
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 개수"),
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    """내가 추가한 보이스 목록 조회"""
    service = VoiceSampleService(db)
    samples, total = await service.get_my_voices(
        user=current_user,
        page=page,
        limit=limit,
    )
    return VoiceSampleListResponse(samples=samples, total=total)
