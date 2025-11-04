from pydantic import BaseModel
from typing import Dict, Optional, List


class VoiceMapping(BaseModel):
    """개별 캐릭터의 보이스 매핑"""

    voiceId: Optional[str] = None
    preserveTone: bool


class VoicePreset(BaseModel):
    """보이스 프리셋 정보"""

    id: str
    name: str
    gender: str
    age: str
    style: str
    language: str


class VoiceConfigResponse(BaseModel):
    """보이스 설정 조회 응답"""

    project_id: str
    voice_config: Dict[str, VoiceMapping]


class VoiceConfigUpdate(BaseModel):
    """보이스 설정 업데이트 요청"""

    voice_config: Dict[str, VoiceMapping]
