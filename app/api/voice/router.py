from fastapi import APIRouter, Depends
from typing import Dict

from ..deps import DbDep
from .models import VoiceConfigResponse, VoiceConfigUpdate
from .service import update_voice_config, get_voice_config

voice_router = APIRouter(prefix="/voice", tags=["Voice"])


@voice_router.get("/{project_id}", response_model=VoiceConfigResponse)
async def get_voice(project_id: str, db: DbDep) -> Dict:
    """프로젝트의 보이스 설정 조회"""
    return await get_voice_config(db, project_id)


@voice_router.put("/{project_id}", response_model=VoiceConfigResponse)
async def update_voice(project_id: str, payload: VoiceConfigUpdate, db: DbDep) -> Dict:
    """프로젝트의 보이스 설정 업데이트"""
    return await update_voice_config(db, project_id, payload.voice_config)
