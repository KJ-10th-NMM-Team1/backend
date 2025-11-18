import logging
from fastapi import APIRouter, HTTPException, Depends

from .models import MuxRequest, MuxResponse
from .service import process_mux
from ..deps import DbDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mux", tags=["mux"])


@router.post("/", response_model=MuxResponse)
async def create_mux(
    request: MuxRequest,
    db: DbDep,
):
    """
    비디오와 오디오를 결합하여 최종 더빙 영상을 생성합니다.

    - video_key: 원본 비디오 S3 키
    - background_audio_key: 배경음 S3 키
    - segments: 세그먼트 정보 배열 (각 세그먼트의 audio_file은 S3 키)
    """
    try:
        # segments를 dict 리스트로 변환
        segments_data = [seg.model_dump() for seg in request.segments]

        result = await process_mux(
            project_id=request.project_id,
            video_key=request.video_key,
            background_audio_key=request.background_audio_key,
            segments=segments_data,
            output_prefix=request.output_prefix,
        )

        return MuxResponse(
            success=True,
            result_key=result["result_key"],
            audio_key=result.get("audio_key"),
            message="Mux completed successfully",
        )
    except Exception as e:
        logger.error(f"Mux failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Mux failed: {str(e)}")
