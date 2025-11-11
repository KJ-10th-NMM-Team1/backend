from fastapi import APIRouter, Depends, status
from ..auth.service import get_current_user_from_cookie
from ..auth.model import UserOut
from ..deps import DbDep
from ..voice_samples.service import VoiceSampleService

me_router = APIRouter(prefix="/me", tags=["Me"])


# Favorites 엔드포인트
@me_router.post(
    "/favorites/voice-samples/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_voice_sample_favorite(
    db: DbDep,
    sample_id: str,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    """음성 샘플을 즐겨찾기에 추가"""
    service = VoiceSampleService(db)
    await service.add_favorite(sample_id, current_user)
    return None


@me_router.delete(
    "/favorites/voice-samples/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_voice_sample_favorite(
    db: DbDep,
    sample_id: str,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    """음성 샘플을 즐겨찾기에서 제거"""
    service = VoiceSampleService(db)
    await service.remove_favorite(sample_id, current_user)
    return None
