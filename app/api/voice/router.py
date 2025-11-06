from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List
from datetime import datetime
import os
from uuid import uuid4

from ..deps import DbDep
from .models import (
    VoiceConfigResponse,
    VoiceConfigUpdate,
    VoicePreset,
    VoiceUploadRequest,
    VoiceUploadFinalize,
    CustomVoice,
)
from .service import update_voice_config, get_voice_config
from app.config.s3 import s3

voice_router = APIRouter(prefix="/voice", tags=["Voice"])

# 보이스 프리셋 목록 (실제로는 Worker에서 가져와야 하지만 일단 하드코딩)
VOICE_PRESETS_DATA = [
    {
        "id": "preset_female_friendly",
        "name": "지민",
        "gender": "female",
        "age": "20대",
        "style": "친근한",
        "language": "한국어",
    },
    {
        "id": "preset_male_professional",
        "name": "준호",
        "gender": "male",
        "age": "30대",
        "style": "전문적",
        "language": "한국어",
    },
    {
        "id": "preset_female_news",
        "name": "서연",
        "gender": "female",
        "age": "30대",
        "style": "뉴스 앵커",
        "language": "한국어",
    },
    {
        "id": "preset_male_calm",
        "name": "민수",
        "gender": "male",
        "age": "40대",
        "style": "차분한",
        "language": "한국어",
    },
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


@voice_router.post("/prepare-upload")
async def prepare_voice_upload(payload: VoiceUploadRequest) -> Dict:
    """보이스 클로닝용 음성 파일 업로드 presigned URL 생성"""
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET env not set")

    # S3 키 생성: voice_cloning/{uuid}_{filename}
    object_key = f"projects/{payload.project_id}/voice_cloning/{uuid4()}_{payload.filename}"

    try:
        presigned = s3.generate_presigned_post(
            Bucket=bucket,
            Key=object_key,
            Fields={"Content-Type": payload.content_type},
            Conditions=[
                ["starts-with", "$Content-Type", payload.content_type.split("/")[0]]
            ],
            ExpiresIn=300,  # 5분
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"presign 실패: {exc}")

    return {
        "upload_url": presigned["url"],
        "fields": presigned["fields"],
        "object_key": object_key,
    }


@voice_router.post("/finish-upload")
async def finish_voice_upload(payload: VoiceUploadFinalize) -> Dict:
    """보이스 파일 업로드 완료 확인"""
    # S3 키를 voiceId로 사용
    return {
        "voice_id": payload.object_key,
        "message": "Voice file uploaded successfully",
    }


@voice_router.get("/custom/{project_id}", response_model=List[CustomVoice])
async def get_custom_voices(project_id: str) -> List[CustomVoice]:
    """프로젝트의 업로드된 커스텀 보이스 목록 조회"""
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET env not set")

    prefix = f"projects/{project_id}/voice_cloning/"
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        voices = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1].split("_", 1)[-1]  # uuid_ 제거
            voices.append(
                CustomVoice(
                    id=key,
                    name=filename,
                    uploaded_at=obj["LastModified"].isoformat(),
                )
            )
        return voices
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {exc}")
