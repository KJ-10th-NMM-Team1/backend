from fastapi import APIRouter, Depends
from typing import Dict, List

from ..deps import DbDep
from .models import VoiceConfigResponse, VoiceConfigUpdate, VoicePreset
from .service import update_voice_config, get_voice_config

voice_router = APIRouter(prefix="/voice", tags=["Voice"])

# 보이스 프리셋 목록 (실제로는 Worker에서 가져와야 하지만 일단 하드코딩)
VOICE_PRESETS_DATA = [
    {"id": "preset_female_friendly", "name": "지민", "gender": "female", "age": "20대", "style": "친근한", "language": "한국어"},
    {"id": "preset_male_professional", "name": "준호", "gender": "male", "age": "30대", "style": "전문적", "language": "한국어"},
    {"id": "preset_female_news", "name": "서연", "gender": "female", "age": "30대", "style": "뉴스 앵커", "language": "한국어"},
    {"id": "preset_male_calm", "name": "민수", "gender": "male", "age": "40대", "style": "차분한", "language": "한국어"},
]


@voice_router.get("/presets/list", response_model=List[VoicePreset])
async def get_voice_presets() -> List[VoicePreset]:
    """사용 가능한 보이스 프리셋 목록 조회"""
    return [VoicePreset(**preset) for preset in VOICE_PRESETS_DATA]


@voice_router.get("/{project_id}", response_model=VoiceConfigResponse)
async def get_voice(project_id: str, db: DbDep) -> Dict:
    """프로젝트의 보이스 설정 조회"""
    return await get_voice_config(db, project_id)


@voice_router.put("/{project_id}", response_model=VoiceConfigResponse)
async def update_voice(project_id: str, payload: VoiceConfigUpdate, db: DbDep) -> Dict:
    """프로젝트의 보이스 설정 업데이트"""
    return await update_voice_config(db, project_id, payload.voice_config)
