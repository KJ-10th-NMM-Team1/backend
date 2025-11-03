from fastapi import HTTPException, status
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError
from typing import Dict
from bson.errors import InvalidId

from ..deps import DbDep
from fastapi import HTTPException


async def get_voice_config(db: DbDep, project_id: str) -> Dict[str, any]:
    """프로젝트의 보이스 설정 조회"""
    try:
        project_oid = ObjectId(project_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_id"
        ) from exc

    project = await db["projects"].find_one({"_id": project_oid})

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    return {"project_id": project_id, "voice_config": project.get("voice_config", {})}


async def update_voice_config(
    db: DbDep, project_id: str, voice_config: Dict[str, str]
) -> Dict[str, any]:
    """프로젝트의 보이스 설정 업데이트"""
    try:
        project_oid = ObjectId(project_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_id"
        ) from exc

    try:
        result = await db["projects"].update_one(
            {"_id": project_oid},
            {"$set": {"voice_config": voice_config, "updated_at": datetime.now()}},
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        return {"project_id": project_id, "voice_config": voice_config}

    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update voice config",
        ) from exc
