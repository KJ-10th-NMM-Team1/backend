from pydantic import BaseModel
from typing import Dict


class VoiceConfigResponse(BaseModel):
    """보이스 설정 조회 응답"""

    project_id: str
    voice_config: Dict[str, str]


class VoiceConfigUpdate(BaseModel):
    """보이스 설정 업데이트 요청"""

    voice_config: Dict[str, str]
