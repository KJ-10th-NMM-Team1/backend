from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from collections import defaultdict
from typing import Dict, Set
from datetime import datetime
import logging

audio_router = APIRouter(prefix="/audio", tags=["Audio"])
logger = logging.getLogger(__name__)

# 프로젝트별 + 언어별 이벤트 채널
# key: f"{project_id}:{language_code}", value: Set[Queue]
audio_channels: Dict[str, Set[asyncio.Queue]] = defaultdict(set)


@audio_router.get("/events")
async def audio_events(
    request: Request,
    projectId: str = Query(..., description="프로젝트 ID"),
    language: str = Query(..., description="언어 코드"),
):
    """
    오디오 생성 이벤트를 SSE로 스트리밍합니다.

    이벤트 타입:
    - audio-completed: 세그먼트 TTS 생성 완료
      데이터: { segmentId, audioS3Key, audioDuration, projectId, languageCode }
    """
    channel_key = f"{projectId}:{language}"
    queue = asyncio.Queue()
    audio_channels[channel_key].add(queue)

    async def event_generator():
        try:
            # 주기적인 하트비트를 위한 카운터
            heartbeat_interval = 30  # 30초마다 하트비트
            last_heartbeat = 0

            while True:
                # 클라이언트 연결 해제 확인
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from audio events for {channel_key}")
                    break

                try:
                    # 타임아웃을 사용하여 queue.get() 무한 대기 방지
                    data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    event_type = data.get("event", "audio-completed")
                    event_data = data.get("data", {})
                    yield {"event": event_type, "data": json.dumps(event_data)}
                    last_heartbeat = 0  # 데이터 전송 시 하트비트 카운터 리셋
                except asyncio.TimeoutError:
                    # 타임아웃 시 하트비트 전송 (연결 유지 확인)
                    last_heartbeat += 5
                    if last_heartbeat >= heartbeat_interval:
                        yield {"event": "heartbeat", "data": json.dumps({"timestamp": datetime.now().isoformat()})}
                        last_heartbeat = 0

        except asyncio.CancelledError:
            logger.info(f"Audio events stream cancelled for {channel_key}")
            raise
        except Exception as e:
            logger.error(f"Error in audio events stream for {channel_key}: {e}")
        finally:
            audio_channels[channel_key].discard(queue)
            # 채널에 리스너가 없으면 삭제하여 메모리 누수 방지
            if not audio_channels[channel_key]:
                del audio_channels[channel_key]
            logger.info(f"Cleaned up audio events connection for {channel_key}")

    return EventSourceResponse(event_generator())
